import React from 'react';

export default function Card({
  children,
  className = '',
  hoverable = false,
  onClick,
  ...props
}) {
  const baseStyles = 'bg-cream rounded-xl border border-border shadow-sm p-6 overflow-hidden';
  const hoverStyles = hoverable
    ? 'hover:-translate-y-0.5 hover:shadow-[0px_6px_24px_rgba(15,107,99,0.08)] transition-all duration-300'
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