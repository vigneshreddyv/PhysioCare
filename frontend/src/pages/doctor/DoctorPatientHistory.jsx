import React, { useState } from 'react';
import { format, parseISO } from 'date-fns';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import { closePdfViewer, preparePdfViewer, showPdfBlob } from '../../utils/openPdfBlob';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';

const statusDetails = {
  scheduled: { label: 'Scheduled', icon: 'event_available' },
  in_progress: { label: 'In progress', icon: 'pending_actions' },
  completed: { label: 'Completed', icon: 'check_circle' },
  cancelled: { label: 'Cancelled', icon: 'cancel' },
  no_show: { label: 'No show', icon: 'person_off' },
};

const filters = [
  { key: 'all', label: 'All visits' },
  { key: 'active', label: 'Upcoming' },
  { key: 'completed', label: 'Completed' },
  { key: 'closed', label: 'Closed' },
];

function formatVisitDate(value) {
  try {
    return format(parseISO(value), 'EEE, d MMM yyyy');
  } catch {
    return 'Date unavailable';
  }
}

function calculateRecordedAge(dateValue) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateValue || '')) return null;
  const [birthYear, birthMonth, birthDay] = dateValue.split('-').map(Number);
  const indiaDateParts = Object.fromEntries(
    new Intl.DateTimeFormat('en', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
    }).formatToParts(new Date()).filter((part) => part.type !== 'literal').map((part) => [part.type, Number(part.value)]),
  );
  let age = indiaDateParts.year - birthYear;
  if (indiaDateParts.month < birthMonth || (indiaDateParts.month === birthMonth && indiaDateParts.day < birthDay)) age -= 1;
  return age >= 0 && age <= 130 ? age : null;
}

function matchesFilter(appointment, filter) {
  if (filter === 'active') return ['scheduled', 'in_progress'].includes(appointment.status);
  if (filter === 'completed') return appointment.status === 'completed';
  if (filter === 'closed') return ['cancelled', 'no_show'].includes(appointment.status);
  return true;
}

export default function DoctorPatientHistory() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const [filter, setFilter] = useState('all');
  const history = useQuery({
    queryKey: ['doctorPatientHistory', patientId],
    enabled: Boolean(patientId),
    queryFn: async () => (await api.get(`/users/doctor/patients/${patientId}/history`)).data,
  });
  const openReport = useMutation({
    mutationFn: async ({ report, viewer }) => {
      if (!viewer) throw new Error('The PDF viewer was blocked.');
      try {
        const response = await api.get(`/lab-requests/${report.request_id}/report-file`, { responseType: 'blob' });
        showPdfBlob(viewer, response.data);
      } catch (error) {
        closePdfViewer(viewer);
        throw error;
      }
    },
  });

  const appointments = history.data?.appointments || [];
  const reports = [...(history.data?.reports || [])].sort(
    (first, second) => Date.parse(second.report_released_at || 0) - Date.parse(first.report_released_at || 0),
  );
  const visibleAppointments = appointments.filter((appointment) => matchesFilter(appointment, filter));
  const completedCount = appointments.filter((item) => item.status === 'completed').length;
  const activeCount = appointments.filter((item) => ['scheduled', 'in_progress'].includes(item.status)).length;

  const pageBack = (
    <button type="button" className="doctor-history__back" onClick={() => navigate('/doctor/patients')}>
      <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
      Assigned patients
    </button>
  );

  if (history.isLoading) {
    return <div className="doctor-history">{pageBack}<Skeleton variant="card" count={3} /></div>;
  }

  if (history.error?.response?.status === 404) {
    return (
      <div className="doctor-history">
        {pageBack}
        <section className="portal-section-card p-6">
          <EmptyState
            title="Patient history is not available"
            message="This record is not in your assigned caseload. Return to your assigned patients."
            icon="shield_lock"
          />
        </section>
      </div>
    );
  }

  if (history.error) {
    return <div className="doctor-history">{pageBack}<ErrorState message="Could not load this assigned patient history." onRetry={() => history.refetch()} /></div>;
  }

  const patient = history.data.patient;
  const recordedAge = calculateRecordedAge(patient.date_of_birth);
  const initials = patient.full_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase();

  return (
    <div className="doctor-history animate-fade-in">
      {pageBack}

      <header className="doctor-history__patient">
        <div className="doctor-history__identity">
          <div className="doctor-history__avatar" aria-hidden="true">{initials}</div>
          <div>
            <span className="doctor-history__eyebrow">Assigned patient</span>
            <h1>{patient.full_name}</h1>
            <p>Appointment history and administratively published laboratory reports.</p>
          </div>
        </div>
        <dl className="doctor-history__contact">
          <div><dt>Phone</dt><dd>{patient.phone || 'Not provided'}</dd></div>
          <div><dt>Date of birth</dt><dd>{patient.date_of_birth || 'Not provided'}</dd></div>
          <div><dt>Age</dt><dd>{recordedAge === null ? 'Not available' : `${recordedAge} years`}</dd></div>
          <div><dt>Gender</dt><dd>{patient.gender || 'Not recorded'}</dd></div>
        </dl>
      </header>

      <div className="doctor-history__privacy" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">shield_lock</span>
        <span>This view contains only patients assigned to you. Use these details only for their care.</span>
      </div>

      <section className="doctor-history__summary" aria-label="Patient history summary">
        <div><strong>{appointments.length}</strong><span>Total visits</span></div>
        <div><strong>{activeCount}</strong><span>Upcoming</span></div>
        <div><strong>{completedCount}</strong><span>Completed</span></div>
        <div><strong>{reports.length}</strong><span>Published reports</span></div>
      </section>

      <section className="portal-section-card doctor-history__section" aria-labelledby="doctor-visit-history-heading">
        <div className="doctor-history__section-head">
          <div>
            <span className="portal-section__eyebrow">Care timeline</span>
            <h2 id="doctor-visit-history-heading">Appointment history</h2>
          </div>
          <span className="portal-count-pill">{visibleAppointments.length} visits</span>
        </div>
        <div className="doctor-history__filters" role="group" aria-label="Filter appointment history">
          {filters.map((item) => (
            <button
              type="button"
              key={item.key}
              aria-pressed={filter === item.key}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {!visibleAppointments.length ? (
          <EmptyState title="No visits in this view" message="Choose another history filter." icon="event_note" />
        ) : (
          <div className="doctor-history__timeline">
            {visibleAppointments.map((appointment) => {
              const status = statusDetails[appointment.status] || statusDetails.scheduled;
              const showHomeAddress = appointment.service_mode === 'home_visit'
                && ['scheduled', 'in_progress'].includes(appointment.status)
                && appointment.home_address;
              return (
                <article className="doctor-history__visit" key={appointment.id}>
                  <div className={`doctor-history__status doctor-history__status--${appointment.status}`}>
                    <span className="material-symbols-outlined" aria-hidden="true">{status.icon}</span>
                    {status.label}
                  </div>
                  <div className="doctor-history__visit-main">
                    <strong>{formatVisitDate(appointment.appointment_date)}</strong>
                    <span>{appointment.time_slot} IST · {appointment.service_mode === 'home_visit' ? 'Home visit' : 'Clinic visit'}</span>
                  </div>
                  {appointment.reason && <p className="doctor-history__reason">{appointment.reason}</p>}
                  {showHomeAddress && (
                    <p className="doctor-history__address">
                      <span className="material-symbols-outlined" aria-hidden="true">home_pin</span>
                      {appointment.home_address}{appointment.city ? `, ${appointment.city}` : ''}
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="portal-section-card doctor-history__section" aria-labelledby="doctor-published-reports-heading">
        <div className="doctor-history__section-head">
          <div>
            <span className="portal-section__eyebrow">Patient records</span>
            <h2 id="doctor-published-reports-heading">Published report history</h2>
          </div>
          <span className="portal-count-pill">{reports.length} reports</span>
        </div>
        <p className="doctor-history__section-note">
          Reports shown here were completed through PhysioCare and published by an administrator. External historical documents are not available in this record.
        </p>
        {openReport.isError && (
          <p className="patient-booking__submit-error" role="alert">
            The published report could not be opened. Your patient record remains unchanged; try again.
          </p>
        )}
        {!reports.length ? (
          <EmptyState
            title="No published reports"
            message="No administrator-published PhysioCare laboratory reports are available for this assigned patient."
            icon="description"
          />
        ) : (
          <div className="doctor-history__reports">
            {reports.map((report) => (
              <article key={report.request_id} className="doctor-history__report">
                <span className="doctor-history__report-icon material-symbols-outlined" aria-hidden="true">description</span>
                <div>
                  <span className="doctor-history__report-kind">Laboratory report</span>
                  <strong>{report.report_file_name || 'Laboratory report'}</strong>
                  <span>{report.selected_tests.join(', ') || 'Test names unavailable'}</span>
                  <small>
                    {report.report_released_at ? `Published ${formatVisitDate(report.report_released_at)}` : 'Publication date unavailable'}
                    {report.report_uploaded_at ? ` · Finalized ${formatVisitDate(report.report_uploaded_at)}` : ''}
                  </small>
                </div>
                <button
                  type="button"
                  disabled={openReport.isPending}
                  onClick={() => openReport.mutate({ report, viewer: preparePdfViewer() })}
                >
                  {openReport.isPending && openReport.variables?.report?.request_id === report.request_id ? 'Opening…' : 'Open PDF'}
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
