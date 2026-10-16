import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';
import QuickActions from './QuickActions';
import { Bell } from 'lucide-react';

export default function RecentActivity({ notifications }) {
  const navigate = useNavigate();

  // If no notifications are provided, show an empty state
  if (!notifications || notifications.length === 0) {
    return (
      <section aria-labelledby="healthcare-widgets-heading" className="h-full">
        <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6 sm:p-8 h-full flex flex-col justify-between space-y-6">
          
          {/* Notifications Section */}
          <div className="space-y-4">
            <div className="flex justify-between items-center pb-2 border-b border-[#E5E0D6]/60">
              <div className="space-y-1">
                <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">System Events</span>
                <h2 id="healthcare-widgets-heading" className="text-base font-extrabold text-[#183B4A]">
                  Notifications
                </h2>
              </div>
              <Button 
                variant="text" 
                size="xs" 
                className="text-xs font-bold text-[#0F6B63] hover:underline p-1" 
                aria-label="View all notifications" 
                onClick={() => navigate('/admin/notifications')}
              >
                View All
              </Button>
            </div>
            <div className="text-center py-8 text-xs text-[#60716E] space-y-2">
              <Bell className="w-6 h-6 text-[#60716E]/40 mx-auto" />
              <p>No recent activity logs recorded.</p>
            </div>
          </div>

          {/* Quick Actions Section */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Platform Quick Actions</h3>
            <QuickActions />
          </div>

        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="healthcare-widgets-heading" className="h-full">
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6 sm:p-8 h-full flex flex-col justify-between space-y-6">
        
        {/* Notifications Section */}
        <div className="space-y-4">
          <div className="flex justify-between items-center pb-2 border-b border-[#E5E0D6]/60">
            <div className="space-y-1">
              <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">System Events</span>
              <h2 id="healthcare-widgets-heading" className="text-base font-extrabold text-[#183B4A]">
                Notifications
              </h2>
            </div>
            <Button 
              variant="text" 
              size="xs" 
              className="text-xs font-bold text-[#0F6B63] hover:underline p-1" 
              aria-label="View all notifications" 
              onClick={() => navigate('/admin/notifications')}
            >
              View All
            </Button>
          </div>
          
          <div className="space-y-3" aria-live="polite">
            {notifications.slice(0, 3).map((notification) => {
              const dotColor =
                notification.type === 'warning'
                  ? 'bg-[#C9A86A]'
                  : notification.type === 'error'
                    ? 'bg-red-600'
                    : 'bg-[#0F6B63]';
              const containerColor =
                notification.type === 'warning'
                  ? 'border-[#C9A86A]/40 bg-[#F7F4ED]/50'
                  : notification.type === 'error'
                    ? 'border-red-200/50 bg-red-50/20'
                    : 'border-[#0F6B63]/25 bg-[#EEF5F1]/30';
              return (
                <div
                  key={notification.id}
                  className={`p-3 rounded-xl border-l-4 ${containerColor} text-xs space-y-1`}
                  role="alert"
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${dotColor}`} />
                    <div className="space-y-0.5">
                      <p className="font-bold text-[#183B4A]">{notification.title}</p>
                      <p className="text-[#60716E] leading-relaxed">
                        {notification.message}
                      </p>
                      <p className="text-[10px] font-bold text-[#60716E]/70 pt-0.5">{notification.time}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Quick Actions Section */}
        <div className="space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Platform Quick Actions</h3>
          <QuickActions />
        </div>

      </div>
    </section>
  );
}