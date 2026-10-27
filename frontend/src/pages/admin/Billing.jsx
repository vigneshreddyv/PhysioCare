import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';
import { format } from 'date-fns';

export default function Billing() {
  const queryClient = useQueryClient();

  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['billingRecords'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  const recordPaymentMutation = useMutation({
    mutationFn: async ({ id, billing_status }) => {
      const response = await api.patch(`/appointments/${id}`, { billing_status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['billingRecords'] });
    }
  });

  const handleMarkAsPaid = (id) => {
    recordPaymentMutation.mutate({ id, billing_status: 'paid' });
  };

  if (error) {
    return <ErrorState message="Could not load billing logs." onRetry={() => refetch()} />;
  }

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">receipt_long</span>Billing records</span>
        <h1>Session billing status</h1>
        <p>Review the billing fields attached to appointments and record the status exposed by the existing clinic API.</p>
      </header>

      <div className="portal-trust-note" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">info</span>
        <span><strong>Scope:</strong> this screen updates an appointment billing-status field. Amount currency is not configured, and this page does not process, collect, refund, or independently verify a payment.</span>
      </div>

      <section className="portal-section-card overflow-hidden" aria-labelledby="billing-records-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Appointment ledger</span>
            <h2 id="billing-records-heading" className="font-headline-md text-headline-md">Billing records</h2>
          </div>
          <span className="portal-count-pill">
            {appointments?.length || 0} records
          </span>
        </div>

        {recordPaymentMutation.isError && (
          <div className="mx-5 mt-5 patient-booking__submit-error" role="alert">Billing status could not be updated. No payment has been recorded.</div>
        )}

        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton variant="row" count={3} />
          </div>
        ) : !appointments || appointments.length === 0 ? (
          <div className="p-6">
            <EmptyState 
              title="No billing records"
              message="Appointment billing fields will appear here after patients book consultations."
              icon="payments"
            />
          </div>
        ) : (
          <>
          <div className="portal-desktop-table overflow-x-auto">
            <table className="portal-data-table w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                  <th className="p-4">Patient</th>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Description</th>
                  <th className="p-4">Recorded amount</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container">
                {appointments.map((appt) => (
                  <tr key={appt.id} className="hover:bg-surface-container-low transition-colors duration-150">
                    <td className="p-4 font-semibold text-on-surface">{appt.patient_name}</td>
                    <td className="p-4 text-on-surface-variant text-sm">
                      <div>{format(new Date(appt.appointment_date), 'MMM dd, yyyy')}</div>
                      <div className="text-xs text-outline">{appt.time_slot}</div>
                    </td>
                    <td className="p-4 text-on-surface-variant text-sm truncate max-w-xs">{appt.reason}</td>
                    <td className="p-4 text-on-surface font-semibold">
                      {appt.billing_amount.toFixed(2)}
                      <span className="block text-xs font-normal text-outline">Currency not configured</span>
                    </td>
                    <td className="p-4">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        appt.billing_status === 'paid' 
                          ? 'bg-primary-container/20 text-primary' 
                          : 'bg-error-container/20 text-error animate-pulse'
                      }`}>
                        {appt.billing_status === 'paid' ? 'Paid' : 'Unpaid'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      {appt.billing_status !== 'paid' ? (
                        <button 
                          onClick={() => handleMarkAsPaid(appt.id)}
                          className="portal-inline-action text-primary hover:text-secondary text-sm font-semibold disabled:opacity-50"
                          disabled={recordPaymentMutation.isPending}
                        >
                          Mark billing status paid
                        </button>
                      ) : (
                        <span className="text-xs text-outline font-semibold">Status recorded</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="portal-mobile-list">
            {appointments.map((appt) => (
              <article key={appt.id} className="portal-mobile-record">
                <div>
                  <span className="portal-section__eyebrow">Patient</span>
                  <h3 className="font-semibold text-on-surface">{appt.patient_name}</h3>
                </div>
                <div className="portal-mobile-record__row"><span>Date</span><strong>{format(new Date(appt.appointment_date), 'MMM dd, yyyy')}</strong></div>
                <div className="portal-mobile-record__row"><span>Recorded amount</span><strong>{appt.billing_amount.toFixed(2)} · currency not configured</strong></div>
                <div className="portal-mobile-record__row"><span>Status</span><strong>{appt.billing_status === 'paid' ? 'Paid' : 'Unpaid'}</strong></div>
                {appt.billing_status !== 'paid' ? (
                  <button type="button" onClick={() => handleMarkAsPaid(appt.id)} className="min-h-11 rounded-xl bg-primary text-on-primary font-semibold disabled:opacity-50" disabled={recordPaymentMutation.isPending}>Mark billing status paid</button>
                ) : (
                  <span className="portal-count-pill justify-center">Status recorded</span>
                )}
              </article>
            ))}
          </div>
          </>
        )}
      </section>
    </div>
  );
}
