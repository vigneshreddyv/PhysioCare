from fastapi import APIRouter, Depends, Query
from app.middleware.auth import RoleChecker
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/stats")
async def get_stats(
    days: int = Query(default=30, ge=7, le=365),
    current_user = Depends(RoleChecker(["admin"]))
):
    return await AnalyticsService.get_clinic_stats(days=days)
