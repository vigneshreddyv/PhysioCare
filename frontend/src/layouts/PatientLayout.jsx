import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutGrid,
  CalendarDays,
  HeartPulse,
  FileText,
  UserRound,
  Settings,
  Bell,
  ChevronDown,
  ChevronRight,
  X,
  LogOut,
  Headset,
  Smartphone,
  Menu,
  TrendingUp,
  Dumbbell,
  History,
  FlaskConical,
  Phone,
} from 'lucide-react';
import { useAuth } from '../context/useAuth';

// Low-opacity, tileable medical motif — a plus mark, a "vital sign" ring and
// a heartbeat trace — used as page texture. Kept as a data-URI so it needs
// no image asset and never competes with foreground content.
const MEDICAL_PATTERN = encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="180" height="180">
    <g fill="none" stroke="#1F4B45" stroke-width="1.4" opacity="0.07">
      <path d="M0 46 H24 L32 30 L42 62 L50 46 H70" />
      <circle cx="140" cy="34" r="9" />
      <circle cx="140" cy="34" r="2.4" fill="#1F4B45" stroke="none" />
      <path d="M96 128 H116 L124 112 L134 144 L142 128 H164" />
    </g>
    <g fill="#1F4B45" opacity="0.05">
      <rect x="18" y="118" width="16" height="4.4" rx="1.4" />
      <rect x="24" y="112" width="4.4" height="16" rx="1.4" />
    </g>
  </svg>
`);

function MedicalBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 lg:left-[268px] -z-10 overflow-hidden">
      {/* base wash */}
      <div className="absolute inset-0 bg-[#F6F2EA] dark:bg-zinc-950" />

      {/* tiled motif */}
      <div
        className="absolute inset-0 opacity-70"
        style={{ backgroundImage: `url("data:image/svg+xml,${MEDICAL_PATTERN}")` }}
      />

      {/* soft color depth */}
      <div className="absolute -top-32 -right-24 w-[420px] h-[420px] rounded-full bg-[#EEF5F1]/25 blur-[100px]" />
      <div className="absolute top-[55%] -left-28 w-[360px] h-[360px] rounded-full bg-[#EEF5F1]/20 blur-[100px]" />
      <div className="absolute bottom-[-140px] right-[18%] w-[300px] h-[300px] rounded-full bg-[#F7F4ED]/20 blur-[90px]" />
    </div>
  );
}

// Sidebar nav — swap the icon components below if a different icon set is
// already installed in the project. `badge` is optional (e.g. unread count).
const navigation = [
  { label: 'Services', icon: LayoutGrid, path: '/patient/dashboard' },
  { label: 'Appointments', icon: CalendarDays, path: '/patient/appointments' },
  { label: 'My Care Plan', icon: HeartPulse, path: '/patient/care-plan' },
  { label: 'Exercises', icon: Dumbbell, path: '/patient/exercises' },
  { label: 'Progress', icon: TrendingUp, path: '/patient/progress' },
  { label: 'Reports', icon: FileText, path: '/patient/reports' },
  { label: 'Notifications', icon: Bell, path: '/notifications' },
  { label: 'Profile', icon: UserRound, path: '/patient/profile' },
  { label: 'Settings', icon: Settings, path: '/patient/settings' },
];

export default function PatientLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const [showMoreMenu, setShowMoreMenu] = useState(false);

  const name = user?.full_name || 'Patient';

  const initials = name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  // Sign out always asks for confirmation first — the actual logout only
  // happens once the user confirms, from any surface (sidebar, dropdown, hub).
  const [confirmLogout, setConfirmLogout] = useState(false);

  const requestLogout = () => {
    setIsDrawerOpen(false);
    setShowMoreMenu(false);
    setConfirmLogout(true);
  };

  const handleLogout = () => {
    setConfirmLogout(false);
    logout();
  };

  const mobileNavItems = [
    { label: 'Home', icon: LayoutGrid, path: '/patient/dashboard' },
    { label: 'Care Plan', icon: HeartPulse, path: '/patient/care-plan' },
    { label: 'Exercises', icon: Dumbbell, path: '/patient/exercises' },
    { label: 'Progress', icon: TrendingUp, path: '/patient/progress' },
  ];

  const serviceGroups = [
    {
      category: 'PRIMARY CARE',
      items: [
        {
          name: 'Appointments',
          description: 'Manage upcoming sessions',
          icon: CalendarDays,
          path: '/patient/appointments',
          isPrimary: true,
        },
        {
          name: 'Laboratory Tests',
          description: 'Blood tests, panels and home collection',
          icon: FlaskConical,
          path: '/patient/laboratory',
        },
      ],
    },
    {
      category: 'MY RECOVERY',
      items: [
        {
          name: 'Reports',
          description: 'View clinical reports',
          icon: FileText,
          path: '/patient/reports',
        },
        {
          name: 'History',
          description: 'Review your recovery history',
          icon: History,
          path: '/patient/history',
        },
      ],
    },
    {
      category: 'ACCOUNT',
      items: [
        {
          name: 'Notifications',
          description: 'View recent updates and alerts',
          icon: Bell,
          path: '/notifications',
        },
        {
          name: 'Profile',
          description: 'Manage your personal information',
          icon: UserRound,
          path: '/patient/profile',
        },
        {
          name: 'Settings',
          description: 'Preferences and appearance',
          icon: Settings,
          path: '/patient/settings',
        },
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-[#F6F2EA] dark:bg-zinc-950">
      {/* SIDEBAR */}
      <aside
        className={`${isDrawerOpen ? 'flex' : 'hidden'} lg:flex fixed left-0 top-0 bottom-0 w-[268px] bg-white dark:bg-zinc-900 border-r border-[#E5E0D6] dark:border-zinc-800 flex-col z-40`}
      >
        {/* LOGO */}
        <div className="h-[76px] px-7 flex items-center gap-3 border-b border-[#E5E0D6] dark:border-zinc-800">
          <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center">
            <HeartPulse className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" strokeWidth={2.4} />
          </div>
          <span className="text-[22px] font-extrabold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Physio<span className="text-[#1F4B45] dark:text-[#5FC2B8]">Care</span>
          </span>
        </div>

        {/* NAVIGATION */}
        <nav className="p-4 space-y-1.5 flex-1 overflow-y-auto">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.label}
                to={item.path}
                end={item.path === '/patient/dashboard'}
                onClick={() => setIsDrawerOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3.5 px-4 py-3 rounded-xl font-semibold text-[15px] transition-colors ${
                    isActive
                       ? 'bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8]'
                       : 'text-[#1E2A2B]/80 dark:text-zinc-300 hover:bg-[#EEF5F1]/50 dark:hover:bg-zinc-800 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8]'
                  }`
                }
              >
                {() => (
                  <>
                    <Icon
                      className="w-[18px] h-[18px] shrink-0"
                      strokeWidth={2}
                    />
                    <span className="flex-1">{item.label}</span>
                    {item.badge ? (
                      <span className="min-w-[20px] h-5 px-1 rounded-full bg-[#1F4B45]/15 dark:bg-zinc-700 text-[#1F4B45] dark:text-[#5FC2B8] text-xs font-bold flex items-center justify-center">
                        {item.badge}
                      </span>
                    ) : null}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        {/* SUPPORT + APP DOWNLOAD */}
        <div className="p-4 space-y-3">
          <div className="rounded-xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED]/50 dark:bg-zinc-800/50 p-4">
            <div className="w-8 h-8 rounded-lg bg-[#EEF5F1] dark:bg-zinc-700 flex items-center justify-center mb-3">
              <Headset className="w-[18px] h-[18px] text-[#1F4B45] dark:text-[#5FC2B8]" />
            </div>
            <p className="font-bold text-[#1E2A2B] dark:text-zinc-100 text-sm">Need help?</p>
            <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1 leading-5">
              Our support team is here for you, day or night.
            </p>
            <button className="mt-4 w-full py-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-[#F7F4ED]/50 dark:bg-zinc-900 text-[#1F4B45] dark:text-[#5FC2B8] font-semibold text-sm hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 transition">
              Contact support
            </button>
          </div>

          <div className="rounded-xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED]/50 dark:bg-zinc-800/50 p-4">
            <div className="relative flex items-center gap-2">
              <Smartphone className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" />
              <p className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-100">Get the app</p>
            </div>
            <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1 leading-5">
              Book and track care on the go.
            </p>
          </div>

          <button
            onClick={requestLogout}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-[#F7F4ED]/50 dark:bg-zinc-900 text-sm font-semibold text-[#60716E] dark:text-zinc-400 hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 transition"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>
      </aside>

      {/* BACKDROP */}
      {isDrawerOpen && (
        <div className="fixed inset-0 z-35 bg-black/40 lg:hidden" onClick={() => setIsDrawerOpen(false)} />
      )}

      {/* MAIN AREA */}
      <div className="lg:ml-[268px] relative pb-[84px] lg:pb-0">
        <MedicalBackdrop />

        {/* TOP BAR */}
        <header className="h-[76px] bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm border-b border-[#E5E0D6] dark:border-zinc-800 sticky top-0 z-30 px-4 lg:px-6 flex items-center justify-between gap-3">
          {/* HAMBURGER (mobile only) */}
          <button
            aria-label="Open navigation"
            onClick={() => setIsDrawerOpen(true)}
            className="w-11 h-11 lg:hidden flex items-center justify-center hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 transition-colors rounded-xl text-[#1E2A2B] dark:text-zinc-100"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* LOGO */}
          <div className="hidden lg:flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center">
              <HeartPulse className="w-4 h-4 text-[#1F4B45] dark:text-[#5FC2B8]" strokeWidth={2} />
            </div>
            <span className="text-[18px] font-extrabold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
              Physio<span className="text-[#1F4B45] dark:text-[#5FC2B8]">Care</span>
            </span>
          </div>

          {/* SPACER */}
          <div className="hidden lg:block flex-1" />

          {/* ACTIONS */}
          <div className="flex items-center gap-2">
            <button
              aria-label="Notifications"
              onClick={() => navigate('/notifications')}
              className="relative w-11 h-11 rounded-xl hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 text-[#60716E] dark:text-zinc-300 flex items-center justify-center transition"
            >
              <Bell className="w-[18px] h-[18px]" />
            </button>

            <div className="relative">
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 pl-2 pr-1 min-h-[44px] rounded-xl hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 transition"
              >
                <div className="w-8 h-8 rounded-full bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center text-[#1F4B45] dark:text-[#5FC2B8] font-medium">
                  {initials}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 leading-tight">
                    {name}
                  </p>
                  <p className="text-xs text-[#60716E] dark:text-zinc-400 leading-tight">
                    Patient
                  </p>
                </div>
                <ChevronDown className="w-3 h-3 text-[#60716E] dark:text-zinc-400" />
              </button>

              {menuOpen && (
                <div
                  className="absolute right-0 mt-2 w-48 bg-white dark:bg-zinc-900 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 shadow-lg py-2 z-50"
                  onMouseLeave={() => setMenuOpen(false)}
                >
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/patient/profile'); }}
                    className="w-full text-left px-3 py-2 text-sm font-medium text-[#60716E] dark:text-zinc-300 hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800"
                  >
                    View profile
                  </button>
                  <button
                    onClick={() => { setMenuOpen(false); navigate('/patient/settings'); }}
                    className="w-full text-left px-3 py-2 text-sm font-medium text-[#60716E] dark:text-zinc-300 hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800"
                  >
                    Settings
                  </button>
                  <button
                    onClick={requestLogout}
                    className="w-full text-left px-3 py-2 text-sm font-medium text-red-500 hover:bg-red-50"
                  >
                    Log out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* CONTENT */}
        <main className="px-5 lg:px-8 py-7">
          <Outlet />
        </main>
      </div>

      {/* MOBILE BOTTOM NAVIGATION BAR */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 h-[68px] bg-white dark:bg-zinc-900 border-t border-[#E5E0D6] dark:border-zinc-800 shadow-lg flex items-center justify-around z-45 px-2 pb-safe">
        {mobileNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.label}
              to={item.path}
              end={item.path === '/patient/dashboard'}
              onClick={() => { setIsDrawerOpen(false); setShowMoreMenu(false); }}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center w-16 h-12 rounded-xl transition duration-150 relative cursor-pointer min-h-[48px] ${
                  isActive 
                    ? 'text-[#1F4B45] dark:text-[#EEF5F1] font-bold' 
                    : 'text-[#60716E] dark:text-zinc-400 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute inset-0 bg-[#EEF5F1] dark:bg-zinc-800 opacity-90 rounded-xl -z-10 scale-95" />
                  )}
                  <Icon className="w-5 h-5" strokeWidth={isActive ? 2.4 : 2} />
                  <span className="text-xs mt-1 tracking-tight truncate max-w-full font-semibold">
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          );
        })}

        {/* MORE INTERACTION BUTTON */}
        <button
          onClick={() => setShowMoreMenu((v) => !v)}
          className={`flex flex-col items-center justify-center w-16 h-12 rounded-xl transition duration-150 relative cursor-pointer min-h-[48px] ${
            showMoreMenu 
              ? 'text-[#1F4B45] dark:text-[#EEF5F1] font-bold' 
              : 'text-[#60716E] dark:text-zinc-400 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8]'
          }`}
        >
          {showMoreMenu && (
            <span className="absolute inset-0 bg-[#EEF5F1] dark:bg-zinc-800 opacity-90 rounded-xl -z-10 scale-95" />
          )}
          <Menu className="w-5 h-5" strokeWidth={showMoreMenu ? 2.4 : 2} />
          <span className="text-xs mt-1 tracking-tight font-semibold">More</span>
        </button>
      </div>

      {/* MOBILE MORE MENU OVERLAY DRAWER / PATIENT SERVICES HUB */}
      {showMoreMenu && (
        <>
          <div 
            className="lg:hidden fixed inset-0 bg-black/40 backdrop-blur-xs z-48 animate-fade-in" 
            onClick={() => setShowMoreMenu(false)}
          />
          <div className="lg:hidden fixed bottom-0 left-0 right-0 max-h-[85vh] bg-[#F6F2EA] dark:bg-zinc-900 rounded-t-3xl border-t border-[#E5E0D6] dark:border-zinc-800 shadow-2xl p-5 sm:p-6 pb-8 z-49 overflow-y-auto animate-in slide-in-from-bottom duration-200">
            
            {/* Sheet Handle */}
            <div className="w-12 h-1 bg-[#E5E0D6] dark:bg-zinc-700 rounded-full mx-auto mb-4" />

            {/* Sheet Header */}
            <div className="flex items-start justify-between pb-4 border-b border-[#E5E0D6]/60 dark:border-zinc-800 gap-4">
              <div className="space-y-1">                  <span className="text-xs font-extrabold uppercase tracking-widest text-[#1F4B45] dark:text-[#EEF5F1] bg-[#1F4B45]/10 dark:bg-zinc-800 px-2.5 py-0.5 rounded-full border border-[#1F4B45]/10 inline-block">
                  MORE
                </span>
                <h2 className="text-xl sm:text-2xl font-black text-[#1E2A2B] dark:text-zinc-50 leading-tight">
                  Patient Services
                </h2>
                <p className="text-xs text-[#60716E] dark:text-zinc-400">
                  Manage appointments, reports, profile and other services.
                </p>
              </div>
              <button 
                onClick={() => setShowMoreMenu(false)}
                className="w-12 h-12 rounded-2xl bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 text-[#60716E] hover:text-[#1F4B45] flex items-center justify-center cursor-pointer min-h-[48px] min-w-[48px] shrink-0"
                aria-label="Close patient services"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {/* Service Groups */}
            <div className="space-y-6 pt-4">
              {serviceGroups.map((group) => (
                <div key={group.category} className="space-y-2">
                  <span className="text-xs font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block px-1">
                    {group.category}
                  </span>
                  <div className="bg-white dark:bg-zinc-850/60 rounded-2xl border border-[#E5E0D6]/80 dark:border-zinc-800 divide-y divide-[#E5E0D6]/40 dark:divide-zinc-800 overflow-hidden shadow-2xs">
                    {group.items.map((item) => {
                      const Icon = item.icon;
                      const isActive = location.pathname.startsWith(item.path);

                      return (
                        <button
                          key={item.name}
                          onClick={() => {
                            setShowMoreMenu(false);
                            navigate(item.path);
                          }}
                          className={`w-full flex items-center justify-between p-3.5 sm:p-4 text-left transition cursor-pointer min-h-[52px] ${
                            isActive
                              ? 'bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#EEF5F1]'
                              : item.isPrimary
                              ? 'bg-[#F7F4ED]/40 dark:bg-zinc-800/40 hover:bg-[#EEF5F1]/30 dark:hover:bg-zinc-800 text-[#1E2A2B] dark:text-zinc-100'
                              : 'hover:bg-[#EEF5F1]/30 dark:hover:bg-zinc-800 text-[#1E2A2B] dark:text-zinc-100'
                          }`}
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                              isActive
                                ? 'bg-[#1F4B45] text-white shadow-xs'
                                : item.isPrimary
                                ? 'bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#EEF5F1] border border-[#1F4B45]/15'
                                : 'bg-[#F7F4ED] dark:bg-zinc-800 text-[#60716E] dark:text-zinc-300 border border-[#E5E0D6]/60 dark:border-zinc-700'
                            }`}>
                              <Icon className="w-4.5 h-4.5" strokeWidth={isActive ? 2.4 : 2} />
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className={`text-sm font-bold truncate ${
                                  isActive ? 'text-[#1F4B45] dark:text-[#EEF5F1]' : 'text-[#1E2A2B] dark:text-zinc-100'
                                }`}>
                                  {item.name}
                                </span>
                                {item.isPrimary && (
                                  <span className="text-xs font-black uppercase px-1.5 py-0.5 rounded bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#EEF5F1] border border-[#1F4B45]/10">
                                    Primary
                                  </span>
                                )}
                              </div>
                              <p className="text-xs sm:text-[13px] text-[#60716E] dark:text-zinc-400 truncate mt-0.5 font-medium">
                                {item.description}
                              </p>
                            </div>
                          </div>

                          <ChevronRight className={`w-4 h-4 shrink-0 transition-transform ${
                            isActive ? 'text-[#1F4B45] dark:text-[#EEF5F1]' : 'text-[#60716E]/70 dark:text-zinc-500'
                          }`} />
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            
            {/* Sign Out Action */}
            <div className="mt-6 pt-4 border-t border-[#E5E0D6]/60 dark:border-zinc-800 space-y-3">
              {/* Emergency contact — visually distinct from normal settings */}
              <a
                href="tel:+911234567890"
                className="w-full flex items-center justify-between gap-3 px-4 py-3.5 rounded-2xl border border-[#C9A86A]/30 bg-[#C9A86A]/10 dark:bg-[#C9A86A]/10 text-[#1E2A2B] dark:text-zinc-100 hover:bg-[#C9A86A]/20 transition cursor-pointer min-h-[52px]"
              >
                <span className="flex items-center gap-3">
                  <span className="w-9 h-9 rounded-xl bg-white/70 dark:bg-zinc-800 flex items-center justify-center shrink-0">
                    <Phone className="w-4.5 h-4.5 text-[#C9A86A]" />
                  </span>
                  <span className="text-left">
                    <span className="block text-xs sm:text-sm font-extrabold">Emergency Contact</span>
                    <span className="block text-xs text-[#60716E] dark:text-zinc-400">Call your care team anytime</span>
                  </span>
                </span>
                <ChevronRight className="w-4 h-4 text-[#C9A86A] shrink-0" />
              </a>

              <button
                onClick={requestLogout}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-2xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 text-xs sm:text-sm font-extrabold text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-950/30 transition cursor-pointer min-h-[48px]"
              >
                <LogOut className="w-4.5 h-4.5" />
                Sign Out
              </button>
            </div>
          </div>
        </>
      )}

      {/* LOGOUT CONFIRMATION MODAL */}
      {confirmLogout && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
          <div className="bg-[#F6F2EA] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-700 rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-xl space-y-6 animate-scale-up">
            <div className="space-y-2">
              <h2 className="text-xl font-extrabold text-[#1E2A2B] dark:text-zinc-50">
                Sign out of PhysioCare?
              </h2>
              <p className="text-sm text-[#60716E] dark:text-zinc-400 leading-relaxed">
                You will need to sign in again to view your recovery plan, exercises and appointments.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => setConfirmLogout(false)}
                className="flex-1 py-3 bg-[#EEF5F1] dark:bg-zinc-800 hover:bg-[#EEF5F1]/80 dark:hover:bg-zinc-700 text-[#1F4B45] dark:text-zinc-100 rounded-xl text-sm font-bold transition border border-[#E5E0D6] dark:border-zinc-700"
                style={{ minHeight: '48px' }}
              >
                Stay Signed In
              </button>
              <button
                onClick={handleLogout}
                className="flex-1 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl text-sm font-bold transition flex items-center justify-center gap-2"
                style={{ minHeight: '48px' }}
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}