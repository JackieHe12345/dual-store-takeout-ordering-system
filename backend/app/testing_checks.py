"""PostgreSQL acceptance check; generates labeled synthetic test records only."""
import asyncio
import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from app.config import get_settings
from app.database import async_session_maker as sessions, engine
from app.models import Store, Category, Dish
from app.models.commerce import Member, Coupon, CouponClaim, Reward, Redemption, Order, Ledger, AuditEvent
from app.services import commerce as svc
from app.schemas.commerce import OrderCreate, StateChange, RedemptionInput, Adjustment
from app.utils.security import hash_password

async def main():
    s=get_settings()
    assert s.app_env=='testing' and s.enable_test_commerce
    assert engine.dialect.name=='postgresql', 'This check requires real PostgreSQL row locks'
    run=secrets.token_hex(6)
    async with sessions() as db:
        store=await db.scalar(select(Store).order_by(Store.id))
        category=await db.scalar(select(Category).where(Category.store_id==store.id))
        dish=Dish(store_id=store.id,category_id=category.id,name='并发验收 '+run,slug='check-'+run,price_cents=100,stock=5,requires_options=False,sold_out=False,enabled=True,sort_order=9999,monthly_sales=0)
        db.add(dish)
        members=[Member(store_id=store.id,phone='test-'+run+'-'+str(i),password_hash=hash_password(secrets.token_hex(16)),name='并发验收',points=100,wallet_cents=0,lifetime_cents=0,enabled=True) for i in range(12)]
        db.add_all(members)
        coupon=Coupon(store_id=store.id,title='并发验收 '+run,amount_cents=10,minimum_cents=0,quantity=1,starts_at=svc.now()-timedelta(days=1),expires_at=svc.now()+timedelta(days=1),birthday_only=False,enabled=True)
        reward=Reward(store_id=store.id,title='并发验收 '+run,description='合成数据',points_cost=10,stock=1,enabled=True)
        db.add_all([coupon,reward]);await db.commit()
        sid,did,cid,rid=store.id,dish.id,coupon.id,reward.id
        ids=[m.id for m in members]
    async def invoke(kind,mid,key):
        async with sessions() as db:
            store=await db.get(Store,sid);m=await db.get(Member,mid)
            try:
                if kind=='order':return await svc.create_order(db,store,m,OrderCreate(items=[{'dish_id':did,'quantity':1}],fulfillment='pickup',contact='并发验收',phone='13900000000',expected_total_cents=100,request_key=key))
                if kind=='coupon':return await svc.claim_coupon(db,store,m,cid)
                return await svc.redeem(db,store,m,RedemptionInput(reward_id=rid,request_key=key))
            except HTTPException as exc:
                assert exc.status_code==409,exc.detail
                return None
    orders=await asyncio.gather(*(invoke('order',mid,'stock-'+run+'-'+str(mid)) for mid in ids))
    assert sum(o is not None for o in orders)==5,orders
    async with sessions() as db:assert (await db.get(Dish,did)).stock==0
    first=next(o for o in orders if o)
    async def cancel():
        async with sessions() as db:return await svc.transition(db,sid,first['number'],StateChange(status='CANCELLED',expected_status='PENDING',reason='并发取消验收'),'acceptance')
    await asyncio.gather(*(cancel() for _ in range(8)))
    async with sessions() as db:assert (await db.get(Dish,did)).stock==1
    duplicates=await asyncio.gather(*(invoke('order',ids[-1],'duplicate-'+run) for _ in range(8)))
    assert all(duplicates) and len({o['number'] for o in duplicates})==1
    coupons=await asyncio.gather(*(invoke('coupon',mid,'coupon-'+run) for mid in ids))
    assert sum(c is not None for c in coupons)==1
    rewards=await asyncio.gather(*(invoke('reward',mid,'reward-'+run) for mid in ids))
    assert sum(r is not None for r in rewards)==1
    async def adjust(delta,key):
        async with sessions() as db:
            try:
                return await svc.adjust_assets(db,sid,ids[0],Adjustment(kind='WALLET',delta=delta,reason='内部测试储值并发验收',request_key=key),'acceptance')
            except HTTPException as exc:
                assert exc.status_code==409,exc.detail
                return None
    credits=await asyncio.gather(*(adjust(50,'wallet-credit-'+run) for _ in range(8)))
    assert all(credits) and len({entry['id'] for entry in credits})==1
    debits=await asyncio.gather(*(adjust(-10,'wallet-debit-'+run+'-'+str(i)) for i in range(12)))
    assert sum(entry is not None for entry in debits)==5,debits
    async with sessions() as db:
        assert (await db.get(Member,ids[0])).wallet_cents==0
        assert await db.scalar(select(func.count()).select_from(Ledger).where(Ledger.member_id==ids[0],Ledger.kind=='WALLET'))==6
        assert await db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.store_id==sid,AuditEvent.subject==str(ids[0]),AuditEvent.action=='member.adjust'))==6
        assert (await db.get(Reward,rid)).stock==0
        assert await db.scalar(select(func.count()).select_from(CouponClaim).where(CouponClaim.coupon_id==cid))==1
        assert await db.scalar(select(func.count()).select_from(Redemption).where(Redemption.reward_id==rid))==1
        assert await db.scalar(select(func.count()).select_from(Order).where(Order.member_id==ids[-1],Order.request_key=='duplicate-'+run))==1
        (await db.get(Dish,did)).enabled=False
        (await db.get(Coupon,cid)).enabled=False
        (await db.get(Reward,rid)).enabled=False
        for mid in ids:(await db.get(Member,mid)).enabled=False
        await db.commit()
    print('PASS: PostgreSQL stock race 12 requests/5 units; 8 duplicate orders; 8 duplicate cancellations; coupon quantity race; reward stock/points race; 8 duplicate wallet credits; 12 concurrent wallet debits/5 successes with exactly 6 ledger and audit records. Run '+run)
    await engine.dispose()

if __name__=='__main__':asyncio.run(main())
