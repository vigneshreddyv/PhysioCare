import React from 'react';
import { format, parseISO } from 'date-fns';

export default function AppointmentCard({
  appointment,
  displayRole = 'admin',
  onStatusChange,
  onCancel,
  cancelPending = false,
}) {
  const {
    id,
    patient_name,
    doctor_name,
    appointment_date,
    time_slot,
    reason,
    status,
    specialty,
    duration,
    can_patient_cancel,
    cancellation_message,
    service_mode = 'clinic',
    home_address,
    city,
  } = appointment;

  // Format date (date-only) and use time_slot for time
  const dateObj = parseISO(appointment_date);
  const formattedDate = format(dateObj, 'EEEE, MMMM do, yyyy');
  // Use the time_slot as provided (already in local time)

  // Status colors and labels
  const statusConfig = {
    completed: { color: 'green-100', text: 'green-800', label: 'Completed', icon: 'check_circle' },
    'in_progress': { color: 'yellow-100', text: 'yellow-800', label: 'In Progress', icon: 'pause_circle_filled' },
    scheduled: { color: 'blue-100', text: 'blue-800', label: 'Scheduled', icon: 'event_available' },
    cancelled: { color: 'red-100', text: 'red-800', label: 'Cancelled', icon: 'cancel' },
    no_show: { color: 'gray-100', text: 'gray-800', label: 'No Show', icon: 'person_off' }
  };

  const statusInfo = statusConfig[status] || statusConfig.scheduled;

  // Specialty mapping with icons
  const specialties = {
    'Physical Therapy': { icon: 'fitness_center', color: 'blue' },
    'Sports Massage': { icon: 'spa', color: 'green' },
    'Chiropractic': { icon: 'chiropractor', color: 'purple' },
    'Acupuncture': { icon: 'acupuncture', color: 'indigo' },
    'Massage Therapy': { icon: 'massage', color: 'teal' }
  };

  const specialtyInfo = specialties[specialty] || { icon: 'local_hospital', color: 'gray' };
  const primaryName = displayRole === 'patient' ? doctor_name : patient_name;
  const secondaryLabel = displayRole === 'patient'
    ? (specialty || 'Physiotherapy specialist')
    : `Patient: ${patient_name}`;
  const initials = primaryName
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join('')
    .toUpperCase() || 'PT';

  return (
    <article
      className={`bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300${displayRole === 'patient' ? ' patient-appointment' : ''}`}
      aria-label={`${statusInfo.label} ${service_mode === 'home_visit' ? 'home visit' : 'clinic appointment'} with ${doctor_name} on ${formattedDate}`}
    >
      {/* Header with patient info and status */}
      <div className="flex items-center justify-between p-4 border-b border-gray-100">
        <div className="flex items-center space-x-4">
          {/* Patient avatar with initials */}
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0 patient-appointment__avatar">
            <span className="text-blue-600 font-bold text-lg">
              {initials}
            </span>
          </div>
          <div>
            <p className="font-semibold text-gray-900">{displayRole === 'patient' ? `Dr. ${primaryName}` : primaryName}</p>
            <p className="text-sm text-gray-500">{service_mode === 'home_visit' ? `Home visit · ${secondaryLabel}` : secondaryLabel}</p>
          </div>
        </div>
        <div className="text-center">
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              statusInfo.color
            } bg-${statusInfo.color}/20${displayRole === 'patient' ? ` patient-appointment__status patient-appointment__status--${status || 'scheduled'}` : ''}`}
          >
            {statusInfo.label}
          </span>
        </div>
      </div>

      {/* Appointment details */}
      <div className="p-4 space-y-3">
        {/* Main info row */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="flex items-center space-x-2">
            <span className="material-symbols-outlined w-4 h-4 text-gray-400">calendar_today</span>
            <span>{formattedDate}</span>
          </div>
          {service_mode === 'home_visit' && home_address && (
            <div className="flex items-center space-x-2 col-span-2">
              <span className="material-symbols-outlined w-4 h-4 text-gray-400">home_pin</span>
              <span>{home_address}{city ? `, ${city}` : ''}</span>
            </div>
          )}
          <div className="flex items-center space-x-2">
            <span className="material-symbols-outlined w-4 h-4 text-gray-400">access_time</span>
            <span>{duration ? `${time_slot} - ${duration} min` : time_slot}</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="material-symbols-outlined w-4 h-4 text-gray-400">stethoscope</span>
            <span>{doctor_name}</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`flex items-center space-x-1`}>
              <span className={`w-2 h-2 rounded-full bg-${specialtyInfo.color}-500`} />
              <span className="text-xs font-medium">{specialty}</span>
            </span>
          </div>
        </div>

        {/* Reason for visit */}
        {reason && (
          <div className="border-t pt-3">
            <p className="flex items-center space-x-2 text-sm text-gray-600">
              <span className="material-symbols-outlined w-4 h-4 text-gray-400">description</span>
              <span>{reason}</span>
            </p>
          </div>
        )}
      </div>

      {displayRole === 'patient' && status === 'scheduled' && (
        <div className="patient-appointment__cancellation px-4 pb-4 pt-3 border-t border-gray-100">
          <p className="text-sm text-gray-600">{cancellation_message}</p>
          {can_patient_cancel && onCancel && (
            <button
              type="button"
              onClick={() => onCancel(appointment)}
              disabled={cancelPending}
              className="mt-3 w-full flex items-center justify-center px-3 py-2 border border-red-300 text-red-700 rounded-lg text-sm font-semibold hover:bg-red-50 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              <span className="material-symbols-outlined mr-1" aria-hidden="true">event_busy</span>
              {cancelPending ? 'Cancelling…' : 'Cancel appointment'}
            </button>
          )}
        </div>
      )}

      {/* Action buttons for admin/doctor roles */}
      {!displayRole || displayRole !== 'patient' && (
        <div className="px-4 pb-4 pt-2 border-t border-gray-100">
          {status === 'scheduled' && (
            <div className="space-y-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onStatusChange(id, 'in_progress');
                }}
                className="w-full flex items-center justify-center px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors duration-200"
              >
                <span className="material-symbols-outlined mr-1">access_time</span>
                Start Visit
              </button>
              <div className="flex space-x-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(id, 'completed');
                  }}
                  className="flex-1 flex items-center justify-center px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors duration-200"
                >
                  <span className="material-symbols-outlined mr-1">check_circle</span>
                  Complete
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(id, 'cancelled');
                  }}
                  className="flex-1 flex items-center justify-center px-3 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors duration-200"
                >
                  <span className="material-symbols-outlined mr-1">cancel</span>
                  Cancel
                </button>
              </div>
            </div>
          )}
          {status !== 'scheduled' && (
            <div className="text-center text-sm text-gray-500">
              {/* Show appointment outcome or notes */}
              {status === 'completed' && (
                <span className="text-green-600 font-medium">
                  <span className="material-symbols-outlined mr-1">check_circle</span>
                  Visit Completed
                </span>
              )}
              {status === 'cancelled' && (
                <span className="text-red-600 font-medium">
                  <span className="material-symbols-outlined mr-1">cancel</span>
                  Appointment Cancelled
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
