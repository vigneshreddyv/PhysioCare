import React from 'react';
import Skeleton from '../../../components/common/Skeleton';
import { HealthcareBarChart, HealthcarePieChart, HealthcareLineChart } from '../../../components/features';

export default function DashboardCharts({ stats, statsLoading, activity }) {
  // Prepare chart data from actual API response
  const appointmentsChartData = stats?.appointments_per_week?.map((item) => ({
    name: item.name,
    appointments: item.appointments,
  })) || [];

  const revenueChartData = stats?.revenue_trend?.map((item) => ({
    name: item.name,
    revenue: item.revenue,
  })) || [];

  const specializationData = stats?.doctor_specializations?.map((item) => ({
    name: item.name,
    value: item.value,
  })) || [];

  const scheduleCounts = activity?.schedule_counts || { morning: 0, afternoon: 0, evening: 0 };

  return (
    <div className="grid min-w-0 grid-cols-1 gap-6 md:grid-cols-2">
      {/* Appointment Trends */}
      <div className="portal-dashboard-card flex min-h-[22rem] min-w-0 flex-col p-5 md:p-6">
        <h3 className="mb-3 text-lg font-semibold">
          Appointment Activity ({stats?.period_days || 30} Days)
        </h3>
        {!statsLoading && appointmentsChartData.length > 0 && (
          <HealthcareBarChart
            data={appointmentsChartData}
            label="appointments"
            title="Appointments per Month"
            height={250}
          />
        )}
        {!statsLoading && appointmentsChartData.length === 0 && (
          <p className="py-16 text-center text-sm text-on-surface-variant">No appointment trend data is available yet.</p>
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Revenue Trend */}
      <div className="portal-dashboard-card flex min-h-[22rem] min-w-0 flex-col p-5 md:p-6">
        <h3 className="mb-3 text-lg font-semibold">
          Recorded Paid Totals (6 Months)
        </h3>
        {!statsLoading && revenueChartData.length > 0 && (
          <HealthcareLineChart
            data={revenueChartData}
            label="revenue"
            title="Recorded paid total"
            unit="INR "
            height={250}
          />
        )}
        {!statsLoading && revenueChartData.length === 0 && (
          <p className="py-16 text-center text-sm text-on-surface-variant">No revenue trend data is available yet.</p>
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Services Distribution */}
      <div className="portal-dashboard-card flex min-h-[22rem] min-w-0 flex-col p-5 md:p-6">
        <h3 className="mb-3 text-lg font-semibold">
          Doctor Specializations
        </h3>
        {!statsLoading && specializationData.length > 0 && (
          <HealthcarePieChart
            data={specializationData}
            title="Doctors"
            height={250}
          />
        )}
        {!statsLoading && specializationData.length === 0 && (
          <p className="py-16 text-center text-sm text-on-surface-variant">No service distribution data is available yet.</p>
        )}
        {statsLoading && (
          <div className="h-64 flex items-center justify-center">
            <Skeleton variant="chart" />
          </div>
        )}
      </div>

      {/* Today's Schedule Overview */}
      <div className="portal-dashboard-card flex min-h-[22rem] min-w-0 flex-col p-5 md:p-6">
        <h3 className="mb-3 text-lg font-semibold">
          Today's Schedule Overview
        </h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span>Morning (8 AM - 12 PM)</span>
            <span className="font-medium">{scheduleCounts.morning} appointments</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Afternoon (12 PM - 5 PM)</span>
            <span className="font-medium">{scheduleCounts.afternoon} appointments</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span>Evening (5 PM - 8 PM)</span>
            <span className="font-medium">{scheduleCounts.evening} appointments</span>
          </div>
        </div>
      </div>
    </div>
  );
}
