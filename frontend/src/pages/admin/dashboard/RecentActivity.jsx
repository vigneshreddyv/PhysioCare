import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';
import QuickActions from './QuickActions';

export default function RecentActivity({ notifications }) {
  const navigate = useNavigate();

  // If no notifications are provided, show an empty state
  if (!notifications || notifications.length === 0) {
    return (
      <div className="space-y-4" aria-labelledby="healthcare-widgets-heading">
        <h2 id="healthcare-widgets-heading" className="text-lg font-semibold">
          Healthcare Widgets
        </h2>

        {/* Notifications/Alerts */}
        <div className="border-b pb-3">
          <h3 className="text-lg font-semibold mb-3 flex items-center justify-between">
            Notifications
            <Button variant="text" size="xs" className="p-1" aria-label="View all notifications" onClick={() => navigate('/admin/notifications')}>
              View All
            </Button>
          </h3>
          <div className="text-center py-8">
            <p className="text-gray-500">No recent activity</p>
          </div>
        </div>

        {/* Quick Actions */}
        <div>
          <h3 className="text-lg font-semibold mb-3">Quick Actions</h3>
          <QuickActions />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" aria-labelledby="healthcare-widgets-heading">
      <h2 id="healthcare-widgets-heading" className="text-lg font-semibold">
        Healthcare Widgets
      </h2>

      {/* Notifications/Alerts */}
      <div className="border-b pb-3">
        <h3 className="text-lg font-semibold mb-3 flex items-center justify-between">
          Notifications
          <Button variant="text" size="xs" className="p-1" aria-label="View all notifications" onClick={() => navigate('/admin/notifications')}>
            View All
          </Button>
        </h3>
        <div className="space-y-2" aria-live="polite">
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
                className={`p-3 mb-2 rounded-lg border-l-4 ${containerColor}`}
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
      </div>

      {/* Quick Actions */}
      <div>
        <h3 className="text-lg font-semibold mb-3">Quick Actions</h3>
        <QuickActions />
      </div>
    </div>
  );
}