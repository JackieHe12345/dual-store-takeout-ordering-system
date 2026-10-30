from sqlalchemy import select

from app.models import Store
from tests.conftest import TEST_PASSWORD, login


async def test_category_and_dish_edits_are_visible_only_in_the_assigned_store(client):
    token = await login(client, "staff_a", "staff-a.localhost")
    headers = {"host": "staff-a.localhost", "authorization": f"Bearer {token}"}
    response = await client.post(
        "/api/staff/categories", headers=headers,
        json={"name": "新品", "slug": "new-dishes"},
    )
    assert response.status_code == 201, response.text
    category_id = response.json()["id"]
    assert response.json()["dishes"] == []
    response = await client.post(
        "/api/staff/dishes", headers=headers,
        json={"category_id": category_id, "name": "新套餐", "slug": "new-meal", "price_cents": 1280},
    )
    assert response.status_code == 201, response.text
    dish_id = response.json()["id"]
    response = await client.patch(
        f"/api/staff/dishes/{dish_id}", headers=headers,
        json={"price_cents": 1380, "sold_out": True},
    )
    assert response.status_code == 200
    response = await client.get("/api/menu", headers={"host": "shop-a.localhost"})
    dishes = [d for c in response.json()["categories"] for d in c["dishes"]]
    changed = next(d for d in dishes if d["id"] == dish_id)
    assert changed["price_cents"] == 1380
    assert changed["sold_out"] is True
    response = await client.get("/api/menu", headers={"host": "shop-b.localhost"})
    assert all(d["id"] != dish_id for c in response.json()["categories"] for d in c["dishes"])
    response = await client.patch(f"/api/staff/dishes/{dish_id}", headers=headers, json={"enabled": False})
    assert response.status_code == 200
    response = await client.get("/api/menu", headers={"host": "shop-a.localhost"})
    assert all(d["id"] != dish_id for c in response.json()["categories"] for d in c["dishes"])


async def test_admin_created_staff_is_bound_to_store_and_disabled_tokens_stop_working(client, session_factory):
    token = await login(client, "admin", "admin.localhost")
    headers = {"host": "admin.localhost", "authorization": f"Bearer {token}"}
    async with session_factory() as session:
        store_id = await session.scalar(select(Store.id).where(Store.slug == "store-a"))
    response = await client.post("/api/admin/users", headers=headers, json={
        "username": "new_staff", "password": TEST_PASSWORD, "display_name": "新店员",
        "role_code": "STORE_ADMIN", "store_id": store_id,
    })
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    staff_token = await login(client, "new_staff", "staff-a.localhost")
    response = await client.get("/api/staff/menu", headers={
        "host": "staff-b.localhost", "authorization": f"Bearer {staff_token}",
    })
    assert response.status_code == 403
    response = await client.patch(f"/api/admin/users/{user_id}/enabled", headers=headers, json={"enabled": False})
    assert response.status_code == 200
    response = await client.get("/api/staff/menu", headers={
        "host": "staff-a.localhost", "authorization": f"Bearer {staff_token}",
    })
    assert response.status_code == 401
