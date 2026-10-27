import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import StatCard from '../../components/features/StatCard';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar
} from 'recharts';

export default function Analytics() {
  const [timeRange, setTimeRange] = useState('30days'); // '30days' or 'quarter'

  // Fetch performance metrics from stats endpoint
  const { 
    data: stats, 
    isLoading, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['analyticsStats', timeRange],
    queryFn: async () => {
      const response = await api.get('/analytics/stats', {
        params: { days: timeRange === 'quarter' ? 90 : 30 },
      });
      return response.data;
    }
  });

  if (error) {
    return <ErrorState message="Could not load performance stats." onRetry={() => refetch()} />;
  }

  // Color constants to match Stitch mockup design
  const colors = {
    primary: '#006184',       // deep teal
    secondary: '#0c6780',     // dark primary blue
    secondaryLight: '#9ae1ff',// sky blue
    tertiary: '#535b60',      // slate grey
    lightBlue: '#baeaff',     // light blue
    fadedBlue: '#e5eeff'      // container low blue
  };

  // Format data for Pie/Donut Chart (Top Specializations)
  const pieData = stats?.doctor_specializations || [];

  const pieColors = [colors.primary, colors.secondaryLight, colors.lightBlue];

  // Format data for Bar Chart (Revenue Trend)
  const barData = stats?.revenue_trend || [];

  // Format data for Area/Line Chart (Appointments per Week)
  const areaData = stats?.appointments_per_week || [];
  const hasAppointments = areaData.some((item) => item.appointments > 0);
  const hasRecordedRevenue = barData.some((item) => item.revenue > 0);

  return (
    <div className="space-y-stack-lg animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-stack-lg">
        <div>
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Clinic Performance</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Insights and metrics for optimizing patient care.</p>
        </div>
        
        {/* Toggle selector buttons */}
        <div className="flex bg-surface-container-low border border-surface-container rounded-full p-1 self-end sm:self-auto shadow-sm">
          <button
            onClick={() => setTimeRange('30days')}
            className={`px-4 py-2 rounded-full font-label-md text-label-md transition-all duration-200 ${
              timeRange === '30days' 
                ? 'bg-primary text-on-primary font-semibold shadow-sm' 
                : 'text-on-surface-variant hover:text-primary'
            }`}
          >
            Last 30 Days
          </button>
          <button
            onClick={() => setTimeRange('quarter')}
            className={`px-4 py-2 rounded-full font-label-md text-label-md transition-all duration-200 ${
              timeRange === 'quarter' 
                ? 'bg-primary text-on-primary font-semibold shadow-sm' 
                : 'text-on-surface-variant hover:text-primary'
            }`}
          >
            Last Quarter
          </button>
        </div>
      </div>

      {/* Indicator cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter mb-12">
        {isLoading ? (
          <Skeleton variant="card" count={3} />
        ) : (
          <>
            <StatCard
              title={`Appointments (${stats?.period_days || 30} days)`}
              value={(stats?.period_appointments ?? 0).toLocaleString()}
              icon="calendar_today"
              changeText="No prior-period comparison available"
              changeType="flat"
              colorVariant="primary"
            />
            <StatCard
              title="Recorded Paid Total"
              value={`$${(stats?.recorded_paid_total ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
              icon="payments"
              changeText="From appointment records; no payment provider connected"
              changeType="flat"
              colorVariant="secondary"
            />
            <StatCard
              title="Cancellation Rate"
              value={`${stats?.cancellation_rate ?? 0}%`}
              icon="block"
              changeText="Calculated from appointments in this period"
              changeType="flat"
              colorVariant="tertiary"
            />
          </>
        )}
      </div>

      {/* Main Charts Bento Grid layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-gutter">
        
        {/* Appointments per Week line chart */}
        <div className="lg:col-span-2 bg-surface-container-lowest border border-surface-container rounded-xl p-6 shadow-sm flex flex-col h-96">
          <div className="mb-4">
            <h3 className="font-headline-md text-headline-md font-bold text-on-surface">Appointments per Week</h3>
            <p className="text-sm text-on-surface-variant">Volume trend over the selected period</p>
          </div>
          <div className="flex-1 w-full relative">
            {isLoading ? (
              <div className="absolute inset-0 bg-surface-container-low animate-pulse rounded-lg" />
            ) : hasAppointments ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={areaData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorAppointments" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={colors.primary} stopOpacity={0.2}/>
                      <stop offset="95%" stopColor={colors.primary} stopOpacity={0.0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" stroke={colors.tertiary} fontSize={11} tickLine={false} />
                  <YAxis stroke={colors.tertiary} fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="appointments"
                    stroke={colors.primary}
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorAppointments)"
                    dot={{ stroke: colors.primary, strokeWidth: 2, r: 4, fill: '#fff' }}
                    activeDot={{ r: 6 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full grid place-items-center text-center text-sm text-on-surface-variant">
                No appointments are recorded in this period.
              </div>
            )}
          </div>
        </div>

        {/* Top Specializations Donut chart */}
        <div className="bg-surface-container-lowest border border-surface-container rounded-xl p-6 shadow-sm flex flex-col h-96">
          <div>
            <h3 className="font-headline-md text-headline-md font-bold text-on-surface">Doctor Specializations</h3>
            <p className="text-sm text-on-surface-variant">Current doctor count by recorded specialization</p>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center relative mt-4">
            {isLoading ? (
              <div className="w-40 h-40 rounded-full border-8 border-surface-container border-t-primary animate-pulse" />
            ) : pieData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height="80%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={pieColors[index % pieColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                {/* Custom Donut center watermark label */}
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none" style={{ height: '80%' }}>
                  <span className="text-2xl font-bold text-on-surface">{pieData.reduce((total, item) => total + item.value, 0)}</span>
                  <span className="text-[10px] text-on-surface-variant font-semibold">Doctors</span>
                </div>
                
                {/* Custom legends matching the design */}
                <div className="w-full grid grid-cols-3 gap-1 text-center mt-2">
                  {pieData.map((item, index) => (
                    <div key={item.name} className="flex flex-col items-center">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: pieColors[index % pieColors.length] }} />
                        <span className="text-[10px] font-semibold text-on-surface truncate max-w-[64px]">{item.name}</span>
                      </div>
                      <span className="text-xs font-bold text-on-surface-variant mt-0.5">{item.value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-center text-sm text-on-surface-variant">No doctor specialization data is available yet.</p>
            )}
          </div>
        </div>

        {/* Revenue Trend chart */}
        <div className="lg:col-span-3 bg-surface-container-lowest border border-surface-container rounded-xl p-6 shadow-sm flex flex-col h-96">
          <div className="mb-4">
            <h3 className="font-headline-md text-headline-md font-bold text-on-surface">Recorded Paid Totals</h3>
            <p className="text-sm text-on-surface-variant">Six months of appointment records marked paid; not payment-provider settlement data</p>
          </div>
          <div className="flex-1 w-full relative">
            {isLoading ? (
              <div className="absolute inset-0 bg-surface-container-low animate-pulse rounded-lg" />
            ) : hasRecordedRevenue ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <XAxis dataKey="name" stroke={colors.tertiary} fontSize={11} tickLine={false} />
                  <YAxis stroke={colors.tertiary} fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(value) => [`$${value.toLocaleString()}`, 'Revenue']} />
                  <Bar dataKey="revenue" radius={[6, 6, 0, 0]}>
                    {barData.map((entry, index) => {
                      // Highlight the final month (June) in primary colors, and others in light blue, matching Stitch designs
                      const isLast = index === barData.length - 1;
                      return (
                        <Cell 
                          key={`cell-${index}`} 
                          fill={isLast ? colors.primary : colors.lightBlue} 
                        />
                      );
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full grid place-items-center text-center text-sm text-on-surface-variant">
                No appointments are recorded as paid in the last six months.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
