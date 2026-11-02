"""Offline query contracts for Phase 23D analytics and schedule windows."""

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

from beanie import PydanticObjectId
import pytest

from app.core.appointment_time import booking_window, clinic_start_to_utc_naive
from app.core.config import settings
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.home_visit_query_repository import HomeVisitQueryRepository
from app.repositories.profile_repository import ProfileRepository
from app.services.analytics_service import AnalyticsService
from app.services.appointment_service import AppointmentService
from app.services.clinician_schedule_service import ClinicianScheduleService
from app.services.home_visit_service import HomeVisitService


DOCTOR_ID = PydanticObjectId('507f1f77bcf86cd799439013')


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        assert length is None or length >= len(self.rows)
        return self.rows


@pytest.mark.asyncio
async def test_schedule_query_filters_doctor_status_and_bounded_calendar_window(monkeypatch):
    target = date(2027, 1, 10)
    slot = clinic_start_to_utc_naive(target, '09:00 AM')
    collection = Mock()
    collection.find.return_value = Cursor([{
        '_id': PydanticObjectId('507f1f77bcf86cd799439014'),
        'starts_at': slot,
        'appointment_date': datetime.combine(target, time.min),
        'time_slot': '09:00 AM',
    }])
    monkeypatch.setattr(Appointment, 'get_pymongo_collection', Mock(return_value=collection))
    records = await AppointmentRepository.list_active_by_doctor_id(str(DOCTOR_ID), target, target)
    assert len(records) == 1
    assert records[0].starts_at == slot
    assert records[0].service_mode == 'clinic'
    query, projection = collection.find.call_args.args
    assert query['doctor_id'] == DOCTOR_ID
    assert query['status'] == {'$in': ['scheduled', 'in_progress']}
    assert query['$or'][0]['starts_at']['$gte'] <= slot < query['$or'][0]['starts_at']['$lt']
    assert query['$or'][1]['appointment_date']['$gte'] == datetime(2027, 1, 9)
    assert query['$or'][1]['appointment_date']['$lt'] == datetime(2027, 1, 11)
    assert set(projection) == {'starts_at', 'appointment_date', 'time_slot', 'service_mode'}
    assert 'reason' not in projection and 'patient_id' not in projection


@pytest.mark.asyncio
async def test_conflict_check_keeps_all_records_in_relevant_day(monkeypatch):
    target = booking_window()[0] + timedelta(days=2)
    start = clinic_start_to_utc_naive(target, '09:00 AM')
    unrelated = [SimpleNamespace(id=index, starts_at=start + timedelta(hours=2),
                                 appointment_date=datetime.combine(target, time.min), time_slot='11:00 AM')
                 for index in range(150)]
    conflict = SimpleNamespace(id='last', starts_at=start,
                               appointment_date=datetime.combine(target, time.min), time_slot='09:00 AM')
    lookup = AsyncMock(return_value=[*unrelated, conflict])
    monkeypatch.setattr(AppointmentRepository, 'list_active_by_doctor_id', lookup)
    assert await AppointmentService._is_slot_occupied(str(DOCTOR_ID), start) is True
    lookup.assert_awaited_once_with(str(DOCTOR_ID), target, target)


@pytest.mark.asyncio
async def test_availability_requests_only_selected_day(monkeypatch):
    target = booking_window()[0] + timedelta(days=2)
    lookup = AsyncMock(return_value=[])
    monkeypatch.setattr(AppointmentRepository, 'list_active_by_doctor_id', lookup)
    monkeypatch.setattr(ProfileRepository, 'get_doctor_by_id', AsyncMock(return_value=SimpleNamespace(id=DOCTOR_ID)))
    monkeypatch.setattr(ClinicianScheduleService, 'effective_slots', AsyncMock(return_value=(['09:00 AM'], True)))
    result = await AppointmentService.get_availability(str(DOCTOR_ID), target)
    assert result.slots[0].available is True
    lookup.assert_awaited_once_with(str(DOCTOR_ID), target, target)


@pytest.mark.asyncio
async def test_legacy_local_midnight_still_blocks_same_day_slot(monkeypatch):
    target = booking_window()[0] + timedelta(days=2)
    legacy_utc_midnight = datetime.combine(target, time.min, tzinfo=ZoneInfo(settings.CLINIC_TIMEZONE))
    legacy_utc_midnight = legacy_utc_midnight.astimezone(timezone.utc).replace(tzinfo=None)
    appointment = SimpleNamespace(
        id=PydanticObjectId(), starts_at=None,
        appointment_date=legacy_utc_midnight, time_slot='09:00 AM',
    )
    lookup = AsyncMock(return_value=[appointment])
    monkeypatch.setattr(AppointmentRepository, 'list_active_by_doctor_id', lookup)
    monkeypatch.setattr(ProfileRepository, 'get_doctor_by_id', AsyncMock(return_value=SimpleNamespace(id=DOCTOR_ID)))
    monkeypatch.setattr(ClinicianScheduleService, 'effective_slots', AsyncMock(return_value=(['09:00 AM'], True)))
    result = await AppointmentService.get_availability(str(DOCTOR_ID), target)
    assert result.slots[0].availability_state == 'occupied'
    lookup.assert_awaited_once_with(str(DOCTOR_ID), target, target)


@pytest.mark.asyncio
async def test_home_visit_availability_uses_selected_day_for_each_doctor(monkeypatch):
    target = booking_window()[0] + timedelta(days=2)
    observed = []
    async def contexts(appointment_date):
        observed.append(appointment_date)
        yield SimpleNamespace(id=DOCTOR_ID, schedule=None, appointments=[])
    monkeypatch.setattr(HomeVisitService, '_entitled_patient', AsyncMock(return_value=object()))
    monkeypatch.setattr(HomeVisitQueryRepository, 'iter_clinician_contexts', contexts)
    result = await HomeVisitService.get_booking_availability(
        'fictional-user', HomeVisitService.NO_PREFERENCE_DOCTOR_ID, target,
    )
    assert result.slots == []
    assert observed == [target]


class CountQuery:
    def __init__(self, count):
        self.value = count

    async def count(self):
        return self.value


class AppointmentCollection:
    def __init__(self, records):
        self.records = records
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        match = pipeline[0]['$match']
        if '$facet' in pipeline[-1]:
            period = match['appointment_date']
            records = [item for item in self.records if period['$gte'] <= item['appointment_date'] <= period['$lte']]
            boundaries = pipeline[-1]['$facet']['weeks'][0]['$bucket']['boundaries']
            weeks = []
            for start, end in zip(boundaries, boundaries[1:]):
                count = sum(start <= item['appointment_date'] < end for item in records)
                if count: weeks.append({'_id': start, 'count': count})
            statuses = Counter(item['status'] for item in records)
            return Cursor([{
                'summary': ([{
                    'count': len(records),
                    'cancelled': statuses['cancelled'],
                    'paid': sum(item['billing_amount'] for item in records if item['billing_status'] == 'paid'),
                }] if records else []),
                'weeks': weeks,
                'statuses': [{'_id': name, 'count': count} for name, count in statuses.items()],
            }])
        dates = match['appointment_date']
        monthly = Counter()
        for item in self.records:
            if (item['billing_status'] == 'paid'
                and dates['$gte'] <= item['appointment_date'] < dates['$lt']):
                monthly[item['appointment_date'].strftime('%Y-%m')] += item['billing_amount']
        return Cursor([{'_id': month, 'revenue': total} for month, total in monthly.items()])


class DoctorCollection:
    def __init__(self, specializations):
        self.specializations = specializations
        self.pipelines = []

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        counts = Counter(self.specializations)
        return Cursor([{'_id': name, 'count': count} for name, count in counts.items()])


@pytest.mark.asyncio
@pytest.mark.parametrize('large', [False, True])
async def test_analytics_aggregates_in_database_without_loading_collections(monkeypatch, large):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            fixed = cls(2027, 1, 31, 12, 0, tzinfo=timezone.utc)
            return fixed if tz else fixed.replace(tzinfo=None)

    monkeypatch.setattr('app.services.analytics_service.datetime', FixedDateTime)
    now = FixedDateTime.now().replace(tzinfo=None)
    records = []
    if large:
        records.extend({'appointment_date': datetime(2025, 1, 1), 'status': 'completed',
                        'billing_status': 'paid', 'billing_amount': 50.0} for _ in range(1200))
    records += [
        {'appointment_date': now - timedelta(days=2), 'status': 'completed', 'billing_status': 'paid', 'billing_amount': 125.0},
        {'appointment_date': now - timedelta(days=4), 'status': 'cancelled', 'billing_status': 'pending', 'billing_amount': 90.0},
    ] if large else []
    appointment_collection = AppointmentCollection(records)
    doctor_collection = DoctorCollection(['Sports', 'Sports', None] if large else [])
    monkeypatch.setattr(Appointment, 'get_pymongo_collection', Mock(return_value=appointment_collection))
    monkeypatch.setattr(Doctor, 'get_pymongo_collection', Mock(return_value=doctor_collection))
    monkeypatch.setattr(Appointment, 'find_all', Mock(return_value=CountQuery(len(records))))
    monkeypatch.setattr(Doctor, 'find_all', Mock(return_value=CountQuery(len(doctor_collection.specializations))))
    monkeypatch.setattr(User, 'find', Mock(return_value=CountQuery(1 if large else 0)))
    monkeypatch.setattr(Patient, 'find', Mock(return_value=CountQuery(2 if large else 0)))
    monkeypatch.setattr(Patient, 'count', AsyncMock(return_value=3 if large else 0))

    stats = await AnalyticsService.get_clinic_stats(days=30)
    assert stats['total_appointments'] == len(records)
    assert stats['period_appointments'] == (2 if large else 0)
    assert stats['recorded_paid_total'] == (125.0 if large else 0)
    assert stats['cancellation_rate'] == (50.0 if large else 0)
    assert stats['status_counts'] == ({'completed': 1, 'cancelled': 1} if large else {})
    assert stats['total_doctors'] == (3 if large else 0)
    assert stats['doctor_specializations'] == ([
        {'name': 'Sports', 'value': 2}, {'name': 'Not specified', 'value': 1},
    ] if large else [])
    assert len(stats['appointments_per_week']) == 5
    assert len(stats['revenue_trend']) == 6
    assert appointment_collection.pipelines[0][0]['$match']['appointment_date']['$gte'] == now - timedelta(days=30)
    assert appointment_collection.pipelines[1][0]['$match']['billing_status'] == 'paid'
    assert doctor_collection.pipelines[0][0]['$group']['_id'] == '$specialization'
