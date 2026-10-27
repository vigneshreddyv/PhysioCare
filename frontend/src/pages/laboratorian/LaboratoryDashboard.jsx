import React, { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';

const MAX_REPORT_BYTES = 5 * 1024 * 1024;

export default function LaboratoryDashboard() {
  const queryClient = useQueryClient();
  const fileInputs = useRef({});
  const [selectedFiles, setSelectedFiles] = useState({});

  const orders = useQuery({
    queryKey: ['laboratorianOrders'],
    queryFn: async () => (await api.get('/lab-requests/laboratory/assigned')).data,
  });

  const upload = useMutation({
    mutationFn: async ({ requestId, file }) => (
      await api.put(`/lab-requests/laboratory/${requestId}/report`, file, {
        headers: {
          'Content-Type': 'application/pdf',
          'X-Report-Filename': file.name,
        },
      })
    ).data,
    onSuccess: (_data, variables) => {
      setSelectedFiles((current) => ({ ...current, [variables.requestId]: null }));
      if (fileInputs.current[variables.requestId]) fileInputs.current[variables.requestId].value = '';
      queryClient.invalidateQueries({ queryKey: ['laboratorianOrders'] });
    },
  });

  const chooseFile = (requestId, file) => {
    if (!file) return;
    if (file.type !== 'application/pdf' || file.size > MAX_REPORT_BYTES) {
      setSelectedFiles((current) => ({ ...current, [requestId]: { error: 'Choose a PDF up to 5 MB.' } }));
      return;
    }
    setSelectedFiles((current) => ({ ...current, [requestId]: { file } }));
  };

  if (orders.error) return <ErrorState message="Could not load assigned laboratory orders." onRetry={() => orders.refetch()} />;

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">biotech</span>Laboratory workspace</span>
        <h1>Finalize only your assigned reports.</h1>
        <p>Upload the finalized PDF for each assigned order. It remains private until an administrator publishes it to the patient.</p>
      </header>

      <section className="portal-section-card" aria-labelledby="laboratory-orders-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Assigned work</span>
            <h2 id="laboratory-orders-heading" className="font-headline-md text-headline-md">Laboratory orders</h2>
          </div>
          <span className="portal-count-pill">{orders.data?.length || 0} orders</span>
        </div>
        {orders.isLoading ? <Skeleton variant="row" count={3} /> : !orders.data?.length ? (
          <div className="p-6"><EmptyState title="No assigned orders" message="Orders appear here only after an administrator assigns them to you." icon="biotech" /></div>
        ) : (
          <div className="reception-schedule-grid">
            {orders.data.map((order) => {
              const selection = selectedFiles[order.id];
              const isThisUpload = upload.isPending && upload.variables?.requestId === order.id;
              return (
                <article key={order.id} className="portal-mobile-record">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-primary">{{ awaiting_publication: 'Awaiting publication', released: 'Published', draft_uploaded: 'Legacy draft uploaded' }[order.report_status] || 'Report not started'}</p>
                    <h3 className="font-semibold">{order.patient_name}</h3>
                    <p className="text-sm text-on-surface-variant">{order.patient_phone || 'No phone provided'} · {order.mode.replaceAll('_', ' ')}</p>
                  </div>
                  <div className="portal-mobile-record__row"><span>Tests</span><strong>{order.selected_tests.join(', ')}</strong></div>
                  {order.home_address && <div className="portal-mobile-record__row"><span>Collection address</span><strong>{order.home_address}, {order.city}</strong></div>}
                  {order.report_file_name && <div className="portal-mobile-record__row"><span>Finalized report</span><strong>{order.report_file_name}</strong></div>}
                  {order.report_status === 'released' ? <p className="text-sm text-on-surface-variant">This report has been published and can no longer be replaced.</p> : <label className="grid gap-2 font-semibold">
                    Finalized report PDF
                    <input
                      ref={(node) => { fileInputs.current[order.id] = node; }}
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => chooseFile(order.id, event.target.files?.[0])}
                    />
                  </label>}
                  {selection?.error && <p className="patient-booking__submit-error" role="alert">{selection.error}</p>}
                  {upload.isError && upload.variables?.requestId === order.id && <p className="patient-booking__submit-error" role="alert">{upload.error?.response?.data?.detail || 'The finalized report could not be uploaded.'}</p>}
                  {order.report_status !== 'released' && <button
                    type="button"
                    className="min-h-11 rounded-xl bg-primary px-4 text-on-primary font-semibold disabled:opacity-50"
                    disabled={!selection?.file || isThisUpload}
                    onClick={() => upload.mutate({ requestId: order.id, file: selection.file })}
                  >
                    {isThisUpload ? 'Uploading…' : order.report_status === 'awaiting_publication' ? 'Replace finalized report' : 'Upload finalized report'}
                  </button>}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
