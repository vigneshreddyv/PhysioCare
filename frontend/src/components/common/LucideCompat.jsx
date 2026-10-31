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

// oxlint-disable-next-line react/only-export-components
function createIcon(name) {
  return function CompatibilityIcon({ className = '', size, ...props }) {
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

export const Activity = createIcon('Activity');
export const AlertCircle = createIcon('AlertCircle');
export const AlertTriangle = createIcon('AlertTriangle');
export const ArrowLeft = createIcon('ArrowLeft');
export const ArrowRight = createIcon('ArrowRight');
export const Bell = createIcon('Bell');
export const Calendar = createIcon('Calendar');
export const CalendarCheck = createIcon('CalendarCheck');
export const CheckCircle = createIcon('CheckCircle');
export const CheckCircle2 = createIcon('CheckCircle2');
export const ChevronRight = createIcon('ChevronRight');
export const ClipboardCheck = createIcon('ClipboardCheck');
export const ClipboardList = createIcon('ClipboardList');
export const Circle = createIcon('Circle');
export const Clock = createIcon('Clock');
export const Dumbbell = createIcon('Dumbbell');
export const Eye = createIcon('Eye');
export const FileText = createIcon('FileText');
export const HeartPulse = createIcon('HeartPulse');
export const History = createIcon('History');
export const Info = createIcon('Info');
export const LogOut = createIcon('LogOut');
export const Moon = createIcon('Moon');
export const Palette = createIcon('Palette');
export const Pause = createIcon('Pause');
export const Play = createIcon('Play');
export const Plus = createIcon('Plus');
export const Save = createIcon('Save');
export const Search = createIcon('Search');
export const ShieldCheck = createIcon('ShieldCheck');
export const Sun = createIcon('Sun');
export const Trash2 = createIcon('Trash2');
export const User = createIcon('User');
export const X = createIcon('X');
export const XCircle = createIcon('XCircle');
