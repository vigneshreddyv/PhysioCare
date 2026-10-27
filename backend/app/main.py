from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.appointments import router as appointments_router
from app.api.users import router as users_router
from app.api.analytics import router as analytics_router
from app.api.home_visits import router as home_visits_router
from app.api.lab_requests import router as lab_requests_router
from app.api.clinician_schedules import router as clinician_schedules_router
from app.database import init_db
from app.core.config import settings

app = FastAPI(
    title="PhysioCare API",
    version="1.0.0"
)

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Report-Filename"],
)


@app.middleware("http")
async def reject_untrusted_unsafe_origins(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        if fetch_site == "cross-site" or (origin and origin not in settings.CORS_ORIGINS):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Origin not allowed"},
            )
    return await call_next(request)

# -----------------------------
# STARTUP
# -----------------------------
@app.on_event("startup")
async def startup_event():
    await init_db()

# -----------------------------
# ROUTES
# -----------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(home_visits_router, prefix="/api")
app.include_router(lab_requests_router, prefix="/api")
app.include_router(clinician_schedules_router, prefix="/api")

# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to PhysioCare API"
    }
