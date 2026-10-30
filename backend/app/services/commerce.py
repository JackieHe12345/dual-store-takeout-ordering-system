from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import Store, Category, Dish
from app.models.commerce import (Member, StorePolicy, DishOptions, Order, Ledger, Coupon,
    CouponClaim, Reward, Redemption, GrowthTask, Rider, AuditEvent)
from app.schemas.commerce import OrderDraft, OrderCreate, PolicyInput, StateChange, Adjustment
from app.schemas.delivery import Coordinates
from app.services.delivery import check_delivery

def is_test(): return get_settings().app_env == "testing"

def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def iso(value): return value.isoformat()+"Z" if value else None
def fail(message, status=409): raise HTTPException(status, message)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

def record(row, omit=()):
    result={}
    for c in row.__table__.columns:
        if c.name in omit or c.name in ("password_hash", "token_hash", "request_hash"): continue
        v=getattr(row,c.name)
        result[c.name]=iso(v) if isinstance(v,datetime) else v
    return result

def audit(db, store_id, actor, action, subject, detail=None):
    db.add(AuditEvent(store_id=store_id,actor=actor,action=action,subject=str(subject),detail=detail or {}))

async def policy(db, store_id):
    p=await db.get(StorePolicy,store_id)
    return PolicyInput.model_validate(p.data if p else {}).model_dump()

def is_open(p):
    if not p["accepting_orders"]: return False
    if not p["hours"]: return True
    local=datetime.now(ZoneInfo("Asia/Shanghai"))
    return any(h["day"]==local.weekday() and h["start"]<=local.strftime("%H:%M")<h["end"] for h in p["hours"])

async def member_lock(db, member_id, store_id, *, allow_disabled=False):
    m=await db.scalar(select(Member).where(Member.id==member_id,Member.store_id==store_id).with_for_update().execution_options(populate_existing=True))
    if not m or (not m.enabled and not allow_disabled): fail("会员不存在或已停用",403)
    return m

async def ledger(db, m, kind, delta, source, reason):
    existing=await db.scalar(select(Ledger).where(Ledger.store_id==m.store_id,Ledger.member_id==m.id,Ledger.kind==kind,Ledger.source_key==source))
    if existing:
        if existing.delta != delta: fail("同一请求不能重复使用不同金额")
        return existing
    field="points" if kind=="POINTS" else "wallet_cents"
    balance=getattr(m,field)+delta
    asset="积分" if kind=="POINTS" else "储值余额"
    if balance<0: fail(f"{asset}不足，不能扣减至负数")
    if balance>2_000_000_000: fail(f"{asset}超出限额")
    setattr(m,field,balance)
    row=Ledger(store_id=m.store_id,member_id=m.id,kind=kind,delta=delta,balance=balance,source_key=source,reason=reason)
    db.add(row)
    return row

async def adjust_assets(db, store_id, member_id, data: Adjustment, actor):
    # Serialize all changes to this member, including retries and another operator's edits.
    m=await member_lock(db,member_id,store_id)
    source=f"adjust:{data.request_key}"
    existing=await db.scalar(select(Ledger).where(
        Ledger.store_id==store_id, Ledger.member_id==member_id, Ledger.source_key==source
    ))
    if existing:
        if existing.kind!=data.kind or existing.delta!=data.delta or existing.reason!=data.reason:
            fail("同一调整请求的资产类型、数值和原因必须一致，请刷新后重新操作")
        return record(existing)
    # Keep the entire user reason within the ledger's 200-character column.
    row=await ledger(db,m,data.kind,data.delta,source,data.reason)
    await db.flush()
    audit(db,store_id,actor,"member.adjust",member_id,{
        "ledger_id":row.id,"kind":data.kind,"delta":data.delta,
        "before_balance":row.balance-row.delta,"after_balance":row.balance,
        "reason":data.reason,
    })
    await db.commit()
    return record(row)

async def member_view(db,m):
    p=await policy(db,m.store_id)
    level=next(t["name"] for t in reversed(p["tiers"]) if m.lifetime_cents>=t["threshold_cents"])
    return {**record(m),"level":level,"is_test":is_test(),"wallet_payment_enabled":False}

def select_options(groups,selections):
    if set(selections)-{g["id"] for g in groups}: fail("菜品规格已更新，请重新选择")
    names=[]; extra=0
    for g in groups:
        ids=selections.get(g["id"],[])
        if len(ids)!=len(set(ids)) or not g["minimum"]<=len(ids)<=g["maximum"]: fail(f'请正确选择{g["name"]}')
        available={o["id"]:o for o in g["options"] if o["enabled"]}
        for i in sorted(ids):
            if i not in available: fail("所选规格已下架")
            o=available[i]; extra+=o["price_cents"]
            names.append({"group":g["name"],"option":o["name"],"price_cents":o["price_cents"]})
    return extra,names

async def calculate(db:AsyncSession,store:Store,member:Member,data:OrderDraft,lock=False):
    p=await policy(db,store.id)
    if not store.enabled or not is_open(p): fail("门店当前休息，请在营业时间下单")
    if data.fulfillment not in p["fulfillments"]: fail("门店暂不支持此取餐方式")
    ids=sorted({x.dish_id for x in data.items})
    stmt=select(Dish).where(Dish.store_id==store.id,Dish.id.in_(ids)).order_by(Dish.id)
    if lock: stmt=stmt.with_for_update().execution_options(populate_existing=True)
    dishes={d.id:d for d in (await db.scalars(stmt)).all()}
    categories=set((await db.scalars(select(Category.id).where(Category.store_id==store.id,Category.enabled.is_(True)))).all())
    options={o.dish_id:o.groups for o in (await db.scalars(select(DishOptions).where(DishOptions.store_id==store.id,DishOptions.dish_id.in_(ids)))).all()}
    totals={}; items=[]; subtotal=0; keys=set()
    for item in data.items:
        d=dishes.get(item.dish_id)
        if not d or not d.enabled or d.sold_out or d.category_id not in categories: fail("菜品已下架或售罄，请刷新菜单")
        groups=options.get(d.id,[])
        if d.requires_options and not groups: fail("该菜品规格尚未配置")
        extra,names=select_options(groups,item.options)
        canonical=json.dumps({k:sorted(v) for k,v in item.options.items()},sort_keys=True)
        key=(d.id,canonical)
        if key in keys: fail("重复商品行，请合并数量",422)
        keys.add(key)
        totals[d.id]=totals.get(d.id,0)+item.quantity
        if d.stock is not None and totals[d.id]>d.stock: fail(f"{d.name}库存不足")
        unit=d.price_cents+extra
        subtotal+=unit*item.quantity
        items.append({"dish_id":d.id,"name":d.name,"image_url":d.image_url,"quantity":item.quantity,"unit_cents":unit,"total_cents":unit*item.quantity,"options":names,"selection":item.options,"stock_reserved":d.stock is not None})
    if subtotal>100_000_000: fail("订单金额超过限额",422)
    delivery=0; delivery_snapshot=None
    if data.fulfillment=="delivery":
        if subtotal<p["minimum_delivery_cents"]: fail(f'未达到最低起送金额 ¥{p["minimum_delivery_cents"]/100:.2f}')
        result=await check_delivery(store,Coordinates.model_validate(data.address.model_dump(include={"latitude","longitude","coordinate_system"})))
        if not result.available or not result.within_range or result.delivery_fee_cents is None: fail(result.reason or "该地址暂不可配送")
        delivery=result.delivery_fee_cents
        delivery_snapshot={**result.model_dump(),"store_latitude":str(store.latitude),"store_longitude":str(store.longitude),"store_coordinate_system":store.coordinate_system.name,"fee_tiers":store.delivery_fee_tiers}
    packaging=sum(totals.values())*p["packaging_per_item_cents"] if data.fulfillment!="dine_in" else 0
    discount=0
    if data.coupon_claim_id:
        claim=await db.scalar(select(CouponClaim).where(CouponClaim.id==data.coupon_claim_id,CouponClaim.store_id==store.id,CouponClaim.member_id==member.id))
        if not claim or claim.status!="AVAILABLE": fail("优惠券不可用")
        cp=claim.snapshot
        start=datetime.fromisoformat(cp["starts_at"].replace("Z","+00:00")).replace(tzinfo=None)
        end=datetime.fromisoformat(cp["expires_at"].replace("Z","+00:00")).replace(tzinfo=None)
        if not start<=now()<end or subtotal<cp["minimum_cents"]: fail("优惠券尚未生效、已过期或未达到使用门槛")
        discount=min(subtotal,cp["amount_cents"])
    total=subtotal+packaging+delivery-discount
    if total>100_000_000: fail("订单金额超过限额",422)
    return {"items":items,"subtotal_cents":subtotal,"packaging_cents":packaging,"delivery_cents":delivery,"discount_cents":discount,"total_cents":total,"delivery_snapshot":delivery_snapshot,"is_test":is_test(),"payment_status":"UNPAID"}

async def create_order(db,store,member,data:OrderCreate):
    m=await member_lock(db,member.id,store.id)
    payload=data.model_dump(mode="json",exclude={"request_key"})
    hashed=digest(json.dumps(payload,sort_keys=True,separators=(",",":")))
    previous=await db.scalar(select(Order).where(Order.store_id==store.id,Order.member_id==m.id,Order.request_key==data.request_key))
    if previous:
        if previous.request_hash!=hashed: fail("重复提交的内容不一致，请刷新订单状态")
        return order_view(previous)
    price=await calculate(db,store,m,data,True)
    if data.expected_total_cents!=price["total_cents"]: fail("金额已变化，请重新核算并确认")
    for did in sorted({i["dish_id"] for i in price["items"]}):
        lines=[i for i in price["items"] if i["dish_id"]==did]
        if not lines[0]["stock_reserved"]: continue
        qty=sum(i["quantity"] for i in lines)
        changed=await db.execute(update(Dish).where(Dish.id==did,Dish.store_id==store.id,Dish.stock>=qty).values(stock=Dish.stock-qty))
        if changed.rowcount!=1: fail("库存刚刚发生变化，请重新确认")
    if data.coupon_claim_id:
        changed=await db.execute(update(CouponClaim).where(CouponClaim.id==data.coupon_claim_id,CouponClaim.member_id==m.id,CouponClaim.store_id==store.id,CouponClaim.status=="AVAILABLE").values(status="RESERVED"))
        if changed.rowcount!=1: fail("优惠券已被其他订单使用")
    row=Order(number="O"+datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d%H%M%S")+secrets.token_hex(4).upper(),store_id=store.id,member_id=m.id,request_key=data.request_key,request_hash=hashed,status="PENDING",fulfillment=data.fulfillment,contact=data.contact,phone=data.phone,note=data.note,table_number=data.table_number,address=data.address.model_dump() if data.address else None,coupon_claim_id=data.coupon_claim_id,events=[{"status":"PENDING","at":iso(now()),"actor":"customer","reason":"订单已提交，尚未收款"}],**{k:v for k,v in price.items() if k not in {"is_test","payment_status"}})
    db.add(row)
    await db.flush()
    audit(db,store.id,f"member:{m.id}","order.create",row.number)
    await db.commit()
    return order_view(row)

def order_view(o): return {**record(o,omit=("request_key",)),"is_test":is_test(),"payment_status":"UNPAID"}

async def transition(db,store_id,number,data:StateChange,actor,customer_id=None):
    initial=await db.scalar(select(Order).where(Order.store_id==store_id,Order.number==number))
    if not initial or (customer_id is not None and initial.member_id!=customer_id): fail("订单不存在",404)
    m=await member_lock(db,initial.member_id,store_id,allow_disabled=True)
    o=await db.scalar(select(Order).where(Order.id==initial.id).with_for_update().execution_options(populate_existing=True))
    if o.status==data.status: return order_view(o)
    if o.status!=data.expected_status: fail("订单状态已变化，请刷新后重试")
    if customer_id is not None and (o.status!="PENDING" or data.status!="CANCELLED"): fail("门店已接单，请联系门店取消",403)
    transitions={"PENDING":{"ACCEPTED","CANCELLED"},"ACCEPTED":{"PREPARING","CANCELLED"},"PREPARING":{"READY","CANCELLED"},"READY":{"DELIVERING" if o.fulfillment=="delivery" else "COMPLETED","CANCELLED"},"DELIVERING":{"COMPLETED","CANCELLED"}}
    if data.status not in transitions.get(o.status,set()): fail("不能执行此状态变更")
    if data.status=="CANCELLED" and not data.reason.strip(): fail("请填写取消原因",422)
    if data.status=="DELIVERING":
        rider=await db.scalar(select(Rider).where(Rider.id==data.rider_id,Rider.store_id==store_id,Rider.enabled.is_(True)))
        if not rider: fail("请分配本店可用配送员")
        o.rider_id=rider.id
    if data.status=="CANCELLED":
        for did in sorted({i["dish_id"] for i in o.items if i["stock_reserved"]}):
            qty=sum(i["quantity"] for i in o.items if i["dish_id"]==did and i["stock_reserved"])
            await db.execute(update(Dish).where(Dish.id==did,Dish.store_id==store_id,Dish.stock.is_not(None)).values(stock=Dish.stock+qty))
        if o.coupon_claim_id:
            await db.execute(update(CouponClaim).where(CouponClaim.id==o.coupon_claim_id,CouponClaim.member_id==m.id,CouponClaim.status=="RESERVED").values(status="AVAILABLE"))
    if data.status=="COMPLETED":
        p=await policy(db,store_id)
        points=(o.total_cents//100)*p["points_per_yuan"]
        await ledger(db,m,"POINTS",points,f"order:{o.id}","完成订单奖励（订单未收款）")
        m.lifetime_cents+=o.total_cents
        for did in sorted({i["dish_id"] for i in o.items}):
            qty=sum(i["quantity"] for i in o.items if i["dish_id"]==did)
            await db.execute(update(Dish).where(Dish.id==did,Dish.store_id==store_id).values(monthly_sales=Dish.monthly_sales+qty))
        if o.coupon_claim_id:
            await db.execute(update(CouponClaim).where(CouponClaim.id==o.coupon_claim_id,CouponClaim.member_id==m.id,CouponClaim.status=="RESERVED").values(status="USED"))
    o.status=data.status
    o.events=[*o.events,{"status":o.status,"at":iso(now()),"actor":actor,"reason":data.reason}]
    audit(db,store_id,actor,"order.transition",o.number,{"status":o.status,"reason":data.reason})
    await db.commit()
    return order_view(o)

async def claim_coupon(db,store,m,coupon_id):
    m=await member_lock(db,m.id,store.id)
    existing=await db.scalar(select(CouponClaim).where(CouponClaim.member_id==m.id,CouponClaim.coupon_id==coupon_id))
    if existing: return record(existing)
    c=await db.scalar(select(Coupon).where(Coupon.id==coupon_id,Coupon.store_id==store.id).with_for_update())
    if not c or not c.enabled or not c.starts_at<=now()<c.expires_at: fail("优惠券不在领取期")
    if c.birthday_only and (not m.birthday or m.birthday[5:7]!=datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%m")): fail("生日券仅限生日当月领取")
    count=await db.scalar(select(func.count()).select_from(CouponClaim).where(CouponClaim.coupon_id==c.id))
    if count>=c.quantity: fail("优惠券已领完")
    claim=CouponClaim(store_id=store.id,member_id=m.id,coupon_id=c.id,status="AVAILABLE",snapshot=record(c))
    db.add(claim); await db.flush(); await db.commit()
    return record(claim)

async def redeem(db,store,m,data):
    m=await member_lock(db,m.id,store.id)
    old=await db.scalar(select(Redemption).where(Redemption.member_id==m.id,Redemption.request_key==data.request_key))
    if old:
        if old.reward_id!=data.reward_id: fail("重复请求内容不同")
        return record(old)
    reward=await db.scalar(select(Reward).where(Reward.id==data.reward_id,Reward.store_id==store.id).with_for_update())
    if not reward or not reward.enabled or reward.stock<1: fail("奖品已兑完或已下架")
    row=Redemption(store_id=store.id,member_id=m.id,reward_id=reward.id,request_key=data.request_key,code=secrets.token_hex(8).upper(),title=reward.title,points_cost=reward.points_cost,status="PENDING")
    db.add(row); await db.flush()
    await ledger(db,m,"POINTS",-reward.points_cost,f"redeem:{row.id}",f"兑换奖品：{reward.title}")
    reward.stock-=1
    await db.commit()
    return record(row)

async def finish_redemption(db,store_id,redemption_id,status,actor):
    initial=await db.scalar(select(Redemption).where(Redemption.id==redemption_id,Redemption.store_id==store_id))
    if not initial: fail("兑换记录不存在",404)
    m=await member_lock(db,initial.member_id,store_id,allow_disabled=True)
    row=await db.scalar(select(Redemption).where(Redemption.id==initial.id).with_for_update().execution_options(populate_existing=True))
    if row.status==status:return record(row)
    if row.status!="PENDING":fail("该兑换已经处理")
    if status=="CANCELLED":
        await ledger(db,m,"POINTS",row.points_cost,f"redeem-refund:{row.id}","取消兑换返还积分")
        await db.execute(update(Reward).where(Reward.id==row.reward_id,Reward.store_id==store_id).values(stock=Reward.stock+1))
    row.status=status; audit(db,store_id,actor,"redemption.transition",row.id,{"status":status})
    await db.commit(); return record(row)

async def task_progress(db,m,t):
    if t.kind=="PROFILE": return 1 if m.name and m.birthday else 0
    if t.kind=="SPEND": return m.lifetime_cents
    return await db.scalar(select(func.count()).select_from(Order).where(Order.store_id==m.store_id,Order.member_id==m.id,Order.status=="COMPLETED"))

async def claim_task(db,store,m,task_id):
    m=await member_lock(db,m.id,store.id)
    t=await db.scalar(select(GrowthTask).where(GrowthTask.id==task_id,GrowthTask.store_id==store.id,GrowthTask.enabled.is_(True)))
    if not t or await task_progress(db,m,t)<t.target:fail("任务尚未完成")
    await ledger(db,m,"POINTS",t.points_reward,f"task:{t.id}",f"成长任务：{t.title}")
    await db.commit();return await member_view(db,m)
