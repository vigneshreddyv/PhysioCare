import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import StatCard from '../../components/features/StatCard';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
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

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }) => {
      const response = await api.patch(`/appointments/${id}`, { status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctorAppointments'] });
    }
  });

  const handleStatusChange = (id, newStatus) => {
    updateStatusMutation.mutate({ id, status: newStatus });
  };

  if (error) {
    return <ErrorState message="Could not load dashboard information." onRetry={() => refetch()} />;
  }

  // Doctor stats calculations
  const todayVisits = appointments?.filter((a) => a.status === 'scheduled' || a.status === 'in_progress') || [];
  const completedToday = appointments?.filter((a) => a.status === 'completed') || [];

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Therapist Dashboard</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage today's therapy schedules and patient assessments.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter mb-12">
        {isLoading ? (
          <Skeleton variant="card" count={3} />
        ) : (
          <>
            <StatCard
              title="Assigned Visits Today"
              value={todayVisits.length}
              icon="calendar_today"
              changeText="Pending visits"
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
              value={appointments ? [...new Set(appointments.map(a => a.patient_id))].length : 0}
              icon="groups"
              changeText="Unique caseload"
              changeType="flat"
              colorVariant="tertiary"
            />
          </>
        )}
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-6">
        <div className="flex justify-between items-center mb-6 border-b border-surface-container-high pb-4">
          <h3 className="font-headline-md text-headline-md text-on-surface">Your Agenda</h3>
          <button 
            onClick={() => refetch()}
            className="text-primary font-label-md text-label-md hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            Refresh Agenda
          </button>
        </div>

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
    </div>
  );
}
