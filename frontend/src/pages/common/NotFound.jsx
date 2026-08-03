import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/common/Button';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 text-center">
      <div className="w-20 h-20 rounded-full bg-surface-container flex items-center justify-center mb-6 text-primary">
        <span className="material-symbols-outlined" style={{ fontSize: '48px' }}>explore_off</span>
      </div>
      <h1 className="font-display-lg text-display-lg text-on-surface mb-2">404</h1>
      <h2 className="font-headline-md text-headline-md text-on-surface mb-4">Page Not Found</h2>
      <p className="text-sm text-on-surface-variant max-w-sm mb-8">
        The requested URL was not found on this server. It might have been moved or deleted.
      </p>
      <Button variant="primary" onClick={() => navigate('/')}>
        Go to Portal
      </Button>
    </div>
  );
}
