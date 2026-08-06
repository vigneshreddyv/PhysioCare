import React from 'react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';

export default function Settings() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="space-y-stack-lg animate-fade-in max-w-2xl">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Settings</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage portal preferences and view account metadata.</p>
      </div>

      <Card className="space-y-6">
        <div>
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface mb-2 border-b border-surface-container pb-2">Profile Information</h3>
          <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
            <div>
              <p className="font-bold text-on-surface-variant">Full Name</p>
              <p className="text-on-surface text-base mt-1">{user?.full_name}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Email Address</p>
              <p className="text-on-surface text-base mt-1">{user?.email}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">User Role</p>
              <p className="text-on-surface text-base mt-1 capitalize">{user?.role}</p>
            </div>
            <div>
              <p className="font-bold text-on-surface-variant">Portal Status</p>
              <p className="text-secondary font-semibold text-base mt-1">Active</p>
            </div>
          </div>
        </div>

        <div>
          <h3 className="font-headline-md text-headline-md font-semibold text-on-surface mb-2 border-b border-surface-container pb-2">Interface Preferences</h3>
          <div className="flex justify-between items-center mt-4">
            <div>
              <p className="font-semibold text-on-surface">Color Theme</p>
              <p className="text-xs text-on-surface-variant">Switch between Light and Dark interface templates</p>
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
