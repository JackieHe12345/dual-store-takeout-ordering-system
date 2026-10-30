from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import AdminUser, Base, Category, Dish, Permission, Role, Store, StoreDomain
from app.models.enums import CoordinateSystem, DomainType, RoleCode
from app.utils.security import hash_password

TEST_PASSWORD = "Testing-Password!234"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with factory() as session:
        menu_read = Permission(code="menu:read", description="read")
        menu_write = Permission(code="menu:write", description="write")
        cross_store = Permission(code="cross_store:read", description="cross store")
        super_role = Role(
            code=RoleCode.SUPER_ADMIN,
            name="Super Admin",
            permissions=[menu_read, menu_write, cross_store],
        )
        store_role = Role(
            code=RoleCode.STORE_ADMIN,
            name="Store Admin",
            permissions=[menu_read, menu_write],
        )
        operator_role = Role(
            code=RoleCode.ORDER_OPERATOR,
            name="Order Operator",
            permissions=[menu_read],
        )
        store_a = Store(
            slug="store-a",
            name="店 A",
            phone="10001",
            address="A address",
            latitude=22.1,
            longitude=113.1,
            coordinate_system=CoordinateSystem.GCJ_02,
            delivery_radius_meters=5000,
            enabled=True,
        )
        store_b = Store(
            slug="store-b",
            name="店 B",
            phone="10002",
            address="B address",
            latitude=22.2,
            longitude=113.2,
            coordinate_system=CoordinateSystem.GCJ_02,
            delivery_radius_meters=5000,
            enabled=True,
        )
        session.add_all([store_a, store_b])
        await session.flush()
        session.add_all(
            [
                StoreDomain(
                    store_id=store_a.id,
                    domain="shop-a.localhost",
                    domain_type=DomainType.CUSTOMER,
                    enabled=True,
                ),
                StoreDomain(
                    store_id=store_a.id,
                    domain="staff-a.localhost",
                    domain_type=DomainType.STAFF,
                    enabled=True,
                ),
                StoreDomain(
                    store_id=store_b.id,
                    domain="shop-b.localhost",
                    domain_type=DomainType.CUSTOMER,
                    enabled=True,
                ),
                StoreDomain(
                    store_id=store_b.id,
                    domain="staff-b.localhost",
                    domain_type=DomainType.STAFF,
                    enabled=True,
                ),
            ]
        )
        category_a = Category(
            store_id=store_a.id,
            name="A 热销",
            slug="hot-a",
            sort_order=1,
            enabled=True,
        )
        category_b = Category(
            store_id=store_b.id,
            name="B 热销",
            slug="hot-b",
            sort_order=1,
            enabled=True,
        )
        session.add_all([category_a, category_b])
        await session.flush()
        session.add_all(
            [
                Dish(
                    store_id=store_a.id,
                    category_id=category_a.id,
                    name="A 专属菜",
                    slug="dish-a",
                    price_cents=1000,
                    monthly_sales=1,
                    requires_options=False,
                    sold_out=False,
                    enabled=True,
                    sort_order=1,
                ),
                Dish(
                    store_id=store_b.id,
                    category_id=category_b.id,
                    name="B 专属菜",
                    slug="dish-b",
                    price_cents=2000,
                    monthly_sales=1,
                    requires_options=False,
                    sold_out=False,
                    enabled=True,
                    sort_order=1,
                ),
            ]
        )
        session.add_all(
            [
                AdminUser(
                    username="admin",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="总管理员",
                    role=super_role,
                    store_id=None,
                    enabled=True,
                ),
                AdminUser(
                    username="staff_a",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="A 店员",
                    role=store_role,
                    store_id=store_a.id,
                    enabled=True,
                ),
                AdminUser(
                    username="operator_a",
                    password_hash=hash_password(TEST_PASSWORD),
                    display_name="A 订单员",
                    role=operator_role,
                    store_id=store_a.id,
                    enabled=True,
                ),
            ]
        )
        await session.commit()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield factory
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def login(client: httpx.AsyncClient, username: str, host: str) -> str:
    response = await client.post(
        "/api/auth/login",
        headers={"host": host},
        json={"username": username, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
