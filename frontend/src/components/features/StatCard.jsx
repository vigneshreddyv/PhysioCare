import React from 'react';
import Card from '../common/Card';

export default function StatCard({
  title,
  value,
  icon,
  changeText,
  changeType = 'up', // 'up', 'down', 'flat'
  colorVariant = 'primary', // 'primary', 'secondary', 'tertiary', 'success', 'warning', 'info'
  trendIcon = undefined, // Optional custom trend icon
  iconSize = 'lg', // 'sm', 'md', 'lg', 'xl'
  valueSize = '2xl', // Size of the value text
  showIconBackground = true, // Whether to show background behind icon
  elevation = true, // Whether to apply shadow/elevation
  fullWidth = false, // Whether card should stretch to full width
  compact = false, // Compact version for tighter spaces
  wrapText = false, // Whether to allow text wrapping for title and value
}) {
  // Enhanced color variants for healthcare dashboard
  const iconBgs = {
    primary: 'bg-primary/10 text-primary',
    secondary: 'bg-secondary/10 text-secondary',
    tertiary: 'bg-tertiary/10 text-tertiary',
    success: 'bg-success/10 text-success',
    warning: 'bg-warning/10 text-warning',
    info: 'bg-info/10 text-info',
    error: 'bg-error/10 text-error',
  };

  const trendColors = {
    up: 'text-success',
    down: 'text-error',
    flat: 'text-muted',
  };

  const iconSizes = {
    sm: 'h-8 w-8 text-sm',
    md: 'h-9 w-9 text-base',
    lg: 'h-10 w-10 text-lg',
    xl: 'h-12 w-12 text-xl',
  };

  const valueSizes = {
    sm: 'text-sm',
    base: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl',
    '2xl': 'text-2xl font-bold',
    '3xl': 'text-3xl font-bold',
  };

  const selectedBg = iconBgs[colorVariant] || iconBgs.primary;
  const selectedTrendColor = trendColors[changeType] || trendColors.up;
  const selectedIconSize = iconSizes[iconSize] || iconSizes.md;
  const selectedValueSize = valueSizes[valueSize] || valueSizes['2xl'];
  const selectedTrendIcon = trendIcon ||
    (changeType === 'up' ? 'trending_up' :
     changeType === 'down' ? 'trending_down' :
     'trending_flat');

  return (
    <Card
      hoverable
      elevation={elevation ? 'shadow-md' : 'shadow-sm'}
      className={`relative overflow-hidden group ${fullWidth ? 'w-full' : ''} ${compact ? 'h-32' : 'h-48'} transition-all duration-300 hover:shadow-lg`}
    >
      {/* Background Icon Watermark */}
      {showIconBackground && (
        <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity duration-300 pointer-events-none">
          <span className={`material-symbols-outlined text-[48px] ${selectedBg.split(' ')[1]} /* text-color from bg class */`}>
            {icon}
          </span>
        </div>
      )}

      {/* Card Content */}
      <div className="relative z-10 p-4 pt-6">
        {/* Header with Title and Icon */}
        <div className="flex items-center mb-3">
          {showIconBackground && (
            <div className={`${selectedBg} ${selectedIconSize} flex-shrink-0 mr-3`}>
              <span className="material-symbols-outlined">{icon}</span>
            </div>
          )}
          <h3 className={`font-medium text-sm text-muted flex-1 ${wrapText ? 'max-w-xs' : 'truncate'}`}>
            {title}
          </h3>
        </div>

        {/* Main Value */}
        <div className={`${selectedValueSize} text-primary mb-2 font-numbers${wrapText ? ' break-words whitespace-normal max-w-full' : ''}`}>
          {value}
        </div>

        {/* Change Indicator */}
        {changeText && (
          <div className="flex items-center gap-2 text-sm">
            <span className={`material-symbols-outlined ${selectedTrendColor}`}>
              {selectedTrendIcon}
            </span>
            <span className={`${selectedTrendColor} font-medium`}>
              {changeText}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}