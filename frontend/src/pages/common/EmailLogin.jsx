import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import Button from '../../components/common/Button';

const loginSchema = z.object({
  email: z.string().email({ message: 'Enter a valid email address' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters' }),
});

export default function EmailLogin() {
  const { login, retryPendingLogin, pendingLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [authError, setAuthError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const requestedDestination = location.state?.from;
  const from = requestedDestination?.pathname || '/app';
  const destinationState = requestedDestination?.state;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data) => {
    if (pendingLogin) return;
    setAuthError('');
    setSubmitting(true);
    try {
      const success = await login(data.email, data.password);
      if (success) navigate(from, { replace: true, state: destinationState });
    } catch (err) {
      setAuthError(typeof err === 'string' ? err : 'Invalid credentials. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const onRetrySessionCheck = async () => {
    setAuthError('');
    setSubmitting(true);
    try {
      if (await retryPendingLogin()) navigate(from, { replace: true, state: destinationState });
    } catch (err) {
      setAuthError(typeof err === 'string' ? err : 'Your account could not be loaded. Retry the session check.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-flow" aria-labelledby="email-login-heading">
      <section className="auth-flow__card">
        <header className="auth-flow__topbar">
          <Link to="/login" state={location.state} aria-label="Back to sign-in options">
            <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
          </Link>
          <span>Sign in</span>
        </header>

        <div className="auth-flow__content">
          <div className="auth-flow__compact-brand" aria-label="PhysioCare">
            <span className="material-symbols-outlined" aria-hidden="true">accessibility_new</span>
            <strong>PhysioCare</strong>
          </div>
          <div className="auth-flow__heading">
            <p>Email access</p>
            <h1 id="email-login-heading">Welcome back</h1>
            <span>Sign in with your registered email and password.</span>
          </div>

          {authError && (
            <div className="auth-flow__auth-error" role="alert" aria-live="polite">
              <span className="material-symbols-outlined" aria-hidden="true">error</span>
              <span><strong>Sign-in is incomplete. </strong>{authError}</span>
            </div>
          )}

          {pendingLogin && (
            <div role="status">
              <p>Sign-in is not complete. Check the existing session before submitting your password again.</p>
              <button type="button" className="auth-flow__primary" disabled={submitting} onClick={onRetrySessionCheck}>
                {submitting ? 'Checking session…' : 'Retry session check'}
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="auth-flow__form" aria-busy={submitting}>
            <div className="auth-flow__field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                inputMode="email"
                placeholder="name@example.com"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'login-email-error' : undefined}
                {...register('email')}
              />
              {errors.email && <p id="login-email-error" className="auth-flow__field-error" role="alert">{errors.email.message}</p>}
            </div>

            <div className="auth-flow__field">
              <label htmlFor="password">Password</label>
              <div className="auth-flow__password">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? 'login-password-error' : undefined}
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  <span className="material-symbols-outlined" aria-hidden="true">{showPassword ? 'visibility_off' : 'visibility'}</span>
                </button>
              </div>
              {errors.password && <p id="login-password-error" className="auth-flow__field-error" role="alert">{errors.password.message}</p>}
            </div>

            <Button variant="patientPrimary" type="submit" className="auth-flow__primary" disabled={submitting || Boolean(pendingLogin)}>
              {submitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <p className="auth-flow__register">New to PhysioCare? <Link to="/register" state={location.state}>Create an account</Link></p>
        </div>
      </section>
    </main>
  );
}
