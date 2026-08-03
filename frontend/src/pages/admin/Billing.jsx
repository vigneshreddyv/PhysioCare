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
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Billing & Invoices</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Track patient subscription billing and individual session charges.</p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
          <h3 className="font-headline-md text-headline-md text-on-surface">Transactions</h3>
          <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
            Invoice Log
          </span>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton variant="row" count={3} />
          </div>
        ) : !appointments || appointments.length === 0 ? (
          <div className="p-6">
            <EmptyState 
              title="No transactions recorded" 
              message="Transaction entries will register here once patients book consultations."
              icon="payments"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                  <th className="p-4">Patient</th>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Description</th>
                  <th className="p-4">Amount</th>
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
                    <td className="p-4 text-on-surface font-semibold">${appt.billing_amount.toFixed(2)}</td>
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
                          className="text-primary hover:text-secondary text-sm font-semibold hover:underline"
                        >
                          Record Payment
                        </button>
                      ) : (
                        <span className="text-xs text-outline font-semibold">Processed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
