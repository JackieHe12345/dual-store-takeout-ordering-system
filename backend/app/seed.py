from __future__ import annotations

import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker
from app.models import AdminUser, Category, Dish, Permission, Role, Store, StoreDomain
from app.models.enums import CoordinateSystem, DomainType, RoleCode
from app.utils.security import hash_password

PERMISSIONS = {
    "menu:read": "查看所属门店菜单",
    "menu:write": "维护所属门店分类和菜品",
    "orders:read": "查看所属门店订单",
    "orders:write": "处理所属门店订单",
    "staff:manage": "管理店员账号",
    "stores:manage": "管理门店配置",
    "cross_store:read": "读取跨门店数据",
}

ROLE_PERMISSIONS = {
    RoleCode.SUPER_ADMIN: set(PERMISSIONS),
    RoleCode.STORE_ADMIN: {"menu:read", "menu:write", "orders:read", "orders:write", "staff:manage"},
    RoleCode.ORDER_OPERATOR: {"menu:read", "orders:read", "orders:write"},
    RoleCode.KITCHEN_OPERATOR: {"menu:read", "orders:read", "orders:write"},
    RoleCode.DELIVERY_OPERATOR: {"menu:read", "orders:read", "orders:write"},
}


async def seed_permissions_and_roles(session: AsyncSession) -> dict[str, Role]:
    permissions: dict[str, Permission] = {}
    for code, description in PERMISSIONS.items():
        permission = await session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, description=description)
            session.add(permission)
        permissions[code] = permission
    await session.flush()

    roles: dict[str, Role] = {}
    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        role = await session.scalar(select(Role).where(Role.code == role_code.value))
        if role is None:
            role = Role(
                code=role_code.value,
                name=role_code.value.replace("_", " ").title(),
                permissions=[permissions[code] for code in sorted(permission_codes)],
            )
            session.add(role)
            await session.flush()
        roles[role_code.value] = role
    return roles


async def ensure_store(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    phone: str,
    address: str,
    latitude: str,
    longitude: str,
    customer_domain: str,
    staff_domain: str,
) -> Store:
    store = await session.scalar(select(Store).where(Store.slug == slug))
    if store is None:
        store = Store(
            slug=slug,
            name=name,
            phone=phone,
            address=address,
            latitude=Decimal(latitude),
            longitude=Decimal(longitude),
            coordinate_system=CoordinateSystem.GCJ_02,
            delivery_radius_meters=5000,
            enabled=True,
        )
        session.add(store)
        await session.flush()
    for domain, domain_type in (
        (customer_domain, DomainType.CUSTOMER),
        (staff_domain, DomainType.STAFF),
    ):
        existing = await session.scalar(select(StoreDomain).where(StoreDomain.domain == domain))
        if existing is None:
            session.add(
                StoreDomain(
                    store_id=store.id,
                    domain=domain,
                    domain_type=domain_type,
                    enabled=True,
                )
            )
    return store


async def ensure_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: str,
    role: Role,
    store_id: int | None,
) -> None:
    existing = await session.scalar(select(AdminUser).where(AdminUser.username == username))
    if existing is None:
        session.add(
            AdminUser(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                store_id=store_id,
                enabled=True,
            )
        )


async def ensure_demo_menu(session: AsyncSession, store: Store, suffix: str) -> None:
    # Demo items are created only for a store with no categories; repeated starts
    # must preserve menu edits and never reintroduce removed dishes.
    existing = await session.scalar(select(Category.id).where(Category.store_id == store.id).limit(1))
    if existing is not None:
        return
    demo_categories = [
        ("热销", "hot-sales", [
            ("经典螺蛳粉", "luosifen", "酸辣鲜香，汤浓味美，配料丰富", 1480),
            ("卤肉饭", "braised-pork-rice", "卤香入味，肥而不腻，米饭香软", 1280),
            ("外婆家的炒饭", "fried-rice", "粒粒分明，锅气十足，家常美味", 1080),
        ]),
        ("招牌推荐", "signature", [
            ("红烧牛肉面", "beef-noodles", "汤浓面劲，牛肉软烂，经典好味", 1680),
            ("香酥鸡排饭", "chicken-rice", "外酥里嫩，搭配时蔬，营养均衡", 1580),
        ]),
        ("小食汤品", "soup", [
            ("鲜肉小馄饨", "wontons", "皮薄馅嫩，汤鲜味美，暖心暖胃", 980),
        ]),
    ]
    for order, (name, slug, dishes) in enumerate(demo_categories):
        category = Category(store_id=store.id, name=name, slug=slug, sort_order=order * 10, enabled=True)
        session.add(category)
        await session.flush()
        for sort_order, (dish_name, dish_slug, description, price) in enumerate(dishes):
            session.add(Dish(
                store_id=store.id, category_id=category.id,
                name=dish_name, slug=dish_slug, description=description,
                image_url=f"/media/{dish_slug}.webp", price_cents=price,
                monthly_sales=0, requires_options=False, sold_out=False,
                enabled=True, sort_order=sort_order * 10,
            ))


async def seed() -> None:
    settings = get_settings()
    passwords = {
        "admin": settings.seed_super_admin_password,
        "staff_a": settings.seed_store_a_password,
        "staff_b": settings.seed_store_b_password,
    }
    missing = [username for username, password in passwords.items() if not password]
    if missing:
        raise RuntimeError(f"缺少初始账号密码环境变量: {', '.join(missing)}")

    async with async_session_maker() as session:
        roles = await seed_permissions_and_roles(session)
        store_a = await ensure_store(
            session,
            slug="shengfuji",
            name="升福记",
            phone="0760-8888 8888",
            address="广东省中山市东区中山三路18号",
            latitude="22.5210000",
            longitude="113.3920000",
            customer_domain="shop-a.localhost",
            staff_domain="staff-a.localhost",
        )
        store_b = await ensure_store(
            session,
            slug="shengsheng-fast-food",
            name="升升快餐",
            phone="0760-6765 4321",
            address="广东省中山市石岐区孙文东路28号",
            latitude="22.5310000",
            longitude="113.3870000",
            customer_domain="shop-b.localhost",
            staff_domain="staff-b.localhost",
        )
        await ensure_user(
            session,
            username="admin",
            password=passwords["admin"],
            display_name="总管理员",
            role=roles[RoleCode.SUPER_ADMIN.value],
            store_id=None,
        )
        await ensure_user(
            session,
            username="staff_a",
            password=passwords["staff_a"],
            display_name="升福记店员",
            role=roles[RoleCode.STORE_ADMIN.value],
            store_id=store_a.id,
        )
        await ensure_user(
            session,
            username="staff_b",
            password=passwords["staff_b"],
            display_name="升升快餐店员",
            role=roles[RoleCode.STORE_ADMIN.value],
            store_id=store_b.id,
        )
        await ensure_demo_menu(session, store_a, "a")
        await ensure_demo_menu(session, store_b, "b")
        await session.commit()


async def seed_initial_database() -> bool:
    """Initialize only an empty business database; never repair live data.

    Keep seed() available for explicit, isolated development/test fixtures.
    Normal CLI startup must not recreate renamed or intentionally removed data.
    """
    async with async_session_maker() as session:
        for model in (Store, AdminUser, Category, Dish):
            if await session.scalar(select(model.id).limit(1)) is not None:
                print("已有业务数据，跳过初始数据创建。")
                return False
    await seed()
    return True


if __name__ == "__main__":
    asyncio.run(seed_initial_database())
