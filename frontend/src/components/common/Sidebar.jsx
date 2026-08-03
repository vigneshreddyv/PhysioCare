import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function Sidebar({ className = '' }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role || 'admin';

  const menuItems = {
    admin: [
      { path: '/admin/dashboard', label: 'Dashboard', icon: 'dashboard' },
      { path: '/admin/patients', label: 'Patients', icon: 'groups' },
      { path: '/admin/doctors', label: 'Doctors', icon: 'medical_services' },
      { path: '/admin/analytics', label: 'Analytics', icon: 'analytics' },
    ],
    doctor: [
      { path: '/doctor/dashboard', label: 'Dashboard', icon: 'dashboard' },
      { path: '/doctor/patients', label: 'Patients', icon: 'groups' },
      { path: '/doctor/home-visits', label: 'Home Visits', icon: 'home_health' },
    ]
  };

  const footerItems = {
    admin: [
      { path: '/admin/billing', label: 'Billing', icon: 'payments' },
      { path: '/admin/settings', label: 'Settings', icon: 'settings' }
    ],
    doctor: [
      { path: '/doctor/settings', label: 'Settings', icon: 'settings' }
    ]
  };

  const items = menuItems[role] || menuItems.admin;
  const footers = footerItems[role] || footerItems.admin;

  const activeClass = "flex items-center gap-3 px-4 py-3 text-primary dark:text-primary-fixed-dim font-bold bg-secondary-container/30 dark:bg-secondary-container/10 rounded-lg scale-95 transition-all duration-200";
  const inactiveClass = "flex items-center gap-3 px-4 py-3 text-on-surface-variant dark:text-outline-variant hover:text-primary dark:hover:text-primary-fixed-dim transition-colors hover:bg-surface-container-high dark:hover:bg-surface-variant transition-all duration-200 rounded-lg";

  return (
    <nav className={`bg-surface-container-low dark:bg-inverse-surface h-screen w-64 fixed left-0 top-0 shadow-sm z-50 flex flex-col py-stack-lg px-stack-md border-r border-surface-container ${className}`}>
      {/* Brand Header */}
      <div className="mb-stack-lg px-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary-container flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined text-on-primary-container">medical_services</span>
        </div>
        <div>
          <h1 className="font-headline-md text-headline-md font-bold text-primary dark:text-primary-fixed-dim">PhysioCare</h1>
          <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">{role} Portal</p>
        </div>
      </div>

      {/* Primary CTA (Role specific or default) */}
      <button 
        onClick={() => role === 'admin' ? navigate('/admin/doctors') : navigate('/doctor/dashboard')}
        className="mb-stack-lg bg-primary text-on-primary font-label-md text-label-md py-3 px-4 rounded-full w-full hover:bg-secondary transition-colors shadow-sm flex items-center justify-center gap-2"
      >
        <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>add</span>
        Portal Actions
      </button>

      {/* Main Navigation links */}
      <div className="flex-1 overflow-y-auto space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => isActive ? activeClass : inactiveClass}
          >
            <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>{item.icon}</span>
            <span className="font-body-md text-body-md">{item.label}</span>
          </NavLink>
        ))}
      </div>

      {/* Footer Navigation links */}
      <div className="mt-auto pt-stack-sm border-t border-outline-variant/30 space-y-1">
        {footers.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => isActive ? activeClass : inactiveClass}
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span className="font-body-md text-body-md">{item.label}</span>
          </NavLink>
        ))}
        {/* Logout Action */}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-4 py-3 text-error hover:bg-error-container/20 transition-colors rounded-lg text-left"
        >
          <span className="material-symbols-outlined">logout</span>
          <span className="font-body-md text-body-md">Logout</span>
        </button>
      </div>
    </nav>
  );
}
