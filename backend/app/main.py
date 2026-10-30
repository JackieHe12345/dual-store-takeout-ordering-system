from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import admin, auth, commerce, delivery, health, menu, staff

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router, prefix="/api")
app.include_router(menu.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(staff.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(delivery.router, prefix="/api")
app.include_router(commerce.router, prefix="/api")
