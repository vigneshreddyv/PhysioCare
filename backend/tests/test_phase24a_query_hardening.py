"""Offline contract for doctor-scoped released-report paging."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from beanie import PydanticObjectId
import pytest

from app.core.pagination import PageWindow
from app.models.lab_request import LabRequest
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.lab_request_service import LabRequestService


DOCTOR_ID = PydanticObjectId("507f1f77bcf86cd799439013")


@pytest.mark.asyncio
async def test_doctor_report_page_filters_assignment_before_skip_and_limit(monkeypatch):
    class Cursor:
        async def to_list(self, length):
            assert length == 17
            return [{"_id": "fictional-report"}]

    collection = Mock()
    collection.aggregate.return_value = Cursor()
    monkeypatch.setattr(LabRequest, "get_pymongo_collection", Mock(return_value=collection))
    validate = Mock(side_effect=lambda row: row)
    monkeypatch.setattr(LabRequest, "model_validate", validate)

    records = await LabRequestRepository.list_page_released_for_doctor(
        str(DOCTOR_ID), PageWindow(3, 17),
    )
    assert records == [{"_id": "fictional-report"}]
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"report_status": "released"}}
    assert pipeline[1] == {"$sort": {"report_released_at": -1, "_id": -1}}
    lookup = pipeline[2]["$lookup"]
    assert lookup["from"] == "appointments"
    assert lookup["let"] == {"report_patient_id": "$patient_id"}
    assignment_match = lookup["pipeline"][0]["$match"]
    assert assignment_match == {
        "doctor_id": DOCTOR_ID,
        "doctor_assignment_pending": {"$ne": True},
        "$expr": {"$eq": ["$patient_id", "$$report_patient_id"]},
    }
    assert lookup["pipeline"][1] == {"$limit": 1}
    assert pipeline[3] == {"$match": {"assigned_appointments.0": {"$exists": True}}}
    assert pipeline[4:6] == [{"$skip": 34}, {"$limit": 17}]
    assert pipeline[6] == {"$project": {"assigned_appointments": 0}}
    validate.assert_called_once()


@pytest.mark.asyncio
async def test_doctor_report_service_does_not_materialize_patient_id_list(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(
        return_value=SimpleNamespace(id=DOCTOR_ID),
    ))
    page_query = AsyncMock(return_value=[])
    old_distinct = AsyncMock()
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_doctor", page_query)
    monkeypatch.setattr(AppointmentRepository, "distinct_assigned_patient_ids", old_distinct)

    assert await LabRequestService.list_doctor_released_reports(
        "fictional-doctor-user", PageWindow(2, 50),
    ) == []
    page_query.assert_awaited_once_with(str(DOCTOR_ID), PageWindow(2, 50))
    old_distinct.assert_not_awaited()


@pytest.mark.asyncio
async def test_doctor_without_profile_does_not_query_released_reports(monkeypatch):
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=None))
    page_query = AsyncMock()
    monkeypatch.setattr(LabRequestRepository, "list_page_released_for_doctor", page_query)
    assert await LabRequestService.list_doctor_released_reports("fictional", PageWindow(1, 50)) == []
    page_query.assert_not_awaited()
