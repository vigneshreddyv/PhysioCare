import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function DoctorsList() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [editingDoctor, setEditingDoctor] = useState(null);
  const [profileDraft, setProfileDraft] = useState({});
  const { 
    data: doctors, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['doctors'],
    queryFn: async () => {
      const response = await api.get('/users/doctors');
      return response.data;
    }
  });

  const updateProfile = useMutation({
    mutationFn: async ({ doctorId, values }) => (await api.patch(`/users/doctors/${doctorId}`, values)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['doctors'] });
      queryClient.invalidateQueries({ queryKey: ['publicDoctors'] });
      setEditingDoctor(null);
    },
  });

  const beginEdit = (doctor) => {
    setEditingDoctor(doctor);
    setProfileDraft({
      full_name: doctor.full_name || '',
      specialization: doctor.specialization || '',
      profile_image: doctor.profile_image || '',
      qualifications: doctor.qualifications || '',
      years_experience: doctor.years_experience ?? '',
      specialties: doctor.specialties?.join(', ') || '',
      bio: doctor.bio || '',
      linkedin_url: doctor.linkedin_url || '',
      website_url: doctor.website_url || '',
      accepts_home_visits: doctor.accepts_home_visits !== false,
    });
    updateProfile.reset();
  };

  const submitProfile = (event) => {
    event.preventDefault();
    updateProfile.mutate({
      doctorId: editingDoctor.id,
      values: {
        full_name: profileDraft.full_name.trim(),
        specialization: profileDraft.specialization.trim(),
        profile_image: profileDraft.profile_image.trim() || null,
        qualifications: profileDraft.qualifications.trim() || null,
        years_experience: profileDraft.years_experience === '' ? null : Number(profileDraft.years_experience),
        specialties: profileDraft.specialties.split(',').map((item) => item.trim()).filter(Boolean),
        bio: profileDraft.bio.trim() || null,
        linkedin_url: profileDraft.linkedin_url.trim() || null,
        website_url: profileDraft.website_url.trim() || null,
        accepts_home_visits: Boolean(profileDraft.accepts_home_visits),
      },
    });
  };

  if (error) {
    return <ErrorState message="Could not load medical staff records." onRetry={() => refetch()} />;
  }

  const getInitials = (name) => name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase() || 'PT';

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">medical_services</span>Clinical team</span>
        <h1>Physiotherapy staff</h1>
        <p>Review practitioner profiles and today's availability supplied by the current staff directory.</p>
      </header>

      <div className="portal-trust-note" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">verified_user</span>
        <span>Publish only clinic-verified qualifications, experience, photos, focus areas, and personal professional links. Empty fields stay absent from the public profile.</span>
      </div>

      {editingDoctor && (
        <form className="portal-section-card portal-profile-editor p-5 grid gap-5" onSubmit={submitProfile} aria-busy={updateProfile.isPending}>
          <div className="portal-section-card__header -m-5 mb-0">
            <div><span className="portal-section__eyebrow">Public profile</span><h2 className="font-headline-md text-headline-md">Edit {editingDoctor.full_name}</h2></div>
            <button type="button" onClick={() => setEditingDoctor(null)} className="portal-icon-button" aria-label="Close profile editor"><span className="material-symbols-outlined">close</span></button>
          </div>
          <div className="portal-profile-editor__grid">
            <label>Full name<input required minLength={2} maxLength={100} value={profileDraft.full_name} onChange={(event) => setProfileDraft((current) => ({ ...current, full_name: event.target.value }))} /></label>
            <label>Primary specialization<input required minLength={2} maxLength={120} value={profileDraft.specialization} onChange={(event) => setProfileDraft((current) => ({ ...current, specialization: event.target.value }))} /></label>
            <label>Qualifications<input maxLength={300} value={profileDraft.qualifications} onChange={(event) => setProfileDraft((current) => ({ ...current, qualifications: event.target.value }))} placeholder="Only verified degrees or certifications" /></label>
            <label>Years of experience<input type="number" min="0" max="80" inputMode="numeric" value={profileDraft.years_experience} onChange={(event) => setProfileDraft((current) => ({ ...current, years_experience: event.target.value }))} /></label>
            <label className="portal-profile-editor__wide">Focus areas, comma separated<input value={profileDraft.specialties} onChange={(event) => setProfileDraft((current) => ({ ...current, specialties: event.target.value }))} placeholder="Sports rehabilitation, Mobility" /></label>
            <label className="portal-profile-editor__wide">Professional photo URL<input type="url" maxLength={500} value={profileDraft.profile_image} onChange={(event) => setProfileDraft((current) => ({ ...current, profile_image: event.target.value }))} placeholder="https://…" /></label>
            <label>Personal LinkedIn URL<input type="url" maxLength={500} value={profileDraft.linkedin_url} onChange={(event) => setProfileDraft((current) => ({ ...current, linkedin_url: event.target.value }))} placeholder="https://www.linkedin.com/…" /></label>
            <label>Professional website URL<input type="url" maxLength={500} value={profileDraft.website_url} onChange={(event) => setProfileDraft((current) => ({ ...current, website_url: event.target.value }))} placeholder="https://…" /></label>
            <label className="portal-profile-editor__wide">Professional biography<textarea rows={5} maxLength={1200} value={profileDraft.bio} onChange={(event) => setProfileDraft((current) => ({ ...current, bio: event.target.value }))} /></label>
            <label className="portal-profile-editor__wide"><span><input type="checkbox" checked={Boolean(profileDraft.accepts_home_visits)} onChange={(event) => setProfileDraft((current) => ({ ...current, accepts_home_visits: event.target.checked }))} /> Available for home-visit allocation</span></label>
          </div>
          {updateProfile.isError && <p className="patient-booking__submit-error" role="alert">{updateProfile.error?.response?.data?.detail || 'The clinician profile was not updated.'}</p>}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={updateProfile.isPending} className="patient-primary px-5 font-semibold">{updateProfile.isPending ? 'Saving…' : 'Save verified profile'}</button>
            <button type="button" disabled={updateProfile.isPending} onClick={() => setEditingDoctor(null)} className="min-h-11 rounded-xl border border-outline-variant px-5 font-semibold">Cancel</button>
          </div>
        </form>
      )}

      <section className="portal-section-card overflow-hidden" aria-labelledby="clinical-team-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Directory</span>
            <h2 id="clinical-team-heading" className="font-headline-md text-headline-md">Clinical team</h2>
          </div>
          <span className="portal-count-pill">
            {doctors ? doctors.length : 0} practitioners
          </span>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : !doctors || doctors.length === 0 ? (
          <div className="p-6">
            <EmptyState 
              title="No doctors added" 
              message="No medical specialists have been created in the database yet."
              icon="stethoscope"
            />
          </div>
        ) : (
          <>
          <div className="portal-desktop-table overflow-x-auto">
            <table className="portal-data-table w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                  <th className="p-4">Physiotherapist</th>
                  <th className="p-4">Specialization</th>
                  <th className="p-4">Bio / Profile Details</th>
                  <th className="p-4">Status Today</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container">
                {doctors.map((doc) => (
                  <tr key={doc.id} className="hover:bg-surface-container-low transition-colors duration-150">
                    <td className="p-4 flex items-center gap-3">
                      {doc.profile_image ? (
                        <img className="w-10 h-10 rounded-full object-cover shadow-sm shrink-0" alt="" src={doc.profile_image} />
                      ) : (
                        <span className="w-10 h-10 rounded-xl bg-primary-container/20 text-primary flex items-center justify-center font-bold text-xs shrink-0" aria-hidden="true">{getInitials(doc.full_name)}</span>
                      )}
                      <div>
                        <span className="font-semibold text-on-surface block">{doc.full_name}</span>
                        <span className="text-xs text-outline block">{doc.email}</span>
                      </div>
                    </td>
                    <td className="p-4 text-on-surface-variant text-sm font-semibold">{doc.specialization}</td>
                    <td className="p-4 text-on-surface-variant text-sm max-w-xs truncate">{doc.bio || '—'}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        doc.is_active_today 
                          ? 'bg-primary-container/20 text-primary' 
                          : 'bg-surface-variant text-on-surface-variant'
                      }`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {doc.is_active_today ? 'Available' : 'Off-duty'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <button type="button" onClick={() => navigate(`/admin/schedules/${doc.id}`)} className="portal-inline-action text-primary text-sm font-semibold mr-1">Schedule</button>
                      <button type="button" onClick={() => beginEdit(doc)} className="portal-inline-action text-on-surface-variant text-sm font-semibold">Edit profile</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="portal-mobile-list">
            {doctors.map((doc) => (
              <article key={doc.id} className="portal-mobile-record">
                <div className="flex items-center gap-3">
                  {doc.profile_image ? (
                    <img className="w-11 h-11 rounded-xl object-cover" alt="" src={doc.profile_image} />
                  ) : (
                    <span className="w-11 h-11 rounded-xl bg-primary-container/20 text-primary flex items-center justify-center font-bold text-xs" aria-hidden="true">{getInitials(doc.full_name)}</span>
                  )}
                  <div className="min-w-0">
                    <h3 className="font-semibold text-on-surface truncate">{doc.full_name}</h3>
                    <p className="text-xs text-on-surface-variant truncate">{doc.email}</p>
                  </div>
                </div>
                <div className="portal-mobile-record__row"><span>Specialization</span><strong>{doc.specialization}</strong></div>
                <div className="portal-mobile-record__row"><span>Today</span><strong>{doc.is_active_today ? 'Available' : 'Off-duty'}</strong></div>
                <div className="portal-mobile-record__row"><span>Home visits</span><strong>{doc.accepts_home_visits === false ? 'Not eligible' : 'Eligible'}</strong></div>
                <div className="portal-mobile-record__actions">
                  <button type="button" onClick={() => navigate(`/admin/schedules/${doc.id}`)} className="bg-primary text-on-primary font-semibold">Manage schedule</button>
                  <button type="button" onClick={() => beginEdit(doc)} className="border border-outline-variant text-on-surface font-semibold">Edit profile</button>
                </div>
              </article>
            ))}
          </div>
          </>
        )}
      </section>
    </div>
  );
}
