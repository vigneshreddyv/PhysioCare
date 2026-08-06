import React from 'react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import Skeleton from '../../components/common/Skeleton';

export default function Notifications() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // Placeholder: In a real app, we would fetch notifications from the backend
  const [notifications, setNotifications] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    // Simulate fetching notifications
    setTimeout(() => {
      setNotifications([
        {
          id: 1,
          title: 'Welcome to PhysioCare',
          message: 'We are excited to have you on our platform.',
          time: 'Just now',
          type: 'info'
        },
        {
          id: 2,
          title: 'New Feature Released',
          message: 'Check out the latest update in the app.',
          time: 'Today',
          type: 'success'
        }
      ]);
      setLoading(false);
    }, 1000);
  }, []);

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Notifications</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage your notifications and alerts.</p>
      </div>

      {loading ? (
        <div className="p-6 space-y-4">
          <Skeleton variant="row" count={3} />
        </div>
      ) : (
        <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
          <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
            <h3 className="font-headline-md text-headline-md text-on-surface">Your Notifications</h3>
            <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
              {notifications.length} Notifications
            </span>
          </div>

          {notifications.length === 0 ? (
            <div className="p-6">
              <p className="text-center text-on-surface-variant">No notifications at this time.</p>
            </div>
          ) : (
            <div className="p-4 space-y-4">
              {notifications.map((notification) => (
                <div key={notification.id} className="bg-surface-container-low/20 rounded-xl p-4 mb-4">
                  <div className="flex items-start space-x-3">
                    <div className={`flex-shrink-0 mt-1 flex h-2 w-2 rounded-full ${
                      notification.type === 'warning'
                        ? 'bg-yellow-500'
                        : notification.type === 'info'
                          ? 'bg-blue-500'
                          : notification.type === 'success'
                            ? 'bg-green-500'
                            : notification.type === 'error'
                              ? 'bg-red-500'
                              : 'bg-gray-500'
                    }`} />
                    <div>
                      <p className="font-medium text-gray-900">{notification.title}</p>
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {notification.message}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">{notification.time}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}