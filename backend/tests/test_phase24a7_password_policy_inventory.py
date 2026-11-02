import pytest
from pydantic import ValidationError

from app.schemas.auth import StaffCreate, UserRegister


def test_current_public_registration_boundary_is_six_characters():
    with pytest.raises(ValidationError):
        UserRegister(
            email="fictional@example.com",
            password="12345",
            full_name="Fictional Patient",
        )
    registration = UserRegister(
        email="fictional@example.com",
        password="123456",
        full_name="Fictional Patient",
    )
    assert len(registration.password) == 6


def test_current_staff_registration_boundary_is_eight_characters():
    with pytest.raises(ValidationError):
        StaffCreate(
            email="fictional-staff@example.com",
            password="1234567",
            full_name="Fictional Clinician",
            role="doctor",
        )
    staff = StaffCreate(
        email="fictional-staff@example.com",
        password="12345678",
        full_name="Fictional Clinician",
        role="doctor",
    )
    assert len(staff.password) == 8
