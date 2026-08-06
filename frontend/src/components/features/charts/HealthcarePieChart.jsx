import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const HealthcarePieChart = ({ data, title, height = 250 }) => {
  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-sm text-muted">
        No data available
      </div>
    );
  }

  const COLORS = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#84cc16', '#f97316'];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={false}
          innerRadius={60}
          outerRadius={100}
          startAngle={180}
          endAngle={360}
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => `${value}%`}
          labelFormatter={label => label}
          contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', padding: '8px', borderRadius: '4px' }}
          labelStyle={{ fontSize: 12, fontWeight: 600 }}
        />
        <Legend
          verticalAlign="bottom"
          align="center"
          height={36}
          formatter={(value) => `${value}%`}
        />
        {/* Center label */}
        <text x="50%" y="50%" textAnchor="middle" dy="4" fill="#666" fontSize={14}>
          {title}
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
};

export default HealthcarePieChart;