from datetime import datetime

import pytest
from beanie import PydanticObjectId
from pydantic import ValidationError

from app.models.appointment import Appointment


def make_appointment(monkeypatch, **overrides):
    monkeypatch.setattr(
        Appointment,
        "get_pymongo_collection",
        classmethod(lambda cls: None),
    )
    values = {
        "patient_id": PydanticObjectId(),
        "doctor_id": PydanticObjectId(),
        "appointment_date": datetime(2026, 10, 27),
        "time_slot": "10:00 AM",
        "reason": "Physiotherapy assessment",
    }
    values.update(overrides)
    return Appointment(**values)


def test_none_symptoms_normalize_to_empty_list(monkeypatch):
    appointment = make_appointment(monkeypatch, symptoms=None)

    assert appointment.symptoms == []


def test_missing_symptoms_use_empty_list_default(monkeypatch):
    appointment = make_appointment(monkeypatch)

    assert appointment.symptoms == []


def test_symptoms_still_requires_a_list(monkeypatch):
    with pytest.raises(ValidationError):
        make_appointment(monkeypatch, symptoms="Pain")
