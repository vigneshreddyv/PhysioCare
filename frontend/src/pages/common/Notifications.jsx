import React from 'react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';

export default function Notifications() {
  const { user: _user } = useAuth();
  const { theme: _theme, toggleTheme: _toggleTheme } = useTheme();

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">
          Notifications
        </h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">
          No new notifications
        </p>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Important updates about your appointments and care will appear here.
        </p>
      </div>
    </div>
  );
}