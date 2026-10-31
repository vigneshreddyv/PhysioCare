import asyncio
import os
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException, Response
from fastapi.routing import APIRoute
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request
from unittest.mock import AsyncMock

from app.api.analytics import router as analytics_router
from app.api.auth import set_session_cookies
from app.api.appointments import router as appointments_router
from app.api.home_visits import create_home_visit_request, router as home_visits_router
from app.api.clinician_schedules import router as clinician_schedules_router
from app.api.lab_requests import router as lab_requests_router, upload_finalized_report as upload_finalized_report_api
from app.api.reports import router as reports_router
from app.api.users import (
    create_staff as create_staff_api,
    list_patients as list_patients_api,
    list_reception_patients as list_reception_patients_api,
    list_staff as list_staff_api,
    router as users_router,
)
from app.core.appointment_time import (
    active_slot_claim,
    booking_window,
    clinic_start_to_utc_naive,
    demo_schedule_slots,
    resolve_appointment_start_utc,
    validate_booking_date,
    validate_demo_slot,
)
from app.core.config import Settings, settings
from app.core.security import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    create_refresh_token,
    decode_token,
)
from app.main import app
from app.middleware.auth import RoleChecker, get_current_user
from app.models.appointment import Appointment
from app.models.home_visit_request import HomeVisitRequest
from app.models.lab_request import LabRequest
from app.models.clinician_schedule import ClinicianSchedule, ScheduleBlock, ScheduleDateException
from app.repositories.demo_service_repository import DemoServiceRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.lab_request_repository import LabRequestRepository
from app.repositories.clinician_schedule_repository import ClinicianScheduleRepository
from app.repositories.profile_repository import ProfileRepository
from app.schemas.appointment import (
    AdminAppointmentCreate,
    AppointmentCreate,
    DoctorAppointmentOut,
    AppointmentUpdate,
    ReceptionAppointmentCreate,
    ReceptionAppointmentOut,
)
from app.schemas.auth import StaffCreate, StaffOut, UserRegister
from app.schemas.patient import (
    DoctorPatientOut,
    PatientProfileUpdate,
    ReceptionPatientOut,
    ReceptionPatientUpdate,
)
from app.schemas.doctor import DoctorProfileUpdate, PublicDoctorOut
from app.schemas.home_visit import (
    DoctorHomeVisitRequestOut,
    HomeVisitBookingCreate,
    HomeVisitDoctorAssignment,
    HomeVisitRequestCreate,
    HomeVisitRequestOut,
    ReceptionHomeVisitRequestOut,
)
from app.schemas.lab_request import LabRequestCreate
from app.schemas.lab_request import LabReportOut
from app.schemas.clinician_schedule import ScheduleBlockIn, ScheduleDateExceptionIn, ScheduleDraftUpdate
from app.services.appointment_service import AppointmentService
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.home_visit_service import HomeVisitService
from app.services.lab_request_service import LabRequestService
from app.services.doctor_history_service import DoctorHistoryService
from app.services.clinician_schedule_service import ClinicianScheduleService
from app.repositories.user_repository import UserRepository


def route_for(router, path, method):
    return next(
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method.upper() in route.methods
    )


def allowed_roles(route):
    checker = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if isinstance(dependency.call, RoleChecker)
    )
    return set(checker.allowed_roles)


def _future_booking_date(days: int = 1):
    earliest, _ = booking_window()
    return earliest + timedelta(days=days)


def _allow_effective_slot(monkeypatch, published=False):
    async def validate(_doctor_id, appointment_date, time_slot, _service_mode):
        return clinic_start_to_utc_naive(appointment_date, time_slot), published
    monkeypatch.setattr(ClinicianScheduleService, "validate_effective_slot", AsyncMock(side_effect=validate))


def test_openapi_exposes_current_api_contract_without_starting_database():
    schema = app.openapi()
    assert {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/csrf",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/users/doctors",
        "/api/users/doctors/{doctor_id}",
        "/api/users/reception/doctors",
        "/api/users/patients",
        "/api/users/doctor/patients/{patient_id}/history",
        "/api/users/reception/patients",
        "/api/users/staff",
        "/api/users/public/doctors",
        "/api/users/me/patient-profile",
        "/api/appointments",
        "/api/appointments/admin",
        "/api/appointments/reception",
        "/api/appointments/reception/{appointment_id}/cancel",
        "/api/appointments/availability",
        "/api/appointments/{appointment_id}",
        "/api/analytics/stats",
        "/api/demo-services/me/entitlement",
        "/api/demo-services/entitlements",
        "/api/demo-services/patients/{patient_id}/entitlement",
        "/api/home-visit-requests",
        "/api/home-visit-requests/me",
        "/api/home-visit-requests/{request_id}/withdraw",
        "/api/home-visit-requests/admin",
        "/api/home-visit-requests/admin/{request_id}",
        "/api/home-visit-requests/reception",
        "/api/home-visit-requests/doctor",
        "/api/home-visit-requests/me/context",
        "/api/home-visit-bookings/availability",
        "/api/home-visit-bookings",
        "/api/lab-requests",
        "/api/lab-requests/me",
        "/api/lab-requests/{request_id}/withdraw",
        "/api/lab-requests/admin",
        "/api/lab-requests/admin/{request_id}",
    }.issubset(schema["paths"])
    assert {"get", "post"}.issubset(schema["paths"]["/api/users/staff"])


def test_public_registration_contract_has_no_role_selector():
    assert set(UserRegister.model_fields) == {"email", "password", "full_name"}

    with pytest.raises(ValidationError):
        StaffCreate(
            email="patient@example.com",
            password="test-password",
            full_name="Patient Example",
            role="patient",
        )
    receptionist = StaffCreate(
        email="reception@example.com",
        password="test-password",
        full_name="Fictional Receptionist",
        role="receptionist",
    )
    assert receptionist.role == "receptionist"
    laboratorian = StaffCreate(
        email="laboratory@example.com",
        password="test-password",
        full_name="Fictional Laboratorian",
        role="laboratorian",
    )
    assert laboratorian.role == "laboratorian"


def test_staff_create_schema_validates_required_fields_and_supported_roles():
    staff = StaffCreate(
        email="lab@example.com",
        password="a-safe-demo-password",
        full_name=" Fictional Laboratorian ",
        role="laboratorian",
    )
    assert staff.full_name == "Fictional Laboratorian"

    for fields in (
        {"email": "not-an-email", "password": "a-safe-demo-password", "full_name": "Staff", "role": "doctor"},
        {"email": "staff@example.com", "password": "short", "full_name": "Staff", "role": "doctor"},
        {"email": "staff@example.com", "password": "a-safe-demo-password", "full_name": " ", "role": "doctor"},
        {"email": "staff@example.com", "password": "a-safe-demo-password", "full_name": "Staff", "role": "patient"},
    ):
        with pytest.raises(ValidationError):
            StaffCreate(**fields)


def test_staff_creation_is_admin_only_and_list_route_is_admin_only():
    assert allowed_roles(route_for(users_router, "/users/staff", "POST")) == {"admin"}
    assert allowed_roles(route_for(users_router, "/users/staff", "GET")) == {"admin"}

    with pytest.raises(HTTPException) as error:
        RoleChecker(["admin"])(type("UserDouble", (), {"role": "doctor"})())
    assert error.value.status_code == 403


def test_staff_creation_hashes_password_and_returns_no_sensitive_fields(monkeypatch):
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.services.auth_service.get_password_hash",
        lambda value: f"hashed:{value}",
    )
    created_values = {}

    def create_user(**values):
        created_values.update(values)
        return type("UserDouble", (), values)()

    monkeypatch.setattr("app.services.auth_service.User", create_user)
    monkeypatch.setattr(UserRepository, "create", AsyncMock(side_effect=lambda user: user))
    schema = StaffCreate(
        email="lab@example.com",
        password="a-safe-demo-password",
        full_name="Fictional Laboratorian",
        role="laboratorian",
    )

    asyncio.run(AuthService.register_staff(schema))
    user = type("UserDouble", (), {
        "email": schema.email,
        "role": schema.role,
    })()
    monkeypatch.setattr(AuthService, "register_staff", AsyncMock(return_value=user))
    response = asyncio.run(create_staff_api(schema, type("AdminDouble", (), {"role": "admin"})()))

    assert created_values["hashed_password"] == "hashed:a-safe-demo-password"
    assert created_values["hashed_password"] != schema.password
    assert response == {
        "message": "Staff account created",
        "email": "lab@example.com",
        "role": "laboratorian",
    }
    assert "password" not in response
    assert "hashed_password" not in response


def test_duplicate_staff_email_is_rejected(monkeypatch):
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=object()))
    create = AsyncMock()
    monkeypatch.setattr(UserRepository, "create", create)
    schema = StaffCreate(
        email="existing@example.com",
        password="a-safe-demo-password",
        full_name="Fictional Staff",
        role="laboratorian",
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(AuthService.register_staff(schema))
    assert error.value.status_code == 400
    create.assert_not_awaited()


def test_concurrent_duplicate_staff_email_is_rejected(monkeypatch):
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.services.auth_service.get_password_hash",
        lambda value: f"hashed:{value}",
    )
    monkeypatch.setattr(
        UserRepository,
        "create",
        AsyncMock(side_effect=DuplicateKeyError("duplicate key")),
    )
    monkeypatch.setattr(
        "app.services.auth_service.User",
        lambda **values: type("UserDouble", (), values)(),
    )
    schema = StaffCreate(
        email="concurrent@example.com",
        password="a-safe-demo-password",
        full_name="Fictional Staff",
        role="laboratorian",
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(AuthService.register_staff(schema))
    assert error.value.status_code == 400
    assert error.value.detail == "Email already registered"


def test_staff_directory_returns_only_safe_fields_and_includes_account_status(monkeypatch):
    created = datetime(2026, 10, 30)
    user = type("UserDouble", (), {
        "id": PydanticObjectId("507f1f77bcf86cd799439011"),
        "full_name": "Fictional Laboratorian",
        "email": "lab@example.com",
        "role": "laboratorian",
        "is_active": False,
        "created_at": created,
        "hashed_password": "must-not-be-returned",
        "password": "must-not-be-returned",
    })()
    monkeypatch.setattr(UserRepository, "list_staff", AsyncMock(return_value=[user]))

    staff = asyncio.run(UserService.list_staff())
    serialized = staff[0].model_dump()
    response_model_fields = set(StaffOut.model_fields)

    assert serialized == {
        "id": "507f1f77bcf86cd799439011",
        "full_name": "Fictional Laboratorian",
        "email": "lab@example.com",
        "role": "laboratorian",
        "is_active": False,
        "created_at": created,
    }
    assert response_model_fields == set(serialized)
    assert "hashed_password" not in serialized
    assert "password" not in serialized


def test_laboratorian_uses_shared_authentication_flow(monkeypatch):
    user = type("UserDouble", (), {
        "id": PydanticObjectId("507f1f77bcf86cd799439011"),
        "email": "lab@example.com",
        "role": "laboratorian",
        "hashed_password": "stored-password-hash",
    })()
    session = object()
    monkeypatch.setattr(UserRepository, "get_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr("app.services.auth_service.verify_password", lambda _password, _hashed: True)
    monkeypatch.setattr("app.services.auth_service.AuthSession", lambda **_values: session)
    monkeypatch.setattr("app.services.auth_service.SessionRepository.create", AsyncMock(return_value=session))
    monkeypatch.setattr(AuthService, "_rotate_session", AsyncMock(return_value="laboratorian-session"))

    result = asyncio.run(AuthService.login("lab@example.com", "not-logged"))

    assert result == "laboratorian-session"
    AuthService._rotate_session.assert_awaited_once_with(session, user)


def test_role_guards_match_authorized_workflows():
    assert allowed_roles(route_for(users_router, "/users/staff", "POST")) == {"admin"}
    assert allowed_roles(route_for(users_router, "/users/me/patient-profile", "PATCH")) == {"patient"}
    assert allowed_roles(route_for(users_router, "/users/patients", "GET")) == {"admin", "doctor"}
    assert allowed_roles(route_for(users_router, "/users/reception/patients", "GET")) == {"receptionist"}
    assert allowed_roles(route_for(users_router, "/users/reception/patients/{patient_id}", "PATCH")) == {"receptionist"}
    assert allowed_roles(route_for(users_router, "/users/doctors", "GET")) == {"admin"}
    assert allowed_roles(route_for(users_router, "/users/doctors/{doctor_id}", "PATCH")) == {"admin"}
    assert allowed_roles(route_for(users_router, "/users/reception/doctors", "GET")) == {"receptionist"}
    assert allowed_roles(route_for(appointments_router, "/appointments", "POST")) == {"patient"}
    assert allowed_roles(route_for(appointments_router, "/appointments/admin", "POST")) == {"admin"}
    assert allowed_roles(route_for(appointments_router, "/appointments/reception", "POST")) == {"receptionist"}
    assert allowed_roles(route_for(appointments_router, "/appointments/reception", "GET")) == {"receptionist"}
    assert allowed_roles(route_for(appointments_router, "/appointments", "GET")) == {"admin", "doctor", "patient"}
    assert get_current_user in {
        dependency.call
        for dependency in route_for(appointments_router, "/appointments/availability", "GET").dependant.dependencies
    }
    assert allowed_roles(route_for(appointments_router, "/appointments/{appointment_id}/cancel", "POST")) == {"patient"}
    assert allowed_roles(route_for(appointments_router, "/appointments/reception/{appointment_id}/cancel", "POST")) == {"receptionist"}
    assert allowed_roles(route_for(appointments_router, "/appointments/{appointment_id}", "PATCH")) == {"admin", "doctor"}
    assert allowed_roles(route_for(analytics_router, "/analytics/stats", "GET")) == {"admin"}
    assert allowed_roles(route_for(home_visits_router, "/demo-services/me/entitlement", "GET")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/demo-services/entitlements", "GET")) == {"admin"}
    assert allowed_roles(route_for(home_visits_router, "/demo-services/patients/{patient_id}/entitlement", "PUT")) == {"admin"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests", "POST")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/me", "GET")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/{request_id}/withdraw", "POST")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/admin", "GET")) == {"admin"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/admin/{request_id}", "PATCH")) == {"admin"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/reception", "GET")) == {"receptionist"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/doctor", "GET")) == {"doctor"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-requests/me/context", "GET")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-bookings/availability", "GET")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-bookings", "POST")) == {"patient"}
    assert allowed_roles(route_for(home_visits_router, "/home-visit-bookings/admin/{appointment_id}/doctor", "PATCH")) == {"admin"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests", "POST")) == {"patient"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/me", "GET")) == {"patient"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/admin", "GET")) == {"admin"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/admin/{request_id}", "PATCH")) == {"admin"}
    assert allowed_roles(route_for(reports_router, "/reports", "POST")) == {"admin", "doctor"}
    assert allowed_roles(route_for(reports_router, "/reports", "GET")) == {"patient"}
    assert allowed_roles(route_for(reports_router, "/reports/{report_id}/download", "GET")) == {"patient"}
    assert route_for(users_router, "/users/public/doctors", "GET").dependant.dependencies == []


def test_patient_profile_update_contract_excludes_privileged_fields():
    assert set(PatientProfileUpdate.model_fields) == {"full_name", "phone", "gender"}
    profile = PatientProfileUpdate.model_validate({
        "full_name": "  Fictional   Patient  ",
        "phone": "+91 98765 43210",
        "gender": "  Non-binary  ",
    })
    assert profile.full_name == "Fictional Patient"
    assert profile.phone == "+91 98765 43210"
    assert profile.gender == "Non-binary"
    with pytest.raises(ValidationError):
        PatientProfileUpdate.model_validate({
            "full_name": "Fictional Patient",
            "role": "admin",
        })


def test_patient_can_update_only_own_name_phone_and_recorded_gender(monkeypatch):
    user = type("UserDouble", (), {"full_name": "Old Name"})()
    patient = type("PatientDouble", (), {"phone": "0000000", "gender": None})()
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "save", AsyncMock(return_value=user))
    monkeypatch.setattr(ProfileRepository, "save_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserService, "get_patient_profile", AsyncMock(return_value="updated-profile"))

    result = asyncio.run(UserService.update_patient_profile(
        "own-user-id",
        PatientProfileUpdate(full_name="New Name", phone="+91 90000 00000", gender="Woman"),
    ))

    assert result == "updated-profile"
    assert user.full_name == "New Name"
    assert patient.phone == "+91 90000 00000"
    assert patient.gender == "Woman"
    UserRepository.save.assert_awaited_once_with(user)
    ProfileRepository.save_patient.assert_awaited_once_with(patient)


def test_authenticated_patient_profile_read_returns_only_profile_contract_fields(monkeypatch):
    patient = type("PatientDouble", (), {
        "id": "patient-id", "user_id": "user-id", "phone": "+91 90000 00000",
        "date_of_birth": "1990-01-01", "gender": "Woman", "subscription_status": "inactive",
    })()
    user = type("UserDouble", (), {"full_name": "Fictional Patient", "email": "patient@example.test"})()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))

    result = asyncio.run(UserService.get_patient_profile("user-id"))

    assert result.model_dump() == {
        "id": "patient-id", "full_name": "Fictional Patient", "email": "patient@example.test",
        "phone": "+91 90000 00000", "date_of_birth": "1990-01-01", "gender": "Woman",
        "subscription_status": "inactive",
    }
    ProfileRepository.get_patient_by_user_id.assert_awaited_once_with("user-id")
    UserRepository.get_by_id.assert_awaited_once_with("user-id")


def test_admin_booking_uses_selected_existing_patient_and_india_time(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {"id": "patient-profile-id"})()
    doctor = type("DoctorDouble", (), {"id": "doctor-profile-id"})()

    class AppointmentDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    async def create_appointment(appointment):
        appointment.id = "appointment-id"
        return appointment

    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(AppointmentRepository, "create", create_appointment)
    monkeypatch.setattr("app.services.appointment_service.Appointment", AppointmentDouble)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="formatted"))

    result = asyncio.run(AppointmentService.create_admin_appointment(
        AdminAppointmentCreate.model_validate({
            "patient_id": "patient-profile-id",
            "doctor_id": "doctor-profile-id",
            "appointment_date": _future_booking_date().isoformat(),
            "time_slot": "09:00 am",
            "reason": "Fictional local verification",
        })
    ))

    assert result == "formatted"
    created = AppointmentService._format_appointment.await_args.args[0]
    assert created.patient_id == "patient-profile-id"
    assert created.doctor_id == "doctor-profile-id"
    assert created.time_slot == "09:00 AM"
    assert created.starts_at == clinic_start_to_utc_naive(_future_booking_date(), "09:00 AM")


def test_reception_booking_collects_no_clinical_reason_and_returns_minimum_fields(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {
        "id": "patient-profile-id",
        "user_id": "patient-user-id",
        "phone": "+91 90000 00000",
    })()
    doctor = type("DoctorDouble", (), {
        "id": "doctor-profile-id",
        "user_id": "doctor-user-id",
    })()
    patient_user = type("UserDouble", (), {
        "full_name": "Fictional Patient",
        "email": "patient@example.com",
    })()
    doctor_user = type("UserDouble", (), {
        "full_name": "Fictional Doctor",
        "email": "doctor-private@example.com",
    })()

    class AppointmentDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    async def create_appointment(appointment):
        appointment.id = "appointment-id"
        appointment.status = "scheduled"
        appointment.cancelled_at = None
        appointment.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return appointment

    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(side_effect=lambda user_id: {
        "patient-user-id": patient_user,
        "doctor-user-id": doctor_user,
    }.get(user_id)))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(AppointmentRepository, "create", create_appointment)
    monkeypatch.setattr("app.services.appointment_service.Appointment", AppointmentDouble)

    schema = ReceptionAppointmentCreate.model_validate({
        "patient_id": "patient-profile-id",
        "doctor_id": "doctor-profile-id",
        "appointment_date": _future_booking_date().isoformat(),
        "time_slot": "09:00 am",
    })
    assert set(ReceptionAppointmentCreate.model_fields) == {"patient_id", "doctor_id", "appointment_date", "time_slot"}
    with pytest.raises(ValidationError):
        ReceptionAppointmentCreate.model_validate({
            **schema.model_dump(),
            "reason": "Must not be accepted",
        })

    result = asyncio.run(AppointmentService.create_reception_appointment(schema))

    assert isinstance(result, ReceptionAppointmentOut)
    assert set(result.model_dump()) == {
        "id", "patient_id", "patient_name", "patient_email", "patient_phone",
        "doctor_id", "doctor_name", "doctor_assignment_pending", "appointment_date", "starts_at",
        "clinic_timezone", "time_slot", "service_mode", "home_address", "city",
        "status", "can_reception_cancel",
        "cancellation_deadline", "cancellation_message",
    }
    assert "reason" not in result.model_dump()
    assert "billing_status" not in result.model_dump()
    assert "billing_amount" not in result.model_dump()


def test_reception_schedule_uses_operational_records_only(monkeypatch):
    appointment = type("AppointmentDouble", (), {})()
    monkeypatch.setattr(AppointmentRepository, "list_operational_schedule", AsyncMock(return_value=[appointment]))
    monkeypatch.setattr(AppointmentService, "_format_reception_appointment", AsyncMock(return_value="minimal-record"))

    result = asyncio.run(AppointmentService.list_reception_schedule())

    assert result == ["minimal-record"]
    AppointmentService._format_reception_appointment.assert_awaited_once_with(appointment)


def test_doctor_patient_directory_is_unique_and_assigned_only(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "assigned-doctor"})()
    appointments = [
        type("AppointmentDouble", (), {"patient_id": "patient-a"})(),
        type("AppointmentDouble", (), {"patient_id": "patient-a"})(),
        type("AppointmentDouble", (), {"patient_id": "patient-b"})(),
    ]
    patients = {
        "patient-a": type("PatientDouble", (), {
            "id": "patient-a",
            "user_id": "user-a",
            "phone": "+91 90000 00001",
            "date_of_birth": "1990-01-01",
            "subscription_status": "private-admin-value",
        })(),
        "patient-b": type("PatientDouble", (), {
            "id": "patient-b",
            "user_id": "user-b",
            "phone": None,
            "date_of_birth": None,
            "subscription_status": "private-admin-value",
        })(),
    }
    users = {
        "user-a": type("UserDouble", (), {"full_name": "Fictional Patient A", "email": "hidden-a@example.com"})(),
        "user-b": type("UserDouble", (), {"full_name": "Fictional Patient B", "email": "hidden-b@example.com"})(),
    }
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=appointments))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(side_effect=lambda patient_id: patients.get(patient_id)))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(side_effect=lambda user_id: users.get(user_id)))

    result = asyncio.run(UserService.list_assigned_patients("doctor-user"))

    assert [patient.id for patient in result] == ["patient-a", "patient-b"]
    assert all(isinstance(patient, DoctorPatientOut) for patient in result)
    assert set(result[0].model_dump()) == {"id", "full_name", "phone", "date_of_birth", "gender"}
    AppointmentRepository.list_by_doctor_id.assert_awaited_once_with("assigned-doctor")


def test_doctor_patient_directory_is_empty_without_assignments(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "doctor-without-assignments"})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=[]))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock())

    result = asyncio.run(UserService.list_assigned_patients("doctor-user"))

    assert result == []
    ProfileRepository.get_patient_by_id.assert_not_awaited()


def test_doctor_patient_history_contains_only_assigned_visits_and_published_reports(monkeypatch):
    patient_id = "507f1f77bcf86cd799439011"
    doctor = type("DoctorDouble", (), {"id": "507f1f77bcf86cd799439012"})()
    assigned = type("AppointmentDouble", (), {
        "id": "appointment-a",
        "patient_id": PydanticObjectId(patient_id),
        "doctor_assignment_pending": False,
    })()
    pending = type("AppointmentDouble", (), {
        "id": "appointment-pending",
        "patient_id": PydanticObjectId(patient_id),
        "doctor_assignment_pending": True,
    })()
    unrelated = type("AppointmentDouble", (), {
        "id": "appointment-b",
        "patient_id": PydanticObjectId("507f1f77bcf86cd799439099"),
        "doctor_assignment_pending": False,
    })()
    patient = type("PatientDouble", (), {
        "id": PydanticObjectId(patient_id),
        "user_id": PydanticObjectId("507f1f77bcf86cd799439013"),
        "phone": "+91 90000 00001",
        "date_of_birth": "1990-01-01",
    })()
    patient_user = type("UserDouble", (), {"full_name": "Fictional Assigned Patient"})()
    formatted_appointment = DoctorAppointmentOut(
        id="appointment-a",
        patient_id=patient_id,
        patient_name="Fictional Assigned Patient",
        doctor_id=str(doctor.id),
        doctor_name="Fictional Doctor",
        appointment_date=datetime(2026, 10, 20),
        clinic_timezone="Asia/Kolkata",
        time_slot="09:00 AM",
        reason="Fictional follow-up",
        status="completed",
        created_at=datetime(2026, 10, 1),
    )
    formatted_report = LabReportOut(
        request_id="507f1f77bcf86cd799439014",
        patient_name="Fictional Assigned Patient",
        selected_tests=["cbc"],
        report_status="released",
        report_file_name="fictional-report.pdf",
        report_released_at=datetime(2026, 10, 21),
    )

    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(
        AppointmentRepository,
        "list_by_doctor_id",
        AsyncMock(return_value=[assigned, pending, unrelated]),
    )
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=patient_user))
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value=formatted_appointment))
    monkeypatch.setattr(
        LabRequestRepository,
        "list_released_for_patients",
        AsyncMock(return_value=[object()]),
    )
    monkeypatch.setattr(LabRequestService, "_format_report", AsyncMock(return_value=formatted_report))

    result = asyncio.run(DoctorHistoryService.get_assigned_patient_history("doctor-user", patient_id))

    assert result.patient.id == patient_id
    assert [appointment.id for appointment in result.appointments] == ["appointment-a"]
    assert [report.request_id for report in result.reports] == ["507f1f77bcf86cd799439014"]
    AppointmentService._format_appointment.assert_awaited_once_with(assigned)
    LabRequestRepository.list_released_for_patients.assert_awaited_once_with([patient_id])


def test_doctor_patient_history_hides_missing_and_unassigned_records(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "507f1f77bcf86cd799439012"})()
    unrelated = type("AppointmentDouble", (), {
        "patient_id": PydanticObjectId("507f1f77bcf86cd799439099"),
        "doctor_assignment_pending": False,
    })()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=[unrelated]))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock())
    monkeypatch.setattr(LabRequestRepository, "list_released_for_patients", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(DoctorHistoryService.get_assigned_patient_history(
            "doctor-user",
            "507f1f77bcf86cd799439011",
        ))

    assert error.value.status_code == 404
    assert error.value.detail == "Assigned patient history not found"
    ProfileRepository.get_patient_by_id.assert_not_awaited()
    LabRequestRepository.list_released_for_patients.assert_not_awaited()


def test_doctor_patient_history_route_is_doctor_only():
    assert allowed_roles(route_for(
        users_router,
        "/users/doctor/patients/{patient_id}/history",
        "GET",
    )) == {"doctor"}


def test_patient_directory_keeps_admin_and_doctor_paths_separate(monkeypatch):
    monkeypatch.setattr(UserService, "list_patients", AsyncMock(return_value=["admin-full-record"]))
    monkeypatch.setattr(UserService, "list_assigned_patients", AsyncMock(return_value=["doctor-minimum-record"]))
    monkeypatch.setattr(UserService, "list_reception_patients", AsyncMock(return_value=["reception-contact-record"]))

    admin = type("UserDouble", (), {"id": "admin-user", "role": "admin"})()
    doctor = type("UserDouble", (), {"id": "doctor-user", "role": "doctor"})()

    assert asyncio.run(list_patients_api(current_user=admin)) == ["admin-full-record"]
    assert asyncio.run(list_patients_api(current_user=doctor)) == ["doctor-minimum-record"]
    assert asyncio.run(list_reception_patients_api(current_user=object())) == ["reception-contact-record"]
    UserService.list_patients.assert_awaited_once()
    UserService.list_assigned_patients.assert_awaited_once_with("doctor-user")
    UserService.list_reception_patients.assert_awaited_once()


def test_reception_patient_directory_contains_contact_fields_only(monkeypatch):
    patient = type("PatientDouble", (), {
        "id": "patient-profile",
        "user_id": "patient-user",
        "phone": "+91 90000 00000",
        "date_of_birth": "1990-01-01",
        "subscription_status": "private-value",
    })()
    user = type("UserDouble", (), {
        "full_name": "Fictional Patient",
        "email": "fictional.patient@example.com",
        "is_active": True,
    })()
    monkeypatch.setattr(ProfileRepository, "list_patients", AsyncMock(return_value=[patient]))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))

    result = asyncio.run(UserService.list_reception_patients())

    assert len(result) == 1
    assert isinstance(result[0], ReceptionPatientOut)
    assert set(result[0].model_dump()) == {"id", "full_name", "email", "phone"}
    assert "date_of_birth" not in result[0].model_dump()
    assert "subscription_status" not in result[0].model_dump()


def test_reception_contact_update_cannot_change_identity_or_private_fields(monkeypatch):
    assert set(ReceptionPatientUpdate.model_fields) == {"full_name", "phone"}
    with pytest.raises(ValidationError):
        ReceptionPatientUpdate.model_validate({
            "full_name": "Fictional Patient",
            "email": "replacement@example.com",
        })
    with pytest.raises(ValidationError):
        ReceptionPatientUpdate.model_validate({
            "phone": "+91 90000 00000",
            "subscription_status": "active",
        })
    with pytest.raises(ValidationError):
        ReceptionPatientUpdate.model_validate({
            "phone": "+91 90000 00000",
            "gender": "Woman",
        })

    patient = type("PatientDouble", (), {
        "id": "patient-profile",
        "user_id": "patient-user",
        "phone": "+91 90000 00000",
    })()
    user = type("UserDouble", (), {
        "full_name": "Old Name",
        "email": "fixed.identity@example.com",
    })()
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(UserRepository, "save", AsyncMock(return_value=user))
    monkeypatch.setattr(ProfileRepository, "save_patient", AsyncMock(return_value=patient))

    result = asyncio.run(UserService.update_reception_patient(
        "patient-profile",
        ReceptionPatientUpdate(full_name="Updated Name", phone="+91 91111 11111"),
    ))

    assert result.full_name == "Updated Name"
    assert result.phone == "+91 91111 11111"
    assert result.email == "fixed.identity@example.com"
    UserRepository.save.assert_awaited_once_with(user)
    ProfileRepository.save_patient.assert_awaited_once_with(patient)


def test_public_doctor_directory_omits_private_staff_fields(monkeypatch):
    doctors = [
        type("DoctorDouble", (), {
            "id": "doctor-public",
            "user_id": "doctor-user-public",
            "specialization": "Sports Physiotherapy",
            "profile_image": None,
            "bio": "Fictional public biography",
            "is_active_today": True,
        })(),
        type("DoctorDouble", (), {
            "id": "doctor-inactive",
            "user_id": "doctor-user-inactive",
            "specialization": "Neurological Physiotherapy",
            "profile_image": None,
            "bio": None,
            "is_active_today": False,
        })(),
    ]
    users = {
        "doctor-user-public": type("UserDouble", (), {
            "full_name": "Fictional Public Doctor",
            "email": "private@example.com",
            "is_active": True,
        })(),
        "doctor-user-inactive": type("UserDouble", (), {
            "full_name": "Inactive Doctor",
            "email": "inactive@example.com",
            "is_active": False,
        })(),
    }
    monkeypatch.setattr(ProfileRepository, "list_doctors", AsyncMock(return_value=doctors))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(side_effect=lambda user_id: users.get(user_id)))

    result = asyncio.run(UserService.list_public_doctors())

    assert len(result) == 1
    assert isinstance(result[0], PublicDoctorOut)
    assert set(result[0].model_dump()) == {
        "id", "full_name", "specialization", "profile_image", "bio",
        "qualifications", "years_experience", "specialties", "linkedin_url", "website_url",
            "accepts_home_visits",
    }
    assert result[0].full_name == "Fictional Public Doctor"


def test_doctor_profile_update_allows_only_verified_public_profile_fields():
    schema = DoctorProfileUpdate.model_validate({
        "full_name": "  Fictional   Clinician  ",
        "specialization": "Sports Physiotherapy",
        "qualifications": "Master of Physiotherapy",
        "years_experience": 8,
        "specialties": ["Sports rehabilitation", " Sports rehabilitation ", "Mobility"],
        "linkedin_url": "https://www.linkedin.com/in/fictional-clinician",
        "website_url": "https://example.com/profile",
    })
    assert schema.full_name == "Fictional Clinician"
    assert schema.specialties == ["Sports rehabilitation", "Mobility"]
    with pytest.raises(ValidationError):
        DoctorProfileUpdate.model_validate({"linkedin_url": "https://example.com/not-linkedin"})
    with pytest.raises(ValidationError):
        DoctorProfileUpdate.model_validate({"role": "admin"})


def test_admin_doctor_profile_update_preserves_account_identity(monkeypatch):
    doctor = type("DoctorDouble", (), {
        "id": "doctor-profile",
        "user_id": "doctor-user",
        "specialization": "General Physiotherapy",
        "profile_image": None,
        "bio": None,
        "qualifications": None,
        "years_experience": None,
        "specialties": [],
        "linkedin_url": None,
        "website_url": None,
        "is_active_today": True,
    })()
    user = type("UserDouble", (), {
        "full_name": "Fictional Doctor",
        "email": "fixed-doctor@example.com",
    })()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(UserRepository, "save", AsyncMock(return_value=user))
    monkeypatch.setattr(ProfileRepository, "save_doctor", AsyncMock(return_value=doctor))

    result = asyncio.run(UserService.update_doctor_profile(
        "doctor-profile",
        DoctorProfileUpdate(
            full_name="Updated Fictional Doctor",
            qualifications="Master of Physiotherapy",
            years_experience=7,
            specialties=["Mobility", "Sports rehabilitation"],
        ),
    ))

    assert result.full_name == "Updated Fictional Doctor"
    assert result.email == "fixed-doctor@example.com"
    assert result.qualifications == "Master of Physiotherapy"
    assert result.specialties == ["Mobility", "Sports rehabilitation"]
    UserRepository.save.assert_awaited_once_with(user)
    ProfileRepository.save_doctor.assert_awaited_once_with(doctor)


def test_home_visit_request_schema_protects_sensitive_fields_and_has_no_schedule_or_payment():
    assert set(HomeVisitRequestCreate.model_fields) == {
        "preferred_doctor_id", "home_address", "reason", "city", "body_regions",
        "symptoms", "duration_days", "pain_severity", "save_address",
    }
    schema = HomeVisitRequestCreate.model_validate({
        "preferred_doctor_id": "doctor-profile",
        "home_address": "  12   Fictional Road, Nellore  ",
        "reason": "  Mobility support after clinic review  ",
        "city": " Nellore ", "body_regions": ["Knee"], "symptoms": ["Pain"],
        "duration_days": 10, "pain_severity": "medium",
    })
    assert schema.home_address == "12 Fictional Road, Nellore"
    assert schema.reason == "Mobility support after clinic review"
    with pytest.raises(ValidationError):
        HomeVisitRequestCreate.model_validate({
            **schema.model_dump(),
            "appointment_time": "09:00 AM",
        })
    with pytest.raises(ValidationError):
        HomeVisitRequestCreate.model_validate({
            **schema.model_dump(),
            "price": 100,
        })


def test_lab_request_schema_is_demo_only_and_requires_home_details():
    clinic = LabRequestCreate(mode="clinic_visit", selected_tests=["albumin", "cbc"])
    assert clinic.home_address is None and clinic.city is None
    with pytest.raises(ValidationError):
        LabRequestCreate(mode="home_collection", selected_tests=["albumin"])
    with pytest.raises(ValidationError):
        LabRequestCreate(mode="clinic_visit", selected_tests=["invented-test"])
    with pytest.raises(ValidationError):
        LabRequestCreate.model_validate({"mode": "clinic_visit", "selected_tests": ["albumin"], "price": 100})


def test_lab_request_idempotency_key_is_forwarded_to_atomic_repository(monkeypatch):
    patient = type("PatientDouble", (), {"id": PydanticObjectId()})()

    class LabRequestDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    saved = LabRequestDouble(id=PydanticObjectId(), patient_id=patient.id)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(LabRequestRepository, "create_idempotent", AsyncMock(return_value=saved))
    monkeypatch.setattr(LabRequestService, "_format", AsyncMock(return_value="formatted-request"))
    monkeypatch.setattr("app.services.lab_request_service.LabRequest", LabRequestDouble)

    result = asyncio.run(LabRequestService.create(
        "patient-user",
        LabRequestCreate(mode="clinic_visit", selected_tests=["albumin", "cbc"]),
        "qa-repeat-1234",
    ))

    assert result == "formatted-request"
    stored = LabRequestRepository.create_idempotent.await_args.args[0]
    assert stored.patient_id == patient.id
    assert stored.submission_key == "qa-repeat-1234"


def test_lab_request_repository_returns_existing_record_after_duplicate_key(monkeypatch):
    patient_id = PydanticObjectId()
    submitted = type("LabRequestDouble", (), {
        "patient_id": patient_id,
        "submission_key": "qa-repeat-5678",
        "insert": AsyncMock(side_effect=DuplicateKeyError("duplicate laboratory submission")),
    })()
    existing = type("LabRequestDouble", (), {"id": PydanticObjectId()})()
    monkeypatch.setattr(LabRequest, "find_one", AsyncMock(return_value=existing))

    result = asyncio.run(LabRequestRepository.create_idempotent(submitted))

    assert result is existing
    LabRequest.find_one.assert_awaited_once()


def test_legacy_home_visit_request_creation_is_retired():
    endpoint_error = asyncio.run(_call_retired_home_visit_endpoint())
    assert endpoint_error.status_code == 410

    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.create_request(
            "patient-user",
            HomeVisitRequestCreate(
                preferred_doctor_id="doctor-profile",
                home_address="12 Fictional Road, Nellore",
                reason="Fictional mobility request",
                city="Nellore",
                body_regions=["Knee"],
                symptoms=["Pain"],
                duration_days=2,
                pain_severity="low",
            ),
        ))

    assert error.value.status_code == 410


async def _call_retired_home_visit_endpoint():
    try:
        await create_home_visit_request(current_user=type("UserDouble", (), {"id": "patient-user"})())
    except HTTPException as error:
        return error
    raise AssertionError("retired endpoint unexpectedly returned successfully")


def test_home_visit_booking_schema_requires_slot_and_idempotency_key():
    booking_date = _future_booking_date()
    booking = HomeVisitBookingCreate.model_validate({
        "preferred_doctor_id": "507f1f77bcf86cd799439012",
        "appointment_date": booking_date.isoformat(),
        "time_slot": "09:00 am",
        "submission_key": "fictional-repeat-1234",
        "home_address": "12 Fictional Road, Nellore",
        "reason": "Fictional mobility support",
        "city": "Nellore",
        "body_regions": ["Knee"],
        "symptoms": ["Pain"],
        "duration_days": 2,
        "pain_severity": "low",
    })
    assert booking.time_slot == "09:00 AM"
    assert booking.appointment_date == booking_date
    no_preference = HomeVisitBookingCreate.model_validate({
        **booking.model_dump(),
        "preferred_doctor_id": None,
    })
    assert no_preference.preferred_doctor_id is None
    for instructions in (None, "", "   "):
        without_instructions = HomeVisitBookingCreate.model_validate({
            **booking.model_dump(),
            "reason": instructions,
        })
        assert without_instructions.reason == ""
    omitted_instructions = booking.model_dump()
    omitted_instructions.pop("reason")
    assert HomeVisitBookingCreate.model_validate(omitted_instructions).reason == ""
    with pytest.raises(ValidationError):
        HomeVisitRequestCreate.model_validate({
            "preferred_doctor_id": "507f1f77bcf86cd799439012",
            "home_address": "12 Fictional Road, Nellore",
            "reason": "",
            "city": "Nellore",
            "body_regions": ["Knee"],
            "symptoms": ["Pain"],
            "duration_days": 2,
            "pain_severity": "low",
        })
    with pytest.raises(ValidationError):
        HomeVisitBookingCreate.model_validate({
            **booking.model_dump(),
            "submission_key": "short",
        })


def test_home_visit_access_status_distinguishes_enabled_feature_from_missing_patient_grant(monkeypatch):
    patient = type("PatientDouble", (), {"id": "patient-profile"})()
    monkeypatch.setattr(settings, "DEMO_HOME_VISIT_REQUESTS_ENABLED", True)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(DemoServiceRepository, "get_entitlement", AsyncMock(return_value=None))

    result = asyncio.run(HomeVisitService.get_patient_entitlement("patient-user"))

    assert result.active is False
    assert result.requests_enabled is True


def test_home_visit_booking_rejects_patient_without_demo_entitlement(monkeypatch):
    patient = type("PatientDouble", (), {"id": PydanticObjectId()})()
    monkeypatch.setattr(settings, "DEMO_HOME_VISIT_REQUESTS_ENABLED", True)
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(DemoServiceRepository, "get_entitlement", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock())
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock())
    schema = HomeVisitBookingCreate(
        preferred_doctor_id="507f1f77bcf86cd799439012",
        appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM",
        submission_key="fictional-no-grant-1234",
        home_address="12 Fictional Road, Nellore",
        reason=None,
        city="Nellore",
        body_regions=["Knee"],
        symptoms=["Pain"],
        duration_days=2,
        pain_severity="low",
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.create_booking("patient-user", schema))

    assert error.value.status_code == 403
    AppointmentRepository.get_by_submission_claim.assert_not_awaited()
    AppointmentRepository.create.assert_not_awaited()


def test_home_visit_booking_reserves_shared_clinician_slot_atomically(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {"id": PydanticObjectId(), "saved_home_address": None})()
    doctor = type("DoctorDouble", (), {"id": PydanticObjectId(), "user_id": PydanticObjectId(), "accepts_home_visits": True})()
    doctor_user = type("UserDouble", (), {"is_active": True})()
    schema = HomeVisitBookingCreate(
        preferred_doctor_id=str(doctor.id),
        appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM",
        submission_key="fictional-repeat-1234",
        home_address="12 Fictional Road, Nellore",
        reason=None,
        city="Nellore",
        body_regions=["Knee"],
        symptoms=["Pain"],
        duration_days=2,
        pain_severity="low",
    )
    class AppointmentDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    async def save_appointment(appointment):
        appointment.id = PydanticObjectId()
        return appointment

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=doctor_user))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentService, "_is_slot_occupied", AsyncMock(return_value=False))
    monkeypatch.setattr("app.services.home_visit_service.Appointment", AppointmentDouble)
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock(side_effect=save_appointment))
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="confirmed-home-visit"))

    result = asyncio.run(HomeVisitService.create_booking("patient-user", schema))

    assert result == "confirmed-home-visit"
    created = AppointmentRepository.create.await_args.args[0]
    assert created.service_mode == "home_visit"
    assert created.city == "Nellore"
    assert created.slot_claim == active_slot_claim(str(doctor.id), created.starts_at)
    assert created.submission_claim.startswith(f"home:{patient.id}:")
    assert created.billing_status == "unconfigured"
    assert created.billing_amount == 0
    assert created.reason == ""
    ClinicianScheduleService.validate_effective_slot.assert_awaited_once_with(
        str(doctor.id), schema.appointment_date, schema.time_slot, "home_visit"
    )


def test_home_visit_booking_rejects_slot_removed_from_schedule_before_creating(monkeypatch):
    patient = type("PatientDouble", (), {"id": PydanticObjectId(), "saved_home_address": None})()
    doctor = type("DoctorDouble", (), {"id": PydanticObjectId(), "user_id": PydanticObjectId(), "accepts_home_visits": True})()
    doctor_user = type("UserDouble", (), {"is_active": True})()
    schema = HomeVisitBookingCreate(
        preferred_doctor_id=str(doctor.id),
        appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM",
        submission_key="fictional-stale-slot-1234",
        home_address="12 Fictional Road, Nellore",
        reason="Fictional mobility support",
        city="Nellore",
        body_regions=["Knee"],
        symptoms=["Pain"],
        duration_days=2,
        pain_severity="low",
    )
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=doctor_user))
    monkeypatch.setattr(
        ClinicianScheduleService,
        "validate_effective_slot",
        AsyncMock(side_effect=HTTPException(status_code=422, detail="Choose a slot inside the published clinician schedule")),
    )
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.create_booking("patient-user", schema))

    assert error.value.status_code == 422
    ClinicianScheduleService.validate_effective_slot.assert_awaited_once_with(
        str(doctor.id), schema.appointment_date, schema.time_slot, "home_visit"
    )
    AppointmentRepository.create.assert_not_awaited()


def test_home_visit_booking_repeat_returns_existing_record(monkeypatch):
    patient = type("PatientDouble", (), {"id": PydanticObjectId()})()
    schema = HomeVisitBookingCreate(
        preferred_doctor_id=str(PydanticObjectId()), appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM", submission_key="fictional-repeat-5678",
        home_address="12 Fictional Road, Nellore", reason="Fictional mobility support",
        city="Nellore", body_regions=["Knee"], symptoms=["Pain"],
        duration_days=2, pain_severity="low",
    )
    fingerprint = sha256(json.dumps(
        schema.model_dump(mode="json", exclude={"submission_key"}),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    existing = type("AppointmentDouble", (), {
        "id": PydanticObjectId(),
        "submission_fingerprint": fingerprint,
    })()
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=type("DoctorDouble", (), {"id": PydanticObjectId()})()))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=existing))
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock())
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="same-confirmed-visit"))

    assert asyncio.run(HomeVisitService.create_booking("patient-user", schema)) == "same-confirmed-visit"
    AppointmentRepository.create.assert_not_awaited()


def test_home_visit_booking_rejects_changed_payload_for_same_submission_key(monkeypatch):
    patient = type("PatientDouble", (), {"id": PydanticObjectId()})()
    schema = HomeVisitBookingCreate(
        preferred_doctor_id=str(PydanticObjectId()), appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM", submission_key="fictional-repeat-9012",
        home_address="12 Fictional Road, Nellore", reason="Fictional mobility support",
        city="Nellore", body_regions=["Knee"], symptoms=["Pain"],
        duration_days=2, pain_severity="low",
    )
    existing = type("AppointmentDouble", (), {
        "id": PydanticObjectId(),
        "submission_fingerprint": "different-payload-fingerprint",
    })()
    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=type("DoctorDouble", (), {"id": PydanticObjectId()})()))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=existing))
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.create_booking("patient-user", schema))

    assert error.value.status_code == 409
    AppointmentRepository.create.assert_not_awaited()


def test_no_preference_booking_reserves_one_real_clinician_atomically(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {"id": PydanticObjectId(), "saved_home_address": None})()
    first = type("DoctorDouble", (), {"id": PydanticObjectId(), "user_id": PydanticObjectId(), "accepts_home_visits": True})()
    second = type("DoctorDouble", (), {"id": PydanticObjectId(), "user_id": PydanticObjectId(), "accepts_home_visits": True})()
    schema = HomeVisitBookingCreate(
        preferred_doctor_id=None,
        appointment_date=_future_booking_date().isoformat(),
        time_slot="09:00 AM",
        submission_key="fictional-no-preference-1234",
        home_address="12 Fictional Road, Nellore",
        reason="Fictional mobility support",
        city="Nellore",
        body_regions=["Knee"],
        symptoms=["Pain"],
        duration_days=2,
        pain_severity="low",
    )

    class AppointmentDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    attempts = []

    async def reserve(appointment):
        attempts.append(appointment)
        if len(attempts) == 1:
            raise DuplicateKeyError("first clinician already occupied")
        appointment.id = PydanticObjectId()
        return appointment

    monkeypatch.setattr(HomeVisitService, "_entitled_patient", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitService, "_eligible_home_visit_doctors", AsyncMock(return_value=[first, second]))
    monkeypatch.setattr(AppointmentRepository, "get_by_submission_claim", AsyncMock(return_value=None))
    monkeypatch.setattr(AppointmentRepository, "create", reserve)
    monkeypatch.setattr("app.services.home_visit_service.Appointment", AppointmentDouble)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(return_value="pending-allocation"))

    result = asyncio.run(HomeVisitService.create_booking("patient-user", schema))

    assert result == "pending-allocation"
    assert len(attempts) == 2
    assert attempts[1].doctor_id == second.id
    assert attempts[1].doctor_assignment_pending is True
    assert attempts[1].slot_claim == active_slot_claim(str(second.id), attempts[1].starts_at)


def test_admin_assignment_conflict_keeps_existing_capacity_holder(monkeypatch):
    _allow_effective_slot(monkeypatch)
    current_doctor_id = PydanticObjectId()
    target_doctor = type("DoctorDouble", (), {
        "id": PydanticObjectId(),
        "user_id": PydanticObjectId(),
        "accepts_home_visits": True,
    })()
    target_user = type("UserDouble", (), {"is_active": True})()
    appointment = type("AppointmentDouble", (), {
        "id": PydanticObjectId(),
        "doctor_id": current_doctor_id,
        "doctor_assignment_pending": True,
        "service_mode": "home_visit",
        "status": "scheduled",
        "starts_at": clinic_start_to_utc_naive(_future_booking_date(), "09:00 AM"),
        "appointment_date": datetime.combine(_future_booking_date(), datetime.min.time()),
        "time_slot": "09:00 AM",
    })()
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=target_doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=target_user))
    monkeypatch.setattr(
        AppointmentRepository,
        "assign_home_visit_doctor",
        AsyncMock(side_effect=DuplicateKeyError("target slot occupied")),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.assign_booking_doctor(
            str(appointment.id),
            str(target_doctor.id),
            str(PydanticObjectId()),
        ))

    assert error.value.status_code == 409
    assert "current reservation was kept" in error.value.detail
    assert appointment.doctor_id == current_doctor_id
    assert appointment.doctor_assignment_pending is True


def test_admin_assignment_repository_transfers_claim_and_records_actor_atomically(monkeypatch):
    captured = {}

    class CollectionDouble:
        async def find_one_and_update(self, filters, update, return_document):
            captured["filters"] = filters
            captured["update"] = update
            captured["return_document"] = return_document
            return None

    appointment_id = str(PydanticObjectId())
    current_doctor_id = str(PydanticObjectId())
    target_doctor_id = str(PydanticObjectId())
    actor_user_id = str(PydanticObjectId())
    changed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: CollectionDouble())

    result = asyncio.run(AppointmentRepository.assign_home_visit_doctor(
        appointment_id,
        current_doctor_id,
        target_doctor_id,
        "target-doctor-slot-claim",
        actor_user_id,
        changed_at,
    ))

    assert result is None
    assert str(captured["filters"]["doctor_id"]) == current_doctor_id
    assert captured["filters"]["service_mode"] == "home_visit"
    assert captured["filters"]["status"] == "scheduled"
    assert str(captured["update"]["$set"]["doctor_id"]) == target_doctor_id
    assert captured["update"]["$set"]["doctor_assignment_pending"] is False
    assert captured["update"]["$set"]["slot_claim"] == "target-doctor-slot-claim"
    assert str(captured["update"]["$push"]["doctor_assignment_audit"]["changed_by_user_id"]) == actor_user_id


def test_doctor_cannot_list_or_update_pending_capacity_reservations(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "doctor-profile"})()
    pending = type("AppointmentDouble", (), {
        "id": "pending", "doctor_id": "doctor-profile", "doctor_assignment_pending": True,
    })()
    assigned = type("AppointmentDouble", (), {
        "id": "assigned", "doctor_id": "doctor-profile", "doctor_assignment_pending": False,
    })()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=[pending, assigned]))
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(side_effect=lambda item: item.id))

    assert asyncio.run(AppointmentService.list_appointments("doctor-user", "doctor")) == ["assigned"]

    pending.status = "scheduled"
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=pending))
    with pytest.raises(HTTPException) as error:
        asyncio.run(AppointmentService.update_appointment(
            "pending",
            AppointmentUpdate(status="in_progress"),
            "doctor-user",
            "doctor",
        ))
    assert error.value.status_code == 403


def test_home_visit_role_responses_minimize_fields(monkeypatch):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    request = type("RequestDouble", (), {
        "id": "request-id",
        "patient_id": "patient-profile",
        "preferred_doctor_id": "doctor-profile",
        "home_address": "12 Fictional Road, Bengaluru",
        "reason": "Fictional clinical reason",
        "city": "Nellore", "body_regions": ["Knee"], "symptoms": ["Pain"],
        "duration_days": 4, "pain_severity": "medium",
        "status": "approved_for_coordination",
        "created_at": now,
        "updated_at": now,
    })()
    patient = type("PatientDouble", (), {
        "id": "patient-profile", "user_id": "patient-user", "phone": "+91 90000 00000",
    })()
    doctor = type("DoctorDouble", (), {"id": "doctor-profile", "user_id": "doctor-user"})()
    users = {
        "patient-user": type("UserDouble", (), {"full_name": "Fictional Patient", "email": "patient@example.com"})(),
        "doctor-user": type("UserDouble", (), {"full_name": "Fictional Doctor", "email": "doctor@example.com"})(),
    }
    monkeypatch.setattr(ProfileRepository, "get_patient_by_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(side_effect=lambda user_id: users[user_id]))

    full = asyncio.run(HomeVisitService._format_full(request))
    reception = asyncio.run(HomeVisitService._format_reception(request))
    doctor_view = asyncio.run(HomeVisitService._format_doctor(request))

    assert isinstance(full, HomeVisitRequestOut)
    assert isinstance(reception, ReceptionHomeVisitRequestOut)
    assert isinstance(doctor_view, DoctorHomeVisitRequestOut)
    assert "reason" not in reception.model_dump()
    assert "patient_email" not in doctor_view.model_dump()
    assert "reason" in doctor_view.model_dump()
    assert all(view.is_confirmed_appointment is False for view in (full, reception, doctor_view))
    assert all(view.reserves_capacity is False for view in (full, reception, doctor_view))


def test_doctor_sees_only_approved_requests_assigned_to_own_profile(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "assigned-doctor"})()
    request = type("RequestDouble", (), {})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(DemoServiceRepository, "list_doctor_coordination", AsyncMock(return_value=[request]))
    monkeypatch.setattr(HomeVisitService, "_format_doctor", AsyncMock(return_value="minimum-clinical-view"))

    result = asyncio.run(HomeVisitService.list_doctor_requests("doctor-user"))

    assert result == ["minimum-clinical-view"]
    DemoServiceRepository.list_doctor_coordination.assert_awaited_once_with("assigned-doctor")


def test_home_visit_review_and_withdraw_transitions_are_bounded(monkeypatch):
    request = type("RequestDouble", (), {
        "id": "request-id", "patient_id": "patient-profile", "status": "pending_clinic_confirmation",
    })()
    patient = type("PatientDouble", (), {"id": "patient-profile"})()
    monkeypatch.setattr(DemoServiceRepository, "get_request", AsyncMock(return_value=request))
    monkeypatch.setattr(DemoServiceRepository, "transition_request", AsyncMock(return_value=True))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))
    monkeypatch.setattr(HomeVisitService, "_format_full", AsyncMock(return_value="formatted"))

    assert asyncio.run(HomeVisitService.review_request(
        "request-id", "admin-user", "approved_for_coordination",
    )) == "formatted"
    DemoServiceRepository.transition_request.assert_awaited_with(
        "request-id", ["pending_clinic_confirmation"], "approved_for_coordination", "admin-user",
    )

    DemoServiceRepository.transition_request.reset_mock()
    assert asyncio.run(HomeVisitService.withdraw_request("request-id", "patient-user")) == "formatted"
    DemoServiceRepository.transition_request.assert_awaited_with(
        "request-id",
        ["pending_clinic_confirmation", "approved_for_coordination"],
        "withdrawn",
    )

    request.patient_id = "other-patient"
    with pytest.raises(HTTPException) as error:
        asyncio.run(HomeVisitService.withdraw_request("request-id", "patient-user"))
    assert error.value.status_code == 403


def test_jwt_configuration_is_required_and_secrets_must_differ(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("JWT_REFRESH_SECRET", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    same_value = "x" * 40
    with pytest.raises(ValidationError):
        Settings(
            JWT_SECRET=same_value,
            JWT_REFRESH_SECRET=same_value,
            _env_file=None,
        )

    with pytest.raises(ValidationError):
        Settings(
            JWT_SECRET="a" * 40,
            JWT_REFRESH_SECRET="b" * 40,
            CORS_ORIGINS=["*"],
            _env_file=None,
        )

    production = Settings(
        JWT_SECRET="a" * 40,
        JWT_REFRESH_SECRET="b" * 40,
        ENVIRONMENT="production",
        _env_file=None,
    )
    assert production.cookie_secure is True


def test_invalid_token_is_generic_and_not_logged(capsys):
    request = Request({"type": "http", "method": "GET", "path": "/api/auth/me", "headers": []})
    with pytest.raises(HTTPException) as error:
        asyncio.run(get_current_user(request, "not-a-jwt"))

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid or expired access token"
    assert capsys.readouterr().out == ""


def test_session_cookies_are_http_only_except_csrf():
    response = Response()
    set_session_cookies(response, "access", "refresh", "csrf")
    cookies = response.headers.getlist("set-cookie")

    access = next(cookie for cookie in cookies if cookie.startswith(f"{ACCESS_COOKIE_NAME}="))
    refresh = next(cookie for cookie in cookies if cookie.startswith(f"{REFRESH_COOKIE_NAME}="))
    csrf = next(cookie for cookie in cookies if cookie.startswith(f"{CSRF_COOKIE_NAME}="))
    assert "HttpOnly" in access and "SameSite=lax" in access and "Path=/api" in access
    assert "HttpOnly" in refresh and "SameSite=lax" in refresh and "Path=/api/auth" in refresh
    assert "HttpOnly" not in csrf and "SameSite=lax" in csrf and "Path=/" in csrf


def test_expired_refresh_token_is_rejected():
    expired = create_refresh_token(
        "test-user",
        "patient",
        "test-session",
        expires_delta=timedelta(seconds=-1),
    )
    assert decode_token(expired, secret="test-refresh-" + "b" * 40) == {}


def test_sensitive_request_and_auth_debug_logging_is_absent():
    backend_root = Path(__file__).resolve().parents[1]
    for relative_path in ("app/main.py", "app/middleware/auth.py"):
        source = (backend_root / relative_path).read_text(encoding="utf-8")
        assert "print(" not in source
        assert "[DIAGNOSTIC]" not in source


def test_public_registration_always_creates_patient(monkeypatch):
    created_users = []
    created_patients = []

    class ModelDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    async def no_existing_user(_email):
        return None

    async def create_user(user):
        user.id = "patient-user-id"
        created_users.append(user)
        return user

    async def create_patient(patient):
        created_patients.append(patient)
        return patient

    monkeypatch.setattr(UserRepository, "get_by_email", no_existing_user)
    monkeypatch.setattr(UserRepository, "create", create_user)
    monkeypatch.setattr(ProfileRepository, "create_patient", create_patient)
    monkeypatch.setattr("app.services.auth_service.get_password_hash", lambda _password: "test-hash")
    monkeypatch.setattr("app.services.auth_service.User", ModelDouble)
    monkeypatch.setattr("app.services.auth_service.Patient", ModelDouble)

    result = asyncio.run(
        AuthService.register(
            UserRegister.model_validate({
                "email": "new.patient@example.com",
                "password": "test-password",
                "full_name": "New Patient",
                "role": "admin",
            })
        )
    )

    assert result.role == "patient"
    assert created_users[0].role == "patient"
    assert len(created_patients) == 1


def test_unassigned_doctor_cannot_update_appointment(monkeypatch):
    appointment = type("AppointmentDouble", (), {})()
    appointment.doctor_id = "assigned-doctor"
    appointment.id = "appointment-id"
    appointment.starts_at = datetime(2027, 1, 10, 3, 30)
    appointment.appointment_date = datetime(2027, 1, 10)
    appointment.time_slot = "09:00 AM"
    appointment.save = AsyncMock()

    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=type("DoctorDouble", (), {"id": "other-doctor"})()),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.update_appointment(
                "appointment-id",
                AppointmentUpdate(status="completed"),
                actor_user_id="doctor-user-id",
                actor_role="doctor",
            )
        )

    assert error.value.status_code == 403
    appointment.save.assert_not_awaited()


def test_assigned_doctor_and_admin_retain_update_access(monkeypatch):
    appointment = type("AppointmentDouble", (), {})()
    appointment.id = "appointment-id"
    appointment.doctor_id = "assigned-doctor"
    appointment.starts_at = datetime(2027, 1, 10, 3, 30)
    appointment.appointment_date = datetime(2027, 1, 10)
    appointment.time_slot = "09:00 AM"
    appointment.status = "scheduled"
    appointment.billing_status = "pending"
    appointment.billing_amount = 0
    appointment.save = AsyncMock()

    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=type("DoctorDouble", (), {"id": "assigned-doctor"})()),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_format_appointment",
        AsyncMock(return_value="formatted-appointment"),
    )
    monkeypatch.setattr(AppointmentService, "_is_slot_occupied", AsyncMock(return_value=False))

    doctor_result = asyncio.run(
        AppointmentService.update_appointment(
            "appointment-id",
            AppointmentUpdate(status="in_progress"),
            actor_user_id="doctor-user-id",
            actor_role="doctor",
        )
    )
    admin_result = asyncio.run(
        AppointmentService.update_appointment(
            "appointment-id",
            AppointmentUpdate(status="completed"),
            actor_user_id="admin-user-id",
            actor_role="admin",
        )
    )

    assert doctor_result == "formatted-appointment"
    assert admin_result == "formatted-appointment"
    assert appointment.save.await_count == 2


def test_doctor_cannot_update_or_receive_billing_fields(monkeypatch):
    appointment = type("AppointmentDouble", (), {})()
    appointment.id = "appointment-id"
    appointment.doctor_id = "assigned-doctor"
    appointment.starts_at = datetime(2027, 1, 10, 3, 30)
    appointment.appointment_date = datetime(2027, 1, 10)
    appointment.time_slot = "09:00 AM"
    appointment.status = "scheduled"
    appointment.billing_status = "pending"
    appointment.billing_amount = 120
    appointment.save = AsyncMock()

    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(
        ProfileRepository,
        "get_doctor_by_user_id",
        AsyncMock(return_value=type("DoctorDouble", (), {"id": "assigned-doctor"})()),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.update_appointment(
                "appointment-id",
                AppointmentUpdate(billing_status="paid", billing_amount=1),
                actor_user_id="doctor-user-id",
                actor_role="doctor",
            )
        )

    assert error.value.status_code == 403
    appointment.save.assert_not_awaited()

    schema = DoctorAppointmentOut(
        id="appointment-id",
        patient_id="patient-id",
        patient_name="Fictional Patient",
        doctor_id="assigned-doctor",
        doctor_name="Fictional Doctor",
        appointment_date=datetime(2027, 1, 10),
        starts_at=datetime(2027, 1, 10, 3, 30),
        clinic_timezone="Asia/Kolkata",
        time_slot="09:00 AM",
        reason="Fictional rehearsal",
        status="scheduled",
        created_at=datetime(2027, 1, 1),
    )
    assert "billing_status" not in schema.model_dump()
    assert "billing_amount" not in schema.model_dump()
    assert "can_patient_cancel" not in schema.model_dump()


def test_analytics_uses_recorded_values_without_fabricated_growth(monkeypatch):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appointments = [
        type("AppointmentDouble", (), {
            "appointment_date": now - timedelta(days=2),
            "billing_amount": 125.0,
            "billing_status": "paid",
            "status": "completed",
        })(),
        type("AppointmentDouble", (), {
            "appointment_date": now - timedelta(days=4),
            "billing_amount": 90.0,
            "billing_status": "pending",
            "status": "cancelled",
        })(),
        type("AppointmentDouble", (), {
            "appointment_date": now - timedelta(days=60),
            "billing_amount": 75.0,
            "billing_status": "paid",
            "status": "completed",
        })(),
    ]
    doctors = [
        type("DoctorDouble", (), {"specialization": "Sports Physiotherapy"})(),
        type("DoctorDouble", (), {"specialization": "Sports Physiotherapy"})(),
    ]

    class ListQuery:
        def __init__(self, values):
            self.values = values

        async def to_list(self):
            return self.values

    class CountQuery:
        def __init__(self, value):
            self.value = value

        async def count(self):
            return self.value

    monkeypatch.setattr("app.services.analytics_service.Appointment.find_all", lambda: ListQuery(appointments))
    monkeypatch.setattr("app.services.analytics_service.Doctor.find_all", lambda: ListQuery(doctors))
    monkeypatch.setattr("app.services.analytics_service.User.find", lambda *args: CountQuery(1))
    monkeypatch.setattr("app.services.analytics_service.Patient.find", lambda *args: CountQuery(1))
    monkeypatch.setattr("app.services.analytics_service.Patient.count", AsyncMock(return_value=3))

    stats = asyncio.run(AnalyticsService.get_clinic_stats(days=30))

    assert stats["period_appointments"] == 2
    assert stats["recorded_paid_total"] == 125.0
    assert stats["cancellation_rate"] == 50.0
    assert stats["total_patients"] == 3
    assert stats["doctor_specializations"] == [
        {"name": "Sports Physiotherapy", "value": 2},
    ]
    assert stats["availability"]["growth_comparisons"] is False
    assert "appointments_growth" not in stats
    assert "revenue_growth" not in stats


def test_india_clinic_time_normalization_preserves_legacy_calendar_date():
    normalized = clinic_start_to_utc_naive(
        datetime(2026, 1, 10).date(),
        "09:00 AM",
    )
    assert normalized == datetime(2026, 1, 10, 3, 30)

    legacy = type("LegacyAppointment", (), {
        "starts_at": None,
        "appointment_date": datetime(2026, 1, 9, 18, 30),
        "time_slot": "09:00 AM",
    })()
    assert resolve_appointment_start_utc(legacy) == datetime(
        2026, 1, 10, 3, 30, tzinfo=timezone.utc,
    )

    schema = AppointmentCreate.model_validate({
        "doctor_id": "doctor-id",
        "appointment_date": "2026-01-09T18:30:00Z",
        "time_slot": "09:00 am",
        "reason": "Fictional test",
    })
    assert schema.appointment_date.isoformat() == "2026-01-10"
    assert schema.time_slot == "09:00 AM"


def test_demo_schedule_boundaries_and_slot_alignment():
    slots = demo_schedule_slots()
    assert len(slots) == 18
    assert slots[0] == "09:00 AM"
    assert slots[-1] == "05:30 PM"

    assert validate_demo_slot(
        datetime(2030, 1, 10).date(),
        "09:00 AM",
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    ) == datetime(2030, 1, 10, 3, 30)
    assert validate_demo_slot(
        datetime(2030, 1, 10).date(),
        "05:30 PM",
        now=datetime(2030, 1, 1, tzinfo=timezone.utc),
    ) == datetime(2030, 1, 10, 12, 0)

    for invalid_slot in ("08:30 AM", "09:15 AM", "06:00 PM"):
        with pytest.raises(ValueError, match="configured demonstration schedule"):
            validate_demo_slot(
                datetime(2030, 1, 10).date(),
                invalid_slot,
                now=datetime(2030, 1, 1, tzinfo=timezone.utc),
            )

    with pytest.raises(ValueError, match="future"):
        validate_demo_slot(
            datetime(2020, 1, 10).date(),
            "09:00 AM",
            now=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )


def test_booking_window_is_thirty_clinic_dates_inclusive():
    now = datetime(2026, 10, 23, 20, 0, tzinfo=timezone.utc)
    earliest, latest = booking_window(now)

    assert earliest.isoformat() == "2026-10-24"
    assert latest.isoformat() == "2026-11-22"
    validate_booking_date(earliest, now)
    validate_booking_date(latest, now)
    with pytest.raises(ValueError, match="today or a future"):
        validate_booking_date(earliest - timedelta(days=1), now)
    with pytest.raises(ValueError, match="within the next 30 days"):
        validate_booking_date(latest + timedelta(days=1), now)


def test_clinician_schedule_routes_are_admin_only():
    assert allowed_roles(route_for(clinician_schedules_router, "/clinician-schedules/admin/{doctor_id}", "GET")) == {"admin"}
    assert allowed_roles(route_for(clinician_schedules_router, "/clinician-schedules/admin/{doctor_id}/draft", "PUT")) == {"admin"}
    assert allowed_roles(route_for(clinician_schedules_router, "/clinician-schedules/admin/{doctor_id}/preview", "GET")) == {"admin"}
    assert allowed_roles(route_for(clinician_schedules_router, "/clinician-schedules/admin/{doctor_id}/publish", "POST")) == {"admin"}


def test_schedule_draft_rejects_cross_mode_overlap_and_off_grid_times():
    with pytest.raises(ValidationError, match="clinic and home blocks cannot overlap"):
        ScheduleDraftUpdate.model_validate({
            "weekly_blocks": [
                {"day_of_week": 0, "service_mode": "clinic", "start_time": "09:00", "end_time": "11:00"},
                {"day_of_week": 0, "service_mode": "home_visit", "start_time": "10:30", "end_time": "12:00"},
            ],
            "date_exceptions": [],
        })
    with pytest.raises(ValidationError, match="30-minute boundaries"):
        ScheduleDraftUpdate.model_validate({
            "weekly_blocks": [
                {"day_of_week": 0, "service_mode": "clinic", "start_time": "09:15", "end_time": "11:00"},
            ],
            "date_exceptions": [],
        })


def test_schedule_exception_overrides_weekly_blocks_and_can_close_date():
    target = _future_booking_date()
    weekday = target.weekday()
    weekly = [ScheduleBlock(day_of_week=weekday, service_mode="clinic", start_time="09:00", end_time="10:00")]
    exception = [ScheduleDateException(
        date=target,
        blocks=[ScheduleBlock(day_of_week=weekday, service_mode="home_visit", start_time="14:00", end_time="15:00")],
    )]
    assert ClinicianScheduleService._slots_from(weekly, [], target, "clinic", 30) == ["09:00 AM", "09:30 AM"]
    assert ClinicianScheduleService._slots_from(weekly, exception, target, "clinic", 30) == []
    assert ClinicianScheduleService._slots_from(weekly, exception, target, "home_visit", 30) == ["02:00 PM", "02:30 PM"]
    assert ClinicianScheduleService._slots_from(
        weekly,
        [ScheduleDateException(date=target, blocks=[])],
        target,
        "clinic",
        30,
    ) == []


def test_schedule_draft_rejects_exception_outside_booking_window(monkeypatch):
    latest = booking_window()[1]
    schema = ScheduleDraftUpdate(
        weekly_blocks=[],
        date_exceptions=[ScheduleDateExceptionIn(date=latest + timedelta(days=1), blocks=[])],
    )
    monkeypatch.setattr(ClinicianScheduleService, "_doctor", AsyncMock(return_value=(object(), type("UserDouble", (), {"full_name": "Fictional Doctor"})())))
    monkeypatch.setattr(ClinicianScheduleRepository, "save_draft", AsyncMock())
    with pytest.raises(HTTPException) as error:
        asyncio.run(ClinicianScheduleService.save_draft(str(PydanticObjectId()), str(PydanticObjectId()), schema))
    assert error.value.status_code == 422
    ClinicianScheduleRepository.save_draft.assert_not_awaited()


def test_published_schedule_is_authoritative_and_mode_specific(monkeypatch):
    target = _future_booking_date()
    schedule = type("ScheduleDouble", (), {
        "doctor_id": PydanticObjectId(),
        "published_revision": 2,
        "slot_minutes": 30,
        "published_date_exceptions": [],
        "published_weekly_blocks": [
            ScheduleBlock(day_of_week=target.weekday(), service_mode="clinic", start_time="10:00", end_time="11:00"),
            ScheduleBlock(day_of_week=target.weekday(), service_mode="home_visit", start_time="14:00", end_time="15:00"),
        ],
    })()
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=schedule))
    clinic_slots, published = asyncio.run(ClinicianScheduleService.effective_slots(str(schedule.doctor_id), target, "clinic"))
    home_slots, _ = asyncio.run(ClinicianScheduleService.effective_slots(str(schedule.doctor_id), target, "home_visit"))
    assert published is True
    assert clinic_slots == ["10:00 AM", "10:30 AM"]
    assert home_slots == ["02:00 PM", "02:30 PM"]


def test_schedule_publish_blocks_existing_appointment_excluded_by_draft(monkeypatch):
    target = _future_booking_date()
    doctor_id = PydanticObjectId()
    schedule = type("ScheduleDouble", (), {
        "doctor_id": doctor_id,
        "draft_revision": 3,
        "slot_minutes": 30,
        "draft_date_exceptions": [],
        "draft_weekly_blocks": [
            ScheduleBlock(day_of_week=target.weekday(), service_mode="clinic", start_time="10:00", end_time="11:00"),
        ],
    })()
    appointment = type("AppointmentDouble", (), {
        "starts_at": clinic_start_to_utc_naive(target, "09:00 AM"),
        "appointment_date": datetime.combine(target, datetime.min.time()),
        "time_slot": "09:00 AM",
        "service_mode": "clinic",
    })()
    user = type("UserDouble", (), {"full_name": "Fictional Doctor"})()
    monkeypatch.setattr(ClinicianScheduleService, "_doctor", AsyncMock(return_value=(object(), user)))
    monkeypatch.setattr(ClinicianScheduleRepository, "get_by_doctor_id", AsyncMock(return_value=schedule))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[appointment]))
    monkeypatch.setattr(ClinicianScheduleRepository, "publish", AsyncMock())
    with pytest.raises(HTTPException) as error:
        asyncio.run(ClinicianScheduleService.publish(str(doctor_id), str(PydanticObjectId()), 3))
    assert error.value.status_code == 409
    assert "existing appointment" in error.value.detail
    ClinicianScheduleRepository.publish.assert_not_awaited()


def test_availability_marks_active_slot_occupied(monkeypatch):
    appointment_date = _future_booking_date()
    starts_at = clinic_start_to_utc_naive(appointment_date, "09:00 AM")
    doctor = type("DoctorDouble", (), {"id": "doctor-profile"})()
    occupied = type("AppointmentDouble", (), {
        "starts_at": starts_at,
        "appointment_date": datetime.combine(appointment_date, datetime.min.time()),
        "time_slot": "09:00 AM",
    })()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[occupied]))
    monkeypatch.setattr(ClinicianScheduleService, "effective_slots", AsyncMock(return_value=(demo_schedule_slots(), False)))

    result = asyncio.run(AppointmentService.get_availability(
        "doctor-profile",
        appointment_date,
    ))

    assert result.demo_configuration is True
    assert result.slot_minutes == 30
    assert result.window_start == "09:00 AM"
    assert result.window_end == "05:30 PM"
    assert result.slots[0].time_slot == "09:00 AM"
    assert result.slots[0].available is False
    assert result.slots[0].availability_state == "occupied"
    assert result.slots[1].time_slot == "09:30 AM"
    assert result.slots[1].available is True
    assert result.slots[1].availability_state == "available"


def test_availability_rejects_past_calendar_dates(monkeypatch):
    doctor = type("DoctorDouble", (), {"id": "doctor-profile"})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_active_by_doctor_id", AsyncMock(return_value=[]))

    with pytest.raises(HTTPException) as error:
        asyncio.run(AppointmentService.get_availability(
            "doctor-profile",
            datetime(2000, 1, 10).date(),
        ))
    assert error.value.status_code == 422


def test_repeat_booking_attempt_is_rejected_before_insert(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {"id": "patient-profile"})()
    doctor = type("DoctorDouble", (), {"id": "doctor-profile"})()
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentService, "_is_slot_occupied", AsyncMock(return_value=True))
    monkeypatch.setattr(AppointmentRepository, "create", AsyncMock())

    schema = AppointmentCreate.model_validate({
        "doctor_id": "doctor-profile",
        "appointment_date": _future_booking_date().isoformat(),
        "time_slot": "09:00 AM",
        "reason": "Fictional repeat attempt",
    })
    with pytest.raises(HTTPException) as error:
        asyncio.run(AppointmentService._create_for_patient(patient, schema))

    assert error.value.status_code == 409
    AppointmentRepository.create.assert_not_awaited()


def test_simultaneous_booking_claim_allows_only_one(monkeypatch):
    _allow_effective_slot(monkeypatch)
    patient = type("PatientDouble", (), {"id": "patient-profile"})()
    doctor = type("DoctorDouble", (), {"id": "doctor-profile"})()

    class AppointmentDouble:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

    claims = set()
    lock = asyncio.Lock()

    async def atomic_create(appointment):
        async with lock:
            await asyncio.sleep(0)
            if appointment.slot_claim in claims:
                raise DuplicateKeyError("duplicate slot claim")
            claims.add(appointment.slot_claim)
            appointment.id = f"appointment-{len(claims)}"
            return appointment

    monkeypatch.setattr(ProfileRepository, "get_doctor_by_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentService, "_is_slot_occupied", AsyncMock(return_value=False))
    monkeypatch.setattr(AppointmentRepository, "create", atomic_create)
    monkeypatch.setattr("app.services.appointment_service.Appointment", AppointmentDouble)
    monkeypatch.setattr(AppointmentService, "_format_appointment", AsyncMock(side_effect=lambda appointment: appointment.id))

    schema = AppointmentCreate.model_validate({
        "doctor_id": "doctor-profile",
        "appointment_date": _future_booking_date().isoformat(),
        "time_slot": "09:30 AM",
        "reason": "Fictional simultaneous attempt",
    })

    async def run_both():
        return await asyncio.gather(
            AppointmentService._create_for_patient(patient, schema),
            AppointmentService._create_for_patient(patient, schema),
            return_exceptions=True,
        )

    results = asyncio.run(run_both())
    assert sum(result == "appointment-1" for result in results) == 1
    conflict = next(result for result in results if isinstance(result, HTTPException))
    assert conflict.status_code == 409
    assert len(claims) == 1


def test_patient_cancellation_releases_slot_claim(monkeypatch):
    captured = {}

    class UpdateResult:
        modified_count = 1

    class CollectionDouble:
        async def update_one(self, filters, update):
            captured["filters"] = filters
            captured["update"] = update
            return UpdateResult()

    monkeypatch.setattr(Appointment, "get_pymongo_collection", lambda: CollectionDouble())
    changed = asyncio.run(AppointmentRepository.cancel_scheduled_owned(
        "507f1f77bcf86cd799439011",
        "507f1f77bcf86cd799439012",
        datetime(2030, 1, 1),
    ))

    assert changed is True
    assert captured["update"]["$set"]["status"] == "cancelled"
    assert captured["update"]["$unset"] == {"slot_claim": ""}


def test_slot_claim_distinguishes_adjacent_non_overlapping_slots():
    first = clinic_start_to_utc_naive(datetime(2030, 1, 10).date(), "09:00 AM")
    second = clinic_start_to_utc_naive(datetime(2030, 1, 10).date(), "09:30 AM")
    assert second - first == timedelta(minutes=30)
    assert active_slot_claim("doctor-profile", first) != active_slot_claim("doctor-profile", second)


def _cancellable_appointment(starts_at, status_value="scheduled", patient_id="patient-profile"):
    return type("AppointmentDouble", (), {
        "id": "appointment-id",
        "patient_id": patient_id,
        "starts_at": starts_at.replace(tzinfo=None),
        "appointment_date": starts_at.replace(tzinfo=None),
        "time_slot": "09:00 AM",
        "status": status_value,
    })()


def _configure_cancellation(monkeypatch, appointment):
    patient = type("PatientDouble", (), {"id": "patient-profile"})()
    monkeypatch.setattr(
        ProfileRepository,
        "get_patient_by_user_id",
        AsyncMock(return_value=patient),
    )
    monkeypatch.setattr(
        AppointmentRepository,
        "get_by_id",
        AsyncMock(return_value=appointment),
    )
    monkeypatch.setattr(
        AppointmentService,
        "_format_appointment",
        AsyncMock(side_effect=lambda item: item.status),
    )


@pytest.mark.parametrize("seconds_before_boundary", [0, 1])
def test_patient_cancellation_allows_exact_and_outside_24_hour_boundary(monkeypatch, seconds_before_boundary):
    starts_at = datetime(2026, 6, 2, 3, 30, tzinfo=timezone.utc)
    now = starts_at - timedelta(hours=24, seconds=seconds_before_boundary)
    appointment = _cancellable_appointment(starts_at)
    _configure_cancellation(monkeypatch, appointment)

    async def cancel_once(*_args):
        appointment.status = "cancelled"
        return True

    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", cancel_once)
    result = asyncio.run(
        AppointmentService.cancel_patient_appointment(
            "appointment-id",
            "patient-user",
            now=now,
        )
    )
    assert result == "cancelled"


@pytest.mark.parametrize("offset,status_code,message", [
    (timedelta(hours=23, minutes=59), 409, "closes 24 hours"),
    (timedelta(hours=-1), 409, "already started or passed"),
])
def test_patient_cancellation_blocks_inside_window_and_past(monkeypatch, offset, status_code, message):
    now = datetime(2026, 6, 1, 3, 30, tzinfo=timezone.utc)
    appointment = _cancellable_appointment(now + offset)
    _configure_cancellation(monkeypatch, appointment)
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.cancel_patient_appointment(
                "appointment-id",
                "patient-user",
                now=now,
            )
        )
    assert error.value.status_code == status_code
    assert message in error.value.detail
    AppointmentRepository.cancel_scheduled_owned.assert_not_awaited()


def test_reception_cancellation_preserves_cutoff_and_releases_slot(monkeypatch):
    starts_at = datetime(2030, 1, 10, 3, 30, tzinfo=timezone.utc)
    appointment = _cancellable_appointment(starts_at)
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(AppointmentService, "_format_reception_appointment", AsyncMock(side_effect=lambda item: item.status))

    async def cancel_once(*_args):
        appointment.status = "cancelled"
        return True

    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled", AsyncMock(side_effect=cancel_once))
    result = asyncio.run(AppointmentService.cancel_reception_appointment(
        "appointment-id",
        now=starts_at - timedelta(hours=24),
    ))

    assert result == "cancelled"
    AppointmentRepository.cancel_scheduled.assert_awaited_once()


def test_reception_cancellation_cannot_override_inside_24_hours(monkeypatch):
    starts_at = datetime(2030, 1, 10, 3, 30, tzinfo=timezone.utc)
    appointment = _cancellable_appointment(starts_at)
    monkeypatch.setattr(AppointmentRepository, "get_by_id", AsyncMock(return_value=appointment))
    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(AppointmentService.cancel_reception_appointment(
            "appointment-id",
            now=starts_at - timedelta(hours=23, minutes=59),
        ))

    assert error.value.status_code == 409
    assert "override policy is not configured" in error.value.detail
    AppointmentRepository.cancel_scheduled.assert_not_awaited()


@pytest.mark.parametrize("appointment_status", ["completed", "in_progress", "no_show"])
def test_patient_cancellation_blocks_non_scheduled_states(monkeypatch, appointment_status):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)
    appointment = _cancellable_appointment(starts_at, status_value=appointment_status)
    _configure_cancellation(monkeypatch, appointment)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.cancel_patient_appointment(
                "appointment-id",
                "patient-user",
            )
        )
    assert error.value.status_code == 409


def test_patient_cancellation_is_idempotent_and_enforces_ownership(monkeypatch):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)
    cancelled = _cancellable_appointment(starts_at, status_value="cancelled")
    _configure_cancellation(monkeypatch, cancelled)
    assert asyncio.run(
        AppointmentService.cancel_patient_appointment("appointment-id", "patient-user")
    ) == "cancelled"

    foreign = _cancellable_appointment(starts_at, patient_id="other-patient")
    _configure_cancellation(monkeypatch, foreign)
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.cancel_patient_appointment("appointment-id", "patient-user")
        )
    assert error.value.status_code == 403


def test_concurrent_patient_cancellation_repeats_are_idempotent(monkeypatch):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)
    appointment = _cancellable_appointment(starts_at)
    _configure_cancellation(monkeypatch, appointment)
    lock = asyncio.Lock()

    async def atomic_cancel(*_args):
        async with lock:
            await asyncio.sleep(0)
            if appointment.status != "scheduled":
                return False
            appointment.status = "cancelled"
            return True

    monkeypatch.setattr(AppointmentRepository, "cancel_scheduled_owned", atomic_cancel)

    async def run_both():
        return await asyncio.gather(
            AppointmentService.cancel_patient_appointment("appointment-id", "patient-user"),
            AppointmentService.cancel_patient_appointment("appointment-id", "patient-user"),
        )

    assert asyncio.run(run_both()) == ["cancelled", "cancelled"]


def test_ambiguous_legacy_time_requires_clinic_contact(monkeypatch):
    appointment = _cancellable_appointment(datetime.now(timezone.utc) + timedelta(days=3))
    appointment.starts_at = None
    appointment.appointment_date = datetime(2026, 6, 1, 0, 0)
    _configure_cancellation(monkeypatch, appointment)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            AppointmentService.cancel_patient_appointment("appointment-id", "patient-user")
        )
    assert error.value.status_code == 409
    assert "cannot be verified" in error.value.detail


def test_laboratory_role_routes_are_object_scoped():
    assert allowed_roles(route_for(users_router, "/users/laboratorians", "GET")) == {"admin"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/admin/{request_id}/assignment", "PATCH")) == {"admin"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/admin/{request_id}/publish-report", "POST")) == {"admin"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/laboratory/assigned", "GET")) == {"laboratorian"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/laboratory/{request_id}/report", "PUT")) == {"laboratorian"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/me/reports", "GET")) == {"patient"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/doctor/reports", "GET")) == {"doctor"}
    assert allowed_roles(route_for(lab_requests_router, "/lab-requests/{request_id}/report-file", "GET")) == {
        "patient", "doctor", "laboratorian", "admin",
    }


def test_admin_assignment_accepts_only_active_laboratorian(monkeypatch):
    request = type("LabRequestDouble", (), {
        "assigned_laboratorian_user_id": None,
        "report_status": "not_started",
        "status": "approved_for_coordination",
    })()
    non_laboratorian = type("UserDouble", (), {"role": "doctor", "is_active": True})()
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=non_laboratorian))
    monkeypatch.setattr(LabRequestRepository, "assign_laboratorian", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.assign_laboratorian(
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439012",
            "507f1f77bcf86cd799439013",
        ))

    assert error.value.status_code == 422
    LabRequestRepository.assign_laboratorian.assert_not_awaited()


def test_laboratorian_cannot_upload_report_for_unassigned_order(monkeypatch):
    request = type("LabRequestDouble", (), {
        "assigned_laboratorian_user_id": PydanticObjectId("507f1f77bcf86cd799439012"),
        "report_status": "not_started",
    })()
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabRequestRepository, "save_finalized_report", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.upload_finalized_report(
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439099",
            b"%PDF-1.4 fictional",
            "fictional-report.pdf",
        ))

    assert error.value.status_code == 403
    LabRequestRepository.save_finalized_report.assert_not_awaited()


def test_patient_cannot_read_another_patients_released_report(monkeypatch):
    request = type("LabRequestDouble", (), {
        "report_storage_key": "fictional.pdf",
        "report_file_name": "fictional.pdf",
        "report_status": "released",
        "patient_id": PydanticObjectId("507f1f77bcf86cd799439011"),
        "assigned_laboratorian_user_id": None,
    })()
    patient = type("PatientDouble", (), {"id": PydanticObjectId("507f1f77bcf86cd799439099")})()
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.get_report_file(
            "507f1f77bcf86cd799439011",
            "507f1f77bcf86cd799439098",
            "patient",
        ))

    assert error.value.status_code == 403


def _lab_request_double(**overrides):
    values = {
        "id": PydanticObjectId("507f1f77bcf86cd799439011"),
        "patient_id": PydanticObjectId("507f1f77bcf86cd799439021"),
        "assigned_laboratorian_user_id": PydanticObjectId("507f1f77bcf86cd799439012"),
        "status": "approved_for_coordination",
        "report_status": "not_started",
        "report_storage_key": None,
        "report_file_name": None,
    }
    values.update(overrides)
    return type("LabRequestDouble", (), values)()


def test_finalized_report_rejects_invalid_pdf_and_oversize_before_writing(monkeypatch, tmp_path):
    request = _lab_request_double()
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabRequestRepository, "save_finalized_report", AsyncMock())
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "LAB_REPORT_MAX_BYTES", 16)

    with pytest.raises(HTTPException) as invalid_pdf:
        asyncio.run(LabRequestService.upload_finalized_report(
            str(request.id), str(request.assigned_laboratorian_user_id), b"not a PDF", "report.pdf"
        ))
    assert invalid_pdf.value.status_code == 422

    with pytest.raises(HTTPException) as oversized:
        asyncio.run(LabRequestService.upload_finalized_report(
            str(request.id), str(request.assigned_laboratorian_user_id), b"%PDF-" + b"x" * 20, "report.pdf"
        ))
    assert oversized.value.status_code == 422
    LabRequestRepository.save_finalized_report.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []


def test_finalized_report_is_written_privately_with_sanitized_metadata(monkeypatch, tmp_path):
    request = _lab_request_double()
    updated = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="generated.pdf",
        report_file_name="unsafe report.pdf",
    )
    monkeypatch.setattr(
        LabRequestRepository,
        "get",
        AsyncMock(side_effect=[request, updated]),
    )
    monkeypatch.setattr(LabRequestRepository, "save_finalized_report", AsyncMock(return_value=True))
    monkeypatch.setattr(LabRequestService, "_format_for_laboratorian", AsyncMock(return_value="formatted"))
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "LAB_REPORT_MAX_BYTES", 1024)

    result = asyncio.run(LabRequestService.upload_finalized_report(
        str(request.id),
        str(request.assigned_laboratorian_user_id),
        b"%PDF-1.4 fictional",
        "../unsafe<script> report.pdf",
    ))

    assert result == "formatted"
    written = list(tmp_path.iterdir())
    assert len(written) == 1
    assert written[0].suffix == ".pdf"
    if os.name == "posix":
        assert written[0].stat().st_mode & 0o777 == 0o600
    saved = LabRequestRepository.save_finalized_report.await_args.kwargs
    assert saved["expected_storage_key"] is None
    assert saved["file_name"] == "unsafe_script_ report.pdf"
    assert saved["content_type"] == "application/pdf"
    assert saved["size_bytes"] == len(b"%PDF-1.4 fictional")


def test_losing_concurrent_report_replacement_removes_new_file(monkeypatch, tmp_path):
    request = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="current.pdf",
        report_file_name="current.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabRequestRepository, "save_finalized_report", AsyncMock(return_value=False))
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "LAB_REPORT_MAX_BYTES", 1024)

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.upload_finalized_report(
            str(request.id),
            str(request.assigned_laboratorian_user_id),
            b"%PDF-1.4 fictional",
            "replacement.pdf",
        ))

    assert error.value.status_code == 409
    assert LabRequestRepository.save_finalized_report.await_args.kwargs["expected_storage_key"] == "current.pdf"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("role", ["patient", "doctor"])
def test_unreleased_report_is_invisible_to_patient_and_doctor(monkeypatch, role):
    request = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="private-draft.pdf",
        report_file_name="private-draft.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock())
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.get_report_file(str(request.id), "user-id", role))

    assert error.value.status_code == 404
    ProfileRepository.get_patient_by_user_id.assert_not_awaited()
    ProfileRepository.get_doctor_by_user_id.assert_not_awaited()


def test_report_download_rejects_storage_key_path_traversal(monkeypatch):
    request = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="../outside.pdf",
        report_file_name="outside.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.get_report_file(
            str(request.id), str(request.assigned_laboratorian_user_id), "laboratorian"
        ))

    assert error.value.status_code == 404


def test_previous_laboratorian_loses_draft_access_after_reassignment(monkeypatch):
    request = _lab_request_double(
        assigned_laboratorian_user_id=PydanticObjectId("507f1f77bcf86cd799439099"),
        report_status="awaiting_publication",
        report_storage_key="private-draft.pdf",
        report_file_name="private-draft.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.get_report_file(
            str(request.id), "507f1f77bcf86cd799439012", "laboratorian"
        ))

    assert error.value.status_code == 403


def test_released_report_cannot_be_reassigned(monkeypatch):
    request = _lab_request_double(report_status="released")
    laboratorian = type("UserDouble", (), {"role": "laboratorian", "is_active": True})()
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(UserRepository, "get_by_id", AsyncMock(return_value=laboratorian))
    monkeypatch.setattr(LabRequestRepository, "assign_laboratorian", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.assign_laboratorian(
            str(request.id), "507f1f77bcf86cd799439099", "507f1f77bcf86cd799439098"
        ))

    assert error.value.status_code == 409
    LabRequestRepository.assign_laboratorian.assert_not_awaited()


def test_legacy_draft_cannot_be_administratively_published(monkeypatch):
    request = _lab_request_double(
        report_status="draft_uploaded",
        report_storage_key="legacy-draft.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabRequestRepository, "publish_report", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.publish_report(str(request.id), "507f1f77bcf86cd799439099"))

    assert error.value.status_code == 409
    LabRequestRepository.publish_report.assert_not_awaited()


def test_admin_cannot_publish_when_finalized_file_is_missing(monkeypatch, tmp_path):
    request = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="missing.pdf",
    )
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(LabRequestRepository, "publish_report", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.publish_report(str(request.id), "507f1f77bcf86cd799439099"))

    assert error.value.status_code == 409
    LabRequestRepository.publish_report.assert_not_awaited()


def test_admin_publication_uses_expected_file_and_is_idempotent(monkeypatch, tmp_path):
    storage_path = tmp_path / "finalized.pdf"
    storage_path.write_bytes(b"%PDF-1.4 fictional")
    awaiting = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key=storage_path.name,
        report_file_name="finalized.pdf",
    )
    released = _lab_request_double(
        report_status="released",
        report_storage_key=storage_path.name,
        report_file_name="finalized.pdf",
    )
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(side_effect=[awaiting, released]))
    monkeypatch.setattr(LabRequestRepository, "publish_report", AsyncMock(return_value=True))
    monkeypatch.setattr(LabRequestService, "_format", AsyncMock(return_value="published"))

    result = asyncio.run(LabRequestService.publish_report(str(awaiting.id), "507f1f77bcf86cd799439099"))

    assert result == "published"
    assert LabRequestRepository.publish_report.await_args.kwargs["expected_storage_key"] == storage_path.name


def test_repeated_admin_publication_is_idempotent(monkeypatch):
    released = _lab_request_double(
        report_status="released",
        report_storage_key="released.pdf",
        report_file_name="released.pdf",
    )
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=released))
    monkeypatch.setattr(LabRequestRepository, "publish_report", AsyncMock())
    monkeypatch.setattr(LabRequestService, "_format", AsyncMock(return_value="already-published"))

    result = asyncio.run(LabRequestService.publish_report(str(released.id), "507f1f77bcf86cd799439099"))

    assert result == "already-published"
    LabRequestRepository.publish_report.assert_not_awaited()


def test_report_publication_repository_records_admin_audit(monkeypatch):
    captured = {}

    class ResultDouble:
        modified_count = 1

    class CollectionDouble:
        async def update_one(self, query, update):
            captured["query"] = query
            captured["update"] = update
            return ResultDouble()

    monkeypatch.setattr(LabRequest, "get_pymongo_collection", lambda: CollectionDouble())
    admin_id = "507f1f77bcf86cd799439099"

    changed = asyncio.run(LabRequestRepository.publish_report(
        "507f1f77bcf86cd799439011",
        admin_id,
        expected_storage_key="finalized.pdf",
    ))

    assert changed is True
    assert captured["query"]["report_status"] == "awaiting_publication"
    assert captured["query"]["report_storage_key"] == "finalized.pdf"
    assert captured["update"]["$set"]["report_status"] == "released"
    assert str(captured["update"]["$set"]["report_released_by_user_id"]) == admin_id
    assert captured["update"]["$push"]["report_publication_history"]["action"] == "administratively_published"


def test_admin_publication_rejects_file_changed_during_review(monkeypatch, tmp_path):
    storage_path = tmp_path / "reviewed.pdf"
    storage_path.write_bytes(b"%PDF-1.4 fictional")
    awaiting = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key=storage_path.name,
    )
    changed = _lab_request_double(
        report_status="awaiting_publication",
        report_storage_key="replacement.pdf",
    )
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(side_effect=[awaiting, changed]))
    monkeypatch.setattr(LabRequestRepository, "publish_report", AsyncMock(return_value=False))

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.publish_report(str(awaiting.id), "507f1f77bcf86cd799439099"))

    assert error.value.status_code == 409
    assert "changed before publication" in error.value.detail


def test_patient_can_download_own_administratively_published_report(monkeypatch, tmp_path):
    storage_path = tmp_path / "released.pdf"
    storage_path.write_bytes(b"%PDF-1.4 fictional")
    request = _lab_request_double(
        report_status="released",
        report_storage_key=storage_path.name,
        report_file_name="released.pdf",
    )
    patient = type("PatientDouble", (), {"id": request.patient_id})()
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(ProfileRepository, "get_patient_by_user_id", AsyncMock(return_value=patient))

    path, name = asyncio.run(LabRequestService.get_report_file(str(request.id), "patient-user", "patient"))

    assert path == storage_path
    assert name == "released.pdf"


def test_unassigned_doctor_cannot_download_published_report(monkeypatch, tmp_path):
    storage_path = tmp_path / "released.pdf"
    storage_path.write_bytes(b"%PDF-1.4 fictional")
    request = _lab_request_double(
        report_status="released",
        report_storage_key=storage_path.name,
        report_file_name="released.pdf",
    )
    doctor = type("DoctorDouble", (), {"id": PydanticObjectId("507f1f77bcf86cd799439099")})()
    monkeypatch.setattr(settings, "LAB_REPORT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(LabRequestRepository, "get", AsyncMock(return_value=request))
    monkeypatch.setattr(ProfileRepository, "get_doctor_by_user_id", AsyncMock(return_value=doctor))
    monkeypatch.setattr(AppointmentRepository, "list_by_doctor_id", AsyncMock(return_value=[]))

    with pytest.raises(HTTPException) as error:
        asyncio.run(LabRequestService.get_report_file(str(request.id), "doctor-user", "doctor"))

    assert error.value.status_code == 403


def test_upload_route_rejects_malformed_content_length(monkeypatch):
    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/lab-requests/laboratory/request/report",
        "headers": [
            (b"content-type", b"application/pdf"),
            (b"content-length", b"not-a-number"),
        ],
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    user = type("UserDouble", (), {"id": PydanticObjectId("507f1f77bcf86cd799439012")})()
    monkeypatch.setattr(LabRequestService, "upload_finalized_report", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload_finalized_report_api(
            "507f1f77bcf86cd799439011", request, "report.pdf", user
        ))

    assert error.value.status_code == 400
    LabRequestService.upload_finalized_report.assert_not_awaited()


def test_upload_route_rejects_non_pdf_content_type(monkeypatch):
    scope = {
        "type": "http",
        "method": "PUT",
        "path": "/lab-requests/laboratory/request/report",
        "headers": [(b"content-type", b"text/plain")],
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(scope, receive)
    user = type("UserDouble", (), {"id": PydanticObjectId("507f1f77bcf86cd799439012")})()
    monkeypatch.setattr(LabRequestService, "upload_finalized_report", AsyncMock())

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload_finalized_report_api(
            "507f1f77bcf86cd799439011", request, "report.pdf", user
        ))

    assert error.value.status_code == 415
    LabRequestService.upload_finalized_report.assert_not_awaited()
