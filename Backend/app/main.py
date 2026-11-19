from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import admin, alerts, auth, dashboard, reports, shipments, telemetry, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:  # dev/demo convenience; in production use `alembic upgrade head`
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title="ColdChain Pulse API", version="1.0.0",
              description="MedSwift Logistics — pharmaceutical cold-chain tracking backend (MVP)", lifespan=lifespan)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=origins != ["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


for r in (auth, users, shipments, telemetry, alerts, dashboard, reports, admin):
    app.include_router(r.router)
