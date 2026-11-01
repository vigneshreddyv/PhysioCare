import asyncio
from contextlib import asynccontextmanager

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
from app.api.payments import router as payments_router
from app.api.laboratory import router as laboratory_router
from app.api.reports import router as reports_router
from app.api.care_plans import router as care_plans_router
from app.api.exercises import router as exercises_router
from app.api.notifications import router as notifications_router
from app.database import init_db
from app.core.config import settings
from app.services.payment_reconciliation_worker import PaymentReconciliationWorker
from app.services.clinical_report_storage import ClinicalReportStorage, LabReportStorage
from app.services.pdf_malware_scanner import ClamAvUnixScanner, UnavailablePdfMalwareScanner


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_runtime_startup()
    scanner = (
        ClamAvUnixScanner(settings.PDF_SCANNER_SOCKET)
        if settings.PDF_SCANNER_MODE == "clamav_unix"
        else UnavailablePdfMalwareScanner()
    )
    if isinstance(scanner, ClamAvUnixScanner):
        try:
            scanner_ready = await asyncio.wait_for(
                scanner.ready(), timeout=min(settings.PDF_SCAN_TIMEOUT_SECONDS, 5.0)
            )
        except asyncio.TimeoutError:
            scanner_ready = False
        if not scanner_ready:
            raise RuntimeError("Configured PDF scanner is unavailable")
    ClinicalReportStorage.scanner = scanner
    LabReportStorage.scanner = scanner
    await init_db()
    reconciliation_worker = None
    if settings.PAYMENT_RECONCILIATION_ENABLED:
        reconciliation_worker = PaymentReconciliationWorker()
        await reconciliation_worker.start()
    app.state.payment_reconciliation_worker = reconciliation_worker
    try:
        yield
    finally:
        if reconciliation_worker is not None:
            await reconciliation_worker.stop()

app = FastAPI(
    title="PhysioCare API",
    version="1.0.0",
    lifespan=lifespan,
)

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token", "X-Report-Filename"],
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
# ROUTES
# -----------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(home_visits_router, prefix="/api")
app.include_router(lab_requests_router, prefix="/api")
app.include_router(clinician_schedules_router, prefix="/api")
app.include_router(payments_router, prefix="/api")
app.include_router(laboratory_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(care_plans_router, prefix="/api")
app.include_router(exercises_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")

# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to PhysioCare API"
    }


@app.get("/health")
async def health():
    return {
        "environment": (
            "home_visit_demo"
            if settings.HOME_VISIT_DEMO_MODE
            else "lab_demo"
            if settings.LAB_DEMO_MODE
            else "application"
        ),
        "database": settings.DATABASE_NAME if (settings.HOME_VISIT_DEMO_MODE or settings.LAB_DEMO_MODE) else None,
        "payments_enabled": settings.RAZORPAY_MODE.strip().lower() != "disabled",
    }
