import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/common/Sidebar';
import Navbar from '../components/common/Navbar';
import usePortalSidebar from '../utils/usePortalSidebar';
import useRouteMainFocus from '../utils/useRouteMainFocus';

export default function AdminLayout() {
  const {
    sidebarOpen,
    menuButtonRef,
    closeSidebar,
    dismissSidebar,
    toggleSidebar,
  } = usePortalSidebar();
  useRouteMainFocus('portal-main');

  return (
    <div className="portal-layout min-h-screen bg-background text-on-surface flex">
      <a className="portal-skip-link" href="#portal-main">Skip to main content</a>
      {/* Sidebar for desktop and mobile */}
      <Sidebar
        className={`transition-transform duration-300 ${sidebarOpen ? 'portal-sidebar--open translate-x-0' : 'portal-sidebar--closed -translate-x-full md:translate-x-0'}`}
        onNavigate={dismissSidebar}
        onClose={() => closeSidebar(true)}
      />
      
      {/* Backdrop overlay for mobile menu drawer */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation menu"
          onClick={() => closeSidebar(true)}
          className="portal-drawer-backdrop fixed inset-0 bg-inverse-surface/40 backdrop-blur-sm z-40 md:hidden"
        />
      )}

      {/* Main Content Wrapper (offset by sidebar width on desktop) */}
      <div className="portal-main-wrap flex-1 flex flex-col ml-0 md:ml-64 w-full min-h-screen">
        <Navbar onMenuToggle={toggleSidebar} menuOpen={sidebarOpen} menuButtonRef={menuButtonRef} />
        <main id="portal-main" className="portal-main flex-1 p-container-padding-mobile md:p-container-padding-desktop pb-section-gap" tabIndex="-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
