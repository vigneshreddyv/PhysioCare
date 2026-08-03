import React from 'react';
import Button from './Button';

export default function ErrorState({
  message = 'An unexpected error occurred while loading data.',
  onRetry
}) {
  return (
    <div className="w-full py-12 px-6 flex flex-col items-center justify-center text-center bg-error-container/20 rounded-xl border border-error/10">
      <div className="w-12 h-12 rounded-full bg-error/10 flex items-center justify-center mb-4 text-error">
        <span className="material-symbols-outlined" style={{ fontSize: '28px' }}>error</span>
      </div>
      <h3 className="font-headline-md text-headline-md text-on-surface mb-2">Something went wrong</h3>
      <p className="text-sm text-on-surface-variant max-w-md mb-6">{message}</p>
      {onRetry && (
        <Button variant="danger" onClick={onRetry}>
          <span className="material-symbols-outlined">refresh</span>
          Try Again
        </Button>
      )}
    </div>
  );
}
