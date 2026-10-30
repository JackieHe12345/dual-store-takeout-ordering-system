from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import seed as seed_module
from app.models import AdminUser, Base, Category, Dish, Permission, Role, Store, StoreDomain
from app.utils.security import verify_password


@pytest.mark.asyncio
async def test_first_bootstrap_and_repeat_preserve_accounts_and_store_data(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    password = "Seed-test-password-234!"
    monkeypatch.setattr(seed_module, "async_session_maker", factory)
    monkeypatch.setattr(
        seed_module,
        "get_settings",
        lambda: SimpleNamespace(
            seed_super_admin_password=password,
            seed_store_a_password=password,
            seed_store_b_password=password,
        ),
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await seed_module.seed()
        async with factory() as session:
            users = (await session.scalars(select(AdminUser))).all()
            first_accounts = {user.username: (user.id, user.password_hash) for user in users}
            assert set(first_accounts) == {"admin", "staff_a", "staff_b"}
            assert all(verify_password(password, user.password_hash) for user in users)

        await seed_module.seed()
        async with factory() as session:
            for model, count in (
                (Store, 2), (StoreDomain, 4), (AdminUser, 3),
                (Role, 5), (Permission, 7), (Category, 6), (Dish, 12),
            ):
                assert await session.scalar(select(func.count()).select_from(model)) == count
            roles = (await session.scalars(select(Role))).all()
            for role in roles:
                assert {p.code for p in role.permissions} == seed_module.ROLE_PERMISSIONS[role.code]
            users = (await session.scalars(select(AdminUser))).all()
            assert {u.username: (u.id, u.password_hash) for u in users} == first_accounts
            by_name = {u.username: u for u in users}
            assert by_name["admin"].store_id is None
            assert by_name["staff_a"].store_id is not None
            assert by_name["staff_b"].store_id is not None
            assert by_name["staff_a"].store_id != by_name["staff_b"].store_id
    finally:
        await engine.dispose()
