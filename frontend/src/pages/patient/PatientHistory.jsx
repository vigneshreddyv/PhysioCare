import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { format, parseISO } from 'date-fns';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';
import Modal from '../../components/common/Modal';
import Button from '../../components/common/Button';
import PatientIcon from '../../components/common/PatientIcon';

const FILTERS = [
  { value: 'upcoming', label: 'Upcoming', statuses: ['scheduled', 'in_progress'] },
  { value: 'completed', label: 'Completed', statuses: ['completed'] },
  { value: 'cancelled', label: 'Cancelled', statuses: ['cancelled'] },
];

function visitTimestamp(appointment) {
  return new Date(appointment.starts_at || `${appointment.appointment_date}T00:00:00`).getTime();
}

function visitDate(appointment) {
  try {
    return format(parseISO(appointment.appointment_date), 'EEEE, MMMM d, yyyy');
  } catch {
    return appointment.appointment_date;
  }
}

function clinicianName(appointment) {
  if (appointment.doctor_assignment_pending) return 'Doctor assignment pending';
  const name = appointment.doctor_name?.replace(/^Dr\.\s*/i, '').trim();
  return name ? `Dr. ${name}` : 'Clinician details pending';
}

function statusLabel(status) {
  if (status === 'in_progress') return 'In progress';
  return status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Scheduled';
}

function AppointmentRecord({ appointment, onCancel, cancelPending }) {
  const isHomeVisit = appointment.service_mode === 'home_visit';
  const isScheduled = appointment.status === 'scheduled';
  const canCancelClinic = !isHomeVisit && isScheduled && appointment.can_patient_cancel;

  return (
    <article className={`patient-visit-record patient-visit-record--${appointment.status || 'scheduled'}`}>
      <div className="patient-visit-record__topline">
        <span className={`patient-status-pill patient-status-pill--${appointment.status === 'completed' ? 'confirmed' : appointment.status === 'cancelled' ? 'cancelled' : 'pending'}`}>
          {statusLabel(appointment.status)}
        </span>
        <span className="patient-visit-record__mode">
          <PatientIcon name={isHomeVisit ? 'visit' : 'clinic'} size={16} />
          {isHomeVisit ? 'Home visit' : 'Clinic visit'}
        </span>
      </div>

      <div className="patient-visit-record__main">
        <span className="patient-visit-record__date-icon"><PatientIcon name="calendar" size={22} /></span>
        <div>
          <h2>{visitDate(appointment)}</h2>
          <p>{appointment.time_slot} IST</p>
        </div>
      </div>

      <dl className="patient-visit-record__details">
        <div>
          <dt>Physiotherapist</dt>
          <dd>{clinicianName(appointment)}</dd>
        </div>
        <div>
          <dt>Location</dt>
          <dd>{isHomeVisit ? `Home visit${appointment.city ? ` · ${appointment.city}` : ''}` : 'PhysioCare clinic'}</dd>
        </div>
      </dl>

      {appointment.reason && (
        <div className="patient-visit-record__reason">
          <span>Visit note</span>
          <p>{appointment.reason}</p>
        </div>
      )}

      {isScheduled && (
        <div className="patient-visit-record__action">
          {isHomeVisit ? (
            <p>Contact the clinic to change or cancel this home visit.</p>
          ) : canCancelClinic ? (
            <>
              <p>{appointment.cancellation_message || 'Online cancellation is available until 24 hours before this appointment.'}</p>
              <button type="button" onClick={() => onCancel(appointment)} disabled={cancelPending}>
                {cancelPending ? 'Cancelling…' : 'Cancel appointment'}
              </button>
            </>
          ) : (
            <p>{appointment.cancellation_message || 'Contact the clinic if you need help changing this appointment.'}</p>
          )}
        </div>
      )}
    </article>
  );
}

export default function PatientHistory() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState('upcoming');
  const [cancelTarget, setCancelTarget] = useState(null);
  const [notice, setNotice] = useState('');
  const {
    data: appointments = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['patientAppointments'],
    queryFn: async () => (await api.get('/appointments')).data,
  });

  const cancelMutation = useMutation({
    mutationFn: async (appointmentId) => (await api.post(`/appointments/${appointmentId}/cancel`)).data,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['patientAppointments'] }),
        queryClient.invalidateQueries({ queryKey: ['appointments'] }),
        queryClient.invalidateQueries({ queryKey: ['patientHistory'] }),
      ]);
      setCancelTarget(null);
      setNotice('Your clinic appointment has been cancelled.');
    },
  });

  const groupedAppointments = useMemo(() => Object.fromEntries(FILTERS.map((option) => {
    const matching = appointments.filter((appointment) => option.statuses.includes(appointment.status));
    matching.sort((left, right) => (
      option.value === 'upcoming'
        ? visitTimestamp(left) - visitTimestamp(right)
        : visitTimestamp(right) - visitTimestamp(left)
    ));
    return [option.value, matching];
  })), [appointments]);

  const activeAppointments = groupedAppointments[filter] || [];
  const cancellationError = cancelMutation.error?.response?.data?.detail
    || (cancelMutation.isError ? 'We could not cancel this appointment. Refresh and try again.' : '');

  const openCancellation = (appointment) => {
    setNotice('');
    cancelMutation.reset();
    setCancelTarget(appointment);
  };

  if (error) {
    return (
      <div className="patient-page patient-history__error">
        <ErrorState message="We could not load your appointments." onRetry={() => refetch()} />
      </div>
    );
  }

  return (
    <div className="patient-page patient-history patient-history--managed animate-fade-in pb-16">
      {notice && <div className="patient-history__notice" role="status" aria-live="polite"><PatientIcon name="check" size={20} />{notice}</div>}

      <header className="patient-history__hero" data-patient-reveal>
        <Link to="/patient/dashboard" className="patient-history__back"><PatientIcon name="back" size={18} /> Home</Link>
        <div>
          <p className="patient-page__eyebrow">Your appointments</p>
          <h1>Care schedule</h1>
          <p>Review upcoming visits and keep a clear record of completed or cancelled care.</p>
        </div>
      </header>

      <section className="patient-history__workspace" aria-labelledby="appointments-heading" data-patient-reveal>
        <div className="patient-history__section-heading patient-history__section-heading--managed">
          <div><p>Appointments</p><h2 id="appointments-heading">Your visit timeline</h2></div>
          {!isLoading && <span className="patient-history__total">{appointments.length} total</span>}
        </div>

        <div className="patient-history__filters patient-history__filters--managed" role="tablist" aria-label="Appointment status">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={filter === option.value}
              className="patient-history__filter"
              onClick={() => setFilter(option.value)}
            >
              <span>{option.label}</span>
              <strong>{groupedAppointments[option.value]?.length || 0}</strong>
            </button>
          ))}
        </div>

        <div role="tabpanel" aria-label={`${FILTERS.find((option) => option.value === filter)?.label} appointments`}>
          {isLoading ? (
            <div className="patient-history__loading"><Skeleton variant="row" count={3} /></div>
          ) : activeAppointments.length === 0 ? (
            <div className="patient-history__empty patient-history__empty--managed">
              <EmptyState
                title={`No ${filter} appointments`}
                message={filter === 'upcoming'
                  ? 'When you book a clinic or home visit, its confirmed time will appear here.'
                  : `Your ${filter} appointments will appear here.`}
                icon={filter === 'completed' ? 'check_circle' : filter === 'cancelled' ? 'event_busy' : 'event_available'}
              />
            </div>
          ) : (
            <div className="patient-history__records">
              {activeAppointments.map((appointment) => (
                <AppointmentRecord
                  key={appointment.id}
                  appointment={appointment}
                  onCancel={openCancellation}
                  cancelPending={cancelMutation.isPending && cancelTarget?.id === appointment.id}
                />
              ))}
            </div>
          )}
        </div>
      </section>

      <Modal
        isOpen={Boolean(cancelTarget)}
        onClose={() => { if (!cancelMutation.isPending) setCancelTarget(null); }}
        title="Cancel clinic appointment?"
      >
        {cancelTarget && (
          <div className="patient-history__cancel-dialog">
            <p>Cancel your clinic appointment with {clinicianName(cancelTarget)} on {visitDate(cancelTarget)} at {cancelTarget.time_slot}?</p>
            <div className="patient-history__cancel-policy">
              Online cancellation is available until exactly 24 hours before a clinic appointment. Inside that window, contact the clinic. No automatic cancellation fee is applied.
            </div>
            {cancellationError && <div role="alert" className="patient-history__cancel-error">{cancellationError}</div>}
            <div className="patient-history__cancel-actions">
              <Button type="button" variant="outline" onClick={() => setCancelTarget(null)} disabled={cancelMutation.isPending}>Keep appointment</Button>
              <Button type="button" variant="danger" onClick={() => cancelMutation.mutate(cancelTarget.id)} disabled={cancelMutation.isPending}>
                {cancelMutation.isPending ? 'Cancelling…' : 'Confirm cancellation'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
