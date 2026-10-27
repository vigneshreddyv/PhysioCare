import React from 'react';

const icons = {
  brand: (
    <>
      <path d="M12 3.5v17M3.5 12h17" />
      <circle cx="12" cy="12" r="9" />
    </>
  ),
  home: <path d="m3.5 10.5 8.5-7 8.5 7v9.25a.75.75 0 0 1-.75.75h-5.5v-6.25h-4.5v6.25h-5.5a.75.75 0 0 1-.75-.75Z" />,
  services: (
    <>
      <rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="14" y="3.5" width="6.5" height="6.5" rx="1.5" />
      <rect x="3.5" y="14" width="6.5" height="6.5" rx="1.5" />
      <rect x="14" y="14" width="6.5" height="6.5" rx="1.5" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="5.5" width="17" height="15" rx="2.5" />
      <path d="M7.5 3.5v4M16.5 3.5v4M3.5 10h17M8 14h.01M12 14h.01M16 14h.01M8 17.5h.01M12 17.5h.01" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4.5 20.5c.8-4.1 3.3-6.2 7.5-6.2s6.7 2.1 7.5 6.2" />
    </>
  ),
  location: (
    <>
      <path d="M19 10c0 5.25-7 10.5-7 10.5S5 15.25 5 10a7 7 0 1 1 14 0Z" />
      <circle cx="12" cy="10" r="2.2" />
    </>
  ),
  back: <path d="M19 12H5M10 7l-5 5 5 5" />,
  arrow: <path d="M5 12h14M14 7l5 5-5 5" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 5 5" />
    </>
  ),
  time: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3.2 1.8" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8h.01" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="10" width="14" height="10" rx="2.5" />
      <path d="M8 10V7.5a4 4 0 0 1 8 0V10" />
    </>
  ),
  warning: (
    <>
      <path d="M10.2 4.2 3 18a1.8 1.8 0 0 0 1.6 2.5h14.8A1.8 1.8 0 0 0 21 18L13.8 4.2a2 2 0 0 0-3.6 0Z" />
      <path d="M12 9v4M12 16.5h.01" />
    </>
  ),
  clinic: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="4" />
      <path d="M12 8v8M8 12h8" />
    </>
  ),
  visit: (
    <>
      <path d="M3.5 10.5 12 3.5l8.5 7v10h-17Z" />
      <path d="M12 11v6M9 14h6" />
    </>
  ),
  lab: (
    <>
      <path d="M9 3.5h6M10 3.5v5l-5 9a2 2 0 0 0 1.75 3h10.5a2 2 0 0 0 1.75-3l-5-9v-5" />
      <path d="M7.5 15h9" />
    </>
  ),
  pending: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.2 12.3 2.4 2.4 5.4-5.4" />
    </>
  ),
  history: (
    <>
      <path d="M5.2 7.2H2.8V4.8" />
      <path d="M4.2 6.3a8.5 8.5 0 1 1-.5 10.5" />
      <path d="M12 7.5V12l3.2 1.8" />
    </>
  ),
  chevron: <path d="m9 5 7 7-7 7" />,
};

export default function PatientIcon({ name, size = 24, className = '' }) {
  return (
    <svg
      className={`patient-icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {icons[name] || icons.services}
    </svg>
  );
}
