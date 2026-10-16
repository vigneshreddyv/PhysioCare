import React, { useState } from 'react';
import { useAuth } from '../../context/useAuth';
import { useNavigate } from 'react-router-dom';
import {
  Menu,
  Search,
  Bell,
  HelpCircle,
  LogOut,
  ChevronDown,
} from 'lucide-react';

export default function Navbar({ onMenuToggle }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // Avatar placeholder if no image exists
  const avatarUrl = "https://lh3.googleusercontent.com/aida-public/AB6AXuCavh9AyrhO8yioOB25FjLYtxaEFV1gL3bFr_5svRuelGJyOhvV40nD-LXDWCsvar4SGkdAq-uO86rzvKJ7iUmkTQJ0mS5NFAW3GsI6t2DxKjur6MeXMnmkJpCAqGAHn7DptS-6X4sE_6IS5GLhUM6LvZLR5uM7jDz7l6ftc_DmtsPUkaNfPS046inTxGS2SEMyE5u0FqKMylkVH0vQCxpGyK_JfLv5A5gk-U8CLWBctzr_bAOoNNJZ";

  return (
    <header className="bg-white border-b border-[#E5E0D6] sticky top-0 z-30 px-4 sm:px-6 h-[76px] flex items-center justify-between gap-3">
      
      {/* Left Side: Mobile Toggle & Search */}
      <div className="flex items-center gap-4">
        {/* Mobile Sidebar Toggle Button */}
        <button 
          aria-label="Open menu"
          onClick={onMenuToggle}
          className="md:hidden text-[#183B4A] p-2 hover:bg-[#EEF5F1]/55 rounded-xl transition-all border border-[#E5E0D6]/40 shadow-xs"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Global Search Bar (Clinician Workspace) */}
        <div className="relative hidden sm:block">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#60716E]" />
          <input
            className="pl-10 pr-4 py-2 bg-[#F7F4ED]/50 border border-[#E5E0D6] rounded-xl text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] w-64 transition-all outline-none"
            placeholder="Search patients, doctors..."
            type="text"
          />
        </div>
      </div>

      {/* Right Side: Quick Links & User Dropdown */}
      <div className="flex items-center gap-2 relative">
        <button 
          aria-label="Notifications"
          onClick={() => navigate('/notifications')} 
          className="p-2 text-[#60716E] hover:bg-[#EEF5F1]/55 rounded-xl transition-all border border-[#E5E0D6]/40 shadow-xs"
        >
          <Bell className="w-4.5 h-4.5" />
        </button>
        <button 
          aria-label="Support"
          className="p-2 text-[#60716E] hover:bg-[#EEF5F1]/55 rounded-xl transition-all border border-[#E5E0D6]/40 shadow-xs"
        >
          <HelpCircle className="w-4.5 h-4.5" />
        </button>
        
        {/* Avatar Trigger with Dropdown */}
        <div className="relative">
          <button 
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="ml-2 flex items-center gap-2 py-1 px-2.5 rounded-xl border border-[#E5E0D6] bg-[#F7F4ED]/30 hover:bg-[#EEF5F1]/20 transition-all shadow-xs cursor-pointer"
          >
            <div className="w-7 h-7 rounded-full overflow-hidden border border-[#E5E0D6] shrink-0">
              <img 
                alt="Profile" 
                className="w-full h-full object-cover" 
                src={user?.profile?.profile_image || avatarUrl} 
              />
            </div>
            <span className="hidden sm:inline text-xs font-bold text-[#183B4A]">{user?.full_name?.split(' ')[0] || 'User'}</span>
            <ChevronDown className="w-3.5 h-3.5 text-[#60716E]" />
          </button>

          {dropdownOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-white border border-[#E5E0D6] rounded-xl shadow-lg py-2.5 z-50">
              <div className="px-4 py-2 border-b border-[#E5E0D6]/50 text-xs text-[#60716E]">
                <p className="font-bold text-[#183B4A] truncate">{user?.full_name}</p>
                <p className="truncate text-[10px] mt-0.5">{user?.email}</p>
                <span className="inline-block px-2.5 py-0.5 mt-1.5 text-[9px] font-bold uppercase rounded bg-[#EEF5F1] text-[#0F6B63] border border-[#0F6B63]/10">
                  {user?.role}
                </span>
              </div>
              <button
                onClick={logout}
                className="w-full text-left px-4 py-2 text-xs text-red-700 hover:bg-red-50 transition-colors flex items-center gap-2 font-bold cursor-pointer mt-1"
              >
                <LogOut className="w-4 h-4 shrink-0 text-red-750" />
                Logout
              </button>
            </div>
          )}
        </div>
      </div>

    </header>
  );
}
