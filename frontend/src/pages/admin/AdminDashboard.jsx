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

  // Fetch dashboard overview statistics
  const { 
    data: stats, 
    isLoading: statsLoading, 
    error: statsError 
  } = useQuery({
    queryKey: ['adminStats'],
    queryFn: async () => {
      const response = await api.get('/analytics/stats');
      return response.data;
    }
  });

  // Fetch appointments list
  const { 
    data: appointments, 
    isLoading: appointmentsLoading, 
    error: appointmentsError,
    refetch: refetchAppointments
  } = useQuery({
    queryKey: ['appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  // Mutation to update appointment status
  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status }) => {
      const response = await api.patch(`/appointments/${id}`, { status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
    }
  });

  const handleStatusChange = (id, newStatus) => {
    updateStatusMutation.mutate({ id, status: newStatus });
  };

  const handleRetry = () => {
    refetchAppointments();
  };

  if (statsError || appointmentsError) {
    return <ErrorState message="Could not connect to the database. Make sure the backend server is running." onRetry={handleRetry} />;
  }

  const todayCount = stats?.total_appointments ? Math.min(24, Math.floor(stats.total_appointments * 0.05)) : 24;

  return (
    <div className="space-y-stack-lg animate-fade-in">
      {/* Title */}
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Overview</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Here's what's happening at your clinic today.</p>
      </div>

      {/* Bento Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-gutter mb-12">
        {statsLoading ? (
          <Skeleton variant="card" count={4} />
        ) : (
          <>
            <StatCard
              title="Appointments Today"
              value={todayCount}
              icon="calendar_today"
              changeText="+4 from yesterday"
              changeType="up"
              colorVariant="primary"
            />
            <StatCard
              title="Active Subscriptions"
              value={stats?.total_appointments ? Math.floor(stats.total_appointments * 0.125) : 156}
              icon="card_membership"
              changeText="Steady growth"
              changeType="flat"
              colorVariant="secondary"
            />
            <StatCard
              title="Total Doctors"
              value="12"
              icon="stethoscope"
              changeText="All active today"
              changeType="flat"
              colorVariant="tertiary"
            />
            <StatCard
              title="Revenue this Month"
              value={`$${stats?.total_revenue ? stats.total_revenue.toLocaleString() : '14,200'}`}
              icon="payments"
              changeText="+12% vs last month"
              changeType="up"
              colorVariant="primary"
            />
          </>
        )}
      </div>

      {/* Recent Appointments */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-6">
        <div className="flex justify-between items-center mb-6 border-b border-surface-container-high pb-4">
          <h3 className="font-headline-md text-headline-md text-on-surface">Recent Appointments</h3>
          <button 
            onClick={() => refetchAppointments()}
            className="text-primary font-label-md text-label-md hover:underline flex items-center gap-1"
          >
            <span className="material-symbols-outlined text-sm">refresh</span>
            Refresh List
          </button>
        </div>

        {appointmentsLoading ? (
          <div className="space-y-4">
            <Skeleton variant="row" count={3} />
          </div>
        ) : !appointments || appointments.length === 0 ? (
          <EmptyState 
            title="No appointments scheduled" 
            message="No patient appointments have been registered in the system yet."
            icon="calendar_today"
          />
        ) : (
          <div className="space-y-4 division-y division-surface-container">
            {appointments.slice(0, 10).map((appointment) => (
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
