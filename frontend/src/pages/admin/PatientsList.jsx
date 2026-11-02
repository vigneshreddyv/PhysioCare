import { MAX_CLINICAL_PAGE, fetchClinicalPage } from '../../services/clinicalPagination';
import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function PatientsList() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const isReceptionist = user?.role === 'receptionist';
  const isDoctor = user?.role === 'doctor';
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageInput, setPageInput] = useState('1');
  const [editingPatient, setEditingPatient] = useState(null);
  const [contactDraft, setContactDraft] = useState({ full_name: '', phone: '' });
  const directoryPath = isReceptionist ? '/users/reception/patients' : '/users/patients';
  useEffect(() => {
    setPage(1);
    setPageInput('1');
    setEditingPatient(null);
  }, [user?.id, user?.role]);
  const {
    data: patientPage,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['patients', 'directory', user?.id, user?.role, page],
    queryFn: () => fetchClinicalPage(directoryPath, page),
    gcTime: 0,
  });
  const patients = patientPage?.data;

  const changePage = (next) => {
    if (!Number.isInteger(next) || next < 1 || next > MAX_CLINICAL_PAGE) return;
    setEditingPatient(null);
    setPage(next);
    setPageInput(String(next));
  };

  const navigate = useNavigate();
  const updateContactMutation = useMutation({
    mutationFn: async ({ patientId, updates }) => (
      await api.patch(`/users/reception/patients/${patientId}`, updates)
    ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients', 'directory', user?.id, user?.role] });
      queryClient.invalidateQueries({ queryKey: ['patients', 'receptionist'] });
      setEditingPatient(null);
    },
  });

  const beginContactEdit = (patient) => {
    setEditingPatient(patient);
    setContactDraft({ full_name: patient.full_name, phone: patient.phone || '' });
    updateContactMutation.reset();
  };

  const submitContactEdit = (event) => {
    event.preventDefault();
    updateContactMutation.mutate({
      patientId: editingPatient.id,
      updates: { full_name: contactDraft.full_name.trim(), phone: contactDraft.phone.trim() || null },
    });
  };

  if (error) {
    return <div>
      <ErrorState message={`Could not load patient directory page ${page}.`} onRetry={() => refetch()} />
      {page > 1 && <button type="button" className="portal-inline-action" onClick={() => changePage(1)}>Return to first page</button>}
    </div>;
  }

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">groups</span>Patient records</span>
        <h1>{isAdmin ? 'Registered patients' : isReceptionist ? 'Patient contacts' : 'Assigned patients'}</h1>
        <p>{isAdmin
          ? 'Review the identity and account fields supplied by the clinic API.'
          : isReceptionist
            ? 'Use the minimum contact details needed to coordinate appointments.'
          : 'Review only the patients linked to appointments assigned to you.'}</p>
      </header>

      <div className="portal-trust-note" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">shield_lock</span>
        <span>{isAdmin
          ? 'Patient contact, birth-date, and subscription fields are sensitive. Avoid copying them into unsecured notes, URLs, messages, or analytics.'
          : isReceptionist
            ? 'Clinical history, reasons, birth dates, subscriptions, and billing details are not available in reception.'
          : 'Patient contact and birth-date fields are sensitive. Use them only for assigned care and avoid copying them into unsecured notes, URLs, or messages.'}</span>
      </div>

      {isReceptionist && editingPatient && (
        <form className="portal-section-card p-5 grid gap-4" onSubmit={submitContactEdit} aria-busy={updateContactMutation.isPending}>
          <div>
            <span className="portal-section__eyebrow">Edit contact</span>
            <h2 className="font-headline-md text-headline-md">Appointment contact details</h2>
            <p className="text-sm text-on-surface-variant mt-1">Email is the patient’s account identity and remains read-only.</p>
          </div>
          <label className="grid gap-2 font-semibold">
            Full name
            <input
              value={contactDraft.full_name}
              onChange={(event) => setContactDraft((current) => ({ ...current, full_name: event.target.value }))}
              minLength={2}
              maxLength={100}
              required
              className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-4"
            />
          </label>
          <label className="grid gap-2 font-semibold">
            Phone
            <input
              value={contactDraft.phone}
              onChange={(event) => setContactDraft((current) => ({ ...current, phone: event.target.value }))}
              maxLength={24}
              inputMode="tel"
              className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-4"
            />
          </label>
          <div className="rounded-xl bg-surface-container-low p-3 text-sm text-on-surface-variant break-all">
            Account email: <strong>{editingPatient.email}</strong>
          </div>
          {updateContactMutation.isError && (
            <p className="patient-booking__submit-error" role="alert">
              {updateContactMutation.error?.response?.data?.detail || 'Contact details were not updated.'}
            </p>
          )}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={updateContactMutation.isPending} className="min-h-11 rounded-xl bg-primary px-5 text-on-primary font-semibold disabled:opacity-50">
              {updateContactMutation.isPending ? 'Saving…' : 'Save contact'}
            </button>
            <button type="button" onClick={() => setEditingPatient(null)} disabled={updateContactMutation.isPending} className="min-h-11 rounded-xl border border-outline-variant px-5 font-semibold">
              Cancel
            </button>
          </div>
        </form>
      )}

      <section className="portal-section-card overflow-hidden" aria-labelledby="patient-records-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Directory</span>
            <h2 id="patient-records-heading" className="font-headline-md text-headline-md">Registered records</h2>
          </div>
          <span className="portal-count-pill">
            {patients ? patients.length : 0} on this page
          </span>
        </div>

        {(() => {
          const isPatientsArray = Array.isArray(patients);
          const isNonEmptyPatientArray = isPatientsArray && patients.length > 0;
          if (isLoading) {
            return <Skeleton variant="row" count={3} />;
          }
          if (!isNonEmptyPatientArray) {
            return (
              <EmptyState
                title={page > 1 ? 'No records on this page' : isAdmin ? 'No patients registered' : isReceptionist ? 'No patient contacts' : 'No assigned patients'}
                message={isAdmin
                  ? page > 1 ? 'Choose an earlier page to continue browsing.' : 'Patient accounts will appear here once they register on the booking portal.'
                  : isReceptionist
                    ? page > 1 ? 'Some directory pages may be empty when inactive contacts are filtered.' : 'Patient contact details will appear here after patient registration.'
                    : page > 1 ? 'Some directory pages may be empty when inactive patients are filtered.' : 'Patients will appear here only after an appointment is assigned to you.'}
                icon="groups"
              />
            );
          }
          return (
            <>
            <div className="portal-desktop-table overflow-x-auto">
              <table className="portal-data-table w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                    <th className="p-4">Name</th>
                    {(isAdmin || isReceptionist) && <th className="p-4">Email</th>}
                    <th className="p-4">Phone</th>
                    {!isReceptionist && <th className="p-4">Date of Birth</th>}
                    {isAdmin && <th className="p-4">Subscription</th>}
                    {(isAdmin || isReceptionist || isDoctor) && <th className="p-4 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container">
                  {patients.map((patient) => (
                    <tr key={patient.id} className="hover:bg-surface-container-low transition-colors duration-150">
                      <td className="p-4 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary-container/20 text-primary flex items-center justify-center font-bold text-xs">
                          {patient.full_name.substring(0, 2).toUpperCase()}
                        </div>
                        <span className="font-semibold text-on-surface">{patient.full_name}</span>
                      </td>
                      {(isAdmin || isReceptionist) && <td className="p-4 text-on-surface-variant text-sm">{patient.email}</td>}
                      <td className="p-4 text-on-surface-variant text-sm">{patient.phone || '—'}</td>
                      {!isReceptionist && <td className="p-4 text-on-surface-variant text-sm">{patient.date_of_birth || '—'}</td>}
                      {isAdmin && <td className="p-4">
                        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          patient.subscription_status === 'active'
                            ? 'bg-primary-container/20 text-primary'
                            : 'bg-error-container/20 text-error'
                        }`}>
                          {patient.subscription_status || 'Not configured'}
                        </span>
                      </td>}
                      {isAdmin && <td className="p-4 text-right">
                        <button
                          className="portal-inline-action text-primary hover:text-secondary text-sm font-semibold mr-1"
                          onClick={() => navigate(`/admin/patients-edit/${patient.id}`)}
                        >
                          Edit
                        </button>
                        <button
                          className="portal-inline-action text-on-surface-variant hover:text-on-surface text-sm font-semibold"
                          onClick={() => navigate(`/admin/patients-history/${patient.id}`)}
                        >
                          History
                        </button>
                        <button
                          className="portal-inline-action text-primary hover:text-secondary text-sm font-semibold ml-1"
                          onClick={() => navigate(`/admin/patients/${patient.id}/care-plan`)}
                        >
                          Care plan
                        </button>
                        <button
                          className="portal-inline-action text-primary hover:text-secondary text-sm font-semibold ml-1"
                          onClick={() => navigate(`/admin/patients/${patient.id}/exercises`)}
                        >
                          Exercises
                        </button>
                      </td>}
                      {isReceptionist && <td className="p-4 text-right">
                        <button type="button" className="portal-inline-action text-primary font-semibold" onClick={() => beginContactEdit(patient)}>Edit contact</button>
                      </td>}
                      {isDoctor && <td className="p-4 text-right">
                        <button type="button" className="portal-inline-action text-primary font-semibold mr-1" onClick={() => navigate(`/doctor/patients/${patient.id}`)}>View history</button>
                        <button type="button" className="portal-inline-action text-primary font-semibold mr-1" onClick={() => navigate(`/doctor/patients/${patient.id}/care-plan`)}>Care plan</button>
                        <button type="button" className="portal-inline-action text-primary font-semibold" onClick={() => navigate(`/doctor/patients/${patient.id}/exercises`)}>Exercises</button>
                      </td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="portal-mobile-list">
              {patients.map((patient) => (
                <article key={patient.id} className="portal-mobile-record">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary-container/20 text-primary flex items-center justify-center font-bold text-xs" aria-hidden="true">
                      {patient.full_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-semibold text-on-surface truncate">{patient.full_name}</h3>
                      {(isAdmin || isReceptionist) && <p className="text-xs text-on-surface-variant truncate">{patient.email}</p>}
                    </div>
                  </div>
                  <div className="portal-mobile-record__row"><span>Phone</span><strong>{patient.phone || 'Not provided'}</strong></div>
                  {!isReceptionist && <div className="portal-mobile-record__row"><span>Date of birth</span><strong>{patient.date_of_birth || 'Not provided'}</strong></div>}
                  {isAdmin && <div className="portal-mobile-record__row"><span>Subscription label</span><strong>{patient.subscription_status || 'Not configured'}</strong></div>}
                  {isAdmin && <div className="portal-mobile-record__actions">
                    <button type="button" className="bg-primary text-on-primary font-semibold" onClick={() => navigate(`/admin/patients-edit/${patient.id}`)}>Edit</button>
                    <button type="button" className="border border-outline-variant text-on-surface font-semibold" onClick={() => navigate(`/admin/patients-history/${patient.id}`)}>History</button>
                    <button type="button" className="border border-outline-variant text-on-surface font-semibold" onClick={() => navigate(`/admin/patients/${patient.id}/care-plan`)}>Care plan</button>
                    <button type="button" className="border border-outline-variant text-on-surface font-semibold" onClick={() => navigate(`/admin/patients/${patient.id}/exercises`)}>Exercises</button>
                  </div>}
                  {isReceptionist && <div className="portal-mobile-record__actions">
                    <button type="button" className="bg-primary text-on-primary font-semibold" onClick={() => beginContactEdit(patient)}>Edit contact</button>
                  </div>}
                  {isDoctor && <div className="portal-mobile-record__actions">
                    <button type="button" className="bg-primary text-on-primary font-semibold" onClick={() => navigate(`/doctor/patients/${patient.id}`)}>View history</button>
                    <button type="button" className="bg-primary text-on-primary font-semibold" onClick={() => navigate(`/doctor/patients/${patient.id}/care-plan`)}>Care plan</button>
                    <button type="button" className="bg-primary text-on-primary font-semibold" onClick={() => navigate(`/doctor/patients/${patient.id}/exercises`)}>Exercises</button>
                  </div>}
                </article>
              ))}
            </div>
            </>
          );
        })()}
      </section>
      <nav className="flex flex-wrap items-center gap-3" aria-label="Patient directory pages">
        <button type="button" className="portal-inline-action" disabled={page === 1 || isLoading} onClick={() => changePage(page - 1)}>Previous page</button>
        <form onSubmit={(event) => { event.preventDefault(); changePage(Number(pageInput)); }} className="flex items-center gap-2">
          <label htmlFor="patient-directory-page">Page</label>
          <input id="patient-directory-page" type="number" min="1" max={MAX_CLINICAL_PAGE} value={pageInput} onChange={(event) => setPageInput(event.target.value)} className="w-20 rounded-lg border border-outline-variant px-2 py-1" />
          <button type="submit" className="portal-inline-action">Go</button>
        </form>
        <span aria-live="polite">of at most {MAX_CLINICAL_PAGE} pages</span>
        <button type="button" className="portal-inline-action" disabled={isLoading || page >= MAX_CLINICAL_PAGE} onClick={() => changePage(page + 1)}>Next page</button>
      </nav>
    </div>
  );
}
