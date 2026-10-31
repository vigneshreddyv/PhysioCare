import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import { useNavigate } from 'react-router-dom';

export default function Navbar({ onMenuToggle, menuOpen = false, menuButtonRef }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const { data: unreadData } = useQuery({
    queryKey: ['notificationsUnreadCount'],
    queryFn: async () => {
      const response = await api.get('/notifications/unread-count');
      return response.data;
    },
    enabled: Boolean(user),
  });
  const unreadCount = unreadData?.count || 0;
  const profileRef = useRef(null);

  const initials = user?.full_name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join('')
    .toUpperCase() || 'PC';

  useEffect(() => {
    if (!dropdownOpen) return undefined;

    const handlePointerDown = (event) => {
      if (!profileRef.current?.contains(event.target)) setDropdownOpen(false);
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') setDropdownOpen(false);
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [dropdownOpen]);

  return (
    <header className="portal-navbar sticky top-0 z-40 flex justify-between items-center w-full px-4 md:px-container-padding-desktop py-stack-sm min-h-16">
      {/* Left Side: Search (or toggle) */}
      <div className="flex items-center gap-4">
        {/* Mobile Sidebar Toggle Button */}
        <button 
          ref={menuButtonRef}
          onClick={onMenuToggle}
          className="portal-icon-button md:hidden"
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={menuOpen}
          aria-controls="portal-sidebar"
        >
          <span className="material-symbols-outlined" aria-hidden="true">{menuOpen ? 'close' : 'menu'}</span>
        </button>
        <div className="portal-search relative hidden sm:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline">search</span>
          <input
            className="pl-10 pr-4 py-2 bg-surface-container-highest/30 border-none rounded-full font-label-md text-label-md text-on-surface focus:ring-2 focus:ring-primary w-64 transition-all focus:bg-surface"
            placeholder="Search..."
            type="text"
            aria-label="Search portal"
          />
        </div>
        <div className="portal-navbar__context sm:hidden">
          <span>{user?.role === 'doctor' ? 'Clinical workspace' : 'Clinic operations'}</span>
        </div>
      </div>

      {/* Right Side: Quick Links & Avatar */}
      <div className="flex items-center gap-2 relative">
        <button onClick={() => navigate('/notifications')} className="portal-icon-button relative" aria-label="Open notifications">
          <span className="material-symbols-outlined" aria-hidden="true">notifications</span>
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 min-w-4 h-4 px-1 bg-primary text-on-primary text-[10px] font-bold rounded-full flex items-center justify-center">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
        <button className="portal-icon-button hidden sm:inline-flex" aria-label="Open help">
          <span className="material-symbols-outlined" aria-hidden="true">help</span>
        </button>
        
        {/* Avatar Trigger with Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            type="button"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="portal-avatar ml-1 w-10 h-10 rounded-full overflow-hidden cursor-pointer transition-colors"
            aria-haspopup="menu"
            aria-expanded={dropdownOpen}
            aria-label="Open account menu"
          >
            {user?.profile?.profile_image ? (
              <img alt="" className="w-full h-full object-cover" src={user.profile.profile_image} />
            ) : (
              <span aria-hidden="true">{initials}</span>
            )}
          </button>

          {dropdownOpen && (
            <div className="portal-account-menu absolute right-0 mt-2 w-56 rounded-2xl py-2 z-50" role="menu">
              <div className="px-4 py-2 border-b border-surface-container text-xs text-on-surface-variant">
                <p className="font-semibold text-on-surface truncate">{user?.full_name}</p>
                <p className="truncate">{user?.email}</p>
                <span className="inline-block px-2 py-0.5 mt-1 text-[10px] font-bold rounded-full bg-primary-container/20 text-primary capitalize">
                  {user?.role}
                </span>
              </div>
              <button
                onClick={async () => {
                  setDropdownOpen(false);
                  await logout();
                  navigate('/login', { replace: true });
                }}
                className="w-full text-left px-4 py-2 text-sm text-error hover:bg-surface-container-high transition-colors flex items-center gap-2"
                role="menuitem"
              >
                <span className="material-symbols-outlined text-sm">logout</span>
                Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
