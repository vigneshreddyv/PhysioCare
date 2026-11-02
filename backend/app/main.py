import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

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
from app.middleware.auth import RoleChecker, get_current_user
from app.core.config import Settings, settings
from app.core.request_limits import MAX_JSON_REQUEST_BYTES, read_bounded_body
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

def api_documentation_enabled(configured_settings: Settings) -> bool:
    """Apply the application-level documentation exposure policy.

    Production is always closed. Staging and the dedicated demo modes require
    an explicit opt-in, which still does not replace an approved network access
    boundary. Ordinary development and tests retain their existing defaults.
    """
    if configured_settings.ENVIRONMENT == "production":
        return False
    if (
        configured_settings.ENVIRONMENT == "staging"
        or configured_settings.LAB_DEMO_MODE
        or configured_settings.HOME_VISIT_DEMO_MODE
    ):
        return configured_settings.API_DOCUMENTATION_ENABLED is True
    return configured_settings.API_DOCUMENTATION_ENABLED is not False


def create_fastapi_application(configured_settings: Settings) -> FastAPI:
    documentation_enabled = api_documentation_enabled(configured_settings)
    documentation_options = {} if documentation_enabled else {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    return FastAPI(
        title="PhysioCare API",
        version="1.0.0",
        lifespan=lifespan,
        **documentation_options,
    )


app = create_fastapi_application(settings)

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


def _authenticated_route(request: Request) -> bool:
    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        return False

    def requires_user(dependency) -> bool:
        return (
            dependency.call is get_current_user
            or isinstance(dependency.call, RoleChecker)
            or any(requires_user(child) for child in dependency.dependencies)
        )

    return any(requires_user(dependency) for dependency in route.dependant.dependencies)


def _set_private_cache_headers(response):
    # Preserve the stronger private PDF policy, but never trust a weaker
    # route-specific cache header on an authenticated response.
    directives = {
        directive.strip().lower()
        for directive in response.headers.get("cache-control", "").split(",")
    }
    if not {"private", "no-store"}.issubset(directives):
        response.headers["Cache-Control"] = "private, no-store"
    response.headers.setdefault("Pragma", "no-cache")
    response.headers.setdefault("Expires", "0")
    return response


@app.middleware("http")
async def protect_private_api_responses(request: Request, call_next):
    response = await call_next(request)
    if request.method != "OPTIONS" and (
        request.url.path in {
            "/api/auth/login", "/api/auth/refresh", "/api/auth/csrf", "/api/auth/logout",
        }
        or _authenticated_route(request)
    ):
        _set_private_cache_headers(response)
    return response


@app.middleware("http")
async def limit_json_request_bodies(request: Request, call_next):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    streamed_upload = (
        request.method == "POST"
        and request.url.path == "/api/reports"
        and content_type == "multipart/form-data"
    ) or (
        request.method == "PUT"
        and request.url.path.startswith("/api/lab-requests/laboratory/")
        and request.url.path.endswith("/report")
        and content_type == "application/pdf"
    )
    if (
        request.url.path.startswith("/api/")
        and request.url.path != "/api/webhooks/razorpay"
        and request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and not streamed_upload
    ):
        try:
            request._body = await read_bounded_body(request, MAX_JSON_REQUEST_BYTES)
        except HTTPException as exc:
            return _set_private_cache_headers(JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            ))
    return await call_next(request)


@app.middleware("http")
async def reject_untrusted_unsafe_origins(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        if fetch_site == "cross-site" or (origin and origin not in settings.CORS_ORIGINS):
            return _set_private_cache_headers(JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Origin not allowed"},
            ))
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
