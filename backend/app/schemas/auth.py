from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class UserRead(ORMModel):
    id: int
    username: str
    display_name: str
    role_code: str
    store_id: int | None
    enabled: bool
    permissions: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)
    role_code: str
    store_id: int | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_scope(self):
        if self.role_code == "SUPER_ADMIN" and self.store_id is not None:
            raise ValueError("SUPER_ADMIN 的 store_id 必须为空")
        if self.role_code != "SUPER_ADMIN" and self.store_id is None:
            raise ValueError("门店角色必须指定 store_id")
        return self


class AdminUserEnabledUpdate(BaseModel):
    enabled: bool
