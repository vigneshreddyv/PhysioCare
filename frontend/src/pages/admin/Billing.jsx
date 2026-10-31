import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';
import { format } from 'date-fns';

export default function Billing() {
  const queryClient = useQueryClient();
  const capturedReviewQuery = useQuery({
    queryKey: ['capturedPaymentReviews'],
    queryFn: async () => (await api.get('/payments/admin/captured-review')).data,
  });
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
  const reconcileCaptured = useMutation({
    mutationFn: async () => (await api.post('/payments/admin/reconcile-captured')).data,
    onSuccess: async () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ['billingRecords'] }),
      queryClient.invalidateQueries({ queryKey: ['capturedPaymentReviews'] }),
    ]),
  });

  if (error) {
    return <ErrorState message="Could not load billing logs." onRetry={() => refetch()} />;
  }

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">receipt_long</span>Billing records</span>
        <h1>Session billing status</h1>
        <p>Review appointment amounts and provider-confirmed payment status.</p>
      </header>

      <div className="portal-trust-note" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">info</span>
        <span><strong>Scope:</strong> amounts are shown in INR. Paid status is recorded only after Razorpay verifies a Test Mode payment; this screen does not collect payment details.</span>
      </div>

      <section className="portal-section-card p-5 sm:p-6" aria-labelledby="captured-payment-reconciliation-heading">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="portal-section__eyebrow">Recovery operation</span>
            <h2 id="captured-payment-reconciliation-heading" className="font-headline-md text-headline-md">Captured payment reconciliation</h2>
            <p className="mt-1 max-w-2xl text-sm text-on-surface-variant">Retry appointment updates for provider-confirmed captures. Cancelled bookings remain cancelled and are listed for clinic review.</p>
          </div>
          <button
            type="button"
            className="min-h-11 shrink-0 rounded-xl bg-primary px-4 font-semibold text-on-primary disabled:cursor-wait disabled:opacity-60"
            disabled={reconcileCaptured.isPending}
            onClick={() => reconcileCaptured.mutate()}
          >
            {reconcileCaptured.isPending ? 'Checking captures…' : 'Reconcile captured payments'}
          </button>
        </div>
        {reconcileCaptured.isError && <p className="mt-4 text-sm font-medium text-error" role="alert">{reconcileCaptured.error?.response?.data?.detail || 'Captured payments could not be reconciled. Please retry.'}</p>}
        {reconcileCaptured.data && (
          <div className="mt-4 grid gap-3" aria-live="polite">
            <p className="text-sm text-on-surface">Checked {reconcileCaptured.data.examined} captured attempt{reconcileCaptured.data.examined === 1 ? '' : 's'}; recovered {reconcileCaptured.data.recovered} appointment record{reconcileCaptured.data.recovered === 1 ? '' : 's'}.</p>
            {reconcileCaptured.data.failed.length > 0 && (
              <div className="rounded-xl border border-error/30 bg-error-container/20 p-4" role="alert">
                <h3 className="font-semibold text-on-surface">Temporary reconciliation failures</h3>
                <p className="mt-1 text-sm text-on-surface-variant">These captured attempts remain queued for automatic retry.</p>
                <ul className="mt-3 grid gap-2">
                  {reconcileCaptured.data.failed.map((capture, index) => (
                    <li key={capture?.appointment_id || index} className="border-t border-error/20 pt-2 text-sm text-on-surface">
                      {capture?.appointment_id ? `Appointment ${capture.appointment_id}: ` : ''}{capture?.reason || 'Database reconciliation failed; the worker will retry.'}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {capturedReviewQuery.isError && <p className="mt-4 text-sm text-error" role="alert">Captured payment review items could not be loaded. Please retry the Billing page.</p>}
        {capturedReviewQuery.data?.clinic_review?.length > 0 ? (
          <div className="mt-4 rounded-xl border border-error/30 bg-error-container/20 p-4">
            <h3 className="font-semibold text-on-surface">Captures requiring clinic review</h3>
            <ul className="mt-3 grid gap-3">
              {capturedReviewQuery.data.clinic_review.map((capture) => (
                <li key={capture.appointment_id} className="border-t border-error/20 pt-3 text-sm text-on-surface">
                  <div className="font-semibold">Appointment {capture.appointment_id}</div>
                  <div>{capture.currency} {(capture.amount_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} · {capture.appointment_status || 'appointment unavailable'} · {capture.payment_status || 'payment state unavailable'}</div>
                  <p className="mt-1 text-on-surface-variant">{capture.reason}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : capturedReviewQuery.isSuccess && !reconcileCaptured.isError && (
          <p className="mt-4 text-sm font-medium text-primary">No captured payments require clinic reconciliation.</p>
        )}
      </section>

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
                      {appt.billing_currency ? `INR ${appt.billing_amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : appt.billing_amount.toFixed(2)}
                      <span className="block text-xs font-normal text-outline">{appt.billing_currency || 'Currency not configured'}</span>
                    </td>
                    <td className="p-4">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        appt.payment_status === 'reconciliation_required'
                          ? 'bg-error-container/20 text-error'
                          : appt.billing_status === 'paid'
                          ? 'bg-primary-container/20 text-primary' 
                          : 'bg-error-container/20 text-error animate-pulse'
                      }`}>
                        {appt.payment_status === 'reconciliation_required' ? 'Reconciliation required' : appt.billing_status === 'paid' ? 'Paid' : 'Unpaid'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <span className="text-xs text-outline font-semibold">{appt.payment_status === 'reconciliation_required' ? 'Provider capture requires clinic reconciliation' : appt.payment_status === 'success' ? 'Provider verified' : appt.billing_status === 'paid' ? 'Previously recorded paid status' : 'Awaiting patient checkout'}</span>
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
                <div className="portal-mobile-record__row"><span>Recorded amount</span><strong>{appt.billing_currency ? `INR ${appt.billing_amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : `${appt.billing_amount.toFixed(2)} - currency not configured`}</strong></div>
                <div className="portal-mobile-record__row"><span>Status</span><strong>{appt.payment_status === 'reconciliation_required' ? 'Reconciliation required' : appt.billing_status === 'paid' ? 'Paid' : 'Unpaid'}</strong></div>
                <div className="portal-mobile-record__row"><span>Verification</span><strong>{appt.payment_status === 'reconciliation_required' ? 'Provider capture requires clinic reconciliation' : appt.payment_status === 'success' ? 'Provider verified' : appt.billing_status === 'paid' ? 'Previously recorded paid status' : 'Awaiting patient checkout'}</strong></div>
              </article>
            ))}
          </div>
          </>
        )}
      </section>
    </div>
  );
}
