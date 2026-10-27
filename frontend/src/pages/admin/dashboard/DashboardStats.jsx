import React from 'react';
import { StatCard } from '../../../components/features';

export default function DashboardStats({ stats, appointments }) {
  const today = new Date().toDateString();
  const appointmentsToday = (appointments || []).filter(
    (appointment) => new Date(appointment.appointment_date).toDateString() === today,
  ).length;

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      {/* Appointments Today */}
      <StatCard
        title="Appointments Today"
        value={appointmentsToday}
        icon="calendar_today"
        changeText={appointmentsToday > 0 ? `${appointmentsToday} scheduled today` : 'No appointments scheduled today'}
        changeType="flat"
        colorVariant="blue"
      />

      {/* Active Patients */}
      <StatCard
        title="Registered Patients"
        value={stats?.total_patients ?? 0}
        icon="person"
        changeText={`${stats?.new_patients ?? 0} registered in the selected period`}
        changeType="flat"
        colorVariant="green"
      />

      {/* Total Doctors */}
      <StatCard
        title="Total Doctors"
        value={stats?.total_doctors ?? 0}
        icon="stethoscope"
        changeText={stats?.total_doctors
          ? `${stats.total_doctors} doctor profiles`
          : 'No doctors registered'}
        changeType="flat"
        colorVariant="purple"
      />

      {/* Recorded billing */}
      <StatCard
        title="Recorded Paid Total"
        value={`$${(stats?.recorded_paid_total ?? 0).toLocaleString()}`}
        icon="attach_money"
        changeText="Appointment records only; no payment provider connected"
        changeType="flat"
        colorVariant="blue"
      />
    </div>
  );
}
