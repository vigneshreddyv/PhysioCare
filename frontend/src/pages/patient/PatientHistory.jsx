import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function PatientHistory() {
  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['patientHistory'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  if (error) {
    return <ErrorState message="Could not load session history." onRetry={() => refetch()} />;
  }

  // Filter completed and cancelled visits
  const history = appointments?.filter(
    (a) => a.status === 'completed' || a.status === 'cancelled'
  ) || [];

  return (
    <div className="space-y-stack-lg animate-fade-in pb-16">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Visit History</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Review past consultations, prescriptions, and therapist notes.</p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm p-6">
        <div className="p-4 border-b border-surface-container flex justify-between items-center bg-surface-container-low/20 mb-4 rounded-lg">
          <h3 className="font-semibold text-on-surface">Consultation Logs</h3>
          <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
            {history.length} Visits Logged
          </span>
        </div>

        {isLoading ? (
          <Skeleton variant="row" count={3} />
        ) : history.length === 0 ? (
          <EmptyState 
            title="No past consults found" 
            message="Your therapy visit log is currently empty. Completed sessions will register here."
            icon="history"
          />
        ) : (
          <div className="space-y-4 divide-y divide-surface-container">
            {history.map((appt) => (
              <AppointmentCard
                key={appt.id}
                appointment={appt}
                displayRole="patient"
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
