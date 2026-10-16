import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import HTTPException
from beanie import PydanticObjectId

from app.services.user_service import UserService
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.api.users import list_patients

@pytest.fixture(autouse=True)
def mock_repository_helpers():
    # Setup doctor mock
    mock_doctor = MagicMock(spec=Doctor)
    mock_doctor.id = PydanticObjectId("999999999999999999999999")
    mock_doctor.user_id = PydanticObjectId("000000000000000000000000")

    # Setup patients mocks
    mock_patient1 = MagicMock(spec=Patient)
    mock_patient1.id = PydanticObjectId("111111111111111111111111")
    mock_patient1.user_id = PydanticObjectId("100000000000000000000000")
    mock_patient1.phone = "1234567890"
    mock_patient1.date_of_birth = "1990-01-01"
    mock_patient1.subscription_status = "active"

    mock_patient2 = MagicMock(spec=Patient)
    mock_patient2.id = PydanticObjectId("222222222222222222222222")
    mock_patient2.user_id = PydanticObjectId("200000000000000000000000")
    mock_patient2.phone = "0987654321"
    mock_patient2.date_of_birth = "1995-05-05"
    mock_patient2.subscription_status = "active"

    # Setup patient users mocks
    mock_user1 = MagicMock(spec=User)
    mock_user1.full_name = "Patient One"
    mock_user1.email = "one@patient.com"

    mock_user2 = MagicMock(spec=User)
    mock_user2.full_name = "Patient Two"
    mock_user2.email = "two@patient.com"

    # Helper function to mock user queries by ID
    def mock_get_user_by_id(uid):
        if str(uid) == str(mock_patient1.user_id):
            return mock_user1
        if str(uid) == str(mock_patient2.user_id):
            return mock_user2
        return None

    with patch("app.repositories.profile_repository.ProfileRepository.get_doctor_by_user_id", return_value=mock_doctor), \
         patch("app.repositories.profile_repository.ProfileRepository.list_patients_by_doctor_id") as mock_list_by_doc, \
         patch("app.repositories.user_repository.UserRepository.get_by_id", side_effect=mock_get_user_by_id):
        
        yield {
            "doctor": mock_doctor,
            "patient1": mock_patient1,
            "patient2": mock_patient2,
            "mock_list_by_doc": mock_list_by_doc
        }

@pytest.mark.asyncio
async def test_doctor_retrieves_assigned_patients(mock_repository_helpers):
    mocks = mock_repository_helpers
    mocks["mock_list_by_doc"].return_value = [mocks["patient1"], mocks["patient2"]]

    result = await UserService.list_patients_by_doctor(str(mocks["doctor"].user_id))
    assert len(result) == 2
    assert result[0].full_name == "Patient One"
    assert result[0].email == "one@patient.com"
    assert result[1].full_name == "Patient Two"
    assert result[1].email == "two@patient.com"
    mocks["mock_list_by_doc"].assert_called_once_with(str(mocks["doctor"].id))

@pytest.mark.asyncio
async def test_doctor_with_zero_assigned_patients(mock_repository_helpers):
    mocks = mock_repository_helpers
    mocks["mock_list_by_doc"].return_value = []

    result = await UserService.list_patients_by_doctor(str(mocks["doctor"].user_id))
    assert len(result) == 0

@pytest.mark.asyncio
async def test_route_uses_authenticated_doctor_id_exclusively():
    # Setup mock doctor user representing the JWT context
    mock_doctor_user = MagicMock(spec=User)
    mock_doctor_user.id = PydanticObjectId("000000000000000000000000")
    mock_doctor_user.role = "doctor"

    with patch("app.services.user_service.UserService.list_patients_by_doctor", new_callable=AsyncMock) as mock_service_call:
        # Call route directly with dependency injection mock
        await list_patients(current_user=mock_doctor_user)
        # Ensure service layer is invoked with the authenticated doctor user's ID
        mock_service_call.assert_called_once_with(str(mock_doctor_user.id))

@pytest.mark.asyncio
async def test_route_for_admin_is_unfiltered():
    # Setup mock admin user representing the JWT context
    mock_admin_user = MagicMock(spec=User)
    mock_admin_user.id = PydanticObjectId("777777777777777777777777")
    mock_admin_user.role = "admin"

    with patch("app.services.user_service.UserService.list_patients", new_callable=AsyncMock) as mock_service_call:
        # Call route directly with dependency injection mock
        await list_patients(current_user=mock_admin_user)
        # Ensure unfiltered service layer is invoked
        mock_service_call.assert_called_once()
