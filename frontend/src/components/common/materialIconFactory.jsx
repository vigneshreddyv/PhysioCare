import React from 'react';

const iconNames = {
  ArrowRight: 'arrow_forward',
  ArrowLeft: 'arrow_back',
  Activity: 'monitoring',
  AlertCircle: 'error',
  AlertTriangle: 'warning',
  Bell: 'notifications',
  Calendar: 'calendar_month',
  CalendarCheck: 'event_available',
  CheckCircle: 'check_circle',
  CheckCircle2: 'check_circle',
  ChevronRight: 'chevron_right',
  ClipboardCheck: 'assignment_turned_in',
  ClipboardList: 'assignment',
  Circle: 'radio_button_unchecked',
  Clock: 'schedule',
  Dumbbell: 'fitness_center',
  Eye: 'visibility',
  FileText: 'description',
  HeartPulse: 'monitor_heart',
  History: 'history',
  Info: 'info',
  LogOut: 'logout',
  Moon: 'dark_mode',
  Palette: 'palette',
  Pause: 'pause',
  Play: 'play_arrow',
  Plus: 'add',
  Save: 'save',
  Search: 'search',
  ShieldCheck: 'verified_user',
  Sun: 'light_mode',
  Trash2: 'delete',
  User: 'person',
  X: 'close',
  XCircle: 'cancel',
};

export function createMaterialIcon(name) {
  return function MaterialCompatibilityIcon({ className = '', size, ...props }) {
    const sizeStyle = size ? { fontSize: size } : undefined;
    return (
      <span
        className={`material-symbols-outlined ${className}`.trim()}
        style={sizeStyle}
        aria-hidden="true"
        {...props}
      >
        {iconNames[name] || 'help'}
      </span>
    );
  };
}
