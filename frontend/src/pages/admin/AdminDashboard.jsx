import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { DashboardHeader, DashboardStats, DashboardCharts, RecentAppointments, RecentActivity } from './dashboard';
import ErrorState from '../../components/common/ErrorState';
import subDays from 'date-fns/subDays';

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

  // Generate meaningful notifications from available data
  const notifications = [];

  // Add notification for new appointments today
  const today = new Date();
  const yesterday = subDays(today, 1);
  const todayAppointments = appointments?.filter(apt => {
    const aptDate = new Date(apt.appointment_date);
    return aptDate.toDateString() === today.toDateString();
  })?.length || 0;

  const yesterdayAppointments = appointments?.filter(apt => {
    const aptDate = new Date(apt.appointment_date);
    return aptDate.toDateString() === yesterday.toDateString();
  })?.length || 0;

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
    <>
      <DashboardHeader
        date={new Date()}
        notifications={notifications}
      />
      <div className="grid gap-6">
        <DashboardStats
          stats={stats}
          appointments={appointments}
        />
        <DashboardCharts
          stats={stats}
          statsLoading={statsLoading}
          appointments={appointments}
        />
    <div className="grid gap-6 md:grid-cols-2">
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
    </>
  );
}