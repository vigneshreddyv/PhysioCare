import React from 'react';
import { Outlet, NavLink, Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';

export default function PatientLayout() {
  const { user, logout, isAuthenticated } = useAuth();

  const activeMobileClass = "flex flex-col items-center justify-center bg-secondary-container dark:bg-on-secondary-fixed-variant text-on-secondary-container dark:text-secondary-fixed rounded-full px-5 py-1 transition-all duration-200 active:scale-90 shrink-0";
  const inactiveMobileClass = "flex flex-col items-center justify-center text-on-surface-variant dark:text-on-tertiary-fixed-variant px-5 py-1 hover:bg-surface-container-high transition-colors rounded-xl shrink-0";

  return (
    <div className="min-h-screen bg-background text-on-surface flex flex-col pb-32 md:pb-8">
      {/* Top App Bar */}
      <header className="bg-surface dark:bg-surface-dim sticky top-0 z-50 bg-surface-container-lowest dark:bg-surface-dim shadow-[0px_4px_20px_rgba(0,123,167,0.05)] flex justify-between items-center w-full px-8 h-16 border-b border-surface-container">
        <Link to="/" className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary dark:text-primary-fixed-dim" style={{ fontVariationSettings: "'FILL' 1" }}>spa</span>
          <span className="font-headline-md text-headline-md font-semibold text-primary dark:text-primary-fixed-dim">PhysioCare</span>
        </Link>
        {isAuthenticated ? (
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-on-surface-variant hidden sm:inline">{user.full_name}</span>
            <button 
              onClick={logout}
              className="font-label-md text-label-md text-primary font-semibold px-4 py-2 rounded-full hover:bg-primary-container/20 transition-colors active:scale-95 transition-transform duration-200"
            >
              Logout
            </button>
          </div>
        ) : (
          <Link
            to="/login"
            className="font-label-md text-label-md text-primary font-semibold px-4 py-2 rounded-full hover:bg-primary-container/20 transition-colors active:scale-95 transition-transform duration-200"
          >
            Login
          </Link>
        )}
      </header>

      {/* Main Viewport */}
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 md:px-8 pt-8">
        <Outlet />
      </main>

      {/* Bottom Nav Bar (Mobile only) */}
      <nav className="md:hidden bg-surface dark:bg-surface-dim fixed bottom-0 w-full z-50 rounded-t-xl bg-surface-container-lowest dark:bg-surface-dim shadow-[0px_-4px_20px_rgba(0,123,167,0.05)] flex justify-around items-center px-4 py-3 pb-safe border-t border-surface-container">
        <NavLink 
          to="/patient/dashboard" 
          className={({ isActive }) => isActive ? activeMobileClass : inactiveMobileClass}
        >
          <span className="material-symbols-outlined mb-1">dashboard</span>
          <span className="font-label-sm text-label-sm">Dashboard</span>
        </NavLink>
        <NavLink 
          to="/patient/book" 
          className={({ isActive }) => isActive ? activeMobileClass : inactiveMobileClass}
        >
          <span className="material-symbols-outlined mb-1" style={{ fontVariationSettings: "'FILL' 1" }}>calendar_month</span>
          <span className="font-label-sm text-label-sm">Book</span>
        </NavLink>
        <NavLink 
          to="/patient/history" 
          className={({ isActive }) => isActive ? activeMobileClass : inactiveMobileClass}
        >
          <span className="material-symbols-outlined mb-1">history</span>
          <span className="font-label-sm text-label-sm">History</span>
        </NavLink>
        <NavLink 
          to="/patient/profile" 
          className={({ isActive }) => isActive ? activeMobileClass : inactiveMobileClass}
        >
          <span className="material-symbols-outlined mb-1">person</span>
          <span className="font-label-sm text-label-sm">Profile</span>
        </NavLink>
      </nav>
    </div>
  );
}
