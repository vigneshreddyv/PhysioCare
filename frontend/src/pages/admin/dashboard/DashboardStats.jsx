import React from 'react';
import { StatCard } from '../../../components/features';

export default function DashboardStats({ stats, appointments }) {
  const appointmentsToday = appointments?.length ?? 0;

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      {/* Appointments Today */}
      <StatCard
        title="Appointments Today"
        value={appointmentsToday}
        icon="calendar_today"
        changeText={stats?.appointments_growth
          ? `+${stats.appointments_growth}% vs last week`
          : appointmentsToday > 0 ? `+${appointmentsToday} today` : 'No appointments'}
        changeType={appointmentsToday > 0 ? "up" : "flat"}
        colorVariant="blue"
      />

      {/* Active Patients */}
      <StatCard
        title="Active Patients"
        value={stats?.active_subscriptions ?? 0}
        icon="person"
        changeText={stats?.active_growth
          ? `+${stats.active_growth}% vs last month`
          : 'Active patients'}
        changeType="flat"
        colorVariant="green"
      />

      {/* Total Doctors */}
      <StatCard
        title="Total Doctors"
        value={stats?.total_doctors ?? 0}
        icon="stethoscope"
        changeText={stats?.total_doctors
          ? `${stats.total_doctors} licensed professionals`
          : 'No doctors registered'}
        changeType="flat"
        colorVariant="purple"
      />

      {/* Revenue */}
      <StatCard
        title="Monthly Revenue"
        value={stats?.total_revenue ? `$${stats.total_revenue.toLocaleString()}` : '$0'}
        icon="attach_money"
        changeText={stats?.revenue_growth
          ? `+${stats.revenue_growth}% vs last month`
          : 'Revenue tracking'}
        changeType={stats?.revenue_growth && stats.revenue_growth >= 0 ? "up" : "down"}
        colorVariant="blue"
      />
    </div>
  );
}