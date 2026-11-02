import { fetchClinicalPage } from '../../services/clinicalPagination';
import ClinicalPageNav from '../../components/common/ClinicalPageNav';
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import StatCard from '../../components/features/StatCard';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
import { closePdfViewer, preparePdfViewer, showPdfBlob } from '../../utils/openPdfBlob';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function DoctorDashboard() {
  const queryClient = useQueryClient();
  const [agendaPage, setAgendaPage] = useState(1);
  const [reportPage, setReportPage] = useState(1);
  const [statusGroup, setStatusGroup] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const agendaParams = new URLSearchParams({ status_group: statusGroup });
  if (startDate) agendaParams.set('start_date', startDate);
  if (endDate) agendaParams.set('end_date', endDate);

  const summary = useQuery({
    queryKey: ['doctorDashboardSummary'],
    queryFn: async ({ signal }) => (await api.get('/appointments/doctor/summary', { signal })).data,
    gcTime: 0,
  });

  const { 
    data: agenda,
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['doctorAppointments', agendaPage, statusGroup, startDate, endDate],
    queryFn: () => fetchClinicalPage(`/appointments?${agendaParams}`, agendaPage),
    gcTime: 0,
  });
  const reports = useQuery({
    queryKey: ['doctorReleasedLabReports', reportPage],
    queryFn: () => fetchClinicalPage('/lab-requests/doctor/reports', reportPage, 'request_id'),
    gcTime: 0,
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status, revision }) => {
      const response = await api.patch(`/appointments/${id}`, { status, expected_revision: revision });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctorAppointments'] });
      queryClient.invalidateQueries({ queryKey: ['doctorDashboardSummary'] });
    }
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

  const handleStatusChange = (id, newStatus, revision) => {
    updateStatusMutation.mutate({ id, status: newStatus, revision });
  };

  const appointments = agenda?.data || [];
  const releasedReports = reports.data?.data || [];

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">clinical_notes</span>Clinical workspace</span>
        <h1>Keep every assigned session moving.</h1>
        <p>Review the current caseload and update appointment status as each physiotherapy session progresses.</p>
        <div className="portal-hero__actions">
          <button type="button" onClick={() => { refetch(); reports.refetch(); summary.refetch(); }} className="patient-primary px-5 py-3 rounded-xl font-semibold inline-flex items-center justify-center gap-2">
            <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
            Refresh agenda
          </button>
        </div>
      </header>

      <div className="portal-dashboard-grid grid grid-cols-1 md:grid-cols-3 gap-gutter">
        {summary.isLoading ? (
          <Skeleton variant="card" count={3} />
        ) : (
          <>
            <StatCard
              title="Open Assigned Visits"
              value={summary.data?.open_visits ?? '—'}
              icon="calendar_today"
              changeText="Scheduled or in progress"
              changeType="flat"
              colorVariant="primary"
            />
            <StatCard
              title="Completed Sessions"
              value={summary.data?.completed_sessions ?? '—'}
              icon="check_circle"
              changeText="Successfully finished"
              changeType="up"
              colorVariant="secondary"
            />
            <StatCard
              title="Assigned Patients"
              value={summary.data?.assigned_patients ?? '—'}
              icon="groups"
              changeText="Unique caseload"
              changeType="flat"
              colorVariant="tertiary"
            />
          </>
        )}
      </div>
      {summary.error && <ErrorState message="Could not load caseload totals." onRetry={() => summary.refetch()} />}

      <div className="flex flex-wrap gap-3" aria-label="Agenda filters">
        <label>Status <select value={statusGroup} onChange={(event) => { setStatusGroup(event.target.value); setAgendaPage(1); }}>
          <option value="all">All visits</option><option value="active">Active</option><option value="completed">Completed</option><option value="closed">Closed</option>
        </select></label>
        <label>From <input type="date" value={startDate} max={endDate || undefined} onChange={(event) => { setStartDate(event.target.value); setAgendaPage(1); }} /></label>
        <label>Through <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setAgendaPage(1); }} /></label>
      </div>

      <section className="portal-section-card overflow-hidden" aria-labelledby="doctor-agenda-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Assigned care</span>
            <h2 id="doctor-agenda-heading" className="font-headline-md text-headline-md">Your agenda</h2>
          </div>
          <button 
            onClick={() => refetch()}
            className="portal-inline-action text-primary font-label-md text-label-md hover:bg-primary-container/20 flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">refresh</span>
            Refresh
          </button>
        </div>

        {updateStatusMutation.isError && (
          <div className="mx-5 mt-5 patient-booking__submit-error" role="alert">
            {updateStatusMutation.error?.response?.status === 409
              ? 'This appointment changed elsewhere. Refresh the agenda and review it before retrying.'
              : 'The appointment status could not be updated. Your agenda remains unchanged; please try again.'}
          </div>
        )}
        {error && <ErrorState message="Could not load your agenda." onRetry={() => refetch()} />}

        <div className="p-4 md:p-6">
          {isLoading ? (
            <Skeleton variant="row" count={3} />
        ) : error ? null : appointments.length === 0 ? (
          <EmptyState 
            title="Agenda is clear" 
            message="No therapy appointments are currently booked for you."
            icon="calendar_today"
          />
        ) : (
          <div className="space-y-4 divide-y divide-surface-container">
            {appointments.map((appt) => (
              <AppointmentCard
                key={appt.id}
                appointment={appt}
                displayRole="doctor"
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>
        )}
        </div>
        {!error && <ClinicalPageNav label="Doctor agenda" page={agendaPage} onPageChange={setAgendaPage}
          isLoading={isLoading} itemCount={appointments.length} hasNext={agenda?.hasNext} />}
      </section>

      <section className="portal-section-card overflow-hidden" aria-labelledby="doctor-lab-reports-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Assigned patients</span><h2 id="doctor-lab-reports-heading" className="font-headline-md text-headline-md">Released laboratory reports</h2></div><span className="portal-count-pill">{releasedReports.length} on this page</span></div>
        {openReport.isError && <div className="mx-5 mt-5 patient-booking__submit-error" role="alert">The report could not be opened. Refresh and try again.</div>}
        {reports.error ? <ErrorState message="Could not load released reports." onRetry={() => reports.refetch()} /> : reports.isLoading ? <Skeleton variant="row" count={2} /> : !releasedReports.length ? <div className="p-6"><EmptyState title="No released reports" message="Only released reports for patients assigned to you appear here." icon="description" /></div> : <div className="reception-schedule-grid">{releasedReports.map((report) => <article key={report.request_id} className="portal-mobile-record"><strong>{report.patient_name}</strong><span>{report.selected_tests.join(', ')}</span><button type="button" disabled={openReport.isPending} onClick={() => openReport.mutate({ report, viewer: preparePdfViewer() })}>{openReport.isPending && openReport.variables?.report?.request_id === report.request_id ? 'Opening…' : 'Open released report'}</button></article>)}</div>}
        {!reports.error && <ClinicalPageNav label="Doctor reports" page={reportPage} onPageChange={setReportPage}
          isLoading={reports.isLoading} itemCount={releasedReports.length} hasNext={reports.data?.hasNext} />}
      </section>
    </div>
  );
}
