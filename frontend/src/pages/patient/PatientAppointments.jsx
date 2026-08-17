import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';

export default function PatientAppointments() {
  const navigate = useNavigate();

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

  const upcomingAppointments = appointments.filter(
    (appointment) =>
      appointment.status === 'confirmed' ||
      appointment.status === 'scheduled' ||
      appointment.status === 'in_progress'
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-gray-500">Loading appointments...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-center">
          <h2 className="text-xl font-semibold text-red-700">
            Something went wrong
          </h2>

          <p className="mt-2 text-red-600">
            Could not load your appointments.
          </p>

          <button
            onClick={() => refetch()}
            className="mt-5 rounded-lg bg-red-600 px-5 py-2.5 font-medium text-white hover:bg-red-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          Appointments
        </h1>

        <p className="mt-1 text-gray-600">
          Manage your upcoming physiotherapy appointments.
        </p>
      </div>

      {upcomingAppointments.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white p-12 text-center">
          <span className="material-symbols-outlined text-5xl text-gray-400">
            calendar_month
          </span>

          <h2 className="mt-4 text-xl font-semibold text-gray-900">
            No upcoming appointments
          </h2>

          <p className="mt-2 text-gray-500">
            You don't have any confirmed appointments yet.
          </p>

          <button
            onClick={() => navigate('/patient/book')}
            className="mt-6 rounded-lg bg-cyan-600 px-6 py-3 font-semibold text-white hover:bg-cyan-700"
          >
            Book an Appointment
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          {upcomingAppointments.map((appointment) => (
            <AppointmentCard
              key={appointment.id}
              appointment={appointment}
              userRole="patient"
            />
          ))}
        </div>
      )}
    </div>
  );
}