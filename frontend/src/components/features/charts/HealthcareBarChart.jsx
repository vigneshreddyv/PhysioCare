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
    <ResponsiveContainer width="100%" height={height}>
      {/* Chart Title */}
      {title && (
        <text
          x="50%"
          y="20"
          textAnchor="middle"
          fill="#666"
          fontSize={14}
          fontWeight="600"
        >
          {title}
        </text>
      )}
      <BarChart
        data={data}
        margin={{ top: 40, right: 30, left: 0, bottom: 5 }}
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
          tick={{ fontSize: 12, rotate: -30 }}
          textAnchor="end"
        />
        <YAxis
          tick={{
            count: 4,
            fontSize: 12,
            formatter: (value) => formatValue(value)
          }}
        >
          <label
            value={unit}
            position="insideLeft"
            angle={-90}
            dy="-20"
            dx="-10"
            textAnchor="middle"
            style={{ fill: '#666', fontSize: 12 }}
          />
        </YAxis>
        <Tooltip
          formatter={(value) => formatValue(value)}
          labelFormatter={label => label}
          contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', padding: '8px', borderRadius: '4px' }}
          labelStyle={{ fontSize: 12, fontWeight: 600 }}
        />
        <Legend verticalAlign="top" height={36} />
        <Bar
          dataKey={label}
          fill="url(#barGradient)"
          radius={[4, 4, 0, 0]}
        >
          {/* Value labels on top of bars */}
          <LabelList
            dataKey={label}
            position="insideTop"
            dy={12}
            fill="#fff"
            fontSize={12}
            fontWeight={600}
            formatter={(value) => formatValue(value)}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default HealthcareBarChart;