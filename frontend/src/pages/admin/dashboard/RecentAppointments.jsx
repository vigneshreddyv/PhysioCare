import React from 'react';
import AppointmentCard from '../../../components/features/AppointmentCard';
import Skeleton from '../../../components/common/Skeleton';
import EmptyState from '../../../components/common/EmptyState';
import Button from '../../../components/common/Button';

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
    <section aria-labelledby="recent-appointments-heading">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-6">
        <div className="flex justify-between items-start mb-4">
          <h2 id="recent-appointments-heading" className="text-lg font-semibold">
            Today's Appointments
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchAppointments()}
            aria-label="Refresh appointments list"
          >
            Refresh
          </Button>
        </div>

        <div className="space-y-3" aria-live="polite">
          {appointments
            .slice(0, 5)
            .map((appointment) => (
              <AppointmentCard
                key={appointment.id}
                appointment={appointment}
                displayRole="admin"
                onStatusChange={onStatusChange}
              />
            ))}
        </div>
      </div>
    </section>
  );
}