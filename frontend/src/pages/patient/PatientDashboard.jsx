import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import PatientIcon from '../../components/common/PatientIcon';
import { format, parseISO } from 'date-fns';

export default function PatientDashboard() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [cancelTarget, setCancelTarget] = useState(null);
  const [cancellationNotice, setCancellationNotice] = useState('');
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'there';
  const initials = user?.full_name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'PC';

  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['patientAppointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  const labRequests = useQuery({
    queryKey: ['myLabRequests'],
    queryFn: async () => (await api.get('/lab-requests/me')).data,
  });
  const homeRequests = useQuery({
    queryKey: ['myHomeVisitRequests'],
    queryFn: async () => (await api.get('/home-visit-requests/me')).data,
  });

  const cancelMutation = useMutation({
    mutationFn: async (appointmentId) => {
      const response = await api.post(`/appointments/${appointmentId}/cancel`);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['appointments'] }),
        queryClient.invalidateQueries({ queryKey: ['patientAppointments'] }),
        queryClient.invalidateQueries({ queryKey: ['patientHistory'] }),
      ]);
      setCancelTarget(null);
      setCancellationNotice('Your appointment is now marked cancelled.');
    },
  });

  const cancellationError = cancelMutation.error?.response?.data?.detail
    || (cancelMutation.isError ? 'The appointment could not be cancelled. Refresh and try again.' : '');

  const openCancellation = (appointment) => {
    setCancellationNotice('');
    cancelMutation.reset();
    setCancelTarget(appointment);
  };

  if (error) {
    return (
      <div className="patient-dashboard patient-dashboard--benchmark animate-fade-in pb-16">
        <header className="patient-home-welcome">
          <div className="patient-home-welcome__copy">
            <p>Welcome back</p>
            <h1>Good to see you, {firstName}.</h1>
            <span>We could not load your care overview.</span>
          </div>
          <div className="patient-home-welcome__avatar" aria-hidden="true">{initials}</div>
        </header>
        <section className="patient-home-section patient-home-error" role="alert">
          <span className="patient-home-error__icon"><PatientIcon name="pending" size={26} /></span>
          <div><p>Connection problem</p><h2>Your dashboard is temporarily unavailable</h2><span>No appointment or request was changed. Check your connection and try again.</span></div>
          <button type="button" onClick={() => refetch()}>Try again</button>
        </section>
      </div>
    );
  }

  // Filter appointments: upcoming (scheduled or in-progress) vs past (completed or cancelled)
  const upcoming = appointments?.filter(
    (a) => a.status === 'scheduled' || a.status === 'in_progress'
  ).sort((left, right) => (
    new Date(left.starts_at || left.appointment_date)
    - new Date(right.starts_at || right.appointment_date)
  )) || [];
  const nextAppointment = upcoming[0];
  const laterAppointments = upcoming.slice(1);
  const requestUpdates = [
    ...(labRequests.data || []).map((item) => ({ ...item, kind: 'Laboratory request', to: '/patient/laboratory', icon: 'lab' })),
    ...(homeRequests.data || []).map((item) => ({ ...item, kind: 'Home-visit request', to: '/patient/home-visits', icon: 'visit' })),
  ].sort((left, right) => new Date(right.updated_at || right.created_at) - new Date(left.updated_at || left.created_at));
  const latestRequest = requestUpdates[0];
  const requestStatus = (value = '') => value.replaceAll('_', ' ');

  return (
    <div className="patient-dashboard patient-dashboard--benchmark animate-fade-in pb-16">
      {cancellationNotice && (
        <div className="patient-dashboard__notice" role="status" aria-live="polite">
          <PatientIcon name="check" size={20} />
          {cancellationNotice}
        </div>
      )}
      <header className="patient-home-welcome" data-patient-reveal>
        <div className="patient-home-welcome__copy">
          <p>Welcome back</p>
          <h1>Good to see you, {firstName}.</h1>
          <span>What would you like help with today?</span>
        </div>
        <div className="patient-home-welcome__avatar" aria-hidden="true">{initials}</div>
      </header>

      <section className="patient-home-section patient-home-next" aria-labelledby="patient-next-heading" data-patient-reveal>
        <div className="patient-home-section__heading">
          <div><p>Next for you</p><h2 id="patient-next-heading">Your care at a glance</h2></div>
          <Link to="/patient/history">View history</Link>
        </div>
        {isLoading ? (
          <div className="patient-home-next__loading" role="status" aria-live="polite" aria-label="Loading your next care item">
            <span className="patient-home-skeleton patient-home-skeleton--pill" />
            <div><span className="patient-home-skeleton patient-home-skeleton--icon" /><span><i className="patient-home-skeleton patient-home-skeleton--title" /><i className="patient-home-skeleton patient-home-skeleton--line" /></span></div>
            <span className="sr-only">Loading your next care item</span>
          </div>
        ) : nextAppointment ? (
          <article className="patient-home-focus patient-home-focus--appointment">
            <div className="patient-home-focus__topline">
              <span className={`patient-status-pill patient-status-pill--${nextAppointment.status === 'in_progress' ? 'pending' : 'confirmed'}`}>
                {nextAppointment.status === 'in_progress' ? 'Visit in progress' : nextAppointment.service_mode === 'home_visit' ? 'Confirmed home visit' : 'Confirmed clinic visit'}
              </span>
              <span>{nextAppointment.service_mode === 'home_visit' ? 'Home' : 'Clinic'}</span>
            </div>
            <div className="patient-home-focus__main">
              <span className="patient-home-focus__icon"><PatientIcon name="calendar" size={24} /></span>
              <div><h3>{format(parseISO(nextAppointment.appointment_date), 'EEEE, MMMM d')}</h3><p>{nextAppointment.time_slot} IST with Dr. {nextAppointment.doctor_name}</p></div>
            </div>
            <div className="patient-home-focus__actions">
              <Link to="/patient/history">View details <PatientIcon name="arrow" size={18} /></Link>
              {nextAppointment.status === 'scheduled' && nextAppointment.can_patient_cancel && (
                <button type="button" onClick={() => openCancellation(nextAppointment)}>Cancel appointment</button>
              )}
            </div>
            {nextAppointment.status === 'scheduled' && !nextAppointment.can_patient_cancel && nextAppointment.cancellation_message && (
              <p className="patient-home-focus__policy">{nextAppointment.cancellation_message}</p>
            )}
          </article>
        ) : latestRequest ? (
          <article className="patient-home-focus patient-home-focus--request">
            <div className="patient-home-focus__topline">
              <span className="patient-status-pill patient-status-pill--pending">{requestStatus(latestRequest.status)}</span>
              <span>Request</span>
            </div>
            <div className="patient-home-focus__main">
              <span className="patient-home-focus__icon"><PatientIcon name="pending" size={24} /></span>
              <div><h3>{latestRequest.kind}</h3><p>Clinic review is still required. This is not a confirmed appointment.</p></div>
            </div>
            <div className="patient-home-focus__actions"><Link to={latestRequest.to}>Review request <PatientIcon name="arrow" size={18} /></Link></div>
          </article>
        ) : (
          <article className="patient-home-focus patient-home-focus--empty">
            <div className="patient-home-focus__main">
              <span className="patient-home-focus__icon"><PatientIcon name="calendar" size={24} /></span>
              <div><h3>No active appointment or request</h3><p>Choose a service when you are ready. Nothing has been submitted yet.</p></div>
            </div>
            <div className="patient-home-focus__actions"><Link to="/patient/services">Explore care options <PatientIcon name="arrow" size={18} /></Link></div>
          </article>
        )}
      </section>

      <section className="patient-home-section patient-home-start" aria-labelledby="patient-start-heading" data-patient-reveal>
        <div className="patient-home-section__heading">
          <div><p>Start here</p><h2 id="patient-start-heading">Choose a service</h2></div>
          <Link to="/patient/services">See all services</Link>
        </div>
        <nav className="patient-home-services" aria-label="Care services">
          <Link to="/patient/book" className="patient-home-service patient-home-service--clinic">
            <span className="patient-home-service__icon"><PatientIcon name="clinic" size={24} /></span>
            <div><strong>Clinic visit</strong><span>Choose a specialist and an available IST time.</span></div>
            <PatientIcon name="chevron" size={20} />
          </Link>
          <Link to="/patient/home-visits" className="patient-home-service patient-home-service--visit">
            <span className="patient-home-service__icon"><PatientIcon name="visit" size={24} /></span>
            <div><strong>Home visit</strong><span>Book an available home-visit time in Nellore.</span></div>
            <PatientIcon name="chevron" size={20} />
          </Link>
          <Link to="/patient/laboratory" className="patient-home-service patient-home-service--lab">
            <span className="patient-home-service__icon"><PatientIcon name="lab" size={24} /></span>
            <div><strong>Laboratory</strong><span>Demo catalogue; no checkout or confirmed collection.</span></div>
            <PatientIcon name="chevron" size={20} />
          </Link>
        </nav>
      </section>

      <section className="patient-home-section patient-dashboard__updates" aria-labelledby="patient-updates-heading" data-patient-reveal>
        <div className="patient-home-section__heading">
          <div><p>Recent activity</p><h2 id="patient-updates-heading">Clinic-review requests</h2></div>
        </div>
        {labRequests.isLoading || homeRequests.isLoading ? (
          <Skeleton variant="row" count={2} />
        ) : labRequests.isError || homeRequests.isError ? (
          <div className="patient-dashboard__inline-state" role="alert">
            <div><strong>Request updates are unavailable.</strong><span>Your existing requests have not changed.</span></div>
            <button type="button" onClick={() => { labRequests.refetch(); homeRequests.refetch(); }}>Try again</button>
          </div>
        ) : requestUpdates.length ? (
          <div className="patient-dashboard__update-list">
            {requestUpdates.slice(0, 3).map((item) => (
              <Link to={item.to} key={`${item.kind}-${item.id}`}>
                <span className="patient-dashboard__update-icon"><PatientIcon name={item.icon} size={20} /></span>
                <div><strong>{item.kind}</strong><small>{requestStatus(item.status)} · Not a confirmed appointment</small></div>
                <PatientIcon name="chevron" size={18} />
              </Link>
            ))}
          </div>
        ) : (
          <div className="patient-dashboard__inline-state"><div><strong>No clinic-review requests yet.</strong><span>Home and laboratory requests will appear here after submission.</span></div></div>
        )}
      </section>

      {laterAppointments.length > 0 && (
        <section className="patient-home-section patient-dashboard__care" aria-labelledby="upcoming-heading" data-patient-reveal>
          <div className="patient-home-section__heading">
            <div><p>Later</p><h2 id="upcoming-heading">More upcoming visits</h2></div>
            <Link to="/patient/history">View all</Link>
          </div>
          <div className="patient-dashboard__more-visits">
            {laterAppointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                displayRole="patient"
                onCancel={openCancellation}
                cancelPending={cancelMutation.isPending && cancelTarget?.id === appointment.id}
              />
            ))}
          </div>
        </section>
      )}

      <Modal
        isOpen={Boolean(cancelTarget)}
        onClose={() => {
          if (!cancelMutation.isPending) setCancelTarget(null);
        }}
        title="Cancel appointment?"
      >
        {cancelTarget && (
          <div className="space-y-5">
            <p className="text-on-surface">
              Cancel your appointment with Dr. {cancelTarget.doctor_name} on{' '}
              {format(parseISO(cancelTarget.appointment_date), 'EEEE, MMMM d, yyyy')} at {cancelTarget.time_slot}?
            </p>
            <div className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
              Online cancellation is available until exactly 24 hours before the appointment. Inside that window, contact the clinic for late changes or emergencies. This demo policy applies no automatic cancellation fee.
            </div>
            {cancellationError && (
              <div role="alert" className="rounded-xl border border-error/30 bg-error-container/20 p-4 text-sm text-error">
                {cancellationError}
              </div>
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCancelTarget(null)}
                disabled={cancelMutation.isPending}
              >
                Keep appointment
              </Button>
              <button
                type="button"
                onClick={() => cancelMutation.mutate(cancelTarget.id)}
                disabled={cancelMutation.isPending}
                className="rounded-xl bg-error px-4 py-3 font-semibold text-on-error disabled:cursor-not-allowed disabled:opacity-60"
              >
                {cancelMutation.isPending ? 'Cancelling…' : 'Confirm cancellation'}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
