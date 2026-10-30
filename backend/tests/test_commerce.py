from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select
from app.config import get_settings, Settings
from app.models import Dish, Store
from app.models.commerce import Order, Member, Ledger, AuditEvent
from app.routers.commerce import _attempts
from tests.conftest import login

@pytest.fixture(autouse=True)
def commerce_mode(monkeypatch):
    monkeypatch.setattr(get_settings(),"app_env","testing")
    monkeypatch.setattr(get_settings(),"enable_commerce",False)
    monkeypatch.setattr(get_settings(),"enable_test_commerce",True)
    _attempts.clear()

async def member(client,phone="13800000001",host="shop-a.localhost"):
    r=await client.post('/api/commerce/members/register',headers={'host':host},json={'phone':phone,'password':'Testing-Member!123'})
    assert r.status_code==201,r.text
    return {'host':host,'x-member-token':r.json()['token']},r.json()['member']

async def manager(client):
    token=await login(client,'staff_a','staff-a.localhost')
    return {'host':'staff-a.localhost','authorization':f'Bearer {token}'}

def draft(**extra):
    return {'items':[{'dish_id':1,'quantity':2,'options':{}}],'fulfillment':'pickup','contact':'测试顾客','phone':'13800000001',**extra}

async def order(client,h,**extra):
    data=draft(**extra)
    q=await client.post('/api/commerce/orders/quote',headers=h,json=data)
    assert q.status_code==200,q.text
    r=await client.post('/api/commerce/orders',headers=h,json={**data,'expected_total_cents':q.json()['total_cents'],'request_key':'test_order_request_001'})
    assert r.status_code==201,r.text
    return r.json()

@pytest.mark.asyncio
async def test_order_stock_idempotency_and_cancel(client,session_factory):
    h,m=await member(client)
    async with session_factory() as s:
        d=await s.get(Dish,1);d.stock=3;await s.commit()
    o=await order(client,h)
    data={**draft(),'expected_total_cents':2000,'request_key':'test_order_request_001'}
    again=await client.post('/api/commerce/orders',headers=h,json=data)
    assert again.json()['number']==o['number']
    changed=await client.post('/api/commerce/orders',headers=h,json={**data,'note':'different'})
    assert changed.status_code==409
    async with session_factory() as s:assert (await s.get(Dish,1)).stock==1
    body={'status':'CANCELLED','expected_status':'PENDING','reason':'测试取消'}
    for _ in range(2):
        r=await client.post(f"/api/commerce/orders/{o['number']}/cancel",headers=h,json=body)
        assert r.status_code==200,r.text
    async with session_factory() as s:assert (await s.get(Dish,1)).stock==3

@pytest.mark.asyncio
async def test_isolation_and_prices(client):
    h,m=await member(client)
    wrong=await client.post('/api/commerce/orders/quote',headers=h,json=draft(items=[{'dish_id':2,'quantity':1}]))
    assert wrong.status_code==409
    bad=await client.post('/api/commerce/orders',headers=h,json={**draft(),'expected_total_cents':1,'request_key':'wrong_price_key_001'})
    assert bad.status_code==409
    o=await order(client,h)
    other,_=await member(client,phone='13800000002')
    assert (await client.get('/api/commerce/orders/'+o['number'],headers=other)).status_code==404
    assert (await client.get('/api/commerce/members/me',headers={**h,'host':'shop-b.localhost'})).status_code==401
    staff=await manager(client)
    assert (await client.get('/api/commerce/manage/2/orders',headers=staff)).status_code==403

@pytest.mark.asyncio
async def test_complete_order_once_and_stats(client,session_factory):
    h,m=await member(client);staff=await manager(client);o=await order(client,h)
    old='PENDING'
    for state in ['ACCEPTED','PREPARING','READY','COMPLETED']:
        r=await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':state,'expected_status':old})
        assert r.status_code==200,r.text
        old=state
    again=await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'COMPLETED','expected_status':'READY'})
    assert again.status_code==200
    me=(await client.get('/api/commerce/members/me',headers=h)).json()
    assert me['points']==20 and me['lifetime_cents']==2000
    assert (await client.get('/api/commerce/manage/1/stats',headers=staff)).json()['real_revenue_cents']==0
    r=await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'CANCELLED','expected_status':'COMPLETED','reason':'late'})
    assert r.status_code==409

@pytest.mark.asyncio
async def test_options_policy_and_stock(client):
    from app.schemas.commerce import Hours
    assert Hours(day=0,start='23:00',end='24:00').end=='24:00'
    h,m=await member(client);staff=await manager(client)
    opts={'groups':[{'id':'size','name':'份量','minimum':1,'maximum':1,'options':[{'id':'large','name':'大份','price_cents':500}]}]}
    r=await client.put('/api/commerce/manage/1/options/1',headers=staff,json=opts);assert r.status_code==200,r.text
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=draft())).status_code==409

    q=await client.post('/api/commerce/orders/quote',headers=h,json=draft(items=[{'dish_id':1,'quantity':2,'options':{'size':['large']}}]))
    assert q.json()['total_cents']==3000
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=draft(items=[{'dish_id':1,'quantity':1,'options':{'size':['large','large']}}]))).status_code==409
    await client.put('/api/commerce/manage/1/policy',headers=staff,json={'accepting_orders':False})
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=draft())).status_code==409

@pytest.mark.asyncio
async def test_disabled_member_existing_order_and_cross_store_stats(client):
    h,m=await member(client);staff=await manager(client);o=await order(client,h)
    assert (await client.patch(f"/api/commerce/manage/1/members/{m['id']}/enabled",headers=staff,json={'enabled':False})).status_code==200
    r=await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'CANCELLED','expected_status':'PENDING','reason':'停用后处理旧单'})
    assert r.status_code==200,r.text
    assert (await client.get('/api/commerce/overview',headers=staff)).status_code==403
    token=await login(client,'admin','admin.localhost')
    r=await client.get('/api/commerce/overview',headers={'host':'admin.localhost','authorization':f'Bearer {token}'})
    assert r.status_code==200,r.text
    assert len(r.json()['stores'])==2
    assert r.json()['stores'][0]['by_status'][0]['status']=='CANCELLED'

@pytest.mark.asyncio
async def test_roles_identity_and_profile_correction(client,session_factory):
    from app.models import AdminUser, Role
    from app.models.enums import RoleCode
    from app.utils.security import hash_password
    from tests.conftest import TEST_PASSWORD
    async with session_factory() as db:
        for code in [RoleCode.KITCHEN_OPERATOR,RoleCode.DELIVERY_OPERATOR]:
            role=Role(code=code,name=code,permissions=[])
            db.add(AdminUser(username=code,password_hash=hash_password(TEST_PASSWORD),display_name=code,role=role,store_id=1,enabled=True))
        await db.commit()
    h,m=await member(client);staff=await manager(client);o=await order(client,h)
    tokens={code:{'host':'staff-a.localhost','authorization':'Bearer '+await login(client,code,'staff-a.localhost')} for code in ['KITCHEN_OPERATOR','DELIVERY_OPERATOR']}
    path=f"/api/commerce/manage/1/orders/{o['number']}/state"
    assert (await client.post(path,headers=tokens['KITCHEN_OPERATOR'],json={'status':'ACCEPTED','expected_status':'PENDING'})).status_code==403
    assert (await client.post(path,headers=staff,json={'status':'ACCEPTED','expected_status':'PENDING'})).status_code==200
    assert (await client.post(path,headers=tokens['KITCHEN_OPERATOR'],json={'status':'PREPARING','expected_status':'ACCEPTED'})).status_code==200
    assert (await client.post(path,headers=tokens['KITCHEN_OPERATOR'],json={'status':'READY','expected_status':'PREPARING'})).status_code==200
    assert (await client.post(path,headers=tokens['DELIVERY_OPERATOR'],json={'status':'COMPLETED','expected_status':'READY'})).status_code==403
    identity={'name':'测试门店新名','phone':'0760-12345678'}
    assert (await client.put('/api/commerce/manage/1/identity',headers=tokens['KITCHEN_OPERATOR'],json=identity)).status_code==403
    assert (await client.put('/api/commerce/manage/1/identity',headers=staff,json=identity)).status_code==200
    assert (await client.get('/api/menu',headers=h)).json()['store']['name']==identity['name']
    body={'name':'更正测试资料','birthday':'2000-01-01','reason':'内部资料验收'}
    assert (await client.put(f"/api/commerce/manage/1/members/{m['id']}/profile",headers=staff,json=body)).status_code==200
    assert (await client.get('/api/commerce/members/me',headers=h)).json()['birthday']=='2000-01-01'

@pytest.mark.asyncio
async def test_coupon_reservation_release(client):
    h,m=await member(client);staff=await manager(client)
    now=datetime.now(timezone.utc)
    coupon={'title':'测试满减','amount_cents':500,'minimum_cents':1000,'quantity':1,'starts_at':(now-timedelta(days=1)).isoformat(),'expires_at':(now+timedelta(days=1)).isoformat()}
    r=await client.post('/api/commerce/manage/1/resources/coupons',headers=staff,json=coupon);assert r.status_code==201,r.text
    cid=r.json()['id']
    r=await client.post(f'/api/commerce/coupons/{cid}/claim',headers=h);assert r.status_code==200,r.text
    claim=r.json()['id'];o=await order(client,h,coupon_claim_id=claim)
    assert o['total_cents']==1500
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=draft(coupon_claim_id=claim))).status_code==409
    await client.post(f"/api/commerce/orders/{o['number']}/cancel",headers=h,json={'status':'CANCELLED','expected_status':'PENDING','reason':'测试'})
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=draft(coupon_claim_id=claim))).status_code==200
    other,_=await member(client,phone='13800000002')
    assert (await client.post(f'/api/commerce/coupons/{cid}/claim',headers=other)).status_code==409

@pytest.mark.asyncio
async def test_rewards_tasks_wallet_and_role(client):
    h,m=await member(client);staff=await manager(client)
    adjustment={'kind':'POINTS','delta':100,'reason':'测试赠送积分','request_key':'test_adjustment_0001'}
    for _ in range(2):assert (await client.post(f"/api/commerce/manage/1/members/{m['id']}/adjust",headers=staff,json=adjustment)).status_code==200
    r=await client.post('/api/commerce/manage/1/resources/rewards',headers=staff,json={'title':'测试饮品','points_cost':30,'stock':1});rid=r.json()['id']
    payload={'reward_id':rid,'request_key':'test_redemption_001'}
    r=await client.post('/api/commerce/rewards/redeem',headers=h,json=payload);assert r.status_code==201,r.text
    redemption=r.json()['id']
    for _ in range(2):assert (await client.post('/api/commerce/rewards/redeem',headers=h,json=payload)).status_code==201
    assert (await client.get('/api/commerce/members/me',headers=h)).json()['points']==70
    for _ in range(2):assert (await client.post(f'/api/commerce/manage/1/redemptions/{redemption}/state',headers=staff,json={'status':'CANCELLED'})).status_code==200
    assert (await client.get('/api/commerce/members/me',headers=h)).json()['points']==100
    task=(await client.post('/api/commerce/manage/1/resources/tasks',headers=staff,json={'title':'完善档案','kind':'PROFILE','target':1,'points_reward':10})).json()
    assert (await client.post(f"/api/commerce/tasks/{task['id']}/claim",headers=h)).status_code==409
    await client.patch('/api/commerce/members/me',headers=h,json={'name':'测试会员','birthday':'1995-01-01'})
    for _ in range(2):assert (await client.post(f"/api/commerce/tasks/{task['id']}/claim",headers=h)).status_code==200
    assert (await client.get('/api/commerce/members/me',headers=h)).json()['points']==110
    token=await login(client,'operator_a','staff-a.localhost')
    op={'host':'staff-a.localhost','authorization':f'Bearer {token}'}
    assert (await client.post(f"/api/commerce/manage/1/members/{m['id']}/adjust",headers=op,json=adjustment)).status_code==403
    assert (await client.post(f"/api/commerce/manage/1/members/{m['id']}/adjust",headers=staff,json={**adjustment,'kind':'WALLET','delta':-1,'request_key':'test_wallet_negative'})).status_code==409

@pytest.mark.asyncio
@pytest.mark.parametrize('kind,field', [('POINTS','points'),('WALLET','wallet_cents')])
async def test_manual_asset_increase_decrease_and_single_audit(client,session_factory,kind,field):
    h,m=await member(client);staff=await manager(client)
    path=f"/api/commerce/manage/1/members/{m['id']}/adjust"
    # The longest accepted reason must fit PostgreSQL VARCHAR(200) without truncation.
    reason='测试原因'+('字'*196)
    credit={'kind':kind,'delta':12345,'reason':reason,'request_key':'manual_asset_credit_001'}
    first=(await client.post(path,headers=staff,json=credit))
    assert first.status_code==200,first.text
    for _ in range(2):
        replay=await client.post(path,headers=staff,json=credit)
        assert replay.status_code==200,replay.text
        assert replay.json()==first.json()
    assert first.json()['reason']==reason and len(first.json()['reason'])==200
    debit={**credit,'delta':-2345,'reason':'测试减少余额','request_key':'manual_asset_debit_001'}
    r=await client.post(path,headers=staff,json=debit)
    assert r.status_code==200,r.text
    assert r.json()['balance']==10000
    assert (await client.get('/api/commerce/members/me',headers=h)).json()[field]==10000
    # A rejected overdraft must not create a ledger entry or an audit event.
    r=await client.post(path,headers=staff,json={**debit,'delta':-10001,'request_key':'manual_asset_overdraft'})
    assert r.status_code==409
    async with session_factory() as db:
        rows=list(await db.scalars(select(Ledger).where(Ledger.member_id==m['id']).order_by(Ledger.id)))
        events=list(await db.scalars(select(AuditEvent).where(AuditEvent.action=='member.adjust').order_by(AuditEvent.id)))
        assert len(rows)==len(events)==2
        assert events[0].detail['ledger_id']==rows[0].id
        assert events[0].detail['before_balance']==0 and events[0].detail['after_balance']==12345
        assert events[1].detail['before_balance']==12345 and events[1].detail['after_balance']==10000
        assert (await db.get(Member,m['id'])).lifetime_cents==0
    # Zero is valid as an ending balance, but not as an adjustment amount.
    r=await client.post(path,headers=staff,json={**debit,'delta':-10000,'request_key':'manual_asset_clear_001'})
    assert r.status_code==200 and r.json()['balance']==0
    assert (await client.post(path,headers=staff,json={**debit,'delta':0,'request_key':'manual_asset_zero_001'})).status_code==422

@pytest.mark.asyncio
async def test_manual_asset_payload_reuse_and_access_rejected(client,session_factory):
    h,m=await member(client);staff=await manager(client)
    path=f"/api/commerce/manage/1/members/{m['id']}/adjust"
    body={'kind':'POINTS','delta':20,'reason':'店内赠送积分','request_key':'manual_asset_request_001'}
    assert (await client.post(path,headers=staff,json=body)).status_code==200
    for change in [{'kind':'WALLET'},{'delta':21},{'reason':'另一条调整原因'}]:
        assert (await client.post(path,headers=staff,json={**body,**change})).status_code==409
    assert (await client.post(path,headers=staff,json={**body,'reason':'  '})).status_code==422
    assert (await client.post(path,headers=h,json=body)).status_code==401
    op={'host':'staff-a.localhost','authorization':'Bearer '+await login(client,'operator_a','staff-a.localhost')}
    assert (await client.post(path,headers=op,json=body)).status_code==403
    other,other_member=await member(client,phone='13800000002',host='shop-b.localhost')
    assert (await client.post(f"/api/commerce/manage/1/members/{other_member['id']}/adjust",headers=staff,json=body)).status_code==403
    assert (await client.post(f"/api/commerce/manage/2/members/{other_member['id']}/adjust",headers=staff,json=body)).status_code==403
    async with session_factory() as db:
        assert (await db.get(Member,m['id'])).points==20
        assert (await db.get(Member,m['id'])).wallet_cents==0
        assert (await db.get(Member,other_member['id'])).points==0
        assert len(list(await db.scalars(select(AuditEvent).where(AuditEvent.action=='member.adjust'))))==1

@pytest.mark.asyncio
async def test_address_devices_and_disabled_member(client):
    h,m=await member(client);other,_=await member(client,phone='13800000002');staff=await manager(client)
    address={'contact':'测试顾客','phone':'13800000001','title':'测试收货点','detail':'一楼','latitude':22.1,'longitude':113.1,'coordinate_system':'GCJ_02','is_default':True}
    r=await client.post('/api/commerce/addresses',headers=h,json=address);assert r.status_code==201,r.text
    aid=r.json()['id']
    assert (await client.put(f'/api/commerce/addresses/{aid}',headers=other,json=address)).status_code==404
    assert (await client.get('/api/commerce/addresses',headers=other)).json()==[]
    devices=(await client.get('/api/commerce/members/devices',headers=h)).json()
    assert devices[0]['current'] and 'token_hash' not in devices[0]
    assert (await client.patch(f"/api/commerce/manage/1/members/{m['id']}/enabled",headers=staff,json={'enabled':False})).status_code==200
    assert (await client.get('/api/commerce/members/me',headers=h)).status_code==401

@pytest.mark.asyncio
async def test_delivery_fail_closed_and_state_machine(client,session_factory):
    h,m=await member(client);staff=await manager(client)
    address={'contact':'测试顾客','phone':'13800000001','title':'测试位置','detail':'一楼','latitude':22.1,'longitude':113.1,'coordinate_system':'GCJ_02'}
    data=draft(fulfillment='delivery',address=address)
    assert (await client.post('/api/commerce/orders/quote',headers=h,json=data)).status_code==409
    async with session_factory() as s:
        st=await s.get(Store,1);st.delivery_location_confirmed=True;st.delivery_fee_tiers=[{'up_to_meters':5000,'fee_cents':300}];await s.commit()
    o=await order(client,h,fulfillment='delivery',address=address)
    assert o['total_cents']==2300 and o['delivery_snapshot']['distance_meters']==0
    r=await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'COMPLETED','expected_status':'PENDING'})
    assert r.status_code==409
    for previous,state in [('PENDING','ACCEPTED'),('ACCEPTED','PREPARING'),('PREPARING','READY')]:
        assert (await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':state,'expected_status':previous})).status_code==200
    assert (await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'DELIVERING','expected_status':'READY'})).status_code==409
    rider=(await client.post('/api/commerce/manage/1/resources/riders',headers=staff,json={'name':'测试配送员','phone':'13800000003'})).json()
    assert (await client.post(f"/api/commerce/manage/1/orders/{o['number']}/state",headers=staff,json={'status':'DELIVERING','expected_status':'READY','rider_id':rider['id']})).status_code==200

@pytest.mark.asyncio
async def test_production_gate(client,monkeypatch):
    monkeypatch.setattr(get_settings(),'enable_test_commerce',False)
    assert not (await client.get('/api/commerce/capabilities')).json()['enabled']
    assert (await client.get('/api/commerce/catalog',headers={'host':'shop-a.localhost'})).status_code==503
    with pytest.raises(ValueError):Settings(app_env='production',enable_test_commerce=True)

def test_production_commerce_configuration(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('ENABLE_COMMERCE','true')
    monkeypatch.setenv('ENABLE_TEST_COMMERCE','false')
    config=Settings(_env_file=None,jwt_secret='production-config-test-secret-over-32-characters',database_url='postgresql+asyncpg://owner:configured-password@db/orders')
    assert config.app_env=='production' and config.commerce_enabled
    assert not config.enable_test_commerce
    with pytest.raises(ValueError,match='ENABLE_TEST_COMMERCE'):
        Settings(_env_file=None,app_env='production',enable_test_commerce=True)

@pytest.mark.asyncio
async def test_production_orders_are_unpaid_and_wallet_cannot_pay(client,monkeypatch):
    monkeypatch.setattr(get_settings(),'app_env','production')
    monkeypatch.setattr(get_settings(),'enable_commerce',True)
    monkeypatch.setattr(get_settings(),'enable_test_commerce',False)
    capabilities=(await client.get('/api/commerce/capabilities')).json()
    assert capabilities=={'enabled':True,'is_test':False,'payment_enabled':False}
    catalog=(await client.get('/api/commerce/catalog',headers={'host':'shop-a.localhost'})).json()
    assert catalog['is_test'] is False and catalog['open'] is True
    h,m=await member(client);staff=await manager(client)
    assert m['is_test'] is False and m['wallet_payment_enabled'] is False
    adjustment={'kind':'WALLET','delta':5000,'reason':'店内账目登记','request_key':'production_wallet_credit'}
    assert (await client.post(f"/api/commerce/manage/1/members/{m['id']}/adjust",headers=staff,json=adjustment)).status_code==200
    q=await client.post('/api/commerce/orders/quote',headers=h,json=draft())
    assert q.json()['is_test'] is False and q.json()['payment_status']=='UNPAID'
    # Payment claims cannot be injected into an otherwise valid order request.
    body={**draft(),'expected_total_cents':2000,'request_key':'production_order_001'}
    for payment in [{'payment_status':'PAID'},{'payment_method':'WALLET'}]:
        assert (await client.post('/api/commerce/orders',headers=h,json={**body,**payment})).status_code==422
    r=await client.post('/api/commerce/orders',headers=h,json=body)
    assert r.status_code==201,r.text
    o=r.json()
    assert o['number'].startswith('O') and o['is_test'] is False and o['payment_status']=='UNPAID'
    assert '测试' not in o['events'][0]['reason']
    path=f"/api/commerce/manage/1/orders/{o['number']}/state"
    assert (await client.post(path,headers=staff,json={'status':'PAID','expected_status':'PENDING'})).status_code==422
    assert (await client.post(f"/api/commerce/orders/{o['number']}/pay",headers=h,json={'method':'WALLET'})).status_code==404
    previous='PENDING'
    for status in ['ACCEPTED','PREPARING','READY','COMPLETED']:
        r=await client.post(path,headers=staff,json={'status':status,'expected_status':previous})
        assert r.status_code==200,r.text
        assert r.json()['payment_status']=='UNPAID' and r.json()['is_test'] is False
        previous=status
    me=(await client.get('/api/commerce/members/me',headers=h)).json()
    assert me['wallet_cents']==5000 and me['wallet_payment_enabled'] is False
    stats=(await client.get('/api/commerce/manage/1/stats',headers=staff)).json()
    assert stats['is_test'] is False and stats['real_revenue_cents']==0
    assert stats['by_status']==[{'status':'COMPLETED','count':1,'unpaid_total_cents':2000,'unpaid_test_total_cents':2000}]
    token=await login(client,'admin','admin.localhost')
    overview=(await client.get('/api/commerce/overview',headers={'host':'admin.localhost','authorization':f'Bearer {token}'})).json()
    assert overview['is_test'] is False and overview['real_revenue_cents']==0
    assert overview['stores'][0]['by_status']==stats['by_status']
    # Explicitly turning the production feature off disables both customer and management APIs.
    monkeypatch.setattr(get_settings(),'enable_commerce',False)
    assert (await client.get('/api/commerce/capabilities')).json()=={'enabled':False,'is_test':False,'payment_enabled':False}
    assert (await client.get('/api/commerce/catalog',headers=h)).status_code==503
    assert (await client.get('/api/commerce/manage/1/members',headers=staff)).status_code==503
