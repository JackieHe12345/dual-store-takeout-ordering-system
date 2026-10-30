"""Explicit initialization for a NEW isolated test database; never live data."""
import asyncio
from datetime import timedelta
from sqlalchemy import select
from app.config import get_settings
from app.database import async_session_maker, engine
from app.models import Base, Store, Dish
from app.models.commerce import Coupon, Reward, GrowthTask, Rider, DishOptions
from app.seed import seed_initial_database
from app.services.commerce import now

async def main():
    s=get_settings()
    if s.app_env!="testing" or not s.enable_test_commerce:raise RuntimeError("Test-only initializer")
    # SQLite is just for local visual QA. PostgreSQL is initialized with Alembic.
    if s.database_url.startswith("sqlite"):
        async with engine.begin() as conn:await conn.run_sync(Base.metadata.create_all)
    if not await seed_initial_database():return
    async with async_session_maker() as db:
        for store in await db.scalars(select(Store)):
            store.name += " · 内部测试"
            db.add_all([Coupon(store_id=store.id,title="内部测试满10减2",amount_cents=200,minimum_cents=1000,quantity=100,starts_at=now()-timedelta(days=1),expires_at=now()+timedelta(days=90),birthday_only=False,enabled=True),Reward(store_id=store.id,title="测试小食兑换",description="内部演练，无真实商品承诺",points_cost=10,stock=50,enabled=True),GrowthTask(store_id=store.id,title="完善测试资料",kind="PROFILE",target=1,points_reward=20,enabled=True),Rider(store_id=store.id,name="内部测试配送员",phone="13900000000",enabled=True)])
            dish=await db.scalar(select(Dish).where(Dish.store_id==store.id).order_by(Dish.id))
            dish.stock=50;dish.requires_options=True
            db.add(DishOptions(store_id=store.id,dish_id=dish.id,groups=[{"id":"size","name":"份量","minimum":1,"maximum":1,"options":[{"id":"normal","name":"标准份","price_cents":0,"enabled":True},{"id":"large","name":"加大份","price_cents":300,"enabled":True}]}]))
        await db.commit()
    print("Isolated test fixtures created. Delivery remains closed until configured.")

if __name__=="__main__":asyncio.run(main())
