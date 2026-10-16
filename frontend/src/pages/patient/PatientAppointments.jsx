import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';
import { CalendarCheck, CalendarDays, Clock3, Calendar, ArrowLeft, AlertTriangle } from 'lucide-react';
import { DayPicker } from 'react-day-picker';
import { format, isBefore, startOfToday } from 'date-fns';

export default function PatientAppointments() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [selectedAppointmentToCancel, setSelectedAppointmentToCancel] = React.useState(null);
  const [cancelError, setCancelError] = React.useState(null);

  const cancelMutation = useMutation({
    mutationFn: async (appointmentId) => {
      const response = await api.patch(`/appointments/${appointmentId}`, { status: 'cancelled' });
      return response.data;
    },
    onSuccess: () => {
      setSelectedAppointmentToCancel(null);
      setCancelError(null);
      queryClient.invalidateQueries({ queryKey: ['patient-appointments'] });
    },
    onError: (err) => {
      setCancelError(err?.response?.data?.detail || 'Unable to cancel appointment.');
    }
  });

  const [selectedAppointmentToReschedule, setSelectedAppointmentToReschedule] = React.useState(null);
  const [rescheduleStep, setRescheduleStep] = React.useState(1);
  const [rescheduleDate, setRescheduleDate] = React.useState(null);
  const [rescheduleTime, setRescheduleTime] = React.useState('');
  const [rescheduleError, setRescheduleError] = React.useState(null);

  const rescheduleMutation = useMutation({
    mutationFn: async ({ appointmentId, date, timeSlot }) => {
      const response = await api.patch(`/appointments/${appointmentId}`, {
        appointment_date: format(date, 'yyyy-MM-dd'),
        time_slot: timeSlot
      });
      return response.data;
    },
    onSuccess: () => {
      setSelectedAppointmentToReschedule(null);
      setRescheduleStep(1);
      setRescheduleDate(null);
      setRescheduleTime('');
      setRescheduleError(null);
      queryClient.invalidateQueries({ queryKey: ['patient-appointments'] });
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
    },
    onError: (err) => {
      setRescheduleError(err?.response?.data?.detail || 'Unable to reschedule appointment.');
    }
  });

  // Helper function to parse appointment date and time into a Date object
  const parseAppointmentDateTime = (appointment) => {
    try {
      const dateStr = appointment.appointment_date;
      const timeStr = appointment.time_slot || '';

      if (!dateStr || !timeStr) return null;

      const [timePart, modifier] = timeStr.trim().split(' ');
      let [hours, minutes] = timePart.split(':').map(Number);

      // Handle 12-hour clock conversion
      if (modifier === 'PM' && hours !== 12) hours += 12;
      if (modifier === 'AM' && hours === 12) hours = 0;

      const [year, month, day] = dateStr.split('-').map(Number);
      return new Date(year, month - 1, day, hours, minutes, 0, 0);
    } catch {} {
      // Return null for any parsing errors
      return null;
    }
  };

  const {
    data: appointments = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['patient-appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
  });

  // Filter and sort appointments
  const now = new Date();
  const upcomingAppointments = appointments
    .filter(appointment => {
      // Filter by status
      if (!(['confirmed', 'scheduled', 'in_progress'].includes(appointment.status))) {
        return false;
      }

      // Parse datetime and filter out past appointments
      const apptDateTime = parseAppointmentDateTime(appointment);
      if (!apptDateTime) return false; // Skip invalid datetime

      return apptDateTime >= now;
    })
    .sort((a, b) => {
      const dateTimeA = parseAppointmentDateTime(a);
      const dateTimeB = parseAppointmentDateTime(b);

      // Both should be valid due to filtering, but guard against nulls
      if (!dateTimeA) return 1;
      if (!dateTimeB) return -1;

      return dateTimeA - dateTimeB; // Ascending order (earliest first)
    });

  if (isLoading) {
    // Skeleton matching the final appointments layout — avoids layout shift
    return (
      <div className="p-6 lg:p-8">
        <div className="mb-8 space-y-3">
          <div className="h-8 w-56 bg-zinc-200 dark:bg-zinc-800 rounded-xl animate-pulse" />
          <div className="h-4 w-2/3 max-w-[288px] bg-zinc-200 dark:bg-zinc-800 rounded-lg animate-pulse" />
        </div>
        <div className="space-y-6">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="rounded-2xl border border-[#E5E0D6] bg-white p-6 animate-pulse"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-zinc-200 dark:bg-zinc-800 shrink-0" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 w-40 bg-zinc-200 dark:bg-zinc-800 rounded" />
                  <div className="h-3 w-28 bg-zinc-200 dark:bg-zinc-800 rounded" />
                </div>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-3">
                <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
                <div className="h-10 bg-zinc-200 dark:bg-zinc-800 rounded-xl" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 lg:p-8">
        <div className="rounded-3xl border border-[#E5E0D6] bg-[#F7F4ED]/50 p-10 sm:p-12 text-center max-w-md mx-auto">
          <div className="w-16 h-16 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="w-7 h-7 text-red-500" />
          </div>

          <h2 className="text-xl font-extrabold text-[#1E2A2B]">
            Something went wrong
          </h2>

          <p className="mt-2 text-sm text-[#60716E] leading-relaxed">
            We couldn't load your appointments right now. Please check your
            connection and try again.
          </p>

          <button
            onClick={() => refetch()}
            className="mt-6 inline-flex items-center justify-center w-full sm:w-auto px-8 rounded-xl bg-[#1F4B45] text-white text-sm font-extrabold shadow-sm hover:bg-[#17352F] transition min-h-[48px]"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold text-[#1E2A2B]">
          Your appointments
        </h1>

        <p className="mt-2 text-[#60716E]">
          Here's where your upcoming care is organized.
        </p>
      </div>

      {upcomingAppointments.length === 0 ? (
        <div className="rounded-xl border border-[#E5E0D6] bg-[#F7F4ED]/50 p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-[#EEF5F1]/20 flex items-center justify-center mx-auto mb-6">
            <CalendarCheck className="w-5 h-5 text-[#1F4B45]" />
          </div>

          <h2 className="mt-4 text-xl font-extrabold text-[#1E2A2B]">
            No upcoming appointments
          </h2>

          <p className="mt-2 text-[#60716E]">
            Your next session will appear here.
          </p>

          <button
            onClick={() => navigate('/patient/book')}
            className="mt-6 inline-flex items-center justify-center w-full sm:w-auto px-8 rounded-xl bg-[#1F4B45] text-white text-sm font-extrabold shadow-sm hover:bg-[#17352F] transition min-h-[48px]"
          >
            Book an appointment
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {upcomingAppointments.map((appointment) => (
            <div key={appointment.id} className="rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
              <AppointmentCard
                appointment={appointment}
                userRole="patient"
                onCancelClick={setSelectedAppointmentToCancel}
                onRescheduleClick={setSelectedAppointmentToReschedule}
              />
            </div>
          ))}
        </div>
      )}

      {selectedAppointmentToCancel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
          <div className="bg-[#F6F2EA] border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-xl space-y-6 animate-scale-up">
            {/* Header */}
            <div className="space-y-2">
              <h2 className="text-xl font-extrabold text-[#1E2A2B]">
                Cancel appointment?
              </h2>
              <p className="text-sm text-[#60716E] leading-relaxed">
                Are you sure you want to cancel your appointment with{' '}
                <strong className="text-[#1E2A2B] font-bold">
                  {selectedAppointmentToCancel.doctor_name}
                </strong>{' '}
                on{' '}
                <strong className="text-[#1E2A2B] font-bold">
                  {selectedAppointmentToCancel.appointment_date}
                </strong>{' '}
                at{' '}
                <strong className="text-[#1E2A2B] font-bold">
                  {selectedAppointmentToCancel.time_slot}
                </strong>?
              </p>
              <p className="text-xs text-red-600 font-medium">
                This action cannot be undone.
              </p>
            </div>

            {/* Error state */}
            {cancelError && (
              <div className="bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl p-3 flex flex-col gap-2">
                <span>{cancelError}</span>
                <button
                  onClick={() => {
                    setCancelError(null);
                    cancelMutation.mutate(selectedAppointmentToCancel.id);
                  }}
                  className="text-left font-bold underline hover:text-red-900"
                >
                  Try Again
                </button>
              </div>
            )}

            {/* Buttons */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <button
                onClick={() => {
                  if (!cancelMutation.isPending) {
                    setSelectedAppointmentToCancel(null);
                    setCancelError(null);
                  }
                }}
                disabled={cancelMutation.isPending}
                className="flex-1 py-3 bg-[#EEF5F1] hover:bg-[#EEF5F1]/80 text-[#1F4B45] rounded-xl text-xs font-bold transition duration-150 border border-[#E5E0D6]"
                style={{ minHeight: '48px' }}
              >
                Keep Appointment
              </button>
              <button
                onClick={() => {
                  cancelMutation.mutate(selectedAppointmentToCancel.id);
                }}
                disabled={cancelMutation.isPending}
                className="flex-1 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition duration-150 shadow-sm flex items-center justify-center gap-2"
                style={{ minHeight: '48px' }}
              >
                {cancelMutation.isPending ? 'Cancelling...' : 'Cancel Appointment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedAppointmentToReschedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto animate-fade-in">
          <div className="bg-[#F6F2EA] border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-xl space-y-6 animate-scale-up my-8 max-h-[90vh] overflow-y-auto">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D6]/50">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    if (rescheduleStep === 2) {
                      setRescheduleStep(1);
                      setRescheduleError(null);
                    } else {
                      setSelectedAppointmentToReschedule(null);
                      setRescheduleDate(null);
                      setRescheduleTime('');
                      setRescheduleError(null);
                    }
                  }}
                  className="p-2 text-[#60716E] hover:text-[#1F4B45] hover:bg-[#EEF5F1]/55 rounded-xl transition-all border border-[#E5E0D6]/40 cursor-pointer"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <div>
                  <h2 className="text-lg font-extrabold text-[#1E2A2B]">
                    Reschedule Appointment
                  </h2>
                  <p className="text-xs text-[#60716E]">
                    Dr. {selectedAppointmentToReschedule.doctor_name}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedAppointmentToReschedule(null);
                  setRescheduleDate(null);
                  setRescheduleTime('');
                  setRescheduleError(null);
                  setRescheduleStep(1);
                }}
                className="text-xs font-bold text-[#60716E] hover:text-red-700 transition cursor-pointer"
              >
                Cancel
              </button>
            </div>

            {/* Error display */}
            {rescheduleError && (
              <div className="bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl p-3 flex flex-col gap-2">
                <span className="font-semibold">{rescheduleError}</span>
                {rescheduleStep === 2 && (
                  <button
                    onClick={() => {
                      setRescheduleError(null);
                      setRescheduleStep(1);
                    }}
                    className="text-left font-bold underline hover:text-red-900 cursor-pointer"
                  >
                    Choose another date or time
                  </button>
                )}
              </div>
            )}

            {/* STEP 1: Date & Time Picker */}
            {rescheduleStep === 1 && (
              <div className="space-y-6">
                {/* Current appointment details card */}
                <div className="bg-white rounded-2xl border border-[#E5E0D6] p-4 text-xs text-[#60716E] space-y-2">
                  <span className="font-bold text-[#1F4B45] uppercase tracking-wider block text-xs">Current Appointment</span>
                  <div className="flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5 text-[#1F4B45] shrink-0" />
                    <span>
                      {selectedAppointmentToReschedule.appointment_date}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock3 className="w-3.5 h-3.5 text-[#1F4B45] shrink-0" />
                    <span>
                      {selectedAppointmentToReschedule.time_slot}
                    </span>
                  </div>
                </div>

                {/* DayPicker Calendar */}
                <div className="bg-white rounded-2xl border border-[#E5E0D6] p-4 flex flex-col items-center">
                  <span className="self-start font-bold text-[#1E2A2B] text-xs mb-3 flex items-center gap-1.5">
                    <CalendarDays className="w-4 h-4 text-[#1F4B45]" /> Select new date
                  </span>
                  <DayPicker
                    mode="single"
                    selected={rescheduleDate}
                    onSelect={(d) => {
                      setRescheduleDate(d);
                      setRescheduleTime('');
                    }}
                    disabled={(date) => isBefore(date, startOfToday())}
                  />
                </div>

                {/* Time Slots */}
                {rescheduleDate && (
                  <div className="bg-white rounded-2xl border border-[#E5E0D6] p-4 space-y-3">
                    <span className="font-bold text-[#1E2A2B] text-xs flex items-center gap-1.5">
                      <Clock3 className="w-4 h-4 text-[#1F4B45]" /> Select new time
                    </span>
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        '09:00 AM',
                        '10:30 AM',
                        '11:00 AM',
                        '01:00 PM',
                        '02:30 PM',
                        '04:00 PM',
                      ].map((time) => {
                        const isSelected = rescheduleTime === time;
                        return (
                          <button
                            key={time}
                            type="button"
                            onClick={() => setRescheduleTime(time)}
                            className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl border-2 text-xs font-bold transition-all cursor-pointer ${
                              isSelected
                                ? 'border-[#1F4B45] bg-[#EEF5F1] text-[#1F4B45]'
                                : 'border-[#E5E0D6] bg-white text-[#60716E] hover:border-[#1F4B45] hover:text-[#1F4B45]'
                            }`}
                            style={{ minHeight: '48px' }}
                          >
                            <Clock3 className="w-3.5 h-3.5" />
                            {time}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Next button */}
                <button
                  type="button"
                  onClick={() => setRescheduleStep(2)}
                  disabled={!rescheduleDate || !rescheduleTime}
                  className="w-full py-3 bg-[#1F4B45] disabled:bg-[#E5E0D6] disabled:text-[#60716E] disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold transition flex items-center justify-center gap-2 cursor-pointer border border-transparent"
                  style={{ minHeight: '48px' }}
                >
                  Continue to Review
                </button>
              </div>
            )}

            {/* STEP 2: Review & Confirmation */}
            {rescheduleStep === 2 && (
              <div className="space-y-6">
                <div className="space-y-4">
                  {/* Current vs New comparison */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="bg-white border border-[#E5E0D6] rounded-2xl p-4 space-y-2.5">
                      <span className="font-mono text-xs uppercase tracking-widest text-[#60716E] font-bold">CURRENT APPOINTMENT</span>
                      <div className="space-y-1.5 text-xs text-[#1E2A2B] font-extrabold">
                        <p>{selectedAppointmentToReschedule.appointment_date}</p>
                        <p className="text-[#60716E] font-bold">{selectedAppointmentToReschedule.time_slot}</p>
                      </div>
                    </div>
                    <div className="bg-white border border-[#1F4B45]/25 bg-[#EEF5F1]/15 rounded-2xl p-4 space-y-2.5">
                      <span className="font-mono text-xs uppercase tracking-widest text-[#1F4B45] font-bold">NEW APPOINTMENT</span>
                      <div className="space-y-1.5 text-xs text-[#1E2A2B] font-extrabold">
                        <p>{rescheduleDate ? format(rescheduleDate, 'yyyy-MM-dd') : ''}</p>
                        <p className="text-[#1F4B45]">{rescheduleTime}</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="bg-[#EEF5F1] border border-[#1F4B45]/10 rounded-2xl p-4 text-xs text-[#60716E] leading-relaxed">
                  Please review the date and time slots carefully. Confirming this reschedule will update your active session details. Billing and payment details will remain completely unchanged.
                </div>

                {/* Confirm / Cancel Buttons */}
                <div className="flex flex-col sm:flex-row gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setRescheduleStep(1)}
                    disabled={rescheduleMutation.isPending}
                    className="flex-1 py-3 bg-[#EEF5F1] hover:bg-[#EEF5F1]/80 text-[#1F4B45] rounded-xl text-xs font-bold transition duration-150 border border-[#E5E0D6] cursor-pointer"
                    style={{ minHeight: '48px' }}
                  >
                    Choose Another Time
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      rescheduleMutation.mutate({
                        appointmentId: selectedAppointmentToReschedule.id,
                        date: rescheduleDate,
                        timeSlot: rescheduleTime
                      });
                    }}
                    disabled={rescheduleMutation.isPending}
                    className="flex-1 py-3 bg-[#1F4B45] hover:bg-[#1F4B45]/90 text-white rounded-xl text-xs font-bold transition duration-150 shadow-sm flex items-center justify-center gap-2 cursor-pointer border border-transparent"
                    style={{ minHeight: '48px' }}
                  >
                    {rescheduleMutation.isPending ? 'Rescheduling...' : 'Confirm Reschedule'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}