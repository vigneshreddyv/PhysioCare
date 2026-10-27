import React from 'react';
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

  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['doctorAppointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });
  const reports = useQuery({
    queryKey: ['doctorReleasedLabReports'],
    queryFn: async () => (await api.get('/lab-requests/doctor/reports')).data,
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }) => {
      const response = await api.patch(`/appointments/${id}`, { status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctorAppointments'] });
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

  const handleStatusChange = (id, newStatus) => {
    updateStatusMutation.mutate({ id, status: newStatus });
  };

  if (error || reports.error) {
    return <ErrorState message="Could not load dashboard information." onRetry={() => { refetch(); reports.refetch(); }} />;
  }

  // Doctor stats calculations
  const openVisits = appointments?.filter((a) => a.status === 'scheduled' || a.status === 'in_progress') || [];
  const completedToday = appointments?.filter((a) => a.status === 'completed') || [];
  const patientCount = appointments ? [...new Set(appointments.map((a) => a.patient_id))].length : 0;

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">clinical_notes</span>Clinical workspace</span>
        <h1>Keep every assigned session moving.</h1>
        <p>Review the current caseload and update appointment status as each physiotherapy session progresses.</p>
        <div className="portal-hero__actions">
          <button type="button" onClick={() => refetch()} className="patient-primary px-5 py-3 rounded-xl font-semibold inline-flex items-center justify-center gap-2">
            <span className="material-symbols-outlined" aria-hidden="true">refresh</span>
            Refresh agenda
          </button>
        </div>
      </header>

      <div className="portal-dashboard-grid grid grid-cols-1 md:grid-cols-3 gap-gutter">
        {isLoading ? (
          <Skeleton variant="card" count={3} />
        ) : (
          <>
            <StatCard
              title="Open Assigned Visits"
              value={openVisits.length}
              icon="calendar_today"
              changeText="Scheduled or in progress"
              changeType="flat"
              colorVariant="primary"
            />
            <StatCard
              title="Completed Sessions"
              value={completedToday.length}
              icon="check_circle"
              changeText="Successfully finished"
              changeType="up"
              colorVariant="secondary"
            />
            <StatCard
              title="Assigned Patients"
              value={patientCount}
              icon="groups"
              changeText="Unique caseload"
              changeType="flat"
              colorVariant="tertiary"
            />
          </>
        )}
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
            The appointment status could not be updated. Your agenda remains unchanged; please try again.
          </div>
        )}

        <div className="p-4 md:p-6">
          {isLoading ? (
            <Skeleton variant="row" count={3} />
        ) : !appointments || appointments.length === 0 ? (
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
      </section>

      <section className="portal-section-card overflow-hidden" aria-labelledby="doctor-lab-reports-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Assigned patients</span><h2 id="doctor-lab-reports-heading" className="font-headline-md text-headline-md">Released laboratory reports</h2></div><span className="portal-count-pill">{reports.data?.length || 0} reports</span></div>
        {openReport.isError && <div className="mx-5 mt-5 patient-booking__submit-error" role="alert">The report could not be opened. Refresh and try again.</div>}
        {reports.isLoading ? <Skeleton variant="row" count={2} /> : !reports.data?.length ? <div className="p-6"><EmptyState title="No released reports" message="Only released reports for patients assigned to you appear here." icon="description" /></div> : <div className="reception-schedule-grid">{reports.data.map((report) => <article key={report.request_id} className="portal-mobile-record"><strong>{report.patient_name}</strong><span>{report.selected_tests.join(', ')}</span><button type="button" disabled={openReport.isPending} onClick={() => openReport.mutate({ report, viewer: preparePdfViewer() })}>{openReport.isPending && openReport.variables?.report?.request_id === report.request_id ? 'Opening…' : 'Open released report'}</button></article>)}</div>}
      </section>
    </div>
  );
}
