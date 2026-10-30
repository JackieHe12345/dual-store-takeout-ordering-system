from __future__ import annotations

import secrets
import time
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, Header, Request, Query
from sqlalchemy import select, func, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import CurrentAdminUser, SuperAdmin, get_super_admin, get_scoped_staff_user
from app.dependencies.store_context import CustomerStore
from app.models import Store, Dish
from app.models.enums import RoleCode
from app.models.commerce import (Member, MemberSession, MemberAddress, StorePolicy, DishOptions, Rider,
    Order, Ledger, Coupon, CouponClaim, Reward, Redemption, GrowthTask, AuditEvent)
from app.schemas.commerce import (MemberCredentials, ProfileUpdate, AddressInput, PolicyInput, OptionsInput,
    OrderDraft, OrderCreate, StateChange, RiderInput, CouponInput, RewardInput, TaskInput, Adjustment,
    RedemptionInput, RedemptionState, EnabledInput, MemberCorrection, StoreIdentity)
from app.services import commerce as svc
from app.utils.security import hash_password, verify_password

router=APIRouter(prefix="/commerce",tags=["commerce"])
DB=Annotated[AsyncSession,Depends(get_db)]

def enabled():
    settings=get_settings()
    if not settings.commerce_enabled:
        svc.fail("点餐功能暂未开放",503)

@router.get("/capabilities")
async def capabilities():
    s=get_settings()
    return {"enabled":s.commerce_enabled,"is_test":svc.is_test(),"payment_enabled":False}

customer=APIRouter(dependencies=[Depends(enabled)])

async def current_member(store:CustomerStore,db:DB,x_member_token:Annotated[str|None,Header()]=None):
    if not x_member_token or len(x_member_token)>200: svc.fail("请先登录本店会员",401)
    token=await db.scalar(select(MemberSession).where(MemberSession.store_id==store.id,MemberSession.token_hash==svc.digest(x_member_token),MemberSession.revoked.is_(False),MemberSession.expires_at>svc.now()))
    if not token: svc.fail("会员登录已失效",401)
    member=await db.scalar(select(Member).where(Member.id==token.member_id,Member.store_id==store.id,Member.enabled.is_(True)))
    if not member:svc.fail("会员账号已停用",401)
    return member

Customer=Annotated[Member,Depends(current_member)]
_attempts={}
def login_limit(request,phone):
    stamp=time.monotonic(); key=(request.client.host if request.client else "",phone)
    for k,v in list(_attempts.items()):
        if stamp-v[0]>300: _attempts.pop(k,None)
    if len(_attempts)>5000: svc.fail("登录请求繁忙，请稍后再试",429)
    start,count=_attempts.get(key,(stamp,0))
    if count>=12: svc.fail("尝试过于频繁，请5分钟后重试",429)
    _attempts[key]=(start,count+1)

async def issue_session(db,m,device):
    active=list(await db.scalars(select(MemberSession).where(MemberSession.member_id==m.id,MemberSession.revoked.is_(False)).order_by(MemberSession.id.desc())))
    for old in active[19:]:old.revoked=True
    token=secrets.token_urlsafe(32)
    db.add(MemberSession(store_id=m.store_id,member_id=m.id,token_hash=svc.digest(token),device_name=device,expires_at=svc.now()+timedelta(days=30),revoked=False))
    await db.commit()
    return {"token":token,"member":await svc.member_view(db,m),"expires_in":30*86400}

@customer.post("/members/register",status_code=201)
async def register(data:MemberCredentials,store:CustomerStore,db:DB,request:Request):
    login_limit(request,data.phone)
    m=Member(store_id=store.id,phone=data.phone,password_hash=hash_password(data.password),name="",points=0,wallet_cents=0,lifetime_cents=0,enabled=True)
    db.add(m)
    try: await db.flush()
    except IntegrityError:
        await db.rollback();svc.fail("无法注册，请尝试登录或联系门店")
    return await issue_session(db,m,data.device_name)

@customer.post("/members/login")
async def member_login(data:MemberCredentials,store:CustomerStore,db:DB,request:Request):
    login_limit(request,data.phone)
    m=await db.scalar(select(Member).where(Member.store_id==store.id,Member.phone==data.phone))
    # Use a real Argon2 operation for unknown accounts too; never reveal account profile by phone lookup.
    encoded=m.password_hash if m else hash_password(secrets.token_urlsafe(24))
    valid=verify_password(data.password,encoded)
    if not m or not valid or not m.enabled:svc.fail("手机号或密码不正确",401)
    return await issue_session(db,m,data.device_name)

@customer.get("/members/me")
async def me(m:Customer,db:DB):return await svc.member_view(db,m)

@customer.patch("/members/me")
async def profile(data:ProfileUpdate,m:Customer,db:DB):
    m=await svc.member_lock(db,m.id,m.store_id)
    if m.birthday and data.birthday and m.birthday!=data.birthday.isoformat():svc.fail("生日已登记，修改请联系门店")
    m.name=data.name
    if data.birthday:m.birthday=data.birthday.isoformat()
    await db.commit();return await svc.member_view(db,m)

@customer.get("/members/devices")
async def devices(m:Customer,db:DB,x_member_token:Annotated[str,Header()]):
    rows=await db.scalars(select(MemberSession).where(MemberSession.member_id==m.id,MemberSession.revoked.is_(False),MemberSession.expires_at>svc.now()).order_by(MemberSession.id.desc()))
    return [{**svc.record(r),"current":r.token_hash==svc.digest(x_member_token)} for r in rows]

@customer.delete("/members/devices/{device_id}")
async def revoke_device(device_id:int,m:Customer,db:DB):
    await db.execute(update(MemberSession).where(MemberSession.id==device_id,MemberSession.member_id==m.id,MemberSession.store_id==m.store_id).values(revoked=True));await db.commit();return {"ok":True}

@customer.post("/members/logout")
async def member_logout(m:Customer,db:DB,x_member_token:Annotated[str,Header()]):
    await db.execute(update(MemberSession).where(MemberSession.token_hash==svc.digest(x_member_token),MemberSession.member_id==m.id).values(revoked=True));await db.commit();return {"ok":True}

@customer.get("/addresses")
async def addresses(m:Customer,db:DB):
    return [svc.record(a) for a in await db.scalars(select(MemberAddress).where(MemberAddress.member_id==m.id,MemberAddress.store_id==m.store_id).order_by(MemberAddress.is_default.desc(),MemberAddress.last_used_at.desc(),MemberAddress.id.desc()))]

async def save_address(db,m,data,address_id=None):
    m=await svc.member_lock(db,m.id,m.store_id)
    row=await db.scalar(select(MemberAddress).where(MemberAddress.id==address_id,MemberAddress.member_id==m.id)) if address_id else None
    if address_id and not row:svc.fail("地址不存在",404)
    if not row:
        count=await db.scalar(select(func.count()).select_from(MemberAddress).where(MemberAddress.member_id==m.id))
        if count>=20:svc.fail("最多保存20个地址")
        row=MemberAddress(store_id=m.store_id,member_id=m.id,data={},is_default=False)
        db.add(row)
    if data.is_default:
        await db.execute(update(MemberAddress).where(MemberAddress.member_id==m.id).values(is_default=False))
    row.data=data.model_dump(exclude={"is_default"});row.is_default=data.is_default
    await db.commit();return svc.record(row)

@customer.post("/addresses",status_code=201)
async def add_address(data:AddressInput,m:Customer,db:DB):return await save_address(db,m,data)

@customer.put("/addresses/{address_id}")
async def edit_address(address_id:int,data:AddressInput,m:Customer,db:DB):return await save_address(db,m,data,address_id)

@customer.delete("/addresses/{address_id}")
async def delete_address(address_id:int,m:Customer,db:DB):
    await db.execute(delete(MemberAddress).where(MemberAddress.id==address_id,MemberAddress.member_id==m.id,MemberAddress.store_id==m.store_id));await db.commit();return {"ok":True}

@customer.post("/addresses/{address_id}/use")
async def use_address(address_id:int,m:Customer,db:DB):
    r=await db.execute(update(MemberAddress).where(MemberAddress.id==address_id,MemberAddress.member_id==m.id).values(last_used_at=svc.now()))
    if not r.rowcount:svc.fail("地址不存在",404)
    await db.commit();return {"ok":True}

@customer.get("/catalog")
async def catalog(store:CustomerStore,db:DB):
    p=await svc.policy(db,store.id)
    groups={str(o.dish_id):o.groups for o in await db.scalars(select(DishOptions).where(DishOptions.store_id==store.id))}
    return {"policy":p,"open":svc.is_open(p),"options":groups,"is_test":svc.is_test()}

@customer.post("/orders/quote")
async def quote(data:OrderDraft,store:CustomerStore,m:Customer,db:DB):return await svc.calculate(db,store,m,data)

@customer.post("/orders",status_code=201)
async def place_order(data:OrderCreate,store:CustomerStore,m:Customer,db:DB):return await svc.create_order(db,store,m,data)

@customer.get("/orders")
async def customer_orders(m:Customer,db:DB,before:int|None=None,limit:int=Query(30,ge=1,le=100)):
    q=select(Order).where(Order.member_id==m.id,Order.store_id==m.store_id)
    if before:q=q.where(Order.id<before)
    return [svc.order_view(o) for o in await db.scalars(q.order_by(Order.id.desc()).limit(limit))]

@customer.get("/orders/{number}")
async def customer_order(number:str,m:Customer,db:DB):
    o=await db.scalar(select(Order).where(Order.number==number,Order.member_id==m.id,Order.store_id==m.store_id))
    if not o:svc.fail("订单不存在",404)
    return svc.order_view(o)

@customer.post("/orders/{number}/cancel")
async def cancel(number:str,data:StateChange,m:Customer,db:DB):
    return await svc.transition(db,m.store_id,number,data,f"member:{m.id}",m.id)

@customer.get("/benefits")
async def benefits(m:Customer,db:DB):
    sid=m.store_id
    coupons=[svc.record(c) for c in await db.scalars(select(Coupon).where(Coupon.store_id==sid,Coupon.enabled.is_(True),Coupon.expires_at>svc.now()).order_by(Coupon.id.desc()).limit(100))]
    claims=[svc.record(c) for c in await db.scalars(select(CouponClaim).where(CouponClaim.store_id==sid,CouponClaim.member_id==m.id).order_by(CouponClaim.id.desc()).limit(200))]
    rewards=[svc.record(r) for r in await db.scalars(select(Reward).where(Reward.store_id==sid,Reward.enabled.is_(True)).limit(100))]
    tasks=[]
    for t in await db.scalars(select(GrowthTask).where(GrowthTask.store_id==sid,GrowthTask.enabled.is_(True)).limit(100)):
        claimed=await db.scalar(select(Ledger.id).where(Ledger.member_id==m.id,Ledger.kind=="POINTS",Ledger.source_key==f"task:{t.id}"))
        tasks.append({**svc.record(t),"progress":await svc.task_progress(db,m,t),"claimed":bool(claimed)})
    reds=[svc.record(r) for r in await db.scalars(select(Redemption).where(Redemption.member_id==m.id,Redemption.store_id==sid).order_by(Redemption.id.desc()).limit(100))]
    return {"coupons":coupons,"claims":claims,"rewards":rewards,"tasks":tasks,"redemptions":reds}

@customer.post("/coupons/{coupon_id}/claim")
async def coupon_claim(coupon_id:int,store:CustomerStore,m:Customer,db:DB):return await svc.claim_coupon(db,store,m,coupon_id)

@customer.post("/rewards/redeem",status_code=201)
async def redemption(data:RedemptionInput,store:CustomerStore,m:Customer,db:DB):return await svc.redeem(db,store,m,data)

@customer.post("/tasks/{task_id}/claim")
async def task_claim(task_id:int,store:CustomerStore,m:Customer,db:DB):return await svc.claim_task(db,store,m,task_id)

@customer.get("/ledgers")
async def ledgers(m:Customer,db:DB,before:int|None=None,limit:int=Query(50,ge=1,le=100)):
    q=select(Ledger).where(Ledger.member_id==m.id,Ledger.store_id==m.store_id)
    if before:q=q.where(Ledger.id<before)
    return [svc.record(r) for r in await db.scalars(q.order_by(Ledger.id.desc()).limit(limit))]

async def management(store_id:int,request:Request,user:CurrentAdminUser,db:DB):
    if user.role.code==RoleCode.SUPER_ADMIN:await get_super_admin(request,user)
    else:
        await get_scoped_staff_user(request,user,db)
        if user.store_id!=store_id:svc.fail("不允许跨店访问",403)
    store=await db.get(Store,store_id)
    if not store:svc.fail("门店不存在",404)
    return (store,user)

Management=Annotated[tuple,Depends(management)]
manage=APIRouter(prefix="/manage/{store_id}",dependencies=[Depends(enabled)])
def manager_only(ctx):
    if ctx[1].role.code not in {RoleCode.SUPER_ADMIN,RoleCode.STORE_ADMIN}:svc.fail("仅门店管理员或总管理员可操作",403)

def order_permission(ctx,state=None):
    role=ctx[1].role.code
    allowed={RoleCode.SUPER_ADMIN,RoleCode.STORE_ADMIN,RoleCode.ORDER_OPERATOR}
    if state in {"PREPARING","READY"}:allowed.add(RoleCode.KITCHEN_OPERATOR)
    if state in {"DELIVERING","COMPLETED"}:allowed.add(RoleCode.DELIVERY_OPERATOR)
    if role not in allowed:svc.fail("当前角色没有此订单操作权限",403)

@manage.get("/policy")
async def get_policy(ctx:Management,db:DB):return await svc.policy(db,ctx[0].id)

@manage.get("/identity")
async def get_identity(ctx:Management):
    manager_only(ctx)
    return {"name":ctx[0].name,"phone":ctx[0].phone}

@manage.put("/identity")
async def put_identity(data:StoreIdentity,ctx:Management,db:DB):
    manager_only(ctx)
    ctx[0].name=data.name;ctx[0].phone=data.phone
    svc.audit(db,ctx[0].id,f"admin:{ctx[1].id}","store.identity",ctx[0].id)
    await db.commit()
    return data.model_dump()

@manage.put("/policy")
async def put_policy(data:PolicyInput,ctx:Management,db:DB):
    manager_only(ctx);store,user=ctx
    row=await db.get(StorePolicy,store.id)
    if not row:row=StorePolicy(store_id=store.id,data={});db.add(row)
    row.data=data.model_dump();svc.audit(db,store.id,f"admin:{user.id}","policy.update",store.id)
    await db.commit();return row.data

@manage.get("/options")
async def get_options(ctx:Management,db:DB):
    return {str(o.dish_id):o.groups for o in await db.scalars(select(DishOptions).where(DishOptions.store_id==ctx[0].id))}

@manage.put("/options/{dish_id}")
async def put_options(dish_id:int,data:OptionsInput,ctx:Management,db:DB):
    manager_only(ctx);store,user=ctx
    dish=await db.scalar(select(Dish).where(Dish.id==dish_id,Dish.store_id==store.id).with_for_update())
    if not dish:svc.fail("菜品不存在",404)
    row=await db.get(DishOptions,dish_id)
    if not row:row=DishOptions(dish_id=dish_id,store_id=store.id,groups=[]);db.add(row)
    row.groups=[g.model_dump() for g in data.groups];dish.requires_options=bool(data.groups)
    svc.audit(db,store.id,f"admin:{user.id}","dish.options",dish.id)
    await db.commit();return svc.record(row)

@manage.get("/orders")
async def manage_orders(ctx:Management,db:DB,status:str|None=None,q:str=Query("",max_length=80),before:int|None=None,limit:int=Query(50,ge=1,le=100)):
    stmt=select(Order).where(Order.store_id==ctx[0].id)
    if status:stmt=stmt.where(Order.status==status)
    if q:stmt=stmt.where(Order.number.contains(q,autoescape=True))
    if before:stmt=stmt.where(Order.id<before)
    return [svc.order_view(o) for o in await db.scalars(stmt.order_by(Order.id.desc()).limit(limit))]

@manage.post("/orders/{number}/state")
async def order_state(number:str,data:StateChange,ctx:Management,db:DB):
    order_permission(ctx,data.status)
    if ctx[1].role.code==RoleCode.DELIVERY_OPERATOR:
        fulfillment=await db.scalar(select(Order.fulfillment).where(Order.number==number,Order.store_id==ctx[0].id))
        if fulfillment!="delivery":svc.fail("配送操作员只能处理配送订单",403)
    return await svc.transition(db,ctx[0].id,number,data,f"admin:{ctx[1].id}")

@manage.get("/members")
async def manage_members(ctx:Management,db:DB,q:str=Query("",max_length=30),before:int|None=None,limit:int=Query(50,ge=1,le=100)):
    manager_only(ctx)
    stmt=select(Member).where(Member.store_id==ctx[0].id)
    if q:stmt=stmt.where(Member.phone.contains(q,autoescape=True))
    if before:stmt=stmt.where(Member.id<before)
    return [await svc.member_view(db,m) for m in await db.scalars(stmt.order_by(Member.id.desc()).limit(limit))]

@manage.patch("/members/{member_id}/enabled")
async def member_enabled(member_id:int,data:EnabledInput,ctx:Management,db:DB):
    manager_only(ctx)
    m=await db.scalar(select(Member).where(Member.id==member_id,Member.store_id==ctx[0].id).with_for_update())
    if not m:svc.fail("会员不存在",404)
    m.enabled=data.enabled
    if not data.enabled:await db.execute(update(MemberSession).where(MemberSession.member_id==m.id).values(revoked=True))
    svc.audit(db,ctx[0].id,f"admin:{ctx[1].id}","member.enabled",m.id,{"enabled":data.enabled})
    await db.commit();return await svc.member_view(db,m)

@manage.post("/members/{member_id}/adjust")
async def adjust(member_id:int,data:Adjustment,ctx:Management,db:DB):
    manager_only(ctx)
    return await svc.adjust_assets(db,ctx[0].id,member_id,data,f"admin:{ctx[1].id}")

@manage.put("/members/{member_id}/profile")
async def correct_member(member_id:int,data:MemberCorrection,ctx:Management,db:DB):
    manager_only(ctx)
    m=await svc.member_lock(db,member_id,ctx[0].id,allow_disabled=True)
    m.name=data.name;m.birthday=data.birthday.isoformat() if data.birthday else None
    svc.audit(db,ctx[0].id,f"admin:{ctx[1].id}","member.profile",m.id,{"reason":data.reason})
    await db.commit()
    return await svc.member_view(db,m)

@manage.get("/members/{member_id}/ledgers")
async def member_ledgers(member_id:int,ctx:Management,db:DB):
    manager_only(ctx)
    return [svc.record(x) for x in await db.scalars(select(Ledger).where(Ledger.member_id==member_id,Ledger.store_id==ctx[0].id).order_by(Ledger.id.desc()).limit(200))]

RESOURCE_MODELS={"riders":Rider,"coupons":Coupon,"rewards":Reward,"tasks":GrowthTask}
RESOURCE_INPUTS={"riders":RiderInput,"coupons":CouponInput,"rewards":RewardInput,"tasks":TaskInput}

@manage.get("/resources/{kind}")
async def resource_list(kind:str,ctx:Management,db:DB):
    if kind not in RESOURCE_MODELS:svc.fail("类型不存在",404)
    if kind!="riders":manager_only(ctx)
    model=RESOURCE_MODELS[kind]
    return [svc.record(r) for r in await db.scalars(select(model).where(model.store_id==ctx[0].id).order_by(model.id.desc()).limit(500))]

async def save_resource(kind,data,ctx,db,resource_id=None):
    manager_only(ctx)
    if kind not in RESOURCE_MODELS:svc.fail("类型不存在",404)
    from pydantic import ValidationError
    try:parsed=RESOURCE_INPUTS[kind].model_validate(data)
    except ValidationError as e:svc.fail("请检查填写内容："+"；".join(str(x["msg"]) for x in e.errors())[:400],422)
    model=RESOURCE_MODELS[kind]
    row=await db.scalar(select(model).where(model.id==resource_id,model.store_id==ctx[0].id).with_for_update()) if resource_id else None
    if resource_id and not row:svc.fail("记录不存在",404)
    if not row:row=model(store_id=ctx[0].id,**parsed.model_dump());db.add(row)
    else:
        if kind=="coupons":
            claims=await db.scalar(select(func.count()).select_from(CouponClaim).where(CouponClaim.coupon_id==row.id))
            if parsed.quantity<claims:svc.fail("发放总量不能小于已领取数量")
        for k,v in parsed.model_dump().items():setattr(row,k,v)
    await db.flush();svc.audit(db,ctx[0].id,f"admin:{ctx[1].id}",f"{kind}.save",row.id)
    await db.commit();return svc.record(row)

@manage.post("/resources/{kind}",status_code=201)
async def resource_create(kind:str,data:dict,ctx:Management,db:DB):return await save_resource(kind,data,ctx,db)

@manage.put("/resources/{kind}/{resource_id}")
async def resource_edit(kind:str,resource_id:int,data:dict,ctx:Management,db:DB):return await save_resource(kind,data,ctx,db,resource_id)

@manage.get("/redemptions")
async def redemptions(ctx:Management,db:DB):
    order_permission(ctx)
    return [svc.record(r) for r in await db.scalars(select(Redemption).where(Redemption.store_id==ctx[0].id).order_by(Redemption.id.desc()).limit(200))]

@manage.post("/redemptions/{redemption_id}/state")
async def redemption_state(redemption_id:int,data:RedemptionState,ctx:Management,db:DB):
    order_permission(ctx)
    return await svc.finish_redemption(db,ctx[0].id,redemption_id,data.status,f"admin:{ctx[1].id}")

@manage.get("/stats")
async def stats(ctx:Management,db:DB,days:int=Query(30,ge=1,le=366)):
    manager_only(ctx);sid=ctx[0].id
    cutoff=svc.now()-timedelta(days=days)
    rows=(await db.execute(select(Order.status,func.count(),func.coalesce(func.sum(Order.total_cents),0)).where(Order.store_id==sid,Order.created_at>=cutoff).group_by(Order.status))).all()
    return {"is_test":svc.is_test(),"days":days,"real_revenue_cents":0,"by_status":[{"status":s,"count":n,"unpaid_total_cents":amount,"unpaid_test_total_cents":amount} for s,n,amount in rows],"members":await db.scalar(select(func.count()).select_from(Member).where(Member.store_id==sid))}

@manage.get("/audit")
async def audit_events(ctx:Management,db:DB,before:int|None=None):
    manager_only(ctx)
    q=select(AuditEvent).where(AuditEvent.store_id==ctx[0].id)
    if before:q=q.where(AuditEvent.id<before)
    return [svc.record(r) for r in await db.scalars(q.order_by(AuditEvent.id.desc()).limit(100))]

@router.get("/overview",dependencies=[Depends(enabled)])
async def overview(user:SuperAdmin,db:DB,days:int=Query(30,ge=1,le=366)):
    cutoff=svc.now()-timedelta(days=days)
    rows=(await db.execute(select(Order.store_id,Order.status,func.count(),func.coalesce(func.sum(Order.total_cents),0)).where(Order.created_at>=cutoff).group_by(Order.store_id,Order.status))).all()
    counts=dict((await db.execute(select(Member.store_id,func.count()).group_by(Member.store_id))).all())
    return {"is_test":svc.is_test(),"days":days,"real_revenue_cents":0,"stores":[{"id":store.id,"name":store.name,"members":counts.get(store.id,0),"by_status":[{"status":s,"count":n,"unpaid_total_cents":amount,"unpaid_test_total_cents":amount} for sid,s,n,amount in rows if sid==store.id]} for store in await db.scalars(select(Store).order_by(Store.id))]}

router.include_router(customer)
router.include_router(manage)
