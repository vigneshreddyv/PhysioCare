import React from 'react';

export default function Button({
  children,
  variant = 'primary',
  className = '',
  type = 'button',
  disabled = false,
  onClick,
  ...props
}) {
  const baseStyles = 'rounded-full font-label-md text-label-md transition-all duration-200 flex items-center justify-center gap-2 active:scale-95 shrink-0';
  
  const variants = {
    primary: 'bg-primary text-on-primary py-3 px-6 hover:bg-secondary shadow-sm disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100',
    secondary: 'bg-secondary-container text-on-secondary-container py-3 px-6 hover:bg-surface-container-high disabled:opacity-50 disabled:cursor-not-allowed',
    outline: 'border border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary hover:text-primary py-3 px-6 disabled:opacity-50 disabled:cursor-not-allowed',
    header: 'text-primary font-semibold px-4 py-2 hover:bg-primary-container/20',
    action: 'py-2 px-4 bg-primary text-on-primary text-sm font-semibold hover:bg-secondary shadow-sm',
    danger: 'bg-error text-on-error py-3 px-6 hover:bg-error/90 disabled:opacity-50 disabled:cursor-not-allowed'
  };

  const selectedVariant = variants[variant] || variants.primary;

  return (
    <button
      type={type}
      className={`${baseStyles} ${selectedVariant} ${className}`}
      disabled={disabled}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
}
