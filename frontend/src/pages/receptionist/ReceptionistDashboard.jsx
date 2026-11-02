import { fetchClinicalPage } from '../../services/clinicalPagination';
import ClinicalPageNav from '../../components/common/ClinicalPageNav';
import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Button from '../../components/common/Button';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';

export default function ReceptionistDashboard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [schedulePage, setSchedulePage] = useState(1);
  const [requestPage, setRequestPage] = useState(1);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const scheduleParams = new URLSearchParams();
  if (startDate) scheduleParams.set('start_date', startDate);
  if (endDate) scheduleParams.set('end_date', endDate);
  const schedulePath = `/appointments/reception${scheduleParams.size ? `?${scheduleParams}` : ''}`;
  const { data: schedule, isLoading, error, refetch } = useQuery({
    queryKey: ['receptionSchedule', schedulePage, startDate, endDate],
    queryFn: () => fetchClinicalPage(schedulePath, schedulePage),
    gcTime: 0,
  });
  const summary = useQuery({
    queryKey: ['receptionScheduleSummary', startDate, endDate],
    queryFn: async ({ signal }) => (await api.get('/appointments/reception/summary', {
      params: { start_date: startDate || undefined, end_date: endDate || undefined }, signal,
    })).data,
    gcTime: 0,
  });
  const homeRequests = useQuery({
    queryKey: ['receptionHomeVisitRequests', requestPage],
    queryFn: () => fetchClinicalPage('/home-visit-requests/reception', requestPage),
    gcTime: 0,
  });
  const cancelMutation = useMutation({
    mutationFn: async (appointmentId) => (
      await api.post(`/appointments/reception/${appointmentId}/cancel`)
    ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['receptionSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['receptionScheduleSummary'] });
      queryClient.invalidateQueries({ queryKey: ['appointmentAvailability'] });
    },
  });

  const appointments = schedule?.data || [];
  const requests = homeRequests.data?.data || [];

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">calendar_month</span>Reception workspace</span>
        <h1>Appointment schedule</h1>
        <p>Coordinate active appointments using minimum necessary contact information.</p>
        <Button onClick={() => navigate('/reception/appointment-booking')}>Book appointment</Button>
      </header>

      <div className="portal-trust-note" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">shield_lock</span>
        <span>Clinical reasons, treatment history, billing, subscriptions, analytics, staff administration, and security settings are restricted.</span>
      </div>

      {cancelMutation.isError && (
        <div className="patient-booking__submit-error" role="alert">
          {cancelMutation.error?.response?.data?.detail || 'The appointment was not cancelled.'}
        </div>
      )}
      <div className="flex flex-wrap gap-3" aria-label="Reception schedule dates">
        <label>From <input type="date" value={startDate} max={endDate || undefined} onChange={(event) => { setStartDate(event.target.value); setSchedulePage(1); }} /></label>
        <label>Through <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setSchedulePage(1); }} /></label>
      </div>

      <section className="portal-section-card" aria-labelledby="reception-schedule-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Active schedule</span>
            <h2 id="reception-schedule-heading" className="font-headline-md text-headline-md">Scheduled and in-progress appointments</h2>
          </div>
          <span className="portal-count-pill">{summary.data?.active_appointments ?? '—'} active appointments</span>
        </div>
        {summary.error && <ErrorState message="Could not load the active appointment count." onRetry={() => summary.refetch()} />}
        {error && <ErrorState message="Could not load the reception schedule." onRetry={() => refetch()} />}

        {isLoading ? <Skeleton variant="row" count={3} /> : error ? null : !appointments.length ? (
          <EmptyState title="No active appointments" message="New bookings will appear here without clinical notes or history." icon="event_available" />
        ) : (
          <div className="reception-schedule-grid">
            {appointments.map((appointment) => (
              <article key={appointment.id} className="portal-mobile-record">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-primary">{appointment.status.replace('_', ' ')}</p>
                  <h3 className="font-semibold text-on-surface">{appointment.patient_name}</h3>
                  <p className="text-sm text-on-surface-variant">With {appointment.doctor_name}</p>
                </div>
                <div className="portal-mobile-record__row"><span>Date</span><strong>{format(parseISO(appointment.appointment_date), 'EEE, MMM d, yyyy')}</strong></div>
                <div className="portal-mobile-record__row"><span>Time</span><strong>{appointment.time_slot} IST</strong></div>
                <div className="portal-mobile-record__row"><span>Email</span><strong className="break-all">{appointment.patient_email}</strong></div>
                <div className="portal-mobile-record__row"><span>Phone</span><strong>{appointment.patient_phone || 'Not provided'}</strong></div>
                <p className="text-xs text-on-surface-variant">{appointment.cancellation_message}</p>
                {appointment.status === 'scheduled' && (
                  <button
                    type="button"
                    onClick={() => cancelMutation.mutate(appointment.id)}
                    disabled={!appointment.can_reception_cancel || cancelMutation.isPending}
                    className="min-h-11 rounded-xl border border-error/30 text-error font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {cancelMutation.isPending ? 'Cancelling…' : 'Cancel appointment'}
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
        {!error && <ClinicalPageNav label="Reception schedule" page={schedulePage} onPageChange={setSchedulePage}
          isLoading={isLoading} itemCount={appointments.length} hasNext={schedule?.hasNext} />}
      </section>

      <section className="portal-section-card" aria-labelledby="reception-home-requests-heading">
        <div className="portal-section-card__header">
          <div><span className="portal-section__eyebrow">Home-visit coordination</span><h2 id="reception-home-requests-heading" className="font-headline-md text-headline-md">Clinic-approved requests</h2></div>
          <span className="portal-count-pill">{requests.length} on this page</span>
        </div>
        {homeRequests.error && <ErrorState message="Could not load approved home-visit requests." onRetry={() => homeRequests.refetch()} />}
        {homeRequests.isLoading ? <Skeleton variant="row" count={2} /> : homeRequests.error ? null : !requests.length ? (
          <div className="p-6"><EmptyState title="No requests ready for coordination" message="Only clinic-approved requests appear here. They are not confirmed visits and reserve no capacity." icon="home_health" /></div>
        ) : (
          <div className="reception-schedule-grid">
            {requests.map((request) => <article key={request.id} className="portal-mobile-record">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">Approved for coordination</p><h3 className="font-semibold">{request.patient_name}</h3><p className="text-sm text-on-surface-variant">Preferred: {request.preferred_doctor_name}</p></div>
              <div className="portal-mobile-record__row"><span>Email</span><strong className="break-all">{request.patient_email}</strong></div>
              <div className="portal-mobile-record__row"><span>Phone</span><strong>{request.patient_phone || 'Not provided'}</strong></div>
              <div className="portal-mobile-record__row"><span>Address</span><strong>{request.home_address}</strong></div>
              <p className="text-sm text-on-surface-variant">{request.confirmation_message}</p>
            </article>)}
          </div>
        )}
        {!homeRequests.error && <ClinicalPageNav label="Reception home-visit requests" page={requestPage} onPageChange={setRequestPage}
          isLoading={homeRequests.isLoading} itemCount={requests.length} hasNext={homeRequests.data?.hasNext} />}
      </section>
    </div>
  );
}
