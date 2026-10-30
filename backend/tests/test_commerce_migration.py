from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, inspect, select, text

from app.config import get_settings


def test_upgrade_from_0003_preserves_existing_business_and_adds_empty_commerce(tmp_path,monkeypatch):
    database=tmp_path/'upgrade.sqlite3'
    monkeypatch.setattr(get_settings(),'database_url',f'sqlite+aiosqlite:///{database}')
    config=Config()
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
    command.upgrade(config,'0003_local_delivery_places')
    engine=create_engine(f'sqlite:///{database}')
    metadata=MetaData()
    metadata.reflect(engine)
    legacy_tables={name:table for name,table in metadata.tables.items() if name!='alembic_version'}
    with engine.begin() as db:
        db.execute(metadata.tables['stores'].insert(),[
            {'id':sid,'slug':f'store-{sid}','name':f'原门店{sid}','phone':'10000','address':'原地址','latitude':22.1,'longitude':113.1,'coordinate_system':'GCJ_02','delivery_radius_meters':5000,'enabled':True}
            for sid in [1,2]
        ])
        db.execute(metadata.tables['roles'].insert(),[{'id':1,'code':'SUPER_ADMIN','name':'总管理员'},{'id':2,'code':'STORE_ADMIN','name':'店长'}])
        db.execute(metadata.tables['admin_users'].insert(),[
            {'id':uid,'username':f'original-{uid}','password_hash':f'preserve-existing-hash-{uid}','display_name':f'原管理员{uid}','role_id':1 if uid==1 else 2,'store_id':None if uid==1 else uid-1,'enabled':True}
            for uid in [1,2,3]
        ])
        db.execute(metadata.tables['categories'].insert(),[
            {'id':sid,'store_id':sid,'name':'原分类','slug':'original','sort_order':1,'enabled':True} for sid in [1,2]
        ])
        db.execute(metadata.tables['dishes'].insert(),[
            {'id':did,'store_id':1 if did<=6 else 2,'category_id':1 if did<=6 else 2,'name':f'原菜品{did}','slug':f'original-{did}','price_cents':1000+did,'monthly_sales':did,'stock':None,'requires_options':False,'sold_out':False,'enabled':True,'sort_order':did}
            for did in range(1,13)
        ])
        before={name:[dict(row) for row in db.execute(select(table).order_by(*table.primary_key.columns)).mappings()] for name,table in legacy_tables.items()}
    command.upgrade(config,'0004_test_commerce')
    with engine.connect() as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0004_test_commerce'
        for name,table in legacy_tables.items():
            assert [dict(row) for row in db.execute(select(table).order_by(*table.primary_key.columns)).mappings()]==before[name]
        commerce_tables=[name for name in inspect(db).get_table_names() if name.startswith('commerce_')]
        assert len(commerce_tables)==14
        for name in commerce_tables:
            assert db.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one()==0
    engine.dispose()
