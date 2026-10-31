import React from 'react';
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../context/useAuth';
import PatientIcon from '../components/common/PatientIcon';
import useRouteMainFocus from '../utils/useRouteMainFocus';

export default function PatientLayout() {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  useRouteMainFocus('patient-main');

  const handleLogout = async () => {
    queryClient.clear();
    await logout();
    navigate('/login', { replace: true });
  };

  const navItems = [
    { to: '/patient/dashboard', label: 'Dashboard', mobileLabel: 'Home', icon: 'home', mobile: true },
    { to: '/patient/services', label: 'Services', icon: 'grid_view', mobile: true },
    { to: '/patient/book', label: 'Book', icon: 'calendar_month' },
    { to: '/patient/home-visits', label: 'Home visits', mobileLabel: 'Visits', icon: 'home_health' },
    { to: '/patient/history', label: 'History', icon: 'history' },
    { to: '/patient/payments', label: 'Payments', icon: 'payments' },
    { to: '/patient/profile', label: 'Profile', icon: 'person', mobile: true },
  ];
  const mobileNavItems = navItems.filter((item) => item.mobile);

  return (
    <div className="patient-portal min-h-screen bg-background text-on-surface flex flex-col">
      <a className="patient-portal__skip-link" href="#patient-main">Skip to main content</a>
      {/* Top App Bar */}
      <header className="patient-portal__header sticky top-0 z-50 flex items-center justify-between w-full border-b">
        <Link to="/patient/dashboard" className="patient-portal__brand flex items-center gap-2">
          <span className="patient-portal__brand-icon" aria-hidden="true"><PatientIcon name="brand" size={20} /></span>
          <span>PhysioCare</span>
        </Link>

        <nav className="patient-portal__desktop-nav" aria-label="Patient navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `patient-portal__nav-link${isActive ? ' is-active' : ''}`}
            >
              <PatientIcon name={item.icon === 'grid_view' ? 'services' : item.icon === 'calendar_month' ? 'calendar' : item.icon} size={20} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {isAuthenticated ? (
          <div className="patient-portal__account flex items-center gap-3">
            <span className="patient-portal__user-name">{user.full_name}</span>
            <button
              onClick={handleLogout}
              className="patient-portal__logout"
            >
              Logout
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="patient-portal__logout"
          >
            Login
          </Link>
        )}
      </header>

      {/* Main Viewport */}
      <main id="patient-main" tabIndex="-1" className="patient-portal__main flex-1 w-full mx-auto px-4 md:px-8 pt-8">
        <Outlet />
      </main>

      {/* Bottom Nav Bar (Mobile only) */}
      <nav className="patient-portal__mobile-nav md:hidden" aria-label="Patient navigation">
        {mobileNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `patient-portal__mobile-link${isActive ? ' is-active' : ''}`}
          >
            <PatientIcon name={item.icon === 'grid_view' ? 'services' : item.icon === 'calendar_month' ? 'calendar' : item.icon} size={21} />
            <span>{item.mobileLabel || item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
