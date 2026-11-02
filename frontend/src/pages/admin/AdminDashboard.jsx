import { fetchClinicalPage } from '../../services/clinicalPagination';
import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { DashboardHeader, DashboardStats, DashboardCharts, RecentAppointments, RecentActivity } from './dashboard';
import ErrorState from '../../components/common/ErrorState';

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
    queryKey: ['appointments', 'admin-dashboard'],
    queryFn: async () => {
      const response = await fetchClinicalPage('/appointments');
      return response.data;
    },
    gcTime: 0,
  });
  const activity = useQuery({
    queryKey: ['adminDailyActivity'],
    queryFn: async () => (await api.get('/analytics/admin-daily-activity')).data,
  });

  const updateStatusMutation = useMutation({
    mutationFn: async ({ id, status, revision }) => {
      const response = await api.patch(`/appointments/${id}`, {
        status,
        expected_revision: revision,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
      queryClient.invalidateQueries({ queryKey: ['adminDailyActivity'] });
    },
  });

  const handleStatusChange = (id, newStatus, revision) => {
    updateStatusMutation.mutate({
      id,
      status: newStatus,
      revision,
    });
  };

  const handleRetry = () => {
    refetchAppointments();
  };

  if (statsError || appointmentsError || activity.error) {
    return (
      <ErrorState
        message="Could not connect to the database. Make sure the backend server is running."
        onRetry={handleRetry}
      />
    );
  }

  // Generate meaningful notifications from available data
  const notifications = [];

  // Add notification for new appointments today
  const todayAppointments = activity.data?.today_appointments || 0;
  const yesterdayAppointments = activity.data?.yesterday_appointments || 0;

  if (todayAppointments > 0) {
    const change = todayAppointments - yesterdayAppointments;
    if (change > 0) {
      notifications.push({
        id: `today-appointments-${Date.now()}`,
        type: 'success',
        title: 'More appointments today',
        message: `${todayAppointments} appointments today, which is ${change} more than yesterday.`,
        time: 'Today',
      });
    } else if (change < 0) {
      notifications.push({
        id: `today-appointments-${Date.now()}`,
        type: 'warning',
        title: 'Fewer appointments today',
        message: `${todayAppointments} appointments today, which is ${Math.abs(change)} fewer than yesterday.`,
        time: 'Today',
      });
    }
  }

  // Add notification for new patients
  const newPatients = stats?.new_patients || 0;
  if (newPatients > 0) {
    notifications.push({
      id: `new-patients-${Date.now()}`,
      type: 'info',
      title: 'New patients registered',
      message: `${newPatients} new patients registered this week.`,
      time: 'This week',
    });
  }

  return (
    <div className="portal-page animate-fade-in">
      <DashboardHeader
        date={new Date()}
        notifications={notifications}
      />
      {updateStatusMutation.isError && (
        <div className="patient-booking__submit-error" role="alert">
          {updateStatusMutation.error?.response?.status === 409
            ? 'This appointment changed elsewhere. Refresh the appointment list and review it before retrying.'
            : 'The appointment status could not be updated. Refresh the list and try again.'}
        </div>
      )}
      <div className="portal-dashboard-grid grid gap-6">
        <DashboardStats stats={stats} activity={activity.data} />
        <DashboardCharts
          stats={stats}
          statsLoading={statsLoading || activity.isLoading}
          activity={activity.data}
        />
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
          <RecentAppointments
            appointments={appointments}
            appointmentsLoading={appointmentsLoading}
            refetchAppointments={refetchAppointments}
            onStatusChange={handleStatusChange}
          />
          <RecentActivity
            notifications={notifications}
          />
        </div>
      </div>
    </div>
  );
}
