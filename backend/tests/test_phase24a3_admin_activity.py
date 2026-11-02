"""Offline admin-only daily aggregate; no patient details or full appointment list."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.core.config import settings
from app.main import app
from app.middleware.auth import get_current_user
from app.models.appointment import Appointment
from app.services.analytics_service import AnalyticsService


@pytest.mark.asyncio
async def test_daily_activity_counts_large_grouped_result_without_patient_rows(monkeypatch):
    today = datetime.now(ZoneInfo(settings.CLINIC_TIMEZONE)).date()
    yesterday = today - timedelta(days=1)
    rows = [
        {"_id": {"day": today.isoformat(), "slot": "09:00 AM"}, "count": 1201},
        {"_id": {"day": today.isoformat(), "slot": "01:00 PM"}, "count": 300},
        {"_id": {"day": yesterday.isoformat(), "slot": "10:00 AM"}, "count": 99},
    ]
    cursor = SimpleNamespace(to_list=AsyncMock(return_value=rows))
    collection = SimpleNamespace(aggregate=Mock(return_value=cursor))
    monkeypatch.setattr(Appointment, "get_pymongo_collection", Mock(return_value=collection))
    result = await AnalyticsService.get_admin_daily_activity()
    assert result == {
        "today_appointments": 1501,
        "yesterday_appointments": 99,
        "schedule_counts": {"morning": 1201, "afternoon": 300, "evening": 0},
    }
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0]["$match"]["appointment_date"]["$gte"].date() == yesterday
    assert pipeline[1]["$group"]["count"] == {"$sum": 1}
    assert "patient_id" not in str(pipeline)


@pytest.mark.asyncio
async def test_daily_activity_route_rejects_non_admin(monkeypatch):
    getter = AsyncMock(return_value={"today_appointments": 0, "yesterday_appointments": 0,
                                     "schedule_counts": {"morning": 0, "afternoon": 0, "evening": 0}})
    monkeypatch.setattr(AnalyticsService, "get_admin_daily_activity", getter)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver") as client:
            for role, expected in (("admin", 200), ("patient", 403), ("doctor", 403),
                                   ("receptionist", 403)):
                app.dependency_overrides[get_current_user] = (
                    lambda role=role: SimpleNamespace(id="fictional-user", role=role, is_active=True)
                )
                response = await client.get("/api/analytics/admin-daily-activity")
                assert response.status_code == expected
                if role == "admin":
                    assert response.headers["cache-control"] == "private, no-store"
        getter.assert_awaited_once()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
