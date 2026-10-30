from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import AdminUser, Role
from app.models.enums import DomainType, RoleCode
from app.repositories.stores import get_store_for_domain, normalize_host
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要登录")
    try:
        user_id = decode_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录令牌无效或已过期") from None

    user = await session.scalar(
        select(AdminUser)
        .where(AdminUser.id == user_id, AdminUser.enabled.is_(True))
        .options(
            selectinload(AdminUser.role).selectinload(Role.permissions),
            selectinload(AdminUser.store),
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不存在或已禁用")
    return user


CurrentAdminUser = Annotated[AdminUser, Depends(get_current_admin_user)]


def require_permission(permission_code: str) -> Callable:
    async def dependency(user: CurrentAdminUser) -> AdminUser:
        permissions = {permission.code for permission in user.role.permissions}
        if permission_code not in permissions:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "没有执行该操作的权限")
        return user

    return dependency


async def get_scoped_staff_user(
    request: Request,
    user: CurrentAdminUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUser:
    if user.role.code == RoleCode.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "总管理员请使用总管理接口")

    if user.store_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "门店账号未绑定门店")
    domain_store = await get_store_for_domain(
        session, request.headers.get("host", ""), DomainType.STAFF
    )
    if domain_store is None or domain_store.id != user.store_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号与当前门店后台不匹配")
    return user


ScopedStaffUser = Annotated[AdminUser, Depends(get_scoped_staff_user)]


async def get_super_admin(request: Request, user: CurrentAdminUser) -> AdminUser:
    if user.role.code != RoleCode.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "仅总管理员可访问")
    if user.store_id is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "总管理员账号范围配置错误")
    if normalize_host(request.headers.get("host", "")) != get_settings().admin_domain:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "总管理员请使用总管理域名")
    return user


SuperAdmin = Annotated[AdminUser, Depends(get_super_admin)]
