import React from 'react';
import AppointmentCard from '../../../components/features/AppointmentCard';
import Skeleton from '../../../components/common/Skeleton';
import EmptyState from '../../../components/common/EmptyState';
import Button from '../../../components/common/Button';
import { RefreshCw } from 'lucide-react';

export default function RecentAppointments({ appointments, appointmentsLoading, refetchAppointments, onStatusChange }) {
  if (appointmentsLoading) {
    return (
      <div className="h-32 flex items-center justify-center" aria-live="polite">
        <Skeleton variant="list" count={3} />
      </div>
    );
  }

  if (!appointments || appointments.length === 0) {
    return (
      <EmptyState
        title="No appointments today"
        message="No appointments scheduled for today."
        icon="calendar_today"
      />
    );
  }

  return (
    <section aria-labelledby="recent-appointments-heading" className="h-full">
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6 sm:p-8 h-full space-y-4">
        <div className="flex justify-between items-center pb-2 border-b border-[#E5E0D6]/60">
          <div className="space-y-1">
            <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">Operational Agenda</span>
            <h2 id="recent-appointments-heading" className="text-base font-extrabold text-[#183B4A]">
              Today's Appointments
            </h2>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchAppointments()}
            className="flex items-center gap-1.5 text-xs font-bold"
            aria-label="Refresh appointments list"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>

        <div className="space-y-3" aria-live="polite">
          {appointments
            .slice(0, 5)
            .map((appointment) => (
              <div key={appointment.id} className="bg-[#F7F4ED]/10 rounded-2xl border border-[#E5E0D6]/60 p-4">
                <AppointmentCard
                  appointment={appointment}
                  displayRole="admin"
                  onStatusChange={onStatusChange}
                />
              </div>
            ))}
        </div>
      </div>
    </section>
  );
}