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
  Dot,
  Label,
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
    <ResponsiveContainer width="100%" height={height}>
      {/* Chart Title */}
      {title && (
        <text
          x="50%"
          y="16"
          textAnchor="middle"
          fill="#666"
          fontSize="14"
          fontWeight="600"
        >
          {title}
        </text>
      )}
      <LineChart
        data={data}
        margin={{ top: 40, right: 30, left: 0, bottom: 5 }}
      >
        <defs>
          <linearGradient id="colorLine1" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.2} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.5} />
        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
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
          wrapperStyle={{ border: 'none' }}
        />
        <Legend verticalAlign="top" height={36} wrapperStyle={{ justifySelf: 'flex-start' }} />
        <Line
          type="monotone"
          dataKey={label}
          stroke="#3b82f6"
          strokeWidth={2}
          isAnimationActive={false}
          dot={false}
        >
          {/* Dot points */}
          {data.map((entry, index) => (
            <Dot
              key={`dot-${index}`}
              r={4}
              fill="#3b82f6"
            />
          ))}
        </Line>
        {/* Label for the line */}
        <Label
          label={label}
          value={data[data.length - 1][label]}
          position="right"
          offset={20}
          fill="#3b82f6"
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default HealthcareLineChart;