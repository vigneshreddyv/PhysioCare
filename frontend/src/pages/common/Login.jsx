import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import Button from '../../components/common/Button';

const loginSchema = z.object({
  email: z.string().email({ message: 'Invalid email address' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters' }),
});

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [authError, setAuthError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const from = location.state?.from?.pathname || '/';

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data) => {
    setAuthError('');
    setSubmitting(true);
    try {
      const success = await login(data.email, data.password);
      if (success) {
        navigate(from, { replace: true });
      }
    } catch (err) {
      setAuthError(typeof err === 'string' ? err : 'Invalid credentials. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // Development Quick-Fill helper
  const handleQuickFill = (email, password) => {
    setValue('email', email);
    setValue('password', password);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md bg-surface-container-lowest border border-surface-container rounded-2xl shadow-lg p-8">
        
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-full bg-primary-container flex items-center justify-center mx-auto mb-4">
            <span className="material-symbols-outlined text-primary text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>spa</span>
          </div>
          <h2 className="font-headline-lg text-headline-lg font-bold text-on-surface">PhysioCare Portal</h2>
          <p className="text-sm text-on-surface-variant mt-2">Sign in to manage your appointments and health records</p>
        </div>

        {/* Error notification */}
        {authError && (
          <div className="mb-6 p-4 bg-error-container/20 border border-error/10 text-error rounded-xl text-sm font-semibold flex items-center gap-2">
            <span className="material-symbols-outlined text-base">error</span>
            {authError}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div className="space-y-1">
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              className="w-full rounded-xl border border-outline-variant bg-surface-container-low p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
              placeholder="e.g. john@example.com"
              {...register('email')}
            />
            {errors.email && (
              <p className="text-xs text-error font-semibold mt-1">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1">
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="w-full rounded-xl border border-outline-variant bg-surface-container-low p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
              placeholder="••••••••"
              {...register('password')}
            />
            {errors.password && (
              <p className="text-xs text-error font-semibold mt-1">{errors.password.message}</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full mt-6 py-4"
            disabled={submitting}
          >
            {submitting ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>

        {/* Development Quick-Fill section */}
        <div className="mt-8 border-t border-surface-container pt-6">
          <p className="text-xs font-semibold text-outline text-center mb-3">TEST ACCOUNTS QUICK FILL</p>
          <div className="grid grid-cols-3 gap-2">
            <button
              onClick={() => handleQuickFill('admin@physiocare.com', 'admin123')}
              className="text-[11px] font-semibold py-2 px-1 bg-surface-container-low border border-surface-container hover:bg-primary-container/20 hover:border-primary rounded-xl text-primary transition-colors"
            >
              Admin
            </button>
            <button
              onClick={() => handleQuickFill('sarah.miller@physiocare.com', 'password123')}
              className="text-[11px] font-semibold py-2 px-1 bg-surface-container-low border border-surface-container hover:bg-primary-container/20 hover:border-primary rounded-xl text-primary transition-colors"
            >
              Doctor
            </button>
            <button
              onClick={() => handleQuickFill('john.doe@gmail.com', 'password123')}
              className="text-[11px] font-semibold py-2 px-1 bg-surface-container-low border border-surface-container hover:bg-primary-container/20 hover:border-primary rounded-xl text-primary transition-colors"
            >
              Patient
            </button>
          </div>
        </div>
        
      </div>
    </div>
  );
}
