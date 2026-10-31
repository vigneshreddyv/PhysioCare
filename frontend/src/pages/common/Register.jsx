import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import api from '../../services/api';
import Button from '../../components/common/Button';

const registerSchema = z.object({
  fullName: z.string().trim().min(2, 'Enter your full name'),
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Use at least 8 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
});

export default function Register() {
  const location = useLocation();
  const [submitError, setSubmitError] = useState('');
  const [registered, setRegistered] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (data) => {
    setSubmitError('');
    try {
      await api.post('/auth/register', {
        full_name: data.fullName.trim(),
        email: data.email,
        password: data.password,
      });
      setRegistered(true);
    } catch (error) {
      const detail = error.response?.data?.detail;
      setSubmitError(typeof detail === 'string' ? detail : 'Account creation is unavailable right now. Please try again later.');
    }
  };

  if (registered) {
    return (
      <div className="patient-register min-h-screen flex items-center justify-center p-4">
        <main className="patient-register__success" aria-labelledby="registration-complete-heading">
          <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
          <p className="patient-page__eyebrow">Patient account created</p>
          <h1 id="registration-complete-heading">You can now sign in.</h1>
          <p>Your account was created as a patient account. No appointment has been booked yet.</p>
          <Link to="/login" state={location.state}>Continue to sign in</Link>
        </main>
      </div>
    );
  }

  return (
    <div className="patient-register min-h-screen flex items-center justify-center p-4">
      <div className="patient-register__layout">
        <aside className="patient-register__welcome" aria-labelledby="register-welcome-heading">
          <div className="patient-register__brand">
            <span className="material-symbols-outlined" aria-hidden="true">medical_services</span>
            <span>PhysioCare</span>
          </div>
          <p className="patient-page__eyebrow">Patient portal</p>
          <h2 id="register-welcome-heading">Care that keeps you moving.</h2>
          <p>Create an account to manage your physiotherapy visits in one place.</p>
          <ul>
            <li><span className="material-symbols-outlined" aria-hidden="true">event_available</span>Book clinic appointments</li>
            <li><span className="material-symbols-outlined" aria-hidden="true">history</span>Keep track of your visits</li>
            <li><span className="material-symbols-outlined" aria-hidden="true">lock</span>Access your account securely</li>
          </ul>
        </aside>

        <main className="patient-register__panel" aria-labelledby="register-heading">
          <Link to="/" className="patient-register__back">
            <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
            Back to PhysioCare
          </Link>
          <div className="patient-register__heading">
            <p className="patient-page__eyebrow">Secure patient access</p>
            <h1 id="register-heading">Create your account</h1>
            <p>Register as a patient to use appointment booking and visit history.</p>
          </div>

          {submitError && <div className="patient-register__error" role="alert">{submitError}</div>}

          <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <label>
            <span>Full name</span>
            <input type="text" autoComplete="name" {...register('fullName')} />
            {errors.fullName && <em>{errors.fullName.message}</em>}
          </label>
          <label>
            <span>Email address</span>
            <input type="email" autoComplete="email" {...register('email')} />
            {errors.email && <em>{errors.email.message}</em>}
          </label>
          <label>
            <span>Password</span>
            <input type="password" autoComplete="new-password" {...register('password')} />
            {errors.password && <em>{errors.password.message}</em>}
          </label>
          <label>
            <span>Confirm password</span>
            <input type="password" autoComplete="new-password" {...register('confirmPassword')} />
            {errors.confirmPassword && <em>{errors.confirmPassword.message}</em>}
          </label>

          <p className="patient-register__privacy">
            <span className="material-symbols-outlined" aria-hidden="true">privacy_tip</span>
            Do not enter symptoms, treatment notes, or other health information in this registration form.
          </p>

          <Button variant="patientPrimary" type="submit" disabled={isSubmitting} className="w-full">
            {isSubmitting ? 'Creating account…' : 'Create patient account'}
          </Button>
          </form>

          <p className="patient-register__signin">Already registered? <Link to="/login" state={location.state}>Sign in</Link></p>
        </main>
      </div>
    </div>
  );
}
