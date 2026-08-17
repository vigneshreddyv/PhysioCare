from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.appointments import router as appointments_router
from app.api.users import router as users_router
from app.api.analytics import router as analytics_router
from app.api.payments import router as payments_router
from app.database import init_db

app = FastAPI(
    title="PhysioCare API",
    version="1.0.0"
)

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# REQUEST LOGGER
# -----------------------------
@app.middleware("http")
async def log_request(request: Request, call_next):
    print("\n" + "=" * 60)
    print(f"[REQUEST] {request.method} {request.url.path}")

    auth = request.headers.get("authorization")

    if auth:
        print("[REQUEST] Authorization Header FOUND")
        print(f"[REQUEST] {auth}")
    else:
        print("[REQUEST] Authorization Header MISSING")

    print("\n[REQUEST] All Headers:")
    for key, value in request.headers.items():
        print(f"{key}: {value}")

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

# -----------------------------
# ROUTES
# -----------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(payments_router, prefix="/api")

# -----------------------------
# ROOT
# -----------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome to PhysioCare API"
    }