import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  Palette,
  ShieldCheck,
  LogOut,
  ArrowRight,
  User,
  Sun,
  Moon,
  Info,
  Calendar,
  Activity,
  Dumbbell,
  FileText,
} from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';

export default function PatientSettings() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // Local-only state for notification toggles (frontend-first presentation)
  const [notifications, setNotifications] = useState({
    appointments: true,
    exercises: true,
    announcements: false,
  });

  // Local-only state for privacy toggles
  const [privacy, setPrivacy] = useState({
    shareData: true,
    analytics: false,
  });

  const handleNotificationChange = (key) => {
    setNotifications((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handlePrivacyChange = (key) => {
    setPrivacy((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. SETTINGS HERO */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-gradient-to-br from-[#EEF5F1] via-[#F7F4ED] to-[#EEF5F1]/20 dark:from-zinc-900 dark:via-zinc-900 dark:to-zinc-800/40 p-6 sm:p-8 lg:p-10 shadow-sm">
        <div className="relative z-10 flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6 text-[#1F4B45] dark:text-[#5FC2B8]" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight text-[#1E2A2B] dark:text-zinc-50">App Preferences</h1>
            <p className="text-xs sm:text-sm text-[#60716E] dark:text-zinc-400 mt-1 leading-relaxed">
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
          <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 space-y-4 shadow-sm">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#60716E] dark:text-zinc-400">Quick Navigation</h3>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => navigate('/patient/profile')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 dark:border-zinc-800 bg-[#F7F4ED]/20 dark:bg-zinc-800/40 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition text-left group min-h-[48px]"
              >
                <div className="flex items-center gap-2.5">
                  <User className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">Profile Details</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] dark:text-zinc-400 group-hover:text-[#1F4B45] dark:group-hover:text-[#5FC2B8] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/care-plan')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 dark:border-zinc-800 bg-[#F7F4ED]/20 dark:bg-zinc-800/40 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition text-left group min-h-[48px]"
              >
                <div className="flex items-center gap-2.5">
                  <Calendar className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">My Care Plan</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] dark:text-zinc-400 group-hover:text-[#1F4B45] dark:group-hover:text-[#5FC2B8] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/exercises')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 dark:border-zinc-800 bg-[#F7F4ED]/20 dark:bg-zinc-800/40 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition text-left group min-h-[48px]"
              >
                <div className="flex items-center gap-2.5">
                  <Dumbbell className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">Guided Exercises</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] dark:text-zinc-400 group-hover:text-[#1F4B45] dark:group-hover:text-[#5FC2B8] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/progress')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 dark:border-zinc-800 bg-[#F7F4ED]/20 dark:bg-zinc-800/40 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition text-left group min-h-[48px]"
              >
                <div className="flex items-center gap-2.5">
                  <Activity className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">Recovery Progress</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] dark:text-zinc-400 group-hover:text-[#1F4B45] dark:group-hover:text-[#5FC2B8] group-hover:translate-x-0.5 transition" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/reports')}
                className="w-full flex items-center justify-between p-3 rounded-xl border border-[#E5E0D6]/40 dark:border-zinc-800 bg-[#F7F4ED]/20 dark:bg-zinc-800/40 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition text-left group min-h-[48px]"
              >
                <div className="flex items-center gap-2.5">
                  <FileText className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">Medical Reports</span>
                </div>
                <ArrowRight className="w-4 h-4 text-[#60716E] dark:text-zinc-400 group-hover:text-[#1F4B45] dark:group-hover:text-[#5FC2B8] group-hover:translate-x-0.5 transition" />
              </button>
            </div>
          </section>

          {/* SIGN OUT ACTION */}
          <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#60716E] dark:text-zinc-400">Session Controls</h3>
            <button
              onClick={logout}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 text-sm font-extrabold text-red-700 dark:text-red-400 hover:bg-red-100/50 dark:hover:bg-red-950/40 transition cursor-pointer min-h-[48px]"
            >
              <LogOut className="w-4 h-4" />
              Sign Out Account
            </button>
          </section>

        </div>

        {/* RIGHT COLUMN: PREFERENCES ACCORDIONS */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* 1. APPEARANCE PREFERENCES */}
          <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40 dark:border-zinc-800">
              <Palette className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
              <h2 className="text-base font-extrabold text-[#1E2A2B] dark:text-zinc-50">Display Appearance</h2>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100">Color Theme Display</p>
                <p className="text-xs text-[#60716E] dark:text-zinc-400 mt-0.5">Toggle light or dark modes. System preferences adapt automatically.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => theme !== 'light' && toggleTheme()}
                  aria-pressed={theme === 'light'}
                  className={`p-4 rounded-2xl border-2 text-center transition flex flex-col items-center justify-center gap-3 select-none min-h-[72px] ${
                    theme === 'light'
                      ? 'border-[#1F4B45] bg-[#EEF5F1]/30 dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8] ring-2 ring-[#1F4B45]/10 font-bold'
                      : 'border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-900 text-[#60716E] dark:text-zinc-400 hover:bg-[#EEF5F1]/10 dark:hover:bg-zinc-800'
                  }`}
                >
                  <Sun className="w-5 h-5 text-[#C9A86A]" />
                  <span className="text-xs font-bold">Light Theme</span>
                  <span className="text-xs font-bold uppercase tracking-wider opacity-70">
                    {theme === 'light' ? 'Active' : 'Tap to switch'}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => theme === 'light' && toggleTheme()}
                  aria-pressed={theme !== 'light'}
                  className={`p-4 rounded-2xl border-2 text-center transition flex flex-col items-center justify-center gap-3 select-none min-h-[72px] ${
                    theme !== 'light'
                      ? 'border-[#1F4B45] bg-[#EEF5F1]/30 dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8] ring-2 ring-[#1F4B45]/10 font-bold'
                      : 'border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-900 text-[#60716E] dark:text-zinc-400 hover:bg-[#EEF5F1]/10 dark:hover:bg-zinc-800'
                  }`}
                >
                  <Moon className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  <span className="text-xs font-bold">Dark Theme</span>
                  <span className="text-xs font-bold uppercase tracking-wider opacity-70">
                    {theme !== 'light' ? 'Active' : 'Tap to switch'}
                  </span>
                </button>
              </div>
            </div>
          </section>

          {/* 2. NOTIFICATIONS */}
          <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40 dark:border-zinc-800">
              <Bell className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
              <h2 className="text-base font-extrabold text-[#1E2A2B] dark:text-zinc-50">Notification Alerts</h2>
            </div>

            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <label htmlFor="notif-appointments" className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100 cursor-pointer">
                    Appointment Confirmations
                  </label>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400">Receive reminders and status updates for clinic test bookings.</p>
                </div>
                <label
                  htmlFor="notif-appointments"
                  aria-label="Toggle appointment confirmations"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                >
                  <input
                    id="notif-appointments"
                    type="checkbox"
                    checked={notifications.appointments}
                    onChange={() => handleNotificationChange('appointments')}
                    className="w-4 h-4 rounded border-[#E5E0D6] text-[#1F4B45] focus:ring-[#1F4B45] cursor-pointer"
                  />
                </label>
              </div>

              <div className="flex items-start justify-between gap-4 border-t border-[#E5E0D6]/20 dark:border-zinc-800 pt-4">
                <div className="space-y-1">
                  <label htmlFor="notif-exercises" className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100 cursor-pointer">
                    Exercise Reminders
                  </label>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400">Receive alerts prompting completion checks of prescribed routines.</p>
                </div>
                <label
                  htmlFor="notif-exercises"
                  aria-label="Toggle exercise reminders"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                >
                  <input
                    id="notif-exercises"
                    type="checkbox"
                    checked={notifications.exercises}
                    onChange={() => handleNotificationChange('exercises')}
                    className="w-4 h-4 rounded border-[#E5E0D6] text-[#1F4B45] focus:ring-[#1F4B45] cursor-pointer"
                  />
                </label>
              </div>

              <div className="flex items-start justify-between gap-4 border-t border-[#E5E0D6]/20 dark:border-zinc-800 pt-4">
                <div className="space-y-1">
                  <label htmlFor="notif-announcements" className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100 cursor-pointer">
                    Clinic Announcements
                  </label>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400">Receive schedule notices and general clinician availability changes.</p>
                </div>
                <label
                  htmlFor="notif-announcements"
                  aria-label="Toggle announcement notices"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                >
                  <input
                    id="notif-announcements"
                    type="checkbox"
                    checked={notifications.announcements}
                    onChange={() => handleNotificationChange('announcements')}
                    className="w-4 h-4 rounded border-[#E5E0D6] text-[#1F4B45] focus:ring-[#1F4B45] cursor-pointer"
                  />
                </label>
              </div>
            </div>

            <div className="rounded-xl bg-[#F7F4ED]/40 dark:bg-zinc-800/40 border border-[#E5E0D6] dark:border-zinc-800 p-3 text-xs text-[#60716E] dark:text-zinc-400 flex items-start gap-2">
              <Info className="w-4 h-4 text-[#C9A86A] shrink-0 mt-0.5" />
              <span>Note: Notification alert toggles configure local notification callbacks and alerts.</span>
            </div>
          </section>

          {/* 3. PRIVACY & SECURITY DATA */}
          <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40 dark:border-zinc-800">
              <ShieldCheck className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
              <h2 className="text-base font-extrabold text-[#1E2A2B] dark:text-zinc-50">Data Privacy & Security</h2>
            </div>

            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <label htmlFor="priv-share" className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100 cursor-pointer">
                    Therapist Data Sharing
                  </label>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400">Share active compliance logs with your assigned therapist.</p>
                </div>
                <label
                  htmlFor="priv-share"
                  aria-label="Toggle data sharing"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                >
                  <input
                    id="priv-share"
                    type="checkbox"
                    checked={privacy.shareData}
                    onChange={() => handlePrivacyChange('shareData')}
                    className="w-4 h-4 rounded border-[#E5E0D6] text-[#1F4B45] focus:ring-[#1F4B45] cursor-pointer"
                  />
                </label>
              </div>

              <div className="flex items-start justify-between gap-4 border-t border-[#E5E0D6]/20 dark:border-zinc-800 pt-4">
                <div className="space-y-1">
                  <label htmlFor="priv-analytics" className="text-xs font-bold text-[#1E2A2B] dark:text-zinc-100 cursor-pointer">
                    Enable Anonymous Telemetry
                  </label>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400">Allows anonymous telemetry capture for page load performance tuning.</p>
                </div>
                <label
                  htmlFor="priv-analytics"
                  aria-label="Toggle analytics telemetry"
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center cursor-pointer shrink-0"
                >
                  <input
                    id="priv-analytics"
                    type="checkbox"
                    checked={privacy.analytics}
                    onChange={() => handlePrivacyChange('analytics')}
                    className="w-4 h-4 rounded border-[#E5E0D6] text-[#1F4B45] focus:ring-[#1F4B45] cursor-pointer"
                  />
                </label>
              </div>
            </div>

            <div className="rounded-xl bg-[#EEF5F1] dark:bg-zinc-800/40 border border-[#1F4B45]/10 dark:border-zinc-700 p-3.5 text-xs text-[#60716E] dark:text-zinc-400 flex items-start gap-2">
              <ShieldCheck className="w-4.5 h-4.5 text-[#1F4B45] dark:text-[#5FC2B8] shrink-0" />
              <span>Medical records, clinic laboratory bookings, care plans, and exercise compliance details are protected under standard client-therapist authorization protocols.</span>
            </div>
          </section>

        </div>

      </div>

    </div>
  );
}
