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
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-6">
        <h3 className="text-lg font-semibold mb-4">
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
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-6">
        <h3 className="text-lg font-semibold mb-4">
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
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-6">
        <h3 className="text-lg font-semibold mb-4">
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
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow duration-300 p-6">
        <h3 className="text-lg font-semibold mb-4">
          Today's Schedule Overview
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span>Morning (8 AM - 12 PM)</span>
            <span className="font-medium">{Math.floor(appointmentsToday * 0.4)} appointments</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Afternoon (12 PM - 5 PM)</span>
            <span className="font-medium">{Math.floor(appointmentsToday * 0.4)} appointments</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Evening (5 PM - 8 PM)</span>
            <span className="font-medium">{Math.floor(appointmentsToday * 0.2)} appointments</span>
          </div>
        </div>
      </div>
    </div>
  );
}