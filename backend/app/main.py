from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.appointments import router as appointments_router
from app.api.users import router as users_router
from app.api.analytics import router as analytics_router
from app.api.laboratory import router as laboratory_router
from app.api.notifications import router as notifications_router
from app.api.reports import router as reports_router
from app.api.care_plans import router as care_plans_router
from app.api.exercises import router as exercises_router
from app.api.webhooks import router as webhooks_router
from app.core.logging_config import configure_logging
from app.database import init_db
from app.services.stale_payment_reconciliation_service import (
    StalePaymentReconciliationService,
)
from app.services.refund_reconciliation_service import (
    RefundReconciliationService,
)

app = FastAPI(
    title="PhysioCare API",
    version="1.0.0"
)

# -----------------------------
# LOGGING
# -----------------------------
# Phase 4, Task 20 — centralized logging, installed ONCE at import time
# (before any request or background loop can run) so the reconciliation
# observability INFO lines (Task 18) are actually visible instead of
# being dropped by the root logger's WARNING default. Pure configuration:
# no flag is flipped, no loop starts, and the only setting read is
# LOG_LEVEL. The print()-based request middleware below is unchanged
# (Task 11's allowlisted SAFE_LOG_HEADERS remain the request-log
# boundary); uvicorn's own loggers are likewise untouched.
configure_logging()

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://172.23.24.123:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# REQUEST LOGGER
# -----------------------------
# Security (Phase 4, Task 11): request logging is ALLOW-LIST based.
# Authentication credentials (Authorization, Cookie), payment signatures
# (x-razorpay-signature), tokens, and secrets can NEVER leak into logs:
# only the headers explicitly listed below are ever printed. Logging the
# full header set or the Authorization header is prohibited here.
SAFE_LOG_HEADERS = frozenset({
    "accept",
    "content-length",
    "content-type",
    "host",
    "origin",
    "referer",
    "user-agent",
})


@app.middleware("http")
async def log_request(request: Request, call_next):
    print("\n" + "=" * 60)
    print(f"[REQUEST] {request.method} {request.url.path}")

    safe_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() in SAFE_LOG_HEADERS
    }
    print(f"[REQUEST] Safe headers: {safe_headers}")

    print("=" * 60)

    response = await call_next(request)

    print(f"[RESPONSE] Status: {response.status_code}")
    print("=" * 60 + "\n")

    return response

# -----------------------------
# STARTUP
# -----------------------------
@app.on_event("startup")
async def startup_event():
    await init_db()

    # Phase 4 Task 9 — minimal background reconciliation loop for stale
    # pending payments. Opt-IN via PAYMENT_RECONCILIATION_ENABLED=true PLUS
    # an explicit PAYMENT_PENDING_EXPIRY_MINUTES value (no expiry duration
    # is approved by default, so the loop does not start by default and no
    # booking is expired). Sleeps before the first run (startup is never
    # blocked), swallows all run errors, and survives for the process
    # lifetime.
    StalePaymentReconciliationService.start_background_loop()

    # Phase 4 Task 16 — refund reconciliation & recovery loop. Same
    # established Task 9 pattern: opt-IN via
    # REFUND_RECONCILIATION_ENABLED=true (default False — no automatic
    # reconciliation policy is approved), sleeps before the first run,
    # swallows all run errors. With the default configuration nothing
    # runs automatically; the batch entry point stays an internal
    # callable.
    RefundReconciliationService.start_background_loop()

# -----------------------------
# ROUTES
# -----------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(laboratory_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(care_plans_router, prefix="/api")
app.include_router(exercises_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")


# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to PhysioCare API"
    }