import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, parseISO } from 'date-fns';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';

function formatNotificationTime(dateString) {
  if (!dateString) return '';
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy · h:mm a');
  } catch {
    return dateString;
  }
}

const typeStyles = {
  appointment: {
    label: 'Appointment',
    dot: 'bg-primary',
    border: 'border-l-primary',
    badge: 'bg-primary-container/20 text-primary',
    icon: 'calendar_month',
  },
  laboratory: {
    label: 'Laboratory',
    dot: 'bg-[#6750A4]',
    border: 'border-l-[#6750A4]',
    badge: 'bg-[#EADDFF] text-[#21005D]',
    icon: 'biotech',
  },
  care_plan: {
    label: 'Care plan',
    dot: 'bg-[#0F6B63]',
    border: 'border-l-[#0F6B63]',
    badge: 'bg-[#EEF5F1] text-[#0F6B63]',
    icon: 'clinical_notes',
  },
  exercise: {
    label: 'Exercise',
    dot: 'bg-[#0F6B63]',
    border: 'border-l-[#0F6B63]',
    badge: 'bg-[#EEF5F1] text-[#0F6B63]',
    icon: 'fitness_center',
  },
  warning: {
    label: 'Alert',
    dot: 'bg-amber-500',
    border: 'border-l-amber-500',
    badge: 'bg-amber-100 text-amber-900',
    icon: 'warning',
  },
  general: {
    label: 'Notice',
    dot: 'bg-outline',
    border: 'border-l-outline',
    badge: 'bg-surface-container text-on-surface-variant',
    icon: 'notifications',
  },
};

export default function Notifications() {
  const queryClient = useQueryClient();

  const {
    data: notifications = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const response = await api.get('/notifications');
      return response.data;
    },
  });

  const { data: unreadData } = useQuery({
    queryKey: ['notificationsUnreadCount'],
    queryFn: async () => {
      const response = await api.get('/notifications/unread-count');
      return response.data;
    },
  });

  const unreadCount = unreadData?.count ?? notifications.filter((n) => !n.is_read).length;

  const markAsReadMutation = useMutation({
    mutationFn: async (notificationId) => {
      const response = await api.patch(`/notifications/${notificationId}/read`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notificationsUnreadCount'] });
    },
  });

  const markAllAsReadMutation = useMutation({
    mutationFn: async () => {
      const response = await api.patch('/notifications/read-all');
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
      queryClient.invalidateQueries({ queryKey: ['notificationsUnreadCount'] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-stack-lg animate-fade-in p-4 sm:p-6 max-w-4xl mx-auto">
        <div className="mb-stack-lg">
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Notifications</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage your notifications and alerts.</p>
        </div>
        <div className="p-6 space-y-4 bg-surface-container-lowest border border-surface-container rounded-xl">
          <Skeleton variant="row" count={4} />
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-stack-lg animate-fade-in p-4 sm:p-6 max-w-4xl mx-auto">
        <div className="mb-stack-lg">
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Notifications</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage your notifications and alerts.</p>
        </div>
        <ErrorState
          message={error?.response?.data?.detail || 'Could not load notifications.'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="space-y-stack-lg animate-fade-in p-4 sm:p-6 max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-stack-lg">
        <div>
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Notifications</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage your notifications and alerts.</p>
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            disabled={markAllAsReadMutation.isPending}
            onClick={() => markAllAsReadMutation.mutate()}
            className="min-h-10 px-4 rounded-xl border border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low text-xs font-semibold text-primary transition-colors flex items-center gap-1.5 disabled:opacity-50 shadow-xs"
          >
            <span className="material-symbols-outlined text-sm" aria-hidden="true">done_all</span>
            {markAllAsReadMutation.isPending ? 'Marking all read…' : 'Mark all as read'}
          </button>
        )}
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
          <h3 className="font-headline-md text-headline-md text-on-surface">Your Notifications</h3>
          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <span className="text-xs bg-primary text-on-primary font-bold px-2.5 py-0.5 rounded-full">
                {unreadCount} unread
              </span>
            )}
            <span className="text-xs bg-surface-container text-on-surface-variant font-semibold px-2.5 py-0.5 rounded-full">
              {notifications.length} total
            </span>
          </div>
        </div>

        {notifications.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No notifications"
              message="You have no notifications or alerts at this time."
              icon="notifications"
            />
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {notifications.map((notification) => {
              const style = typeStyles[notification.notification_type] || typeStyles.general;
              const isUnread = !notification.is_read;
              return (
                <article
                  key={notification.id}
                  className={`p-4 rounded-xl border transition-all duration-150 flex flex-col sm:flex-row items-start justify-between gap-3 ${
                    isUnread
                      ? `bg-surface-container-lowest border-outline-variant/60 border-l-4 ${style.border} shadow-xs`
                      : 'bg-surface-container-low/30 border-surface-container opacity-80'
                  }`}
                  aria-label={notification.title}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-surface-container flex items-center justify-center shrink-0 mt-0.5">
                      <span className="material-symbols-outlined text-base text-on-surface-variant" aria-hidden="true">
                        {style.icon}
                      </span>
                    </div>
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-md ${style.badge}`}>
                          {style.label}
                        </span>
                        {isUnread && (
                          <span className="w-2 h-2 rounded-full bg-primary" aria-label="Unread notification" />
                        )}
                        <h4 className={`text-sm leading-snug text-on-surface ${isUnread ? 'font-bold' : 'font-medium'}`}>
                          {notification.title}
                        </h4>
                      </div>
                      <p className="text-xs text-on-surface-variant leading-relaxed">
                        {notification.message}
                      </p>
                      {notification.created_at && (
                        <p className="text-[11px] text-outline font-medium">
                          {formatNotificationTime(notification.created_at)}
                        </p>
                      )}
                    </div>
                  </div>
                  {isUnread && (
                    <button
                      type="button"
                      disabled={markAsReadMutation.isPending && markAsReadMutation.variables === notification.id}
                      onClick={() => markAsReadMutation.mutate(notification.id)}
                      className="text-xs font-semibold text-primary hover:text-secondary self-end sm:self-center shrink-0 px-3 py-1.5 rounded-lg hover:bg-primary-container/10 transition-colors disabled:opacity-50 flex items-center gap-1"
                    >
                      <span className="material-symbols-outlined text-sm" aria-hidden="true">check</span>
                      Mark read
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
