import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/common/Sidebar';
import Navbar from '../components/common/Navbar';

const MEDICAL_PATTERN = encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="180" height="180">
    <g fill="none" stroke="#0F6B63" stroke-width="1.4" opacity="0.09">
      <path d="M0 46 H24 L32 30 L42 62 L50 46 H70" />
      <circle cx="140" cy="34" r="9" />
      <circle cx="140" cy="34" r="2.4" fill="#0F6B63" stroke="none" />
      <path d="M96 128 H116 L124 112 L134 144 L142 128 H164" />
    </g>
    <g fill="#0F6B63" opacity="0.06">
      <rect x="18" y="118" width="16" height="4.4" rx="1.4" />
      <rect x="24" y="112" width="4.4" height="16" rx="1.4" />
    </g>
  </svg>
`);

function MedicalBackdrop() {
  return (
    <div className="pointer-events-none fixed inset-0 lg:left-[268px] -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-[#F6F2EA] dark:bg-zinc-950" />
      <div
        className="absolute inset-0 opacity-50"
        style={{ backgroundImage: `url("data:image/svg+xml,${MEDICAL_PATTERN}")` }}
      />
    </div>
  );
}

export default function DoctorLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#F6F2EA] dark:bg-zinc-950 text-[#183B4A] dark:text-zinc-100 flex">
      {/* Sidebar for desktop and mobile */}
      <Sidebar 
        className={`transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`} 
      />
      
      {/* Backdrop overlay for mobile menu drawer */}
      {sidebarOpen && (
        <div 
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-black/40 backdrop-blur-xs z-35 lg:hidden"
        />
      )}

      {/* Main Content Wrapper (offset by sidebar width on desktop) */}
      <div className="flex-1 flex flex-col ml-0 lg:ml-[268px] w-full min-h-screen">
        <Navbar onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />
        <MedicalBackdrop />
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
