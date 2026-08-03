import React from 'react';

export default function Skeleton({ variant = 'card', count = 1 }) {
  const renderItem = (index) => {
    switch (variant) {
      case 'card':
        return (
          <div key={index} className="bg-surface-container-lowest rounded-xl p-6 border border-surface-container flex flex-col justify-between h-40 animate-pulse">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-surface-container-high"></div>
              <div className="h-4 bg-surface-container-high rounded w-24"></div>
            </div>
            <div className="space-y-2 mt-4">
              <div className="h-8 bg-surface-container-high rounded w-16"></div>
              <div className="h-3 bg-surface-container-high rounded w-32"></div>
            </div>
          </div>
        );
      case 'row':
        return (
          <div key={index} className="flex justify-between items-center p-3 rounded-lg border-b border-surface-container animate-pulse">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-surface-container-high"></div>
              <div className="space-y-2">
                <div className="h-4 bg-surface-container-high rounded w-28"></div>
                <div className="h-3 bg-surface-container-high rounded w-20"></div>
              </div>
            </div>
            <div className="space-y-1 text-right">
              <div className="h-4 bg-surface-container-high rounded w-16"></div>
              <div className="h-3 bg-surface-container-high rounded w-12 ml-auto"></div>
            </div>
          </div>
        );
      case 'chart':
        return (
          <div key={index} className="bg-surface-container-lowest rounded-xl p-6 border border-surface-container h-80 animate-pulse flex flex-col justify-between">
            <div className="h-4 bg-surface-container-high rounded w-48 mb-6"></div>
            <div className="flex items-end gap-3 flex-1 px-4">
              <div className="bg-surface-container-high rounded w-full h-[30%]"></div>
              <div className="bg-surface-container-high rounded w-full h-[50%]"></div>
              <div className="bg-surface-container-high rounded w-full h-[20%]"></div>
              <div className="bg-surface-container-high rounded w-full h-[70%]"></div>
              <div className="bg-surface-container-high rounded w-full h-[40%]"></div>
              <div className="bg-surface-container-high rounded w-full h-[85%]"></div>
            </div>
          </div>
        );
      default:
        return (
          <div key={index} className="animate-pulse space-y-2">
            <div className="h-4 bg-surface-container-high rounded w-full"></div>
            <div className="h-4 bg-surface-container-high rounded w-5/6"></div>
          </div>
        );
    }
  };

  return (
    <>
      {Array.from({ length: count }).map((_, i) => renderItem(i))}
    </>
  );
}
