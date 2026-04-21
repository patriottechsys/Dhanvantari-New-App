"""
Dhanvantari Ayurveda Care Platform — FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import engine, Base
from app.api.routes import auth, practitioners, patients, plans, checkins, portal, ai, billing, supplements, recipes, followups, consultation_notes, assessments, yoga, pranayama, intake, therapies


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Alembic is authoritative; this covers models
    # added without migrations to avoid cold-start crashes).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Ayurvedic practice management platform",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "https://dhanvantari.patriottechsystems.com",
        "http://localhost:3000",
        "http://localhost:3747",
    ],
    # Any Render deploy for this project (e.g. dhanvantari-pxgv.onrender.com, PR previews)
    allow_origin_regex=r"^https://dhanvantari(-[a-z0-9]+)?\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,          prefix="/api/auth",         tags=["auth"])
app.include_router(practitioners.router, prefix="/api/practitioners", tags=["practitioners"])
app.include_router(patients.router,      prefix="/api/patients",      tags=["patients"])
app.include_router(plans.router,         prefix="/api",               tags=["plans"])
app.include_router(supplements.router,   prefix="/api/supplements",   tags=["supplements"])
app.include_router(recipes.router,       prefix="/api/recipes",       tags=["recipes"])
app.include_router(checkins.router,      prefix="/api",               tags=["checkins"])
app.include_router(portal.router,        prefix="/api/portal",        tags=["portal"])
app.include_router(ai.router,            prefix="/api/ai",            tags=["ai"])
app.include_router(billing.router,       prefix="/api/billing",       tags=["billing"])
app.include_router(followups.router,     prefix="/api/followups",      tags=["followups"])
app.include_router(consultation_notes.router, prefix="/api/patients", tags=["consultation-notes"])
app.include_router(assessments.router,        prefix="/api/patients", tags=["assessments"])
app.include_router(yoga.router,              prefix="/api/yoga-asanas", tags=["yoga"])
app.include_router(yoga.video_router,        prefix="/api/videos",      tags=["videos"])
app.include_router(yoga.plan_yoga_router,    prefix="/api/plans",       tags=["plan-yoga"])
app.include_router(pranayama.router,             prefix="/api/pranayama",   tags=["pranayama"])
app.include_router(pranayama.plan_pranayama_router, prefix="/api/plans",   tags=["plan-pranayama"])
app.include_router(intake.router,                    prefix="/api/intake",  tags=["intake"])
app.include_router(therapies.router,               prefix="/api/therapies",  tags=["therapies"])
app.include_router(therapies.package_router,       prefix="/api/packages",   tags=["packages"])
app.include_router(therapies.plan_therapy_router,  prefix="/api/plans",      tags=["plan-therapies"])
app.include_router(therapies.plan_package_router,  prefix="/api/plans",      tags=["plan-packages"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "build": "demo-seed-v1"}


# ── Static files (logo uploads) ───────────────────────────────────────────────
_upload_dir = settings.STORAGE_LOCAL_PATH
os.makedirs(_upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_upload_dir), name="uploads")
