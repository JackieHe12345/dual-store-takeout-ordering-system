"""Loopback-only local preview. Production uses Nginx, never this adapter."""
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.routing import Mount, Route
from app.config import get_settings
from app.main import app as api
from app.services import images

if get_settings().app_env != "testing" or not get_settings().enable_test_commerce:
    raise RuntimeError("Preview requires an isolated testing database")

root = Path(__file__).resolve().parents[2]
images.UPLOAD_DIR = root / "test-data/uploads"
images.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
entries = {"Adiandiancan":("customer","shop-a.localhost"), "Bdiandiancan":("customer","shop-b.localhost"), "Adianneibuguanli":("staff","staff-a.localhost"), "Bdianneibuguanli":("staff","staff-b.localhost"), "neibuguanli":("admin","admin.localhost")}
static = Starlette(routes=[Route("/",lambda _:RedirectResponse("/Adiandiancan/")), Mount("/media/uploads",StaticFiles(directory=images.UPLOAD_DIR)), Mount("/media",StaticFiles(directory=root/"nginx/html/media")), *[Mount("/"+entry,StaticFiles(directory=root/"nginx/html"/kind,html=True)) for entry,(kind,host) in entries.items()]])

async def app(scope,receive,send):
    if scope["type"]=="http":
        parts=scope["path"].split("/",3)
        if len(parts)>=3 and parts[1] in entries and parts[2]=="api":
            scope={**scope,"path":"/api/"+(parts[3] if len(parts)>3 else ""),"headers":[(k,v) for k,v in scope["headers"] if k.lower()!=b"host"]+[(b"host",entries[parts[1]][1].encode())]}
            return await api(scope,receive,send)
    await static(scope,receive,send)
