import React, { useState } from 'react';
import { useAuth } from '../../context/useAuth';
import { useNavigate } from 'react-router-dom';

export default function Navbar({ onMenuToggle }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Avatar placeholder if no image exists
  const avatarUrl = "https://lh3.googleusercontent.com/aida-public/AB6AXuCavh9AyrhO8yioOB25FjLYtxaEFV1gL3bFr_5svRuelGJyOhvV40nD-LXDWCsvar4SGkdAq-uO86rzvKJ7iUmkTQJ0mS5NFAW3GsI6t2DxKjur6MeXMnmkJpCAqGAHn7DptS-6X4sE_6IS5GLhUM6LvZLR5uM7jDz7l6ftc_DmtsPUkaNfPS046inTxGS2SEMyE5u0FqKMylkVH0vQCxpGyK_JfLv5A5gk-U8CLWBctzr_bAOoNNJZ";

  return (
    <header className="bg-surface/80 dark:bg-surface-dim/80 backdrop-blur-md sticky top-0 z-40 shadow-sm flex justify-between items-center w-full px-container-padding-desktop py-stack-sm h-16 border-b border-surface-container">
      {/* Left Side: Search (or toggle) */}
      <div className="flex items-center gap-4">
        {/* Mobile Sidebar Toggle Button */}
        <button 
          onClick={onMenuToggle}
          className="md:hidden text-primary p-2 hover:bg-surface-container-highest/50 rounded-full transition-all"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>
        <div className="relative hidden sm:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline">search</span>
          <input
            className="pl-10 pr-4 py-2 bg-surface-container-highest/30 border-none rounded-full font-label-md text-label-md text-on-surface focus:ring-2 focus:ring-primary w-64 transition-all focus:bg-surface"
            placeholder="Search..."
            type="text"
          />
        </div>
      </div>

      {/* Right Side: Quick Links & Avatar */}
      <div className="flex items-center gap-2 relative">
        <button onClick={() => navigate('/notifications')} className="p-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-highest/50 dark:hover:bg-surface-variant/50 rounded-full transition-all">
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button className="p-2 text-on-surface-variant dark:text-outline-variant hover:bg-surface-container-highest/50 dark:hover:bg-surface-variant/50 rounded-full transition-all">
          <span className="material-symbols-outlined">help</span>
        </button>
        
        {/* Avatar Trigger with Dropdown */}
        <div className="relative">
          <div 
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="ml-2 w-8 h-8 rounded-full overflow-hidden border-2 border-primary-container/30 cursor-pointer hover:border-primary transition-colors"
          >
            <img 
              alt="Profile" 
              className="w-full h-full object-cover" 
              src={user?.profile?.profile_image || avatarUrl} 
            />
          </div>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-surface-container-lowest border border-surface-container rounded-xl shadow-lg py-2 z-50">
              <div className="px-4 py-2 border-b border-surface-container text-xs text-on-surface-variant">
                <p className="font-semibold text-on-surface truncate">{user?.full_name}</p>
                <p className="truncate">{user?.email}</p>
                <span className="inline-block px-2 py-0.5 mt-1 text-[10px] font-bold rounded-full bg-primary-container/20 text-primary capitalize">
                  {user?.role}
                </span>
              </div>
              <button
                onClick={logout}
                className="w-full text-left px-4 py-2 text-sm text-error hover:bg-surface-container-high transition-colors flex items-center gap-2"
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
