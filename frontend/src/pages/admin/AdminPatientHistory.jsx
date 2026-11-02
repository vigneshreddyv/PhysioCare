import React, { useEffect, useRef, useState } from 'react';
import { format, parseISO } from 'date-fns';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import { CLINICAL_PAGE_SIZE } from '../../services/clinicalPagination';
import ClinicalPageNav from '../../components/common/ClinicalPageNav';
import Button from '../../components/common/Button';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';
import { closePdfViewer, preparePdfViewer, showPdfBlob } from '../../utils/openPdfBlob';

function displayDate(value, includeTime = false) {
  if (!value) return 'Not available';
  try {
    return format(parseISO(value), includeTime ? 'd MMM yyyy, h:mm a' : 'd MMM yyyy');
  } catch {
    return 'Not available';
  }
}

export default function AdminPatientHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const activePatientRef = useRef(id);
  const viewerRef = useRef(null);
  useEffect(() => {
    activePatientRef.current = id;
    return () => {
      activePatientRef.current = null;
      if (viewerRef.current) closePdfViewer(viewerRef.current);
      viewerRef.current = null;
    };
  }, [id]);
  const history = useQuery({
    queryKey: ['adminPatientHistory', id, page, startDate, endDate],
    enabled: Boolean(id),
    gcTime: 0,
    queryFn: async ({ signal }) => {
      const data = (await api.get(`/users/patients/${id}/history`, {
        params: { page, page_size: CLINICAL_PAGE_SIZE, start_date: startDate || undefined, end_date: endDate || undefined },
        signal,
      })).data;
      if (!data || !Array.isArray(data.appointments) || !Array.isArray(data.reports)
        || data.appointments.length > CLINICAL_PAGE_SIZE || data.reports.length > CLINICAL_PAGE_SIZE) {
        throw new Error('Invalid patient history response');
      }
      return data;
    },
  });
  const openReport = useMutation({
    mutationFn: async ({ report, viewer, patientIdAtOpen }) => {
      if (!viewer) throw new Error('The PDF viewer was blocked.');
      viewerRef.current = viewer;
      try {
        const response = await api.get(`/lab-requests/${report.request_id}/report-file`, { responseType: 'blob' });
        if (activePatientRef.current !== patientIdAtOpen) {
          closePdfViewer(viewer);
          return;
        }
        showPdfBlob(viewer, response.data);
      } catch (error) {
        closePdfViewer(viewer);
        throw error;
      } finally {
        if (viewerRef.current === viewer) viewerRef.current = null;
      }
    },
  });
  const backButton = (
    <Button variant="outline" onClick={() => navigate('/admin/patients')}>
      <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
      Back to patients
    </Button>
  );
  if (history.isLoading) return <div className="space-y-4">{backButton}<Skeleton variant="card" count={3} /></div>;
  if (history.error?.response?.status === 404) return <div className="space-y-4">{backButton}<EmptyState title="Patient history not found" message="This patient record is no longer available." icon="person_off" /></div>;
  if (history.error) return <div className="space-y-4">{backButton}<ErrorState message="Could not load this patient history." onRetry={() => history.refetch()} /></div>;

  const { patient, appointments = [], reports = [], profile_audit: audit = [] } = history.data;
  return (
    <div className="doctor-history animate-fade-in pb-16">
      <div className="flex flex-wrap gap-3">{backButton}<Button onClick={() => navigate(`/admin/patients-edit/${id}`)}>Edit patient</Button></div>
      <header className="doctor-history__patient">
        <div className="doctor-history__identity">
          <div className="doctor-history__avatar" aria-hidden="true">{patient.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</div>
          <div><span className="doctor-history__eyebrow">Administrative patient record</span><h1>{patient.full_name}</h1><p>Visits, released laboratory reports, and profile-edit audit metadata.</p></div>
        </div>
        <dl className="doctor-history__contact">
          <div><dt>Email</dt><dd>{patient.email}</dd></div>
          <div><dt>Phone</dt><dd>{patient.phone || 'Not provided'}</dd></div>
          <div><dt>Date of birth</dt><dd>{patient.date_of_birth || 'Not provided'}</dd></div>
          <div><dt>Gender</dt><dd>{patient.gender || 'Not recorded'}</dd></div>
          <div><dt>Status label</dt><dd>{patient.subscription_status}</dd></div>
        </dl>
      </header>
      <section className="doctor-history__summary" aria-label="Patient record summary">
        <div><strong>{appointments.length}</strong><span>Visits on this page</span></div>
        <div><strong>{appointments.filter((item) => item.status === 'completed').length}</strong><span>Completed on this page</span></div>
        <div><strong>{reports.length}</strong><span>Reports on this page</span></div>
        <div><strong>{audit.length}</strong><span>Profile edits</span></div>
      </section>
      <div className="flex flex-wrap gap-3" aria-label="History date filters">
        <label>From <input type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); setPage(1); }} /></label>
        <label>Through <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setPage(1); }} /></label>
      </div>
      <section className="portal-section-card doctor-history__section" aria-labelledby="admin-patient-visits-heading">
        <div className="doctor-history__section-head"><div><span className="portal-section__eyebrow">Care timeline</span><h2 id="admin-patient-visits-heading">Appointment history</h2></div><span className="portal-count-pill">{appointments.length} visits</span></div>
        {!appointments.length ? <EmptyState title="No appointment history" message="This patient has no recorded PhysioCare visits." icon="event_note" /> : (
          <div className="doctor-history__timeline">
            {appointments.map((appointment) => (
              <article className="doctor-history__visit" key={appointment.id}>
                <div className={`doctor-history__status doctor-history__status--${appointment.status}`}>{appointment.status.replaceAll('_', ' ')}</div>
                <div className="doctor-history__visit-main"><strong>{displayDate(appointment.appointment_date)}</strong><span>{appointment.time_slot} IST · {appointment.doctor_name}</span></div>
                <p className="doctor-history__reason">{appointment.reason}</p>
                <small>{appointment.service_mode === 'home_visit' ? 'Home visit' : 'Clinic visit'} · Billing {appointment.billing_status} · {appointment.billing_currency || 'INR'} {appointment.billing_amount}</small>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="portal-section-card doctor-history__section" aria-labelledby="admin-patient-reports-heading">
        <div className="doctor-history__section-head"><div><span className="portal-section__eyebrow">Patient records</span><h2 id="admin-patient-reports-heading">Published laboratory reports</h2></div><span className="portal-count-pill">{reports.length} reports</span></div>
        {openReport.isError && <p className="patient-booking__submit-error" role="alert">The report could not be opened. Try again.</p>}
        {!reports.length ? <EmptyState title="No published reports" message="No released laboratory reports are available." icon="description" /> : (
          <div className="doctor-history__reports">
            {reports.map((report) => (
              <article key={report.request_id} className="doctor-history__report">
                <span className="doctor-history__report-icon material-symbols-outlined" aria-hidden="true">description</span>
                <div><strong>{report.report_file_name || 'Laboratory report'}</strong><span>{report.selected_tests.join(', ')}</span><small>{displayDate(report.report_released_at)}</small></div>
                <button type="button" disabled={openReport.isPending} onClick={() => openReport.mutate({ report, viewer: preparePdfViewer(), patientIdAtOpen: id })}>Open PDF</button>
              </article>
            ))}
          </div>
        )}
      </section>
      <ClinicalPageNav label="Patient history" page={page} onPageChange={setPage}
        isLoading={history.isFetching} itemCount={appointments.length + reports.length}
        hasNext={appointments.length === CLINICAL_PAGE_SIZE || reports.length === CLINICAL_PAGE_SIZE} />
      <section className="portal-section-card doctor-history__section" aria-labelledby="admin-patient-audit-heading">
        <div className="doctor-history__section-head"><div><span className="portal-section__eyebrow">Administrative accountability</span><h2 id="admin-patient-audit-heading">Profile edit audit</h2></div><span className="portal-count-pill">Latest {audit.length}</span></div>
        <p className="doctor-history__section-note">The audit stores the administrator identifier, time, and changed field names only. Previous contact or identity values are not duplicated.</p>
        {!audit.length ? <EmptyState title="No administrative edits" message="No profile edits have been recorded for this patient." icon="history" /> : (
          <div className="space-y-3">
            {audit.map((event) => <article key={`${event.changed_at}-${event.actor_user_id}`} className="portal-mobile-record"><strong>{event.changed_fields.join(', ').replaceAll('_', ' ')}</strong><span>{displayDate(event.changed_at, true)}</span><small>Administrator {event.actor_user_id.slice(-8)}</small></article>)}
          </div>
        )}
      </section>
    </div>
  );
}
