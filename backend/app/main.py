from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.appointments import router as appointments_router
from app.api.users import router as users_router
from app.api.analytics import router as analytics_router
from app.database import init_db

app = FastAPI(title="PhysioCare API", version="1.0.0")

# CORS middleware to support local frontend development
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

@app.on_event("startup")
async def startup_event():
    await init_db()

# Include routers under the standard prefix
app.include_router(auth_router, prefix="/api")
app.include_router(appointments_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to PhysioCare API"}
