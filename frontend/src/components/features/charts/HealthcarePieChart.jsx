import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
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
    <div className="grid w-full min-w-0 gap-2">
      <ResponsiveContainer width="100%" height={Math.max(height - 52, 160)}>
        <PieChart margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={false}
            innerRadius="46%"
            outerRadius="70%"
            startAngle={90}
            endAngle={-270}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => value.toLocaleString()}
            labelFormatter={label => label}
            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', padding: '8px', borderRadius: '4px' }}
            labelStyle={{ fontSize: 12, fontWeight: 600 }}
          />
          <text x="50%" y="50%" textAnchor="middle" dy="4" fill="#3f484e" fontSize={13} fontWeight={600}>
            {title}
          </text>
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex min-w-0 flex-wrap items-center justify-center gap-x-4 gap-y-1 px-2 text-xs text-on-surface-variant">
        {data.map((entry, index) => (
          <li key={`legend-${entry.name}-${index}`} className="flex min-w-0 max-w-full items-center gap-1.5">
            <span
              aria-hidden="true"
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: COLORS[index % COLORS.length] }}
            />
            <span className="min-w-0 [overflow-wrap:anywhere]">{entry.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default HealthcarePieChart;