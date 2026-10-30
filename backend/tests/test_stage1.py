from __future__ import annotations

import httpx
from sqlalchemy import select

from app.models import Category, Dish, Store
from tests.conftest import TEST_PASSWORD, login


async def test_health(client: httpx.AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_customer_menu_is_bound_by_host_and_never_leaks_other_store(
    client: httpx.AsyncClient,
):
    response_a = await client.get(
        "/api/menu?store_id=2", headers={"host": "shop-a.localhost"}
    )
    response_b = await client.get("/api/menu", headers={"host": "shop-b.localhost"})

    assert response_a.status_code == response_b.status_code == 200
    assert response_a.json()["store"]["name"] == "店 A"
    assert response_b.json()["store"]["name"] == "店 B"
    assert [dish["name"] for dish in response_a.json()["categories"][0]["dishes"]] == [
        "A 专属菜"
    ]
    assert [dish["name"] for dish in response_b.json()["categories"][0]["dishes"]] == [
        "B 专属菜"
    ]

    unknown = await client.get("/api/menu", headers={"host": "unknown.localhost"})
    assert unknown.status_code == 404


async def test_store_a_staff_cannot_login_or_use_token_on_store_b_domain(
    client: httpx.AsyncClient,
):
    wrong_login = await client.post(
        "/api/auth/login",
        headers={"host": "staff-b.localhost"},
        json={"username": "staff_a", "password": TEST_PASSWORD},
    )
    assert wrong_login.status_code == 403

    token = await login(client, "staff_a", "staff-a.localhost")
    own_menu = await client.get(
        "/api/staff/menu",
        headers={"host": "staff-a.localhost", "authorization": f"Bearer {token}"},
    )
    other_menu = await client.get(
        "/api/staff/menu",
        headers={"host": "staff-b.localhost", "authorization": f"Bearer {token}"},
    )
    assert own_menu.status_code == 200
    assert own_menu.json()["store"]["name"] == "店 A"
    assert other_menu.status_code == 403


async def test_store_a_cannot_create_dish_under_store_b_category(
    client: httpx.AsyncClient, session_factory
):
    async with session_factory() as session:
        store_b_id = await session.scalar(select(Store.id).where(Store.slug == "store-b"))
        category_b_id = await session.scalar(
            select(Category.id).where(Category.store_id == store_b_id)
        )

    token = await login(client, "staff_a", "staff-a.localhost")
    response = await client.post(
        "/api/staff/dishes",
        headers={"host": "staff-a.localhost", "authorization": f"Bearer {token}"},
        json={
            "category_id": category_b_id,
            "name": "越权菜品",
            "slug": "cross-store-dish",
            "price_cents": 1,
        },
    )
    assert response.status_code == 422
    async with session_factory() as session:
        leaked = await session.scalar(select(Dish).where(Dish.slug == "cross-store-dish"))
        assert leaked is None


async def test_role_permission_blocks_menu_write(client: httpx.AsyncClient):
    token = await login(client, "operator_a", "staff-a.localhost")
    response = await client.post(
        "/api/staff/categories",
        headers={"host": "staff-a.localhost", "authorization": f"Bearer {token}"},
        json={"name": "无权限分类", "slug": "forbidden-category"},
    )
    assert response.status_code == 403


async def test_only_super_admin_on_admin_domain_can_view_all_stores(
    client: httpx.AsyncClient,
):
    admin_token = await login(client, "admin", "admin.localhost")
    response = await client.get(
        "/api/admin/stores",
        headers={"host": "admin.localhost", "authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert [store["name"] for store in response.json()] == ["店 A", "店 B"]

    wrong_domain = await client.get(
        "/api/admin/stores",
        headers={"host": "staff-a.localhost", "authorization": f"Bearer {admin_token}"},
    )
    assert wrong_domain.status_code == 403

    staff_token = await login(client, "staff_a", "staff-a.localhost")
    staff_attempt = await client.get(
        "/api/admin/stores",
        headers={"host": "admin.localhost", "authorization": f"Bearer {staff_token}"},
    )
    assert staff_attempt.status_code == 403
