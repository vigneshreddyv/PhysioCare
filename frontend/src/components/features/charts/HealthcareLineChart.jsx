import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const HealthcareLineChart = ({ data, label, title, unit = '', height = 200 }) => {
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
        <div className="mb-1 flex min-w-0 items-center justify-between gap-2 text-sm font-semibold text-on-surface-variant">
          <span className="truncate" title={title}>{title}</span>
          <span className="shrink-0 text-primary">
            Latest: {formatValue(data[data.length - 1][label])}
          </span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 8, right: 12, left: 4, bottom: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.5} />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} tickMargin={8} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={formatValue}
            width={unit ? 60 : 40}
          />
          <Tooltip
            formatter={(value) => formatValue(value)}
            labelFormatter={label => label}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', padding: '8px', borderRadius: '4px' }}
            labelStyle={{ fontSize: 12, fontWeight: 600 }}
            wrapperStyle={{ border: 'none' }}
          />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey={label}
            stroke="#3b82f6"
            strokeWidth={2}
            isAnimationActive={false}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default HealthcareLineChart;