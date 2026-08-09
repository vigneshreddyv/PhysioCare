import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import api from '../../services/api';

const registerSchema = z
  .object({
    full_name: z
      .string()
      .min(2, 'Please enter your full name'),

    email: z
      .string()
      .email('Enter a valid email address'),

    password: z
      .string()
      .min(6, 'Password must be at least 6 characters'),

    confirm_password: z
      .string()
      .min(6, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

export default function Register() {
  const navigate = useNavigate();

  const [registerError, setRegisterError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data) => {
    setRegisterError('');
    setSuccessMessage('');
    setSubmitting(true);

    try {
      await api.post('/auth/register', {
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        role: 'patient',
      });

      setSuccessMessage(
        'Your account has been created successfully. Redirecting to login...'
      );

      setTimeout(() => {
        navigate('/login');
      }, 1500);
    } catch (error) {
      const message =
        error.response?.data?.detail ||
        'Unable to create your account. Please try again.';

      setRegisterError(message);
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
            Start your personalized healthcare journey
          </p>
        </div>

        {/* Card */}
        <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl">

          <div className="mb-7">
            <h2 className="text-2xl font-bold text-slate-900">
              Create your account
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              Register as a patient to access PhysioCare services.
            </p>
          </div>

          {/* Error */}
          {registerError && (
            <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">
              {registerError}
            </div>
          )}

          {/* Success */}
          {successMessage && (
            <div className="mb-6 rounded-xl border border-green-200 bg-green-50 p-4 text-sm font-semibold text-green-700">
              {successMessage}
            </div>
          )}

          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-5"
          >

            {/* Full name */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Full Name
              </label>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  person
                </span>

                <input
                  type="text"
                  placeholder="Enter your full name"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-4 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
                  {...register('full_name')}
                />
              </div>

              {errors.full_name && (
                <p className="mt-1 text-xs font-medium text-red-600">
                  {errors.full_name.message}
                </p>
              )}
            </div>

            {/* Email */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Email Address
              </label>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  mail
                </span>

                <input
                  type="email"
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-4 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
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
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Password
              </label>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  lock
                </span>

                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Create a password"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-12 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
                  {...register('password')}
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
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

            {/* Confirm password */}
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Confirm Password
              </label>

              <div className="relative">
                <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
                  lock
                </span>

                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Confirm your password"
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 py-4 pl-12 pr-12 outline-none transition focus:border-cyan-600 focus:bg-white focus:ring-2 focus:ring-cyan-100"
                  {...register('confirm_password')}
                />

                <button
                  type="button"
                  onClick={() =>
                    setShowConfirmPassword(!showConfirmPassword)
                  }
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400"
                >
                  <span className="material-symbols-outlined">
                    {showConfirmPassword
                      ? 'visibility_off'
                      : 'visibility'}
                  </span>
                </button>
              </div>

              {errors.confirm_password && (
                <p className="mt-1 text-xs font-medium text-red-600">
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-cyan-700 py-4 text-sm font-bold text-white shadow-md transition hover:bg-cyan-800 disabled:opacity-60"
            >
              {submitting
                ? 'Creating account...'
                : 'Create Patient Account'}
            </button>
          </form>

          <div className="mt-7 text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link
              to="/login"
              className="font-bold text-cyan-700 hover:text-cyan-900"
            >
              Sign in
            </Link>
          </div>

        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Your information is securely protected by PhysioCare
        </p>
      </div>
    </div>
  );
}