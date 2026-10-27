import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [phoneError, setPhoneError] = useState('');

  const handlePhoneContinue = (event) => {
    event.preventDefault();
    if (phoneNumber.length !== 10) {
      setPhoneError('Enter a 10-digit Indian mobile number.');
      return;
    }

    setPhoneError('');
    navigate('/verify-phone', { state: location.state });
  };

  return (
    <main className="auth-flow" aria-labelledby="phone-login-heading">
      <section className="auth-flow__card auth-flow__card--entry">
        <header className="auth-flow__brand">
          <span className="auth-flow__brand-mark material-symbols-outlined" aria-hidden="true">accessibility_new</span>
          <div><strong>PhysioCare</strong><span>Move better. Feel supported.</span></div>
        </header>

        <div className="auth-flow__content">
          <div className="auth-flow__heading">
            <p>Welcome</p>
            <h1 id="phone-login-heading">Sign in to continue</h1>
            <span>Use your mobile number, or continue with your registered email.</span>
          </div>

          <form className="auth-flow__form" onSubmit={handlePhoneContinue} noValidate>
            <div className="auth-flow__field">
              <label htmlFor="login-phone">Mobile number</label>
              <div className="auth-flow__phone-field">
                <span aria-hidden="true">+91</span>
                <input
                  id="login-phone"
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel-national"
                  value={phoneNumber}
                  onChange={(event) => {
                    setPhoneNumber(event.target.value.replace(/\D/g, '').slice(0, 10));
                    if (phoneError) setPhoneError('');
                  }}
                  placeholder="10-digit mobile number"
                  aria-invalid={Boolean(phoneError)}
                  aria-describedby={phoneError ? 'login-phone-error' : 'login-phone-note'}
                />
              </div>
              {phoneError ? (
                <p id="login-phone-error" className="auth-flow__field-error" role="alert">{phoneError}</p>
              ) : (
                <p id="login-phone-note" className="auth-flow__field-note">Your number stays on this screen. No message is sent.</p>
              )}
            </div>

            <button type="submit" className="auth-flow__primary">Continue</button>
          </form>

          <div className="auth-flow__divider" aria-hidden="true"><span>or</span></div>

          <Link to="/login/email" state={location.state} className="auth-flow__secondary">
            <span className="material-symbols-outlined" aria-hidden="true">mail</span>
            Continue with email
          </Link>

          <p className="auth-flow__register">New to PhysioCare? <Link to="/register" state={location.state}>Create an account</Link></p>
        </div>
      </section>
    </main>
  );
}
