import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import api from '../../services/api';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';

export default function PatientProfile() {
  const { user, refreshUserProfile } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({ full_name: '', phone: '', gender: '' });

  useEffect(() => {
    setFormData({
      full_name: user?.full_name || '',
      phone: user?.profile?.phone || '',
      gender: user?.profile?.gender || '',
    });
  }, [user]);

  const updateProfile = useMutation({
    mutationFn: async (payload) => {
      const response = await api.patch('/users/me/patient-profile', payload);
      return response.data;
    },
    onSuccess: async () => {
      await refreshUserProfile();
      setIsEditing(false);
    },
  });
  const profileErrorDetail = updateProfile.error?.response?.data?.detail;
  const profileErrorMessage = typeof profileErrorDetail === 'string'
    ? profileErrorDetail
    : profileErrorDetail?.[0]?.msg || 'Your profile could not be updated. Please review the fields and try again.';

  const handleSubmit = (event) => {
    event.preventDefault();
    updateProfile.mutate({
      full_name: formData.full_name.trim(),
      phone: formData.phone.trim() || null,
      gender: formData.gender.trim() || null,
    });
  };

  const handleCancel = () => {
    setFormData({
      full_name: user?.full_name || '',
      phone: user?.profile?.phone || '',
      gender: user?.profile?.gender || '',
    });
    updateProfile.reset();
    setIsEditing(false);
  };
  const initials = user?.full_name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join('')
    .toUpperCase() || 'PC';

  return (
    <div className="patient-page patient-profile animate-fade-in pb-16 max-w-2xl mx-auto">
      <header className="patient-page__header" data-patient-reveal>
        <div className="patient-page__header-copy">
          <p className="patient-page__eyebrow">Account</p>
          <h1 className="patient-page__title">Profile & Preferences</h1>
          <p className="patient-page__description">Review the account details connected to your care and choose the display that works for you.</p>
        </div>
      </header>

      <Card className="patient-profile__card space-y-6" data-patient-reveal>
        <div className="patient-profile__summary">
          <span className="patient-profile__avatar" aria-hidden="true">{initials}</span>
          <div>
            <p>Patient account</p>
            <h2>{user?.full_name || 'PhysioCare patient'}</h2>
            <span>{user?.email || 'No email registered'}</span>
          </div>
          {!isEditing && (
            <Button variant="outline" onClick={() => setIsEditing(true)}>
              <span className="material-symbols-outlined" aria-hidden="true">edit</span>
              Edit profile
            </Button>
          )}
        </div>

        <form className="patient-profile__identity" aria-labelledby="health-card-heading" onSubmit={handleSubmit}>
          <h2 id="health-card-heading" className="patient-profile__section-title">Medical Health Card</h2>
          <dl className="patient-profile__fields">
            <div className="patient-profile__field">
              <dt>Full Name</dt>
              <dd>
                {isEditing ? (
                  <input
                    aria-label="Full name"
                    value={formData.full_name}
                    onChange={(event) => setFormData((current) => ({ ...current, full_name: event.target.value }))}
                    minLength={2}
                    maxLength={100}
                    required
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                ) : user?.full_name}
              </dd>
            </div>
            <div className="patient-profile__field">
              <dt>Registered Email</dt>
              <dd>{user?.email}</dd>
            </div>
            <div className="patient-profile__field">
              <dt>Contact Phone</dt>
              <dd>
                {isEditing ? (
                  <input
                    aria-label="Contact phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(event) => setFormData((current) => ({ ...current, phone: event.target.value }))}
                    maxLength={24}
                    placeholder="Optional"
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                ) : user?.profile?.phone || 'Not registered'}
              </dd>
            </div>
            <div className="patient-profile__field">
              <dt>Date of Birth</dt>
              <dd>{user?.profile?.date_of_birth || 'Not registered'}</dd>
            </div>
            <div className="patient-profile__field">
              <dt>Gender</dt>
              <dd>
                {isEditing ? (
                  <input
                    aria-label="Gender"
                    value={formData.gender}
                    onChange={(event) => setFormData((current) => ({ ...current, gender: event.target.value }))}
                    maxLength={80}
                    placeholder="Optional; enter how you describe your gender"
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                ) : user?.profile?.gender || 'Not recorded'}
              </dd>
            </div>
            <div className="patient-profile__field patient-profile__field--status">
              <dt>Care Subscription Status</dt>
              <dd>
                <span className="patient-profile__subscription">
                  {user?.profile?.subscription_status || 'Not configured'}
                </span>
              </dd>
            </div>
          </dl>
          {isEditing && (
            <div className="space-y-3 mt-5">
              <p className="text-sm text-on-surface-variant">Gender is optional and patient-recorded. Email, date of birth, role, and care status remain read-only.</p>
              {updateProfile.isError && (
                <p className="patient-booking__submit-error" role="alert">
                  {profileErrorMessage}
                </p>
              )}
              <div className="flex flex-wrap gap-3">
                <Button type="submit" disabled={updateProfile.isPending}>
                  {updateProfile.isPending ? 'Saving…' : 'Save changes'}
                </Button>
                <Button variant="outline" onClick={handleCancel} disabled={updateProfile.isPending}>Cancel</Button>
              </div>
            </div>
          )}
        </form>

        <section className="patient-profile__settings" aria-labelledby="accessibility-heading">
          <h2 id="accessibility-heading" className="patient-profile__section-title">Accessibility Settings</h2>
          <div className="patient-profile__theme-row">
            <div className="patient-profile__theme-copy">
              <h3>Color Theme</h3>
              <p>Toggle dark/light background display</p>
            </div>
            <Button variant="outline" onClick={toggleTheme} className="patient-profile__theme-button">
              <span className="material-symbols-outlined" aria-hidden="true">
                {theme === 'light' ? 'dark_mode' : 'light_mode'}
              </span>
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </Button>
          </div>
        </section>

        <p className="patient-profile__privacy-note">
          <span className="material-symbols-outlined" aria-hidden="true">shield_lock</span>
          Your profile is visible only after sign-in. Sign out when using a shared device.
        </p>
      </Card>
    </div>
  );
}
