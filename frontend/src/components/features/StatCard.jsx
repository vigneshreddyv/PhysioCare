import React from 'react';
import Card from '../common/Card';

export default function StatCard({
  title,
  value,
  icon,
  changeText,
  changeType = 'up', // 'up', 'down', 'flat'
  colorVariant = 'primary' // 'primary', 'secondary', 'tertiary'
}) {
  const iconBgs = {
    primary: 'bg-primary-container/20 text-primary',
    secondary: 'bg-secondary-container/30 text-secondary',
    tertiary: 'bg-tertiary-container/20 text-tertiary'
  };

  const trendColors = {
    up: 'text-secondary', // Stitch uses text-secondary for positive growth
    down: 'text-error',
    flat: 'text-outline'
  };

  const trendIcons = {
    up: 'trending_up',
    down: 'trending_down',
    flat: 'trending_flat'
  };

  const selectedBg = iconBgs[colorVariant] || iconBgs.primary;
  const selectedTrendColor = trendColors[changeType] || trendColors.up;
  const selectedTrendIcon = trendIcons[changeType] || trendIcons.up;

  return (
    <Card hoverable className="relative overflow-hidden group flex flex-col justify-between h-40">
      {/* Background Icon Watermark */}
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity duration-300">
        <span className="material-symbols-outlined text-[64px] text-current">{icon}</span>
      </div>

      {/* Card Header */}
      <div className="flex items-center gap-2 mb-4 relative z-10">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${selectedBg}`}>
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>{icon}</span>
        </div>
        <h3 className="font-label-md text-label-md text-on-surface-variant truncate">{title}</h3>
      </div>

      {/* Card Content */}
      <div className="relative z-10">
        <div className="font-display-lg text-display-lg text-on-surface leading-none">{value}</div>
        {changeText && (
          <div className={`font-label-sm text-label-sm ${selectedTrendColor} mt-2 flex items-center gap-1`}>
            <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>{selectedTrendIcon}</span>
            <span>{changeText}</span>
          </div>
        )}
      </div>
    </Card>
  );
}
