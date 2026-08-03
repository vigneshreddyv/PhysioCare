import React from 'react';

export default function Loading({ fullScreen = false }) {
  const containerStyle = fullScreen 
    ? 'fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center'
    : 'w-full py-12 flex items-center justify-center';

  return (
    <div className={containerStyle}>
      <div className="flex flex-col items-center gap-3">
        <div className="w-12 h-12 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
        <p className="text-sm font-semibold text-primary">Loading PhysioCare...</p>
      </div>
    </div>
  );
}
