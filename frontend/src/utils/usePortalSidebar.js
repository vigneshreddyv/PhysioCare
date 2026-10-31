import { useEffect, useRef, useState } from 'react';

export default function usePortalSidebar(drawerId = 'portal-sidebar') {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const menuButtonRef = useRef(null);

  const closeSidebar = (restoreFocus = false) => {
    setSidebarOpen(false);
    if (restoreFocus) {
      window.requestAnimationFrame(() => menuButtonRef.current?.focus());
    }
  };

  const toggleSidebar = () => {
    if (sidebarOpen) closeSidebar(true);
    else setSidebarOpen(true);
  };

  useEffect(() => {
    if (!sidebarOpen) return undefined;

    const drawer = document.getElementById(drawerId);
    const frame = window.requestAnimationFrame(() => {
      drawer?.querySelector('[data-sidebar-close]')?.focus();
    });
    const handleEscape = (event) => {
      if (event.key === 'Escape') closeSidebar(true);
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [drawerId, sidebarOpen]);

  return {
    sidebarOpen,
    menuButtonRef,
    closeSidebar,
    dismissSidebar: () => setSidebarOpen(false),
    toggleSidebar,
  };
}
