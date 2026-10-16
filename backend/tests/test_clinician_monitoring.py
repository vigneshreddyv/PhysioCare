import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
from beanie import PydanticObjectId

from app.services.user_service import UserService
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.middleware.auth import verify_caseload
from app.api.users import list_patients_monitoring


@pytest.fixture
def mock_users_and_profiles():
    # Setup doctors
    doctor_a = MagicMock(spec=Doctor)
    doctor_a.id = PydanticObjectId("99999999999999999999999a")
    doctor_a.user_id = PydanticObjectId("00000000000000000000000a")

    doctor_b = MagicMock(spec=Doctor)
    doctor_b.id = PydanticObjectId("99999999999999999999999b")
    doctor_b.user_id = PydanticObjectId("00000000000000000000000b")

    # Setup patients
    patient_a = MagicMock(spec=Patient)
    patient_a.id = PydanticObjectId("11111111111111111111111a")
    patient_a.user_id = PydanticObjectId("10000000000000000000000a")
    patient_a.primary_doctor_id = doctor_a.id

    patient_b = MagicMock(spec=Patient)
    patient_b.id = PydanticObjectId("11111111111111111111111b")
    patient_b.user_id = PydanticObjectId("10000000000000000000000b")
    patient_b.primary_doctor_id = doctor_b.id

    # Users
    user_doc_a = MagicMock(spec=User)
    user_doc_a.id = doctor_a.user_id
    user_doc_a.role = "doctor"

    user_doc_b = MagicMock(spec=User)
    user_doc_b.id = doctor_b.user_id
    user_doc_b.role = "doctor"

    user_pat_a = MagicMock(spec=User)
    user_pat_a.id = patient_a.user_id
    user_pat_a.role = "patient"

    return {
        "doctor_a": doctor_a,
        "doctor_b": doctor_b,
        "patient_a": patient_a,
        "patient_b": patient_b,
        "user_doc_a": user_doc_a,
        "user_doc_b": user_doc_b,
        "user_pat_a": user_pat_a,
    }


@pytest.mark.asyncio
async def test_verify_caseload_success(mock_users_and_profiles):
    mocks = mock_users_and_profiles

    # Mock DB fetches
    async def mock_get_patient(pid):
        if str(pid) == str(mocks["patient_a"].id):
            return mocks["patient_a"]
        return None

    with patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", return_value=mocks["doctor_a"]), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id", side_effect=mock_get_patient):
        
        # Doctor A access Patient A should pass
        await verify_caseload(str(mocks["patient_a"].id), mocks["user_doc_a"])


@pytest.mark.asyncio
async def test_verify_caseload_unauthorized_mismatch(mock_users_and_profiles):
    mocks = mock_users_and_profiles

    async def mock_get_patient(pid):
        if str(pid) == str(mocks["patient_b"].id):
            return mocks["patient_b"]
        return None

    with patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", return_value=mocks["doctor_a"]), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id", side_effect=mock_get_patient):
        
        # Doctor A access Patient B (assigned to Doctor B) should raise 404 Not Found (non-leaking)
        with pytest.raises(HTTPException) as exc:
            await verify_caseload(str(mocks["patient_b"].id), mocks["user_doc_a"])
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_verify_caseload_patient_denied(mock_users_and_profiles):
    mocks = mock_users_and_profiles

    # Patient accessing clinician monitoring should raise 403 Forbidden
    with pytest.raises(HTTPException) as exc:
        await verify_caseload(str(mocks["patient_a"].id), mocks["user_pat_a"])
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_monitoring_endpoint_restricted_to_authenticated(mock_users_and_profiles):
    mocks = mock_users_and_profiles

    with patch("app.services.user_service.UserService.list_patients_monitoring", new_callable=AsyncMock) as mock_service:
        mock_service.return_value = []
        res = await list_patients_monitoring(current_user=mocks["user_doc_a"])
        assert res == []
        mock_service.assert_called_once_with(mocks["user_doc_a"])


from app.api.users import get_patient_snapshot as api_get_patient_snapshot

@pytest.mark.asyncio
async def test_get_patient_snapshot_authorized_success(mock_users_and_profiles):
    mocks = mock_users_and_profiles
    patient_id_str = str(mocks["patient_a"].id)

    async def mock_get_patient(pid):
        if str(pid) == patient_id_str:
            return mocks["patient_a"]
        return None

    # Mock service layer and verify caseload check passes
    mock_snapshot_data = {
        "id": patient_id_str,
        "full_name": "Patient A",
        "email": "a@patient.com",
        "subscription_status": "active",
        "adherence_percentage": 90,
        "status": "Active"
    }

    with patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", return_value=mocks["doctor_a"]), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id", side_effect=mock_get_patient), \
         patch("app.services.user_service.UserService.get_patient_snapshot", new_callable=AsyncMock, return_value=mock_snapshot_data):
        
        response = await api_get_patient_snapshot(patient_id_str, current_user=mocks["user_doc_a"])
        assert response.full_name == "Patient A"
        assert response.adherence_percentage == 90


@pytest.mark.asyncio
async def test_get_patient_snapshot_unauthorized_mismatch(mock_users_and_profiles):
    mocks = mock_users_and_profiles
    patient_b_id_str = str(mocks["patient_b"].id)

    async def mock_get_patient(pid):
        if str(pid) == patient_b_id_str:
            return mocks["patient_b"]
        return None

    with patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", return_value=mocks["doctor_a"]), \
         patch("app.repositories.profile_repository.ProfileRepository.get_patient_by_id", side_effect=mock_get_patient):
        
        # Doctor A tries to retrieve Doctor B's patient snapshot -> raises 404
        with pytest.raises(HTTPException) as exc:
            await api_get_patient_snapshot(patient_b_id_str, current_user=mocks["user_doc_a"])
        assert exc.value.status_code == 404

