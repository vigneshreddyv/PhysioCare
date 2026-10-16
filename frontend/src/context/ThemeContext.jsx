import React, { createContext, useState, useEffect } from 'react';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    // Check if user explicitly selected a theme preference in settings
    const userSelected = localStorage.getItem('theme_user_selected');
    if (userSelected === 'dark' || userSelected === 'light') {
      return userSelected;
    }
    // Clean up any stale auto-persisted dark theme from the previous matchMedia bug
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' && !userSelected) {
      localStorage.setItem('theme', 'light');
    }
    // The approved default presentation for PhysioCare is ALWAYS light mode
    return 'light';
  });

  useEffect(() => {
    const root = window.document.documentElement;
    root.classList.remove('light', 'dark');
    root.classList.add(theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      localStorage.setItem('theme_user_selected', next);
      return next;
    });
  };

  const setExplicitTheme = (newTheme) => {
    if (newTheme === 'light' || newTheme === 'dark') {
      localStorage.setItem('theme_user_selected', newTheme);
      setTheme(newTheme);
    }
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme: setExplicitTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export { ThemeContext };