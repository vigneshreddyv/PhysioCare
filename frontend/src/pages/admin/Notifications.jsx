import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import Button from '../../components/common/Button';

export default function Notifications() {
  const [notifications, setNotifications] = useState([]);

  // We'll fetch appointments and stats to generate similar notifications as in AdminDashboard
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

  const {
    data: appointments,
    isLoading: appointmentsLoading,
    error: appointmentsError
  } = useQuery({
    queryKey: ['appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  useEffect(() => {
    if (
      !statsLoading &&
      !appointmentsLoading &&
      stats &&
      appointments &&
      Array.isArray(appointments) // Added this check to ensure appointments is an array
    ) {
      const generatedNotifications = [];

      // Add notification for new appointments today
      const today = new Date();
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      const todayAppointments = appointments.filter(apt => {
        const aptDate = new Date(apt.appointment_date);
        return aptDate.toDateString() === today.toDateString();
      }).length;
      const yesterdayAppointments = appointments.filter(apt => {
        const aptDate = new Date(apt.appointment_date);
        return aptDate.toDateString() === yesterday.toDateString();
      }).length;

      if (todayAppointments > 0) {
        const change = todayAppointments - yesterdayAppointments;
        if (change > 0) {
          generatedNotifications.push({
            id: `today-appointments-${Date.now()}`,
            type: 'success',
            title: 'More appointments today',
            message: `${todayAppointments} appointments today, which is ${change} more than yesterday.`,
            time: 'Today'
          });
        } else if (change < 0) {
          generatedNotifications.push({
            id: `today-appointments-${Date.now()}`,
            type: 'warning',
            title: 'Fewer appointments today',
            message: `${todayAppointments} appointments today, which is ${Math.abs(change)} fewer than yesterday.`,
            time: 'Today'
          });
        }
      }

      // Add notification for new patients
      const newPatients = stats?.new_patients || 0;
      if (newPatients > 0) {
        generatedNotifications.push({
          id: `new-patients-${Date.now()}`,
          type: 'info',
          title: 'New patients registered',
          message: `${newPatients} new patients registered this week.`,
          time: 'This week'
        });
      }

      setNotifications(generatedNotifications);
    }
  }, [statsLoading, appointmentsLoading, stats, appointments]);

  if (statsError || appointmentsError) {
    return <div className="p-6">Error loading notifications.</div>;
  }

  if (statsLoading || appointmentsLoading) {
    return <div className="p-6 text-center">Loading notifications...</div>;
  }

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-stack-lg">
        <div>
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Notifications</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">View all system alerts and updates.</p>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-on-surface-variant">No notifications at this time.</p>
          <button onClick={() => window.location.reload()} className="text-primary hover:text-secondary text-sm font-semibold hover:underline">
            Refresh
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {notifications.map((notification) => {
            const dotColor =
              notification.type === 'warning'
                ? 'bg-yellow-500'
                : notification.type === 'info'
                  ? 'bg-blue-500'
                  : notification.type === 'success'
                    ? 'bg-green-500'
                    : notification.type === 'error'
                      ? 'bg-red-500'
                      : 'bg-gray-500';
            const containerColor =
              notification.type === 'warning'
                ? 'border-yellow-400 bg-yellow-50'
                : notification.type === 'info'
                  ? 'border-blue-400 bg-blue-50'
                  : notification.type === 'success'
                    ? 'border-green-400 bg-green-50'
                    : notification.type === 'error'
                      ? 'border-red-400 bg-red-50'
                      : 'border-gray-400 bg-gray-50';
            return (
              <div
                key={notification.id}
                className={`p-4 mb-3 rounded-lg border-l-4 ${containerColor}`}
                role="alert"
              >
                <div className="flex items-start space-x-3">
                  <div className={`flex-shrink-0 mt-1 flex h-2 w-2 rounded-full ${dotColor}`} />
                  <div>
                    <p className="font-medium text-gray-900">{notification.title}</p>
                    <p className="text-sm text-gray-600 line-clamp-1">
                      {notification.message}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">{notification.time}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}