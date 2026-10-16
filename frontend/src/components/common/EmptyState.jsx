import React from 'react';
import Button from './Button';
import {
  FolderOpen,
  Calendar,
  Beaker,
  Users,
  ShieldCheck,
  HeartPulse,
} from 'lucide-react';

const iconMap = {
  folder_open: FolderOpen,
  calendar_today: Calendar,
  science: Beaker,
  groups: Users,
  shield: ShieldCheck,
  heart_pulse: HeartPulse,
};

export default function EmptyState({
  title = 'No records found',
  message = 'There is currently no data in this view.',
  icon = 'folder_open',
  actionLabel,
  onAction
}) {
  const IconComponent = typeof icon === 'string' ? (iconMap[icon] || FolderOpen) : icon;

  return (
    <div className="w-full py-12 px-6 flex flex-col items-center justify-center text-center bg-[#F7F4ED]/30 rounded-2xl border border-[#E5E0D6] max-w-lg mx-auto">
      <div className="w-12 h-12 rounded-xl bg-[#EEF5F1] border border-[#0F6B63]/10 flex items-center justify-center mb-4 text-[#0F6B63]">
        <IconComponent className="w-6 h-6" />
      </div>
      <h3 className="text-base font-extrabold text-[#183B4A] mb-2">{title}</h3>
      <p className="text-xs text-[#60716E] max-w-sm mb-6 leading-relaxed">{message}</p>
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction} className="text-xs py-2 px-5 font-bold">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
