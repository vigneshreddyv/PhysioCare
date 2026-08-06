import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import StatCard from '../../components/features/StatCard';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function AdminDashboard() {
  const queryClient = useQueryClient();

  const {
    data: stats,
    isLoading: statsLoading,
    error: statsError,
  } = useQuery({
    queryKey: ['adminStats'],
    queryFn: async () => {
      const response = await api.get('/analytics/stats');
      return response.data;
    },
  });

  const {
    data: appointments,
    isLoading: appointmentsLoading,
    error: appointmentsError,
    refetch: refetchAppointments,
  } = useQuery({
    queryKey: ['appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }) => {
      const response = await api.patch(`/appointments/${id}`, {
        status,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
    },
  });

  const handleStatusChange = (id, newStatus) => {
    updateStatusMutation.mutate({
      id,
      status: newStatus,
    });
  };

  const handleRetry = () => {
    refetchAppointments();
  };

  if (statsError || appointmentsError) {
    return (
      <ErrorState
        message="Could not connect to the database. Make sure the backend server is running."
        onRetry={handleRetry}
      />
    );
  }

  const appointmentsToday = appointments?.length ?? 0;

  return (
    <div className="space-y-stack-lg animate-fade-in">

      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface">
          Overview
        </h2>

        <p className="font-body-md text-body-md text-on-surface-variant mt-1">
          Here's what's happening at your clinic today.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-12">

        {statsLoading ? (
          <Skeleton variant="card" count={4} />
        ) : (
          <>
            <StatCard
              title="Appointments Today"
              value={appointmentsToday}
              icon="calendar_today"
              changeText="+4 from yesterday"
              changeType="up"
              colorVariant="primary"
            />

            <StatCard
              title="Active Subscriptions"
              value={stats?.active_subscriptions ?? 0}
              icon="card_membership"
              changeText="Currently Active"
              changeType="flat"
              colorVariant="secondary"
            />

            <StatCard
              title="Total Doctors"
              value={stats?.total_doctors ?? 0}
              icon="stethoscope"
              changeText="Registered Doctors"
              changeType="flat"
              colorVariant="tertiary"
            />

            <StatCard
              title="Revenue"
              value={`$${stats?.total_revenue?.toLocaleString() ?? 0}`}
              icon="payments"
              changeText="+8.4% vs last month"
              changeType="up"
              colorVariant="primary"
            />
          </>
        )}
      </div>

      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-6">

        <div className="flex justify-between items-center mb-6 border-b border-surface-container-high pb-4">
          <h3 className="font-headline-md text-headline-md">
            Recent Appointments
          </h3>

          <button
            onClick={() => refetchAppointments()}
            className="text-primary hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">
              refresh
            </span>

            Refresh List
          </button>
        </div>

        {appointmentsLoading ? (
          <Skeleton variant="row" count={3} />
        ) : !appointments || appointments.length === 0 ? (
          <EmptyState
            title="No appointments"
            message="No appointments found."
            icon="calendar_today"
          />
        ) : (
          <div className="space-y-4">
            {appointments.map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                displayRole="admin"
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}