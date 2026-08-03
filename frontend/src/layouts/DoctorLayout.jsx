import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/common/Sidebar';
import Navbar from '../components/common/Navbar';

export default function DoctorLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      {/* Sidebar for desktop and mobile */}
      <Sidebar className={`transition-transform duration-300 md:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:hidden'}`} />
      
      {/* Backdrop overlay for mobile menu drawer */}
      {sidebarOpen && (
        <div 
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-inverse-surface/40 backdrop-blur-sm z-40 md:hidden"
        />
      )}

      {/* Main Content Wrapper */}
      <div className="flex-1 flex flex-col ml-0 md:ml-64 w-full min-h-screen">
        <Navbar onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />
        <main className="flex-1 p-container-padding-mobile md:p-container-padding-desktop pb-section-gap">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
