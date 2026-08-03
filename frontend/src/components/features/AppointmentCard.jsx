import React from 'react';
import { format } from 'date-fns';

export default function AppointmentCard({ appointment, displayRole = 'admin', onStatusChange }) {
  const {
    id,
    patient_name,
    doctor_name,
    appointment_date,
    time_slot,
    reason,
    status
  } = appointment;

  const statusColors = {
    completed: 'bg-primary-container/20 text-primary',
    'in_progress': 'bg-secondary-container/30 text-secondary',
    scheduled: 'bg-tertiary-container/20 text-tertiary',
    cancelled: 'bg-error-container/20 text-error'
  };

  const statusLabels = {
    completed: 'Completed',
    'in_progress': 'In Progress',
    scheduled: 'Scheduled',
    cancelled: 'Cancelled'
  };

  const getInitials = (name) => {
    if (!name) return 'PC';
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  };

  const formattedDate = format(new Date(appointment_date), 'MMM dd, yyyy');
  const badgeClass = statusColors[status] || statusColors.scheduled;
  const badgeLabel = statusLabels[status] || status;

  return (
    <div className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-container-low transition-colors duration-200">
      <div className="flex items-center gap-4 min-w-0">
        <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface-variant font-label-md shrink-0">
          {getInitials(displayRole === 'patient' ? doctor_name : patient_name)}
        </div>
        <div className="min-w-0">
          <p className="font-label-md text-label-md text-on-surface truncate">
            {displayRole === 'patient' ? `Dr. ${doctor_name}` : patient_name}
          </p>
          <p className="font-label-sm text-label-sm text-on-surface-variant truncate">
            {reason}
          </p>
          {displayRole !== 'patient' && (
            <p className="text-xs text-outline truncate">Doctor: Dr. {doctor_name}</p>
          )}
        </div>
      </div>

      <div className="text-right shrink-0">
        <p className="font-label-md text-label-md text-on-surface">{time_slot}</p>
        <p className="text-xs text-outline">{formattedDate}</p>
        <div className="flex items-center gap-2 mt-1 justify-end">
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${badgeClass}`}>
            {badgeLabel}
          </span>
          {onStatusChange && status === 'scheduled' && (
            <select
              value={status}
              onChange={(e) => onStatusChange(id, e.target.value)}
              className="text-[10px] bg-surface-container-lowest border border-outline-variant rounded p-0.5 focus:ring-1 focus:ring-primary focus:border-primary cursor-pointer text-on-surface-variant"
            >
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">Start Visit</option>
              <option value="completed">Complete</option>
              <option value="cancelled">Cancel</option>
            </select>
          )}
        </div>
      </div>
    </div>
  );
}
