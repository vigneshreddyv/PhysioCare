import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LabelList,
} from 'recharts';

const HealthcareBarChart = ({ data, label, title, unit = '', height = 250 }) => {
  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-muted">
        No data available
      </div>
    );
  }

  const formatValue = (value) => {
    if (unit === '%') return `${value}%`;
    if (unit === '$') return `$${value.toLocaleString()}`;
    return value.toLocaleString();
  };

  return (
    <div className="w-full min-w-0">
      {title && (
        <div className="mb-1 min-w-0 truncate text-center text-sm font-semibold text-on-surface-variant" title={title}>
          {title}
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 12, left: 4, bottom: 22 }}
        >
          <defs>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.2} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.5} />
          <XAxis
            dataKey="name"
            interval="preserveStartEnd"
            angle={-30}
            textAnchor="end"
            height={42}
            tick={{ fontSize: 11 }}
            tickMargin={8}
          />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={formatValue}
            width={unit ? 52 : 36}
          />
          <Tooltip
            formatter={(value) => formatValue(value)}
            labelFormatter={label => label}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', padding: '8px', borderRadius: '4px' }}
            labelStyle={{ fontSize: 12, fontWeight: 600 }}
          />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
          <Bar
            dataKey={label}
            fill="url(#barGradient)"
            radius={[4, 4, 0, 0]}
            maxBarSize={48}
          >
            <LabelList
              dataKey={label}
              position="top"
              offset={6}
              fill="#3f484e"
              fontSize={11}
              formatter={(value) => formatValue(value)}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default HealthcareBarChart;