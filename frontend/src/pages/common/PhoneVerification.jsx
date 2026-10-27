import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

const CHANNELS = [
  { id: 'sms', label: 'SMS', icon: 'sms' },
  { id: 'whatsapp', label: 'WhatsApp', icon: 'chat' },
];

export default function PhoneVerification() {
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedChannel, setSelectedChannel] = useState('sms');

  const previewVerification = () => {
    navigate(`/verify-phone/code?channel=${selectedChannel}`, { state: location.state });
  };

  return (
    <main className="auth-flow" aria-labelledby="channel-heading">
      <section className="auth-flow__card">
        <header className="auth-flow__topbar">
          <Link to="/login" state={location.state} aria-label="Back to mobile number">
            <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
          </Link>
          <span>Phone verification</span>
        </header>

        <div className="auth-flow__content">
          <div className="auth-flow__compact-brand" aria-label="PhysioCare">
            <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
            <strong>PhysioCare</strong>
          </div>
          <div className="auth-flow__heading">
            <p>Choose a channel</p>
            <h1 id="channel-heading">How should we send your code?</h1>
            <span>Your number was not submitted or saved. This screen is available for flow review.</span>
          </div>

          <div className="auth-flow__channel-list" role="radiogroup" aria-label="Verification channel">
            {CHANNELS.map((channel) => (
              <button
                key={channel.id}
                type="button"
                role="radio"
                aria-checked={selectedChannel === channel.id}
                className={selectedChannel === channel.id ? 'is-selected' : ''}
                onClick={() => setSelectedChannel(channel.id)}
              >
                <span className="material-symbols-outlined" aria-hidden="true">{channel.icon}</span>
                <span><strong>{channel.label}</strong><small>Not connected</small></span>
                <span className="material-symbols-outlined auth-flow__radio-mark" aria-hidden="true">
                  {selectedChannel === channel.id ? 'radio_button_checked' : 'radio_button_unchecked'}
                </span>
              </button>
            ))}
          </div>

          <div className="auth-flow__status" role="status">
            <span className="material-symbols-outlined" aria-hidden="true">info</span>
            <span>Provider not connected—no code will be sent.</span>
          </div>

          <button type="button" className="auth-flow__primary" onClick={previewVerification}>
            Preview verification
          </button>

          <Link to="/login/email" state={location.state} className="auth-flow__text-action">Continue with email</Link>
        </div>
      </section>
    </main>
  );
}
