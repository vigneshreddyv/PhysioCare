import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';
import AdminLabRequestsPanel from './AdminLabRequestsPanel';

export default function DemoServices() {
  const queryClient = useQueryClient();
  const [doctorChoices, setDoctorChoices] = useState({});
  const entitlements = useQuery({
    queryKey: ['demoEntitlements'],
    queryFn: async () => (await api.get('/demo-services/entitlements')).data,
  });
  const requests = useQuery({
    queryKey: ['adminHomeVisitRequests'],
    queryFn: async () => (await api.get('/home-visit-requests/admin')).data,
  });
  const appointments = useQuery({ queryKey: ['appointments'], queryFn: async () => (await api.get('/appointments')).data });
  const doctors = useQuery({ queryKey: ['doctors'], queryFn: async () => (await api.get('/users/doctors')).data });
  const entitlementMutation = useMutation({
    mutationFn: async ({ patientId, active }) => (await api.put(`/demo-services/patients/${patientId}/entitlement`, { active })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['demoEntitlements'] }),
  });
  const reviewMutation = useMutation({
    mutationFn: async ({ requestId, status }) => (await api.patch(`/home-visit-requests/admin/${requestId}`, { status })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['adminHomeVisitRequests'] }),
  });
  const assignDoctorMutation = useMutation({
    mutationFn: async ({ appointmentId, doctorId }) => (await api.patch(`/home-visit-bookings/admin/${appointmentId}/doctor`, { doctor_id: doctorId })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['appointments'] }),
  });

  if (entitlements.error || requests.error || appointments.error || doctors.error) return <ErrorState message="Could not load demo service controls." onRetry={() => { entitlements.refetch(); requests.refetch(); appointments.refetch(); doctors.refetch(); }} />;

  const homeBookings = (appointments.data || []).filter((appointment) => appointment.service_mode === 'home_visit' && appointment.status === 'scheduled');
  const homeVisitDoctors = (doctors.data || []).filter((doctor) => doctor.accepts_home_visits !== false);

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">science</span>Provisional demo</span>
        <h1>Demo access and home-visit requests</h1>
        <p>Grant reversible demonstration access and review patient requests without creating a paid subscription or scheduled visit.</p>
      </header>
      <div className="portal-trust-note" role="note"><span className="material-symbols-outlined" aria-hidden="true">payments</span><span><strong>Payments are unconfigured.</strong> No price, payment provider, charge, refund, coverage, service area, visit time, or capacity reservation is represented here.</span></div>

      <section className="portal-section-card" aria-labelledby="demo-entitlements-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Demo entitlements</span><h2 id="demo-entitlements-heading" className="font-headline-md text-headline-md">Home-request access</h2></div><span className="portal-count-pill">{entitlements.data?.length || 0} patients</span></div>
        {entitlements.isLoading ? <Skeleton variant="row" count={3} /> : !entitlements.data?.length ? <div className="p-6"><EmptyState title="No patient accounts" message="Demo access can be granted only to registered patient accounts." icon="person_off" /></div> : (
          <div className="reception-schedule-grid">
            {entitlements.data.map((item) => <article key={item.patient_id} className="portal-mobile-record">
              <div><h3 className="font-semibold">{item.patient_name}</h3><p className="text-sm text-on-surface-variant break-all">{item.patient_email}</p></div>
              <div className="portal-mobile-record__row"><span>Demo access</span><strong>{item.active ? 'Enabled' : 'Disabled'}</strong></div>
              <div className="portal-mobile-record__row"><span>Payment</span><strong>Not configured</strong></div>
              <button type="button" disabled={entitlementMutation.isPending} onClick={() => entitlementMutation.mutate({ patientId: item.patient_id, active: !item.active })} className="min-h-11 rounded-xl bg-primary text-on-primary font-semibold disabled:opacity-50">{item.active ? 'Revoke demo access' : 'Grant demo access'}</button>
            </article>)}
          </div>
        )}
      </section>

      <section className="portal-section-card" aria-labelledby="admin-home-bookings-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Confirmed visits</span><h2 id="admin-home-bookings-heading" className="font-headline-md text-headline-md">Home-visit clinician allocation</h2></div><span className="portal-count-pill">{homeBookings.length} visits</span></div>
        {appointments.isLoading || doctors.isLoading ? <Skeleton variant="row" count={3} /> : !homeBookings.length ? <div className="p-6"><EmptyState title="No confirmed home visits" message="Confirmed home visits will appear here for clinician allocation." icon="home_health" /></div> : (
          <div className="reception-schedule-grid">
            {homeBookings.map((booking) => {
              const selectedDoctorId = doctorChoices[booking.id] ?? booking.doctor_id ?? '';
              return <article key={booking.id} className="portal-mobile-record">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">{booking.doctor_assignment_pending ? 'Doctor assignment pending' : 'Clinician assigned'}</p><h3 className="font-semibold">{booking.patient_name}</h3><p className="text-sm text-on-surface-variant">{booking.appointment_date.slice(0, 10)} · {booking.time_slot} IST</p></div>
                <label>Physiotherapist<select value={selectedDoctorId} onChange={(event) => setDoctorChoices((current) => ({ ...current, [booking.id]: event.target.value }))}><option value="">Choose a physiotherapist</option>{homeVisitDoctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.full_name} · {doctor.specialization}</option>)}</select></label>
                {assignDoctorMutation.isError && assignDoctorMutation.variables?.appointmentId === booking.id && <p className="patient-booking__submit-error" role="alert">{assignDoctorMutation.error?.response?.data?.detail || 'The clinician assignment could not be saved.'}</p>}
                <button type="button" disabled={!selectedDoctorId || assignDoctorMutation.isPending} onClick={() => assignDoctorMutation.mutate({ appointmentId: booking.id, doctorId: selectedDoctorId })} className="min-h-11 rounded-xl bg-primary px-3 text-on-primary font-semibold disabled:opacity-50">{assignDoctorMutation.isPending && assignDoctorMutation.variables?.appointmentId === booking.id ? 'Saving…' : booking.doctor_assignment_pending ? 'Assign clinician' : 'Update assignment'}</button>
              </article>;
            })}
          </div>
        )}
      </section>

      <AdminLabRequestsPanel />

      <section className="portal-section-card" aria-labelledby="admin-home-requests-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Clinic review</span><h2 id="admin-home-requests-heading" className="font-headline-md text-headline-md">Home-visit requests</h2></div><span className="portal-count-pill">{requests.data?.length || 0} requests</span></div>
        {requests.isLoading ? <Skeleton variant="row" count={3} /> : !requests.data?.length ? <div className="p-6"><EmptyState title="No home-visit requests" message="Patient demo requests will appear here for clinic review." icon="home_health" /></div> : (
          <div className="reception-schedule-grid">
            {requests.data.map((request) => <article key={request.id} className="portal-mobile-record">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">{request.status.replaceAll('_', ' ')}</p><h3 className="font-semibold">{request.patient_name}</h3><p className="text-sm text-on-surface-variant">Preferred: {request.preferred_doctor_name}</p></div>
              <div className="portal-mobile-record__row"><span>Address</span><strong>{request.home_address}</strong></div>
              <div className="portal-mobile-record__row"><span>Reason</span><strong>{request.reason}</strong></div>
              <p className="text-sm text-on-surface-variant">{request.confirmation_message}</p>
              {request.status === 'pending_clinic_confirmation' && <div className="grid grid-cols-2 gap-2">
                <button type="button" disabled={reviewMutation.isPending} onClick={() => reviewMutation.mutate({ requestId: request.id, status: 'approved_for_coordination' })} className="min-h-11 rounded-xl bg-primary text-on-primary font-semibold disabled:opacity-50">Approve coordination</button>
                <button type="button" disabled={reviewMutation.isPending} onClick={() => reviewMutation.mutate({ requestId: request.id, status: 'declined' })} className="min-h-11 rounded-xl border border-error/30 text-error font-semibold disabled:opacity-50">Decline</button>
              </div>}
            </article>)}
          </div>
        )}
      </section>
    </div>
  );
}
