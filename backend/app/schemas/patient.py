from pydantic import BaseModel
from typing import Optional


class SavedAddress(BaseModel):
    building_name: str
    door_number: str
    area: str
    street: str
    landmark: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class SavedAddressUpdate(BaseModel):
    building_name: str
    door_number: str
    area: str
    street: str
    landmark: str
    pincode: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class PatientOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    subscription_status: str
    saved_address: Optional[SavedAddress] = None


from typing import List

class RecentActivityOut(BaseModel):
    exercise_name: str
    completed_sets: int
    completed_reps: int
    completed_at: str
    completion_status: str
    notes: Optional[str] = None


class PatientMonitoringOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    active_program: Optional[str] = None
    current_stage: Optional[str] = None
    adherence_percentage: int
    last_activity: Optional[str] = None
    status: str
    recent_activity: List[RecentActivityOut] = []


class UpcomingAppointmentOut(BaseModel):
    doctor_name: str
    appointment_date: str
    time_slot: str
    status: str
    reason: Optional[str] = None


class PatientSnapshotOut(BaseModel):
    id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    subscription_status: str
    active_program: Optional[str] = None
    current_stage: Optional[str] = None
    adherence_percentage: int
    status: str
    recent_activity: List[RecentActivityOut] = []
    upcoming_appointment: Optional[UpcomingAppointmentOut] = None
    goals: List[dict] = []
    stages: List[dict] = []