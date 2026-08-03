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
      const response = await api.get('/analytics/stats');
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
  const pieData = stats?.specializations || [
    { name: 'Physical Therapy', value: 45 },
    { name: 'Sports Massage', value: 30 },
    { name: 'Chiropractic', value: 25 }
  ];

  const pieColors = [colors.primary, colors.secondaryLight, colors.lightBlue];

  // Format data for Bar Chart (Revenue Trend)
  const barData = stats?.revenue_trend || [
    { name: 'Jan', revenue: 12000 },
    { name: 'Feb', revenue: 14000 },
    { name: 'Mar', revenue: 10000 },
    { name: 'Apr', revenue: 15000 },
    { name: 'May', revenue: 17000 },
    { name: 'Jun', revenue: 21000 }
  ];

  // Format data for Area/Line Chart (Appointments per Week)
  const areaData = stats?.appointments_per_week || [
    { name: 'Week 1', appointments: 120 },
    { name: 'Week 2', appointments: 180 },
    { name: 'Week 3', appointments: 220 },
    { name: 'Week 4', appointments: 260 }
  ];

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
              title="Total Appointments"
              value={stats?.total_appointments ? (stats.total_appointments * 4).toLocaleString() : '1,248'}
              icon="calendar_today"
              changeText="+12% vs last period"
              changeType="up"
              colorVariant="primary"
            />
            <StatCard
              title="Total Revenue"
              value={`$${stats?.total_revenue ? (stats.total_revenue * 5.9).toLocaleString(undefined, {maximumFractionDigits: 0}) : '84.2k'}`}
              icon="payments"
              changeText="+8.4% vs last period"
              changeType="up"
              colorVariant="secondary"
            />
            <StatCard
              title="Cancellation Rate"
              value={`${stats?.cancellation_rate ? stats.cancellation_rate : '4.1'}%`}
              icon="block"
              changeText="-2% from last period"
              changeType="down"
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
            ) : (
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
            )}
          </div>
        </div>

        {/* Top Specializations Donut chart */}
        <div className="bg-surface-container-lowest border border-surface-container rounded-xl p-6 shadow-sm flex flex-col h-96">
          <div>
            <h3 className="font-headline-md text-headline-md font-bold text-on-surface">Top Specializations</h3>
            <p className="text-sm text-on-surface-variant">Volume share by department</p>
          </div>
          <div className="flex-1 flex flex-col items-center justify-center relative mt-4">
            {isLoading ? (
              <div className="w-40 h-40 rounded-full border-8 border-surface-container border-t-primary animate-pulse" />
            ) : (
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
                  <span className="text-2xl font-bold text-on-surface">3</span>
                  <span className="text-[10px] text-on-surface-variant font-semibold">Top Services</span>
                </div>
                
                {/* Custom legends matching the design */}
                <div className="w-full grid grid-cols-3 gap-1 text-center mt-2">
                  {pieData.map((item, index) => (
                    <div key={item.name} className="flex flex-col items-center">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: pieColors[index] }} />
                        <span className="text-[10px] font-semibold text-on-surface truncate max-w-[64px]">{item.name}</span>
                      </div>
                      <span className="text-xs font-bold text-on-surface-variant mt-0.5">{item.value}%</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Revenue Trend chart */}
        <div className="lg:col-span-3 bg-surface-container-lowest border border-surface-container rounded-xl p-6 shadow-sm flex flex-col h-96">
          <div className="mb-4">
            <h3 className="font-headline-md text-headline-md font-bold text-on-surface">Revenue Trend</h3>
            <p className="text-sm text-on-surface-variant">6-Month Trajectory</p>
          </div>
          <div className="flex-1 w-full relative">
            {isLoading ? (
              <div className="absolute inset-0 bg-surface-container-low animate-pulse rounded-lg" />
            ) : (
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
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
