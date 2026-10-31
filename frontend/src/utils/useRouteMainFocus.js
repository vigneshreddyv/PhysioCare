import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

export default function useRouteMainFocus(mainId) {
  const { pathname } = useLocation();
  const previousPath = useRef(pathname);

  useEffect(() => {
    if (previousPath.current === pathname) return undefined;

    previousPath.current = pathname;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(mainId)?.focus();
    });

    return () => window.cancelAnimationFrame(frame);
  }, [mainId, pathname]);
}
