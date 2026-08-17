import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutGrid,
  CalendarDays,
  HeartPulse,
  FileText,
  Mail,
  UserRound,
  Settings,
  Search,
  Bell,
  MessageCircle,
  ChevronDown,
  LogOut,
  Headset,
  Smartphone,
} from 'lucide-react';
import { useAuth } from '../context/useAuth';

// Low-opacity, tileable medical motif — a plus mark, a "vital sign" ring and
// a heartbeat trace — used as page texture. Kept as a data-URI so it needs
// no image asset and never competes with foreground content.
const MEDICAL_PATTERN = encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="180" height="180">
    <g fill="none" stroke="#0b84a5" stroke-width="1.4" opacity="0.09">
      <path d="M0 46 H24 L32 30 L42 62 L50 46 H70" />
      <circle cx="140" cy="34" r="9" />
      <circle cx="140" cy="34" r="2.4" fill="#0b84a5" stroke="none" />
      <path d="M96 128 H116 L124 112 L134 144 L142 128 H164" />
    </g>
    <g fill="#0b84a5" opacity="0.06">
      <rect x="18" y="118" width="16" height="4.4" rx="1.4" />
      <rect x="24" y="112" width="4.4" height="16" rx="1.4" />
    </g>
  </svg>
`);

function MedicalBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 lg:left-[268px] -z-10 overflow-hidden">
      {/* base wash */}
      <div className="absolute inset-0 bg-[#f5f9fc]" />

      {/* tiled motif */}
      <div
        className="absolute inset-0 opacity-70"
        style={{ backgroundImage: `url("data:image/svg+xml,${MEDICAL_PATTERN}")` }}
      />

      {/* soft color depth */}
      <div className="absolute -top-32 -right-24 w-[420px] h-[420px] rounded-full bg-cyan-200/25 blur-[100px]" />
      <div className="absolute top-[55%] -left-28 w-[360px] h-[360px] rounded-full bg-emerald-200/20 blur-[100px]" />
      <div className="absolute bottom-[-140px] right-[18%] w-[300px] h-[300px] rounded-full bg-blue-200/20 blur-[90px]" />
    </div>
  );
}

// Sidebar nav — swap the icon components below if a different icon set is
// already installed in the project. `badge` is optional (e.g. unread count).
const navigation = [
  { label: 'Services', icon: LayoutGrid, path: '/patient/dashboard' },
  { label: 'Appointments', icon: CalendarDays, path: '/patient/appointments' },
  { label: 'My Care Plan', icon: HeartPulse, path: '/patient/care-plan' },
  { label: 'Reports', icon: FileText, path: '/patient/reports' },
  { label: 'Messages', icon: Mail, path: '/notifications', badge: 3 },
  { label: 'Profile', icon: UserRound, path: '/patient/profile' },
  { label: 'Settings', icon: Settings, path: '/patient/settings' },
];

export default function PatientLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const name = user?.full_name || 'Patient';

  const initials = name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="min-h-screen bg-[#f5f9fc]">
      {/* SIDEBAR */}
      <aside className="hidden lg:flex fixed left-0 top-0 bottom-0 w-[268px] bg-white border-r border-slate-100 flex-col z-40">
        {/* LOGO */}
        <div className="h-[76px] px-7 flex items-center gap-3 border-b border-slate-100">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-cyan-400 to-[#0b6d8f] flex items-center justify-center shadow-md shadow-cyan-900/10">
            <HeartPulse className="w-5 h-5 text-white" strokeWidth={2.4} />
          </div>
          <span className="text-[22px] font-extrabold tracking-tight text-[#0a2540]">
            Physio<span className="text-[#0b84a5]">Care</span>
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
                className={({ isActive }) =>
                  `flex items-center gap-3.5 px-4 py-3 rounded-xl font-semibold text-[15px] transition-colors ${
                    isActive
                      ? 'bg-[#eaf7fd] text-[#0b84a5]'
                      : 'text-slate-500 hover:bg-slate-50 hover:text-[#0b84a5]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className="w-[18px] h-[18px] shrink-0"
                      strokeWidth={isActive ? 2.5 : 2}
                    />
                    <span className="flex-1">{item.label}</span>
                    {item.badge ? (
                      <span className="min-w-[20px] h-5 px-1 rounded-full bg-[#0b84a5] text-white text-[11px] font-bold flex items-center justify-center">
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
          <div className="rounded-2xl bg-gradient-to-br from-[#eaf7fd] to-[#e6fbf5] border border-cyan-50 p-5">
            <div className="w-9 h-9 rounded-xl bg-white shadow-sm flex items-center justify-center mb-3">
              <Headset className="w-[18px] h-[18px] text-[#0b84a5]" />
            </div>
            <p className="font-bold text-[#0a2540] text-sm">Need help?</p>
            <p className="text-[13px] text-slate-500 mt-1 leading-5">
              Our support team is here for you, day or night.
            </p>
            <button className="mt-4 w-full py-2.5 rounded-xl bg-white border border-cyan-100 text-[#0b84a5] font-semibold text-sm hover:bg-cyan-50/60 transition">
              Contact support
            </button>
          </div>

          <div className="rounded-2xl bg-[#0a2540] p-5 relative overflow-hidden">
            <div className="absolute -right-6 -bottom-6 w-24 h-24 rounded-full bg-white/5" />
            <div className="relative flex items-center gap-2 text-white">
              <Smartphone className="w-4 h-4" />
              <p className="font-bold text-sm">Get the app</p>
            </div>
            <p className="relative text-[13px] text-slate-300 mt-1 leading-5">
              Book and track care on the go.
            </p>
          </div>

          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold text-slate-400 hover:bg-red-50 hover:text-red-500 transition"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>
      </aside>

      {/* MAIN AREA */}
      <div className="lg:ml-[268px] relative">
        <MedicalBackdrop />

        {/* TOP BAR */}
        <header className="h-[76px] bg-white/90 backdrop-blur border-b border-slate-100 sticky top-0 z-30 px-5 lg:px-8 flex items-center justify-between gap-4">
          {/* SEARCH */}
          <div className="relative w-full max-w-[400px]">
            <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search anything..."
              className="w-full bg-slate-50 border border-slate-200 rounded-xl py-3 pl-11 pr-4 text-sm outline-none focus:border-cyan-300 focus:ring-2 focus:ring-cyan-100 transition"
            />
          </div>

          {/* ACTIONS */}
          <div className="flex items-center gap-2 ml-4 shrink-0">
            <button
              aria-label="Messages"
              onClick={() => navigate('/notifications')}
              className="w-10 h-10 rounded-xl hover:bg-slate-50 text-slate-500 flex items-center justify-center transition"
            >
              <MessageCircle className="w-[19px] h-[19px]" />
            </button>

            <button
              aria-label="Notifications"
              onClick={() => navigate('/notifications')}
              className="relative w-10 h-10 rounded-xl hover:bg-slate-50 text-slate-500 flex items-center justify-center transition"
            >
              <Bell className="w-[19px] h-[19px]" />
              <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-[#0b84a5] ring-2 ring-white" />
            </button>

            <div className="relative">
              <button
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-3 pl-3 pr-2 py-1.5 rounded-xl hover:bg-slate-50 transition"
              >
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-[#0b6d8f] text-white flex items-center justify-center font-bold shadow-sm text-sm">
                  {initials}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-bold text-[#0a2540] leading-tight">
                    {name}
                  </p>
                  <p className="text-xs text-slate-400 leading-tight">
                    Patient
                  </p>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-400" />
              </button>

              {menuOpen && (
                <div
                  className="absolute right-0 mt-2 w-48 bg-white rounded-xl border border-slate-100 shadow-lg py-2 z-50"
                  onMouseLeave={() => setMenuOpen(false)}
                >
                  <button
                    onClick={() => navigate('/patient/profile')}
                    className="w-full text-left px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    View profile
                  </button>
                  <button
                    onClick={() => navigate('/patient/settings')}
                    className="w-full text-left px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                  >
                    Settings
                  </button>
                  <button
                    onClick={logout}
                    className="w-full text-left px-4 py-2.5 text-sm font-medium text-red-500 hover:bg-red-50"
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
    </div>
  );
}