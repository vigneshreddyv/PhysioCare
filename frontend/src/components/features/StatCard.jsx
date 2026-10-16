import React from 'react';
import Card from '../common/Card';
import {
  Calendar,
  CheckCircle2,
  Users,
  User,
  Stethoscope,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';

const iconMap = {
  calendar_today: Calendar,
  check_circle: CheckCircle2,
  groups: Users,
  person: User,
  stethoscope: Stethoscope,
  attach_money: DollarSign,
};

export default function StatCard({
  title,
  value,
  icon,
  changeText,
  changeType = 'up', // 'up', 'down', 'flat'
  colorVariant = 'primary', // 'primary', 'secondary', 'tertiary', 'success', 'warning', 'info'
  trendIcon = undefined,
  _elevation = true,
  fullWidth = false,
  compact = false,
  wrapText = false,
}) {
  
  // Custom healthcare themed color setups
  const iconBgs = {
    primary: 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10',
    secondary: 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10',
    tertiary: 'bg-[#DDEFEA] text-[#0F6B63] border-[#0F6B63]/10',
    success: 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10',
    warning: 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20',
    info: 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10',
    error: 'bg-red-50 text-red-700 border-red-200/50',
    blue: 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10',
    green: 'bg-[#DDEFEA] text-[#0F6B63] border-[#0F6B63]/10',
    purple: 'bg-[#F7F4ED] text-[#183B4A] border-[#E5E0D6]',
  };

  const trendColors = {
    up: 'text-[#0F6B63]',
    down: 'text-red-750',
    flat: 'text-[#60716E]',
  };

  const selectedBg = iconBgs[colorVariant] || iconBgs.primary;
  const selectedTrendColor = trendColors[changeType] || trendColors.up;

  // Resolve Lucide Icon dynamically
  const IconComponent = typeof icon === 'string' ? (iconMap[icon] || Stethoscope) : icon;

  // Resolve Trend Icon dynamically
  let TrendIconComponent = Minus;
  if (changeType === 'up') TrendIconComponent = TrendingUp;
  if (changeType === 'down') TrendIconComponent = TrendingDown;
  if (trendIcon) TrendIconComponent = trendIcon;

  return (
    <Card
      hoverable
      className={`relative overflow-hidden group border-[#E5E0D6] bg-white rounded-2xl p-5 ${
        fullWidth ? 'w-full' : ''
      } ${compact ? 'h-32' : 'h-44'} transition-all duration-300 shadow-sm`}
    >
      <div className="flex flex-col h-full justify-between">
        
        {/* Header with Title and Icon */}
        <div className="flex items-center justify-between gap-3">
          <h3 className={`font-bold text-xs uppercase tracking-wider text-[#60716E] ${wrapText ? 'max-w-xs' : 'truncate'}`}>
            {title}
          </h3>
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center border shrink-0 ${selectedBg}`}>
            <IconComponent className="w-4.5 h-4.5" />
          </div>
        </div>

        {/* Main Value */}
        <div className="text-2xl font-black text-[#183B4A] tracking-tight">
          {value}
        </div>

        {/* Change Indicator */}
        {changeText && (
          <div className="flex items-center gap-1.5 text-[11px] font-bold">
            <TrendIconComponent className={`w-3.5 h-3.5 ${selectedTrendColor}`} />
            <span className={`${selectedTrendColor}`}>
              {changeText}
            </span>
          </div>
        )}

      </div>
    </Card>
  );
}