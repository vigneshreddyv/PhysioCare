import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';

const labels = {
  pending: 'Pending',
  success: 'Paid',
  failed: 'Failed',
  cancelled: 'Cancelled',
  abandoned: 'Abandoned',
};

export default function PatientPaymentHistory() {
  const payments = useQuery({
    queryKey: ['patientPaymentHistory'],
    queryFn: async () => (await api.get('/payments/history')).data,
  });

  if (payments.isLoading) return <p role="status">Loading payment history…</p>;
  if (payments.isError) return <ErrorState message="Could not load payment history." onRetry={() => payments.refetch()} />;

  return (
    <div className="patient-page animate-fade-in space-y-6">
      <header className="patient-product-header">
        <p className="patient-page__eyebrow">Billing records</p>
        <h1>Payment history</h1>
        <p>Review payment attempts linked to your appointments.</p>
      </header>
      {!payments.data?.length ? (
        <EmptyState title="No payment history" message="Payments will appear here after a checkout is started." icon="payments" />
      ) : (
        <section className="space-y-3" aria-label="Payment history">
          {payments.data.map((payment) => (
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
    </div>
  );
}
