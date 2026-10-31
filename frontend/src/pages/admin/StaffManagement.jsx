import React, { useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';
import {
  filterStaff,
  getStaffCreateError,
  staffRoleLabels,
  staffRoles,
  validateStaffForm,
} from '../../utils/staffManagement';

const initialForm = {
  full_name: '',
  email: '',
  password: '',
  confirm_password: '',
  role: 'laboratorian',
};

function formatCreatedAt(value) {
  if (!value) return 'Not recorded';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Not recorded' : date.toLocaleDateString();
}

export default function StaffManagement() {
  const queryClient = useQueryClient();
  const submissionLock = useRef(false);
  const [form, setForm] = useState(initialForm);
  const [formErrors, setFormErrors] = useState({});
  const [notice, setNotice] = useState('');
  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  const staffQuery = useQuery({
    queryKey: ['staff'],
    queryFn: async () => (await api.get('/users/staff')).data,
  });

  const createStaff = useMutation({
    mutationFn: async (payload) => (await api.post('/users/staff', payload)).data,
    onSuccess: async () => {
      setForm(initialForm);
      setFormErrors({});
      setNotice('Staff account created and is active. The staff member can sign in using the shared email login.');
      await queryClient.invalidateQueries({ queryKey: ['staff'] });
    },
    onSettled: () => {
      submissionLock.current = false;
    },
  });

  const visibleStaff = useMemo(
    () => filterStaff(staffQuery.data, { query, role: roleFilter, status: statusFilter }),
    [staffQuery.data, query, roleFilter, statusFilter],
  );

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    setFormErrors((current) => ({ ...current, [name]: undefined }));
    createStaff.reset();
    setNotice('');
  };

  const submit = (event) => {
    event.preventDefault();
    if (submissionLock.current || createStaff.isPending) return;

    const errors = validateStaffForm(form);
    setFormErrors(errors);
    setNotice('');
    if (Object.keys(errors).length) return;

    submissionLock.current = true;
    createStaff.mutate({
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      password: form.password,
      role: form.role,
    });
  };

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow">
          <span className="material-symbols-outlined" aria-hidden="true">manage_accounts</span>
          Admin controls
        </span>
        <h1>Staff Management</h1>
        <p>Manage staff access for the clinical, reception, and laboratory workspaces.</p>
      </header>

      <section className="portal-section-card p-5 sm:p-6" aria-labelledby="create-staff-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">New account</span>
            <h2 id="create-staff-heading" className="font-headline-md text-headline-md">Create staff account</h2>
          </div>
        </div>
        <p className="mb-5 text-sm text-on-surface-variant">
          New accounts are active immediately. Share the initial password with the staff member securely.
        </p>

        {notice && <p className="mb-4 text-sm font-semibold text-primary" role="status">{notice}</p>}
        {createStaff.isError && <p className="patient-booking__submit-error mb-4" role="alert">{getStaffCreateError(createStaff.error)}</p>}

        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" aria-busy={createStaff.isPending} noValidate>
          <div className="grid gap-2">
            <label htmlFor="staff-full-name" className="font-semibold">Full name</label>
            <input id="staff-full-name" name="full_name" value={form.full_name} onChange={updateField} autoComplete="name" required minLength={2} aria-invalid={Boolean(formErrors.full_name)} aria-describedby={formErrors.full_name ? 'staff-name-error' : undefined} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3" />
            {formErrors.full_name && <p id="staff-name-error" className="patient-booking__submit-error" role="alert">{formErrors.full_name}</p>}
          </div>

          <div className="grid gap-2">
            <label htmlFor="staff-email" className="font-semibold">Email address</label>
            <input id="staff-email" name="email" type="email" value={form.email} onChange={updateField} autoComplete="email" required aria-invalid={Boolean(formErrors.email)} aria-describedby={formErrors.email ? 'staff-email-error' : undefined} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3" />
            {formErrors.email && <p id="staff-email-error" className="patient-booking__submit-error" role="alert">{formErrors.email}</p>}
          </div>

          <div className="grid gap-2">
            <label htmlFor="staff-password" className="font-semibold">Initial password</label>
            <input id="staff-password" name="password" type="password" value={form.password} onChange={updateField} autoComplete="new-password" required minLength={8} aria-invalid={Boolean(formErrors.password)} aria-describedby={formErrors.password ? 'staff-password-error' : 'staff-password-note'} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3" />
            <p id={formErrors.password ? 'staff-password-error' : 'staff-password-note'} className={formErrors.password ? 'patient-booking__submit-error' : 'text-xs text-on-surface-variant'} role={formErrors.password ? 'alert' : undefined}>{formErrors.password || 'Use at least 8 characters. The password is never shown in the staff directory.'}</p>
          </div>

          <div className="grid gap-2">
            <label htmlFor="staff-confirm-password" className="font-semibold">Confirm password</label>
            <input id="staff-confirm-password" name="confirm_password" type="password" value={form.confirm_password} onChange={updateField} autoComplete="new-password" required aria-invalid={Boolean(formErrors.confirm_password)} aria-describedby={formErrors.confirm_password ? 'staff-confirm-error' : undefined} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3" />
            {formErrors.confirm_password && <p id="staff-confirm-error" className="patient-booking__submit-error" role="alert">{formErrors.confirm_password}</p>}
          </div>

          <div className="grid gap-2 sm:col-span-2">
            <label htmlFor="staff-role" className="font-semibold">Staff role</label>
            <select id="staff-role" name="role" value={form.role} onChange={updateField} required aria-invalid={Boolean(formErrors.role)} aria-describedby={formErrors.role ? 'staff-role-error' : undefined} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3">
              {staffRoles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            {formErrors.role && <p id="staff-role-error" className="patient-booking__submit-error" role="alert">{formErrors.role}</p>}
          </div>

          <div className="sm:col-span-2">
            <button type="submit" disabled={createStaff.isPending} className="patient-primary min-h-11 rounded-xl px-5 font-semibold disabled:cursor-not-allowed disabled:opacity-50">
              {createStaff.isPending ? 'Creating account…' : 'Create staff account'}
            </button>
          </div>
        </form>
      </section>

      <section className="portal-section-card overflow-hidden" aria-labelledby="staff-directory-heading">
        <div className="portal-section-card__header">
          <div>
            <span className="portal-section__eyebrow">Directory</span>
            <h2 id="staff-directory-heading" className="font-headline-md text-headline-md">Staff accounts</h2>
          </div>
          <span className="portal-count-pill">{visibleStaff.length} staff</span>
        </div>

        <div className="grid gap-3 p-5 sm:grid-cols-3">
          <label className="grid gap-2 text-sm font-semibold">
            Search name or email
            <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3 font-normal" />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Filter by role
            <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3 font-normal">
              <option value="all">All roles</option>
              {staffRoles.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Filter by account status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="min-h-11 rounded-xl border border-outline-variant bg-surface-container-lowest px-3 font-normal">
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </label>
        </div>

        {staffQuery.error ? (
          <div className="p-5"><ErrorState message="Could not load staff accounts." onRetry={() => staffQuery.refetch()} /></div>
        ) : staffQuery.isLoading ? (
          <div className="p-5"><Skeleton variant="row" count={3} /></div>
        ) : !visibleStaff.length ? (
          <div className="p-5"><EmptyState title={staffQuery.data?.length ? 'No matching staff' : 'No staff accounts'} message={staffQuery.data?.length ? 'Try changing the search or filters.' : 'Staff accounts will appear here after an administrator creates them.'} icon="manage_accounts" /></div>
        ) : (
          <>
            <div className="portal-desktop-table overflow-x-auto">
              <table className="portal-data-table w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-surface-container bg-surface-container text-on-surface-variant">
                    <th scope="col" className="p-4">Name</th>
                    <th scope="col" className="p-4">Email</th>
                    <th scope="col" className="p-4">Role</th>
                    <th scope="col" className="p-4">Account status</th>
                    <th scope="col" className="p-4">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container">
                  {visibleStaff.map((person) => (
                    <tr key={person.id} className="hover:bg-surface-container-low">
                      <td className="p-4 font-semibold">{person.full_name}</td>
                      <td className="p-4 text-sm text-on-surface-variant">{person.email}</td>
                      <td className="p-4">{staffRoleLabels[person.role] || person.role}</td>
                      <td className="p-4">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${person.is_active ? 'bg-primary-container/20 text-primary' : 'bg-surface-variant text-on-surface-variant'}`}>
                          {person.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-on-surface-variant">{formatCreatedAt(person.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-3 p-4 md:hidden">
              {visibleStaff.map((person) => (
                <article key={person.id} className="rounded-xl border border-outline-variant p-4">
                  <h3 className="font-semibold">{person.full_name}</h3>
                  <p className="text-sm text-on-surface-variant">{person.email}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                    <span>{staffRoleLabels[person.role] || person.role}</span>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${person.is_active ? 'bg-primary-container/20 text-primary' : 'bg-surface-variant text-on-surface-variant'}`}>{person.is_active ? 'Active' : 'Inactive'}</span>
                    <span className="text-on-surface-variant">Created {formatCreatedAt(person.created_at)}</span>
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
