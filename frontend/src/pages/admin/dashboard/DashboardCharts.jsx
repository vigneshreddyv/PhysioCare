import React from 'react';
import Skeleton from '../../../components/common/Skeleton';
import { HealthcareBarChart, HealthcarePieChart, HealthcareLineChart } from '../../../components/features';

export default function DashboardCharts({ stats, statsLoading, appointments }) {
  // Prepare chart data from actual API response
  const appointmentsChartData = stats?.appointments_per_week?.map((item) => ({
    name: item.name,
    appointments: item.appointments,
  })) || [];

  const revenueChartData = stats?.revenue_trend?.map((item) => ({
    name: item.name,
    revenue: item.revenue,
  })) || [];

  const specializationData = stats?.specializations?.map((item) => ({
    name: item.name,
    value: item.value,
  })) || [];

  const appointmentsToday = appointments?.length ?? 0;

  return (
    <div className="grid gap-6 md:grid-cols-2">
      
      {/* Appointment Trends */}
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6">
        <h3 className="text-base font-extrabold text-[#183B4A] mb-4">
          Appointment Trends (6 Months)
        </h3>
        {!statsLoading && appointmentsChartData.length > 0 && (
          <HealthcareBarChart
            data={appointmentsChartData}
            label="appointments"
            title="Appointments per Month"
            height={250}
          />
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Revenue Trend */}
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6">
        <h3 className="text-base font-extrabold text-[#183B4A] mb-4">
          Revenue Trend (6 Months)
        </h3>
        {!statsLoading && revenueChartData.length > 0 && (
          <HealthcareLineChart
            data={revenueChartData}
            label="revenue"
            title="Revenue"
            unit="$"
            height={250}
          />
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Services Distribution */}
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6">
        <h3 className="text-base font-extrabold text-[#183B4A] mb-4">
          Services Distribution
        </h3>
        {!statsLoading && specializationData.length > 0 && (
          <HealthcarePieChart
            data={specializationData}
            title="Services"
            height={250}
          />
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Today's Schedule Overview */}
      <div className="bg-white rounded-3xl border border-[#E5E0D6] shadow-sm p-6 flex flex-col justify-between">
        <h3 className="text-base font-extrabold text-[#183B4A] mb-4">
          Today's Schedule Overview
        </h3>
        <div className="space-y-4 flex-1 flex flex-col justify-center">
          <div className="flex items-center justify-between text-xs border-b border-[#E5E0D6]/40 pb-2">
            <span className="font-bold text-[#60716E]">Morning (8 AM - 12 PM)</span>
            <span className="font-extrabold text-[#183B4A] bg-[#EEF5F1] px-2 py-0.5 rounded border border-[#0F6B63]/10">
              {Math.floor(appointmentsToday * 0.4)} appointments
            </span>
          </div>
          <div className="flex items-center justify-between text-xs border-b border-[#E5E0D6]/40 pb-2">
            <span className="font-bold text-[#60716E]">Afternoon (12 PM - 5 PM)</span>
            <span className="font-extrabold text-[#183B4A] bg-[#EEF5F1] px-2 py-0.5 rounded border border-[#0F6B63]/10">
              {Math.floor(appointmentsToday * 0.4)} appointments
            </span>
          </div>
          <div className="flex items-center justify-between text-xs pb-1">
            <span className="font-bold text-[#60716E]">Evening (5 PM - 8 PM)</span>
            <span className="font-extrabold text-[#183B4A] bg-[#EEF5F1] px-2 py-0.5 rounded border border-[#0F6B63]/10">
              {Math.floor(appointmentsToday * 0.2)} appointments
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}