from datetime import date

from fastapi import APIRouter, Depends, status

from app.middleware.auth import RoleChecker
from app.models.user import User
from app.schemas.home_visit import (
    AdminDemoEntitlementOut,
    DemoEntitlementOut,
    DemoEntitlementUpdate,
    DoctorHomeVisitRequestOut,
    HomeVisitBookingCreate,
    HomeVisitDoctorAssignment,
    HomeVisitRequestCreate,
    HomeVisitContextOut,
    HomeVisitRequestOut,
    HomeVisitRequestStatusUpdate,
    ReceptionHomeVisitRequestOut,
)
from app.schemas.appointment import AppointmentAvailabilityOut, AppointmentOut
from app.services.home_visit_service import HomeVisitService


router = APIRouter(tags=["demo services and home visits"])


@router.get("/home-visit-requests/me/context", response_model=HomeVisitContextOut)
async def get_home_visit_context(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.get_patient_context(str(current_user.id))


@router.get("/demo-services/me/entitlement", response_model=DemoEntitlementOut)
async def get_own_demo_entitlement(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.get_patient_entitlement(str(current_user.id))


@router.get("/demo-services/entitlements", response_model=list[AdminDemoEntitlementOut])
async def list_demo_entitlements(
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await HomeVisitService.list_admin_entitlements()


@router.put("/demo-services/patients/{patient_id}/entitlement", response_model=AdminDemoEntitlementOut)
async def set_demo_entitlement(
    patient_id: str,
    schema: DemoEntitlementUpdate,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await HomeVisitService.set_demo_entitlement(
        patient_id,
        str(current_user.id),
        schema.active,
    )


@router.post("/home-visit-requests", response_model=HomeVisitRequestOut, status_code=status.HTTP_201_CREATED)
async def create_home_visit_request(
    schema: HomeVisitRequestCreate,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.create_request(str(current_user.id), schema)


@router.get("/home-visit-bookings/availability", response_model=AppointmentAvailabilityOut)
async def get_home_visit_booking_availability(
    doctor_id: str,
    appointment_date: date,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.get_booking_availability(
        str(current_user.id),
        doctor_id,
        appointment_date,
    )


@router.post("/home-visit-bookings", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
async def create_home_visit_booking(
    schema: HomeVisitBookingCreate,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.create_booking(str(current_user.id), schema)


@router.patch("/home-visit-bookings/admin/{appointment_id}/doctor", response_model=AppointmentOut)
async def assign_home_visit_doctor(
    appointment_id: str,
    schema: HomeVisitDoctorAssignment,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await HomeVisitService.assign_booking_doctor(
        appointment_id,
        schema.doctor_id,
        str(current_user.id),
    )


@router.get("/home-visit-requests/me", response_model=list[HomeVisitRequestOut])
async def list_own_home_visit_requests(
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.list_patient_requests(str(current_user.id))


@router.post("/home-visit-requests/{request_id}/withdraw", response_model=HomeVisitRequestOut)
async def withdraw_home_visit_request(
    request_id: str,
    current_user: User = Depends(RoleChecker(["patient"])),
):
    return await HomeVisitService.withdraw_request(request_id, str(current_user.id))


@router.get("/home-visit-requests/admin", response_model=list[HomeVisitRequestOut])
async def list_admin_home_visit_requests(
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await HomeVisitService.list_admin_requests()


@router.patch("/home-visit-requests/admin/{request_id}", response_model=HomeVisitRequestOut)
async def review_home_visit_request(
    request_id: str,
    schema: HomeVisitRequestStatusUpdate,
    current_user: User = Depends(RoleChecker(["admin"])),
):
    return await HomeVisitService.review_request(
        request_id,
        str(current_user.id),
        schema.status,
    )


@router.get("/home-visit-requests/reception", response_model=list[ReceptionHomeVisitRequestOut])
async def list_reception_home_visit_requests(
    current_user: User = Depends(RoleChecker(["receptionist"])),
):
    return await HomeVisitService.list_reception_requests()


@router.get("/home-visit-requests/doctor", response_model=list[DoctorHomeVisitRequestOut])
async def list_doctor_home_visit_requests(
    current_user: User = Depends(RoleChecker(["doctor"])),
):
    return await HomeVisitService.list_doctor_requests(str(current_user.id))
