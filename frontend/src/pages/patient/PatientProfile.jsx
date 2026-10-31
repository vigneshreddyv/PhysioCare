import React, { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useAuth } from '../../context/useAuth';
import api from '../../services/api';
import Card from '../../components/common/Card';
import Button from '../../components/common/Button';
import { validatePatientProfile } from '../../utils/patientProfileValidation';

export default function PatientProfile() {
  const { user, loading: authLoading, refreshUserProfile } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({ full_name: '', phone: '', gender: '' });
  const [fieldErrors, setFieldErrors] = useState({});
  const [profileLoadError, setProfileLoadError] = useState(false);
  const [saveSucceeded, setSaveSucceeded] = useState(false);
  const [profileRefreshError, setProfileRefreshError] = useState(false);

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
      const refreshed = await refreshUserProfile();
      setProfileRefreshError(!refreshed);
      setIsEditing(false);
      setFieldErrors({});
      setSaveSucceeded(true);
    },
  });
  const profileErrorDetail = updateProfile.error?.response?.data?.detail;
  const profileErrorMessage = typeof profileErrorDetail === 'string'
    ? profileErrorDetail
    : profileErrorDetail?.[0]?.msg || 'Your profile could not be updated. Please review the fields and try again.';

  const handleSubmit = (event) => {
    event.preventDefault();
    setSaveSucceeded(false);
    const errors = validatePatientProfile(formData);
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
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
    setFieldErrors({});
    setSaveSucceeded(false);
    setIsEditing(false);
  };
  const handleRetryProfile = async () => {
    setProfileLoadError(false);
    const refreshed = await refreshUserProfile();
    setProfileLoadError(!refreshed);
  };

  if (authLoading) {
    return <div className="patient-page patient-profile" role="status" aria-live="polite">Loading your profile…</div>;
  }

  if (profileLoadError || !user) {
    return (
      <div className="patient-page patient-profile">
        <section className="patient-profile__state" role="alert">
          <h1 className="patient-page__title">Profile unavailable</h1>
          <p>We couldn’t load your account details. Check your connection and try again.</p>
          <Button onClick={handleRetryProfile}>Try again</Button>
        </section>
      </div>
    );
  }

  if (!user.profile) {
    return (
      <div className="patient-page patient-profile">
        <section className="patient-profile__state" role="status">
          <h1 className="patient-page__title">Profile not found</h1>
          <p>Your signed-in account does not have a patient profile yet. Please contact the clinic for help.</p>
        </section>
      </div>
    );
  }
  const initials = user?.full_name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join('')
    .toUpperCase() || 'PC';

  return (
    <div className="patient-page patient-profile animate-fade-in pb-16 max-w-3xl mx-auto">
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
            <Button variant="outline" onClick={() => { updateProfile.reset(); setFieldErrors({}); setSaveSucceeded(false); setIsEditing(true); }}>
              <span className="material-symbols-outlined" aria-hidden="true">edit</span>
              Edit profile
            </Button>
          )}
        </div>

        <form className="patient-profile__identity" aria-labelledby="health-card-heading" onSubmit={handleSubmit} noValidate>
          <h2 id="health-card-heading" className="patient-profile__section-title">Medical Health Card</h2>
          <dl className="patient-profile__fields">
            <div className="patient-profile__field">
              <dt>Full Name</dt>
              <dd>
                {isEditing ? (
                  <>
                  <input
                    aria-label="Full name"
                    aria-invalid={Boolean(fieldErrors.full_name)}
                    aria-describedby={fieldErrors.full_name ? 'profile-full-name-error' : undefined}
                    value={formData.full_name}
                    onChange={(event) => {
                      setFormData((current) => ({ ...current, full_name: event.target.value }));
                      setFieldErrors((current) => ({ ...current, full_name: undefined }));
                      setSaveSucceeded(false);
                    }}
                    minLength={2}
                    maxLength={100}
                    required
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                  {fieldErrors.full_name && <span id="profile-full-name-error" className="patient-profile__field-error">{fieldErrors.full_name}</span>}
                  </>
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
                  <>
                  <input
                    aria-label="Contact phone"
                    aria-invalid={Boolean(fieldErrors.phone)}
                    aria-describedby={fieldErrors.phone ? 'profile-phone-error' : undefined}
                    type="tel"
                    value={formData.phone}
                    onChange={(event) => {
                      setFormData((current) => ({ ...current, phone: event.target.value }));
                      setFieldErrors((current) => ({ ...current, phone: undefined }));
                      setSaveSucceeded(false);
                    }}
                    maxLength={24}
                    placeholder="Optional"
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                  {fieldErrors.phone && <span id="profile-phone-error" className="patient-profile__field-error">{fieldErrors.phone}</span>}
                  </>
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
                  <>
                  <input
                    aria-label="Gender"
                    aria-invalid={Boolean(fieldErrors.gender)}
                    aria-describedby={fieldErrors.gender ? 'profile-gender-error' : undefined}
                    value={formData.gender}
                    onChange={(event) => {
                      setFormData((current) => ({ ...current, gender: event.target.value }));
                      setFieldErrors((current) => ({ ...current, gender: undefined }));
                      setSaveSucceeded(false);
                    }}
                    maxLength={80}
                    placeholder="Optional; enter how you describe your gender"
                    className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3"
                  />
                  {fieldErrors.gender && <span id="profile-gender-error" className="patient-profile__field-error">{fieldErrors.gender}</span>}
                  </>
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

        {saveSucceeded && (
          <p className="patient-profile__success" role="status">
            Your profile changes have been saved.{profileRefreshError ? ' Refresh the page if the updated details are not shown yet.' : ''}
          </p>
        )}

        <p className="patient-profile__privacy-note">
          <span className="material-symbols-outlined" aria-hidden="true">shield_lock</span>
          Your profile is visible only after sign-in. Sign out when using a shared device.
        </p>
      </Card>
    </div>
  );
}
