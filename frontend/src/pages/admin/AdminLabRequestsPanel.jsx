import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { closePdfViewer, preparePdfViewer, showPdfBlob } from '../../utils/openPdfBlob';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';

const reportLabels = {
  not_started: 'Not started',
  draft_uploaded: 'Legacy draft uploaded',
  awaiting_publication: 'Awaiting publication',
  released: 'Published',
};

export default function AdminLabRequestsPanel() {
  const queryClient = useQueryClient();
  const [laboratorianChoices, setLaboratorianChoices] = useState({});
  const [publicationAcknowledgements, setPublicationAcknowledgements] = useState({});
  const labRequests = useQuery({ queryKey: ['adminLabRequests'], queryFn: async () => (await api.get('/lab-requests/admin')).data });
  const laboratorians = useQuery({ queryKey: ['laboratorians'], queryFn: async () => (await api.get('/users/laboratorians')).data });
  const labReviewMutation = useMutation({
    mutationFn: async ({ requestId, status }) => (await api.patch(`/lab-requests/admin/${requestId}`, { status })).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['adminLabRequests'] }),
  });
  const assignLaboratorianMutation = useMutation({
    mutationFn: async ({ requestId, laboratorianId }) => (
      await api.patch(`/lab-requests/admin/${requestId}/assignment`, { laboratorian_user_id: laboratorianId })
    ).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['adminLabRequests'] }),
  });
  const openLabReport = useMutation({
    mutationFn: async ({ request, viewer }) => {
      if (!viewer) throw new Error('The PDF viewer was blocked.');
      try {
        const response = await api.get(`/lab-requests/${request.id}/report-file`, { responseType: 'blob' });
        showPdfBlob(viewer, response.data);
      } catch (error) {
        closePdfViewer(viewer);
        throw error;
      }
    },
  });
  const publishLabReport = useMutation({
    mutationFn: async (requestId) => (await api.post(`/lab-requests/admin/${requestId}/publish-report`)).data,
    onSuccess: (_data, requestId) => {
      setPublicationAcknowledgements((current) => ({ ...current, [requestId]: false }));
      queryClient.invalidateQueries({ queryKey: ['adminLabRequests'] });
    },
  });

  if (labRequests.error || laboratorians.error) {
    return <ErrorState message="Could not load laboratory request controls." onRetry={() => { labRequests.refetch(); laboratorians.refetch(); }} />;
  }

  return (
    <section className="portal-section-card" aria-labelledby="admin-lab-requests-heading">
      <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Laboratory workflow</span><h2 id="admin-lab-requests-heading" className="font-headline-md text-headline-md">Requests and report publication</h2></div><span className="portal-count-pill">{labRequests.data?.length || 0} requests</span></div>
      {labRequests.isLoading || laboratorians.isLoading ? <Skeleton variant="row" count={3} /> : !labRequests.data?.length ? <div className="p-6"><EmptyState title="No laboratory requests" message="Patient test requests will appear here for review and assignment." icon="biotech" /></div> : <div className="reception-schedule-grid">{labRequests.data.map((request) => {
        const selectedLaboratorianId = laboratorianChoices[request.id] ?? request.assigned_laboratorian_user_id ?? '';
        const isThisPublication = publishLabReport.isPending && publishLabReport.variables === request.id;
        return <article key={request.id} className="portal-mobile-record">
          <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">{reportLabels[request.report_status] || request.report_status.replaceAll('_', ' ')}</p><h3 className="font-semibold">{request.patient_name}</h3><p className="text-sm text-on-surface-variant">{request.mode.replaceAll('_',' ')} · {request.selected_tests.length} tests</p></div>
          {request.home_address && <div className="portal-mobile-record__row"><span>Address</span><strong>{request.home_address}, {request.city}</strong></div>}
          {request.report_file_name && <div className="portal-mobile-record__row"><span>Finalized report</span><strong>{request.report_file_name}</strong></div>}
          <p>{request.confirmation_message}</p>
          {request.status === 'pending_clinic_confirmation' && <div className="grid grid-cols-1 gap-2 sm:grid-cols-2"><button type="button" disabled={labReviewMutation.isPending} onClick={() => labReviewMutation.mutate({requestId:request.id,status:'approved_for_coordination'})} className="min-h-11 rounded-xl bg-primary px-3 text-on-primary font-semibold disabled:opacity-50">Approve coordination</button><button type="button" disabled={labReviewMutation.isPending} onClick={() => labReviewMutation.mutate({requestId:request.id,status:'declined'})} className="min-h-11 rounded-xl border border-error/30 px-3 text-error font-semibold disabled:opacity-50">Decline</button></div>}
          {request.status === 'approved_for_coordination' && <>
            <label>Laboratorian<select value={selectedLaboratorianId} onChange={(event) => setLaboratorianChoices((current) => ({ ...current, [request.id]: event.target.value }))}><option value="">Choose a Laboratorian</option>{(laboratorians.data || []).map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label>
            {assignLaboratorianMutation.isError && assignLaboratorianMutation.variables?.requestId === request.id && <p className="patient-booking__submit-error" role="alert">{assignLaboratorianMutation.error?.response?.data?.detail || 'The laboratory assignment could not be saved.'}</p>}
            <button type="button" disabled={!selectedLaboratorianId || assignLaboratorianMutation.isPending || request.report_status === 'released'} onClick={() => assignLaboratorianMutation.mutate({ requestId: request.id, laboratorianId: selectedLaboratorianId })} className="min-h-11 rounded-xl bg-primary px-3 text-on-primary font-semibold disabled:opacity-50">{assignLaboratorianMutation.isPending && assignLaboratorianMutation.variables?.requestId === request.id ? 'Saving…' : request.assigned_laboratorian_user_id ? 'Update assignment' : 'Assign Laboratorian'}</button>
            {['awaiting_publication', 'released'].includes(request.report_status) && <button type="button" disabled={openLabReport.isPending} onClick={() => openLabReport.mutate({ request, viewer: preparePdfViewer() })} className="min-h-11 rounded-xl border border-primary/30 px-3 text-primary font-semibold disabled:opacity-50">{openLabReport.isPending && openLabReport.variables?.request?.id === request.id ? 'Opening…' : 'Review finalized PDF'}</button>}
            {openLabReport.isError && openLabReport.variables?.request?.id === request.id && <p className="patient-booking__submit-error" role="alert">The finalized report could not be opened. Allow pop-ups, then try again.</p>}
            {request.report_status === 'awaiting_publication' && <div className="grid gap-3 rounded-xl border border-primary/20 bg-primary-container/20 p-3"><p className="text-sm text-on-surface-variant">Publishing makes this finalized report available to the patient and their assigned doctors. This administrative action does not provide medical validation.</p><label className="flex min-h-11 items-start gap-2 text-sm"><input type="checkbox" checked={Boolean(publicationAcknowledgements[request.id])} onChange={(event) => setPublicationAcknowledgements((current) => ({ ...current, [request.id]: event.target.checked }))} /><span>I intend to publish this exact finalized PDF.</span></label>{publishLabReport.isError && publishLabReport.variables === request.id && <p className="patient-booking__submit-error" role="alert">{publishLabReport.error?.response?.data?.detail || 'The report could not be published.'}</p>}<button type="button" disabled={!publicationAcknowledgements[request.id] || isThisPublication || openLabReport.isPending} onClick={() => publishLabReport.mutate(request.id)} className="min-h-11 rounded-xl bg-primary px-3 text-on-primary font-semibold disabled:opacity-50">{isThisPublication ? 'Publishing…' : 'Publish report to patient'}</button></div>}
            {request.report_status === 'draft_uploaded' && <p className="text-sm text-on-surface-variant">Ask the assigned Laboratorian to upload the finalized report before publication.</p>}
            {request.report_status === 'released' && <p className="text-sm font-medium text-primary">Published to the patient and eligible assigned doctors.</p>}
          </>}
        </article>;
      })}</div>}
    </section>
  );
}
