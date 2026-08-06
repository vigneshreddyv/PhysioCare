import React from 'react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';

export default function PatientProfile() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="space-y-stack-lg animate-fade-in pb-16 max-w-2xl mx-auto">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Profile & Preferences</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage health card metadata and dark theme preferences.</p>
      </div>

      <Card className="space-y-6">
        <div>
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface mb-2 border-b border-surface-container pb-2">Medical Health Card</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 text-sm">
            <div>
              <p className="font-bold text-on-surface-variant">Full Name</p>
              <p className="text-on-surface text-base mt-1">{user?.full_name}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Registered Email</p>
              <p className="text-on-surface text-base mt-1">{user?.email}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Contact Phone</p>
              <p className="text-on-surface text-base mt-1">{user?.profile?.phone || 'Not registered'}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Date of Birth</p>
              <p className="text-on-surface text-base mt-1">{user?.profile?.date_of_birth || 'Not registered'}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Care Subscription Status</p>
              <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-primary-container/20 text-primary capitalize mt-1">
                {user?.profile?.subscription_status || 'Active'}
              </span>
            </div>
          </div>
        </div>

        <div className="pt-4 border-t border-surface-container">
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface mb-2">Accessibility Settings</h3>
          <div className="flex justify-between items-center mt-4">
            <div>
              <p className="font-semibold text-on-surface">Color Theme</p>
              <p className="text-xs text-on-surface-variant">Toggle dark/light background display</p>
            </div>
            <Button variant="outline" onClick={toggleTheme} className="flex items-center gap-2">
              <span className="material-symbols-outlined">
                {theme === 'light' ? 'dark_mode' : 'light_mode'}
              </span>
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
