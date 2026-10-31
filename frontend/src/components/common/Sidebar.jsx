import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';

export default function Sidebar({ className = '', onNavigate, onClose }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role || 'admin';

  const menuItems = {
    admin: [
      { path: '/admin/dashboard', label: 'Dashboard', icon: 'dashboard' },
      { path: '/admin/patients', label: 'Patients', icon: 'groups' },
      { path: '/admin/care-management', label: 'Care management', icon: 'clinical_notes' },
      { path: '/admin/reports/new', label: 'Clinical reports', icon: 'description' },
      { path: '/admin/doctors', label: 'Doctors', icon: 'medical_services' },
      { path: '/admin/staff', label: 'Staff Management', icon: 'manage_accounts' },
      { path: '/admin/laboratory', label: 'Laboratory Requests', icon: 'biotech' },
      { path: '/admin/demo-services', label: 'Demo services', icon: 'science' },
      { path: '/admin/analytics', label: 'Analytics', icon: 'analytics' },
      { path: '/admin/notifications', label: 'Notifications', icon: 'notifications' },
    ],
    doctor: [
      { path: '/doctor/dashboard', label: 'Dashboard', icon: 'dashboard' },
      { path: '/doctor/patients', label: 'Patients', icon: 'groups' },
      { path: '/doctor/care-management', label: 'Care management', icon: 'clinical_notes' },
      { path: '/doctor/reports/new', label: 'Clinical reports', icon: 'description' },
      { path: '/doctor/home-visits', label: 'Home Visits', icon: 'home_health' },
    ],
    receptionist: [
      { path: '/reception/dashboard', label: 'Schedule', icon: 'calendar_month' },
      { path: '/reception/appointment-booking', label: 'Book appointment', icon: 'event_available' },
      { path: '/reception/patients', label: 'Patient contacts', icon: 'contact_phone' },
    ],
    laboratorian: [
      { path: '/laboratory/dashboard', label: 'Assigned tests', icon: 'biotech' },
    ],
  };

  const footerItems = {
    admin: [
      { path: '/admin/billing', label: 'Billing', icon: 'payments' },
      { path: '/admin/settings', label: 'Settings', icon: 'settings' }
    ],
    doctor: [
      { path: '/doctor/settings', label: 'Settings', icon: 'settings' }
    ],
    receptionist: [],
    laboratorian: [],
  };

  const items = menuItems[role] || [];
  const footers = footerItems[role] || [];

  const activeClass = "portal-sidebar__link portal-sidebar__link--active flex items-center gap-3 px-4 py-3 font-bold rounded-xl transition-all duration-200";
  const inactiveClass = "portal-sidebar__link flex items-center gap-3 px-4 py-3 transition-all duration-200 rounded-xl";
  const actionLabel = role === 'admin'
    ? 'View clinical team'
    : role === 'laboratorian'
      ? 'View assigned tests'
      : role === 'receptionist'
        ? 'Book appointment'
        : "View today's agenda";
  const actionIcon = role === 'admin' ? 'clinical_notes' : role === 'laboratorian' ? 'biotech' : role === 'receptionist' ? 'event_available' : 'today';
  const actionPath = role === 'admin'
    ? '/admin/doctors'
    : role === 'laboratorian'
      ? '/laboratory/dashboard'
      : role === 'receptionist'
        ? '/reception/appointment-booking'
        : '/doctor/dashboard';

  return (
    <aside className={`portal-sidebar h-screen w-64 fixed left-0 top-0 z-50 flex flex-col py-stack-lg px-stack-md ${className}`} aria-label={`${role} portal navigation`}>
      {/* Brand Header */}
      <div className="portal-sidebar__brand mb-stack-lg px-3 flex items-center gap-3">
        <div className="portal-sidebar__mark w-11 h-11 rounded-2xl flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined" aria-hidden="true">physical_therapy</span>
        </div>
        <div className="min-w-0">
          <h1 className="font-headline-md text-headline-md font-bold">PhysioCare</h1>
          <p className="font-label-sm text-label-sm uppercase tracking-wider">{role} workspace</p>
        </div>
        <button type="button" onClick={onClose} className="portal-sidebar__close md:hidden" aria-label="Close navigation menu">
          <span className="material-symbols-outlined" aria-hidden="true">close</span>
        </button>
      </div>

      {/* Primary CTA (Role specific or default) */}
      <button
        onClick={() => {
          navigate(actionPath);
          onNavigate?.();
        }}
        className="portal-sidebar__action mb-stack-lg font-label-md text-label-md py-3 px-4 rounded-2xl w-full transition-colors flex items-center justify-center gap-2"
      >
        <span className="material-symbols-outlined" aria-hidden="true" style={{ fontVariationSettings: "'FILL' 1" }}>{actionIcon}</span>
        {actionLabel}
      </button>

      {/* Main Navigation links */}
      <nav className="flex-1 overflow-y-auto space-y-1" aria-label="Primary">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            className={({ isActive }) => isActive ? activeClass : inactiveClass}
          >
            <span className="material-symbols-outlined" aria-hidden="true" style={{ fontVariationSettings: "'FILL' 1" }}>{item.icon}</span>
            <span className="font-body-md text-body-md">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Footer Navigation links */}
      <div className="mt-auto pt-stack-sm border-t border-outline-variant/30 space-y-1">
        {footers.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onNavigate}
            className={({ isActive }) => isActive ? activeClass : inactiveClass}
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span className="font-body-md text-body-md">{item.label}</span>
          </NavLink>
        ))}
        {/* Logout Action */}
        <button
          onClick={async () => {
            onNavigate?.();
            await logout();
            navigate('/login', { replace: true });
          }}
          className="portal-sidebar__logout w-full flex items-center gap-3 px-4 py-3 transition-colors rounded-xl text-left"
        >
          <span className="material-symbols-outlined">logout</span>
          <span className="font-body-md text-body-md">Logout</span>
        </button>
      </div>
    </aside>
  );
}
