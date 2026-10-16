import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  LayoutGrid,
  Users,
  Stethoscope,
  TrendingUp,
  Home,
  CreditCard,
  Settings,
  LogOut,
  PlusCircle,
  HeartPulse,
} from 'lucide-react';

export default function Sidebar({ className = '' }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const role = user?.role || 'admin';

  const menuItems = {
    admin: [
      { path: '/admin/dashboard', label: 'Dashboard', icon: LayoutGrid },
      { path: '/admin/patients', label: 'Patients', icon: Users },
      { path: '/admin/doctors', label: 'Doctors', icon: Stethoscope },
      { path: '/admin/analytics', label: 'Analytics', icon: TrendingUp },
    ],
    doctor: [
      { path: '/doctor/dashboard', label: 'Dashboard', icon: LayoutGrid },
      { path: '/doctor/patients', label: 'My Patients', icon: Users },
      { path: '/doctor/home-visits', label: 'Home Visits', icon: Home },
    ]
  };

  const footerItems = {
    admin: [
      { path: '/admin/billing', label: 'Billing', icon: CreditCard },
      { path: '/admin/settings', label: 'Settings', icon: Settings }
    ],
    doctor: [
      { path: '/doctor/settings', label: 'Settings', icon: Settings }
    ]
  };

  const items = menuItems[role] || menuItems.admin;
  const footers = footerItems[role] || footerItems.admin;

  const activeClass = "flex items-center gap-3 px-4 py-2.5 text-[#0F6B63] font-bold bg-[#EEF5F1] rounded-xl border border-[#0F6B63]/10 transition-all duration-150 text-xs uppercase tracking-wider";
  const inactiveClass = "flex items-center gap-3 px-4 py-2.5 text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 transition-all duration-150 rounded-xl text-xs uppercase tracking-wider font-semibold";

  return (
    <nav className={`bg-white h-screen w-[268px] fixed left-0 top-0 border-r border-[#E5E0D6] flex flex-col py-6 px-4 z-40 ${className}`}>
      
      {/* Brand Header */}
      <div className="mb-8 px-2.5 flex items-center gap-3 pb-5 border-b border-[#E5E0D6]/60">
        <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] flex items-center justify-center shrink-0 border border-[#0F6B63]/15">
          <HeartPulse className="w-5 h-5 text-[#0F6B63]" />
        </div>
        <div>
          <h1 className="text-lg font-black tracking-tight text-[#183B4A]">PhysioCare</h1>
          <p className="text-[9px] font-bold text-[#60716E] uppercase tracking-widest">{role} Workspace</p>
        </div>
      </div>

      {/* Primary Action Button */}
      <button 
        onClick={() => role === 'admin' ? navigate('/admin/patients/create') : navigate('/doctor/dashboard')}
        className="mb-6 bg-[#0F6B63] hover:bg-[#0F6B63]/90 text-white py-2.5 px-4 rounded-xl w-full transition-all text-xs font-bold shadow-xs flex items-center justify-center gap-2 cursor-pointer border border-transparent"
      >
        <PlusCircle className="w-4 h-4" />
        Portal Actions
      </button>

      {/* Main Navigation */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => isActive ? activeClass : inactiveClass}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>

      {/* Footer Links & Logout */}
      <div className="mt-auto pt-4 border-t border-[#E5E0D6]/60 space-y-1.5">
        {footers.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => isActive ? activeClass : inactiveClass}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
        
        {/* Logout */}
        <button
          onClick={logout}
          className="w-full flex items-center gap-3 px-4 py-2.5 text-red-700 hover:bg-red-50 transition-all rounded-xl text-left text-xs uppercase tracking-wider font-bold cursor-pointer"
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span>Logout</span>
        </button>
      </div>

    </nav>
  );
}
