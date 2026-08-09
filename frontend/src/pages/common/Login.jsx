import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';

const loginSchema = z.object({
  email: z.string().email({ message: 'Enter a valid email address' }),
  password: z
    .string()
    .min(6, { message: 'Password must be at least 6 characters' }),
});

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [authError, setAuthError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const from = location.state?.from?.pathname || '/';

  const {
    register,
    handleSubmit,
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
      setAuthError(
        typeof err === 'string'
          ? err
          : 'Invalid email or password. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-600 shadow-lg">
            <span
              className="material-symbols-outlined text-white text-4xl"
              style={{ fontVariationSettings: "'FILL' 1" }}
            >
              spa
            </span>
          </div>

          <h1 className="text-4xl font-bold text-slate-900">
            PhysioCare
          </h1>

          <p className="mt-2 text-slate-500">
            Your complete physiotherapy care platform
          </p>
        </div>

        {/* Login Card */}
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">

          <div className="mb-7">
            <h2 className="text-2xl font-bold text-slate-900">
              Welcome Back 👋
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              Sign in to continue your healthcare journey.
            </p>
          </div>

          {/* Error */}
          {authError && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <span className="material-symbols-outlined text-lg">
                error
              </span>

              <span>{authError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">

            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-sm font-semibold text-slate-700"
              >
                Email Address
              </label>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  mail
                </span>

                <input
                  id="email"
                  type="email"
                  placeholder="Enter your email address"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-4 text-slate-900 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
                  {...register('email')}
                />
              </div>

              {errors.email && (
                <p className="mt-1 text-xs font-medium text-red-600">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-sm font-semibold text-slate-700"
                >
                  Password
                </label>

                <button
                  type="button"
                  className="text-xs font-semibold text-cyan-700 hover:text-cyan-900"
                >
                  Forgot password?
                </button>
              </div>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  lock
                </span>

                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-12 text-slate-900 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
                  {...register('password')}
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                >
                  <span className="material-symbols-outlined">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>

              {errors.password && (
                <p className="mt-1 text-xs font-medium text-red-600">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Login */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-cyan-700 py-4 text-sm font-bold text-white shadow-md transition hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {/* Divider */}
          <div className="my-7 flex items-center gap-4">
            <div className="h-px flex-1 bg-slate-200" />
            <span className="text-xs font-medium text-slate-400">
              OR
            </span>
            <div className="h-px flex-1 bg-slate-200" />
          </div>

          {/* Google */}
          <button
            type="button"
            className="flex w-full items-center justify-center gap-3 rounded-xl border border-slate-300 bg-white py-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            <span className="text-lg font-bold">G</span>
            Continue with Google
          </button>

          {/* Register */}
          <div className="mt-7 text-center text-sm text-slate-500">
            New to PhysioCare?{' '}
            <Link
              to="/register"
              className="font-bold text-cyan-700 hover:text-cyan-900"
            >
              Create account
            </Link>
          </div>

        </div>

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-slate-400">
          Secure healthcare management powered by PhysioCare
        </p>
      </div>
    </div>
  );
}