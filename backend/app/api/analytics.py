from fastapi import APIRouter, Depends
from app.middleware.auth import RoleChecker
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/stats")
async def get_stats(
    current_user = Depends(RoleChecker(["admin"]))
):
    return await AnalyticsService.get_clinic_stats()
