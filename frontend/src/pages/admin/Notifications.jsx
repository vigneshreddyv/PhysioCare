import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';

export default function Notifications() {
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
    data: activity,
    isLoading: activityLoading,
    error: activityError
  } = useQuery({
    queryKey: ['adminDailyActivity'],
    queryFn: async () => (await api.get('/analytics/admin-daily-activity')).data,
  });

  const notifications = [];
  if (stats && activity) {
      const todayAppointments = activity.today_appointments || 0;
      const yesterdayAppointments = activity.yesterday_appointments || 0;

      if (todayAppointments > 0) {
        const change = todayAppointments - yesterdayAppointments;
        if (change > 0) {
          notifications.push({
            id: 'today-appointments',
            type: 'success',
            title: 'More appointments today',
            message: `${todayAppointments} appointments today, which is ${change} more than yesterday.`,
            time: 'Today'
          });
        } else if (change < 0) {
          notifications.push({
            id: 'today-appointments',
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
        notifications.push({
          id: 'new-patients',
          type: 'info',
          title: 'New patients registered',
          message: `${newPatients} new patients registered in the selected period.`,
          time: 'Selected period'
        });
      }

  }

  if (statsError || activityError) {
    return <div className="p-6">Error loading notifications.</div>;
  }

  if (statsLoading || activityLoading) {
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
