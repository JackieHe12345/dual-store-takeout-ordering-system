from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models import AdminUser, Role
from app.models.enums import DomainType, RoleCode
from app.repositories.stores import get_store_for_domain, normalize_host
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.utils.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


def serialize_user(user: AdminUser) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role_code=user.role.code,
        store_id=user.store_id,
        enabled=user.enabled,
        permissions=sorted(permission.code for permission in user.role.permissions),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    user = await session.scalar(
        select(AdminUser)
        .where(AdminUser.username == data.username)
        .options(selectinload(AdminUser.role).selectinload(Role.permissions))
    )
    if user is None or not user.enabled or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户名或密码错误")

    host = normalize_host(request.headers.get("host", ""))
    if user.role.code == RoleCode.SUPER_ADMIN:
        if host != get_settings().admin_domain:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "总管理员请使用总管理域名")
        if user.store_id is not None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "总管理员账号范围配置错误")
    else:
        domain_store = await get_store_for_domain(session, host, DomainType.STAFF)
        if user.store_id is None or domain_store is None or domain_store.id != user.store_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "账号与当前门店后台不匹配")

    # The migration uses timestamp without time zone; keep naive UTC consistently.
    user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
    await session.commit()
    token, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=token, expires_in=expires_in, user=serialize_user(user))
