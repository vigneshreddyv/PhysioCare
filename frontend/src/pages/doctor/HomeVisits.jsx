import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';
import { format } from 'date-fns';

export default function HomeVisits() {
  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  if (error) {
    return <ErrorState message="Could not load visit logs." onRetry={() => refetch()} />;
  }

  // Filter appointments to show in-progress or scheduled home visits
  const visits = appointments?.filter(
    (a) => a.reason.toLowerCase().includes('home') || a.status === 'scheduled' || a.status === 'in_progress'
  ) || [];

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Home Visits</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Track and manage therapy sessions scheduled at patients' residences.</p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
          <h3 className="font-headline-md text-headline-md text-on-surface">Scheduled Visits</h3>
          <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
            {visits.length} Visits Pending
          </span>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : visits.length === 0 ? (
          <div className="p-6">
            <EmptyState 
              title="No home visits scheduled" 
              message="No patient appointments are registered as home visit services today."
              icon="home_health"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                  <th className="p-4">Patient</th>
                  <th className="p-4">Date & Time</th>
                  <th className="p-4">Treatment / Symptoms</th>
                  <th className="p-4">Visit Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container">
                {visits.map((visit) => (
                  <tr key={visit.id} className="hover:bg-surface-container-low transition-colors duration-150">
                    <td className="p-4 font-semibold text-on-surface">{visit.patient_name}</td>
                    <td className="p-4 text-on-surface-variant text-sm">
                      <div>{format(new Date(visit.appointment_date), 'MMM dd, yyyy')}</div>
                      <div className="text-xs text-outline">{visit.time_slot}</div>
                    </td>
                    <td className="p-4 text-on-surface-variant text-sm">{visit.reason}</td>
                    <td className="p-4">
                      <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        visit.status === 'in_progress'
                          ? 'bg-secondary-container/30 text-secondary'
                          : 'bg-primary-container/20 text-primary'
                      }`}>
                        {visit.status === 'in_progress' ? 'In Progress' : 'Scheduled'}
                      </span>
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
