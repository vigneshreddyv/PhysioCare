import React from 'react';

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  disabled = false,
  onClick,
  ...props
}) {
  // Base styles without padding
  const baseStyles =
    'rounded-lg font-label-md text-label-md transition-all duration-200 flex items-center justify-center gap-2 active:scale-95 shrink-0';

  // Size-based padding for variants that should scale
  const sizePadding = {
    xs: 'px-2 py-1',
    sm: 'px-3 py-2',
    md: 'px-6 py-3',
    lg: 'px-8 py-4'
  }[size] || 'px-6 py-3';

  // Variants that use size-based padding (primary, secondary, outline, danger, text)
  const sizeDependentVariants = {
    primary: `bg-teal text-white ${sizePadding} hover:bg-navy shadow-sm disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100`,
    secondary: `bg-cream text-navy ${sizePadding} hover:bg-cream/80 disabled:opacity-50 disabled:cursor-not-allowed`,
    outline: `border border-teal text-teal ${sizePadding} hover:bg-teal hover:text-white disabled:opacity-50 disabled:cursor-not-allowed`,
    danger: `bg-error text-on-error ${sizePadding} hover:bg-error/90 disabled:opacity-50 disabled:cursor-not-allowed`,
    text: `text-teal ${sizePadding} hover:bg-teal/20 hover:text-teal/80 disabled:opacity-50 disabled:cursor-not-allowed`,
  };

  // Variants that use fixed padding (preserve existing appearance)
  const fixedVariants = {
    header: 'text-teal font-semibold px-4 py-2 hover:bg-teal/20',
    action: 'bg-teal text-white text-sm font-semibold hover:bg-teal/80 py-2 px-4 shadow-sm',
  };

  // Select variant - check size-dependent first, then fixed, then fallback to primary
  const selectedVariant =
    sizeDependentVariants[variant] ||
    fixedVariants[variant] ||
    sizeDependentVariants.primary;

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