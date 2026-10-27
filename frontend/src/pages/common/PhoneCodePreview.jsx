import React from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';

const CODE_DIGITS = 6;

export default function PhoneCodePreview() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const channelKey = searchParams.get('channel') === 'whatsapp' ? 'whatsapp' : 'sms';
  const channel = channelKey === 'whatsapp' ? 'WhatsApp' : 'SMS';

  return (
    <main className={`auth-flow auth-flow--${channelKey}`} aria-labelledby="code-preview-heading">
      <section className="auth-flow__card">
        <header className="auth-flow__topbar">
          <Link to="/verify-phone" state={location.state} aria-label="Back to channel selection">
            <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
          </Link>
          <span>Verify phone number</span>
        </header>

        <div className="auth-flow__content auth-flow__content--centered">
          <div className="auth-flow__verification-mark" aria-hidden="true">
            <span className="material-symbols-outlined">phonelink_lock</span>
          </div>
          <div className="auth-flow__heading auth-flow__heading--centered">
            <p>Verification preview</p>
            <h1 id="code-preview-heading">Enter your 6-digit code</h1>
            <span>{channel} is not connected yet, so no code was sent.</span>
          </div>

          <div className="auth-flow__code" role="group" aria-label="Six-digit verification code preview">
            {Array.from({ length: CODE_DIGITS }, (_, index) => (
              <label key={index}>
                <span className="sr-only">Digit {index + 1}</span>
                <input type="text" inputMode="numeric" maxLength={1} disabled aria-label={`Verification code digit ${index + 1}`} />
              </label>
            ))}
          </div>

          <div className="auth-flow__status" role="status">
            <span className="material-symbols-outlined" aria-hidden="true">info</span>
            <span>Verification becomes available after a provider is connected.</span>
          </div>

          <button type="button" className="auth-flow__primary" disabled>Verify and continue</button>
          <Link to="/login" state={location.state} className="auth-flow__text-action">Change phone number</Link>
          <Link to="/login/email" state={location.state} className="auth-flow__text-action auth-flow__text-action--muted">Continue with email</Link>
        </div>
      </section>
    </main>
  );
}
