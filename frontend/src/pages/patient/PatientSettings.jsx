import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  ShieldCheck,
  LogOut,
  ArrowRight,
  User,
  Info,
  Calendar,
  Activity,
  Dumbbell,
  FileText,
} from '../../components/common/LucideCompat';
import { useAuth } from '../../context/useAuth';

export default function PatientSettings() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. SETTINGS HERO */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E5E0D6] bg-gradient-to-br from-[#EEF5F1] via-[#F7F4ED] to-[#DDEFEA]/20 p-6 sm:p-8 lg:p-10 shadow-sm">
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-white border border-[#E5E0D6] flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6 text-[#0F6B63]" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight text-[#183B4A]">App Preferences</h1>
            <p className="text-xs sm:text-sm text-[#60716E] mt-1 leading-relaxed">
              Configure your PhysioCare dashboard displays, local notification alerts, and session credentials.
            </p>
          </div>
        </div>
      </section>

      {/* 2. SPLIT LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: NAVIGATION SHORTCUTS */}
        <div className="space-y-6">
          
          {/* QUICK LINKS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 space-y-4 shadow-sm">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Quick Navigation</h3>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => navigate('/patient/profile')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 bg-[#F7F4ED]/20 hover:bg-[#EEF5F1] transition text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <User className="w-4 h-4 text-[#0F6B63]" />
                  <span className="text-xs font-bold text-[#183B4A]">Profile Details</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/care-plan')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 bg-[#F7F4ED]/20 hover:bg-[#EEF5F1] transition text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <Calendar className="w-4 h-4 text-[#0F6B63]" />
                  <span className="text-xs font-bold text-[#183B4A]">My Care Plan</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/exercises')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 bg-[#F7F4ED]/20 hover:bg-[#EEF5F1] transition text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <Dumbbell className="w-4 h-4 text-[#0F6B63]" />
                  <span className="text-xs font-bold text-[#183B4A]">Guided Exercises</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/progress')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 bg-[#F7F4ED]/20 hover:bg-[#EEF5F1] transition text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <Activity className="w-4 h-4 text-[#0F6B63]" />
                  <span className="text-xs font-bold text-[#183B4A]">Recovery Progress</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/reports')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 bg-[#F7F4ED]/20 hover:bg-[#EEF5F1] transition text-left group"
              >
                <div className="flex items-center gap-2.5">
                  <FileText className="w-4 h-4 text-[#0F6B63]" />
                  <span className="text-xs font-bold text-[#183B4A]">Medical Reports</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] group-hover:translate-x-0.5 transition" />
              </button>
            </div>
          </section>

          {/* SIGN OUT ACTION */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 shadow-sm space-y-4">
            <h3 className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Session Controls</h3>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-red-200 bg-red-50 text-xs font-extrabold text-red-700 hover:bg-red-100/50 transition cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              Sign Out Account
            </button>
          </section>

        </div>

        {/* RIGHT COLUMN: PREFERENCES ACCORDIONS */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* NOTIFICATIONS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40">
              <Bell className="w-5 h-5 text-[#0F6B63]" />
              <h2 className="text-base font-extrabold text-[#183B4A]">Notification Alerts</h2>
            </div>

            <div className="rounded-xl bg-[#F7F4ED]/40 border border-[#E5E0D6] p-3 text-[10px] text-[#60716E] flex items-start gap-2">
              <Info className="w-4 h-4 text-[#C9A86A] shrink-0 mt-0.5" />
              <span>Notification delivery is managed by the clinic notification service. Patient-specific alert preferences are not currently persisted.</span>
            </div>
          </section>

          {/* 3. PRIVACY & SECURITY DATA */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40">
              <ShieldCheck className="w-5 h-5 text-[#0F6B63]" />
              <h2 className="text-base font-extrabold text-[#183B4A]">Data Privacy & Security</h2>
            </div>

            <div className="rounded-xl bg-[#EEF5F1] border border-[#0F6B63]/10 p-3.5 text-[10px] text-[#60716E] flex items-start gap-2">
              <ShieldCheck className="w-4.5 h-4.5 text-[#0F6B63] shrink-0" />
              <span>Medical records, laboratory reports, care plans, and exercise details are protected by the existing role and ownership controls. Privacy preference persistence is not currently available.</span>
            </div>
          </section>

        </div>

      </div>

    </div>
  );
}
