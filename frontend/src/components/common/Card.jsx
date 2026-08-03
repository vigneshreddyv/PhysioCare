import React from 'react';

export default function Card({
  children,
  className = '',
  hoverable = false,
  onClick,
  ...props
}) {
  const baseStyles = 'bg-surface-container-lowest rounded-xl border border-surface-container shadow-sm p-6 overflow-hidden';
  const hoverStyles = hoverable 
    ? 'hover:-translate-y-0.5 hover:shadow-[0px_6px_24px_rgba(0,123,167,0.08)] transition-all duration-300' 
    : '';
  const clickStyles = onClick ? 'cursor-pointer' : '';

  return (
    <div
      className={`${baseStyles} ${hoverStyles} ${clickStyles} ${className}`}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
}
