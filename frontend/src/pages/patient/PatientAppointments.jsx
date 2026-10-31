import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';
import { CalendarCheck } from '../../components/common/LucideCompat';

export default function PatientAppointments() {
  const navigate = useNavigate();

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
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-[#60716E]">Loading appointments...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 lg:p-8">
        <div className="rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
          <h2 className="text-xl font-extrabold text-[#183B4A]">
            Something went wrong
          </h2>

          <p className="mt-2 text-[#60716E]">
            Could not load your appointments.
          </p>

          <button
            onClick={() => refetch()}
            className="mt-5 w-full border border-[#E5E0D6]/50 text-[#60716E] hover:text-[#0F6B63] hover:border-[#0F6B63]/50"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold text-[#183B4A]">
          Your appointments
        </h1>

        <p className="mt-2 text-[#60716E]">
          Here's where your upcoming care is organized.
        </p>
      </div>

      {upcomingAppointments.length === 0 ? (
        <div className="rounded-xl border border-[#E5E0D6] bg-[#F7F4ED]/50 p-12 text-center">
          <div className="w-12 h-12 rounded-full bg-[#DDEFEA]/20 flex items-center justify-center mx-auto mb-6">
            <CalendarCheck className="w-5 h-5 text-[#0F6B63]" />
          </div>

          <h2 className="mt-4 text-xl font-extrabold text-[#183B4A]">
            No upcoming appointments
          </h2>

          <p className="mt-2 text-[#60716E]">
            Your next session will appear here.
          </p>

          <button
            onClick={() => navigate('/patient/book')}
            className="mt-6 w-full border border-[#E5E0D6]/50 text-[#60716E] hover:text-[#0F6B63] hover:border-[#0F6B63]/50"
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
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}