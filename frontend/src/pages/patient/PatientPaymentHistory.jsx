import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import ClinicalPageNav from '../../components/common/ClinicalPageNav';
import { fetchClinicalPage } from '../../services/clinicalPagination';

const labels = {
  creating: 'Starting',
  pending: 'Pending',
  success: 'Paid',
  failed: 'Failed',
  cancelled: 'Cancelled',
  abandoned: 'Abandoned',
};

export default function PatientPaymentHistory() {
  const [page, setPage] = useState(1);
  const [paymentStatus, setPaymentStatus] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const filters = new URLSearchParams();
  if (paymentStatus !== 'all') filters.set('payment_status', paymentStatus);
  if (startDate) filters.set('start_date', startDate);
  if (endDate) filters.set('end_date', endDate);
  const historyPath = `/payments/history${filters.size ? `?${filters}` : ''}`;
  const payments = useQuery({
    queryKey: ['patientPaymentHistory', page, paymentStatus, startDate, endDate],
    queryFn: () => fetchClinicalPage(historyPath, page),
    gcTime: 0,
  });

  if (payments.isLoading) return <p role="status">Loading payment history…</p>;
  if (payments.isError) return <ErrorState message="Could not load payment history." onRetry={() => payments.refetch()} />;

  const history = payments.data?.data || [];

  return (
    <div className="patient-page animate-fade-in space-y-6">
      <header className="patient-product-header">
        <p className="patient-page__eyebrow">Billing records</p>
        <h1>Payment history</h1>
        <p>Review payment attempts linked to your appointments.</p>
      </header>
      <section className="portal-section-card p-4 grid gap-3 sm:grid-cols-3" aria-label="Payment history filters">
        <label className="grid gap-2 text-sm font-semibold">Payment status
          <select value={paymentStatus} onChange={(event) => { setPaymentStatus(event.target.value); setPage(1); }}>
            <option value="all">All statuses</option>
            {Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label className="grid gap-2 text-sm font-semibold">From date
          <input type="date" value={startDate} max={endDate || undefined} onChange={(event) => { setStartDate(event.target.value); setPage(1); }} />
        </label>
        <label className="grid gap-2 text-sm font-semibold">To date
          <input type="date" value={endDate} min={startDate || undefined} onChange={(event) => { setEndDate(event.target.value); setPage(1); }} />
        </label>
      </section>
      {!history.length ? (
        <EmptyState title="No payment history" message="Payments will appear here after a checkout is started." icon="payments" />
      ) : (
        <section className="space-y-3" aria-label="Payment history">
          {history.map((payment) => (
            <article className="portal-section-card p-5 space-y-2" key={payment.id}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-bold">{labels[payment.status] || payment.status}</h2>
                <strong>{payment.currency} {payment.amount.toFixed(2)}</strong>
              </div>
              <p className="text-sm text-on-surface-variant">
                {payment.appointment_date
                  ? new Date(payment.appointment_date).toLocaleDateString()
                  : 'Appointment date unavailable'}
                {payment.time_slot ? ` · ${payment.time_slot}` : ''}
                {payment.service_mode ? ` · ${payment.service_mode === 'home_visit' ? 'Home visit' : 'Clinic visit'}` : ''}
              </p>
              <p className="text-xs text-on-surface-variant">
                Billing: {payment.billing_status} · Appointment payment: {payment.payment_status}
                {payment.reconciliation_status !== 'pending' ? ` · Reconciliation: ${payment.reconciliation_status}` : ''}
              </p>
            </article>
          ))}
        </section>
      )}
      <ClinicalPageNav label="Payment history" page={page} onPageChange={setPage} isLoading={payments.isFetching} itemCount={history.length} hasNext={payments.data?.hasNext} />
    </div>
  );
}
