import React from 'react';
import Button from './Button';

export default function EmptyState({
  title = 'No records found',
  message = 'There is currently no data in this view.',
  icon = 'folder_open',
  actionLabel,
  onAction
}) {
  return (
    <div className="w-full py-12 px-6 flex flex-col items-center justify-center text-center bg-surface-container-low/40 rounded-xl border border-surface-container/60">
      <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center mb-4 text-on-surface-variant">
        <span className="material-symbols-outlined" style={{ fontSize: '28px' }}>{icon}</span>
      </div>
      <h3 className="font-headline-md text-headline-md text-on-surface mb-2">{title}</h3>
      <p className="text-sm text-on-surface-variant max-w-md mb-6">{message}</p>
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
