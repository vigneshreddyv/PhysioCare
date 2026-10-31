import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../../services/api';
import Button from '../../components/common/Button';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';
import { validatePatientProfile } from '../../utils/patientProfileValidation';

const emptyForm = {
  full_name: '',
  email: '',
  phone: '',
  date_of_birth: '',
  gender: '',
  subscription_status: 'active',
};

function errorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  return detail?.[0]?.msg || 'The patient record could not be updated. Review the fields and try again.';
}

export default function AdminPatientEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(emptyForm);
  const [fieldErrors, setFieldErrors] = useState({});
  const [saved, setSaved] = useState(false);
  const patient = useQuery({
    queryKey: ['adminPatient', id],
    enabled: Boolean(id),
    queryFn: async () => (await api.get(`/users/patients/${id}`)).data,
  });

  useEffect(() => {
    if (!patient.data) return;
    setForm({
      full_name: patient.data.full_name || '',
      email: patient.data.email || '',
      phone: patient.data.phone || '',
      date_of_birth: patient.data.date_of_birth || '',
      gender: patient.data.gender || '',
      subscription_status: patient.data.subscription_status || 'active',
    });
  }, [patient.data]);

  const updatePatient = useMutation({
    mutationFn: async (payload) => (await api.patch(`/users/patients/${id}`, payload)).data,
    onSuccess: (updated) => {
      queryClient.setQueryData(['adminPatient', id], updated);
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      queryClient.invalidateQueries({ queryKey: ['adminPatientHistory', id] });
      setSaved(true);
      setFieldErrors({});
    },
  });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: undefined }));
    setSaved(false);
    updatePatient.reset();
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const errors = validatePatientProfile(form);
    if (form.date_of_birth && form.date_of_birth > new Date().toISOString().slice(0, 10)) {
      errors.date_of_birth = 'Date of birth cannot be in the future.';
    }
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;
    updatePatient.mutate({
      full_name: form.full_name.trim(),
      phone: form.phone.trim() || null,
      date_of_birth: form.date_of_birth || null,
      gender: form.gender.trim() || null,
      subscription_status: form.subscription_status,
    });
  };

  const backButton = (
    <Button variant="outline" onClick={() => navigate('/admin/patients')}>
      <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
      Back to patients
    </Button>
  );
  if (patient.isLoading) return <div className="space-y-4">{backButton}<Skeleton variant="card" count={2} /></div>;
  if (patient.error?.response?.status === 404) return <div className="space-y-4">{backButton}<ErrorState message="This patient record was not found." /></div>;
  if (patient.error) return <div className="space-y-4">{backButton}<ErrorState message="Could not load this patient record." onRetry={() => patient.refetch()} /></div>;

  return (
    <div className="space-y-stack-lg animate-fade-in pb-16 max-w-3xl">
      {backButton}
      <header>
        <p className="patient-page__eyebrow">Administrative record</p>
        <h1 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Edit patient</h1>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Update identity and contact fields. The registered email and account role cannot be changed here.</p>
      </header>
      <form onSubmit={handleSubmit} noValidate className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm p-6 space-y-5">
        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-name">Full name</label>
          <input id="admin-patient-name" name="full_name" value={form.full_name} onChange={handleChange} minLength={2} maxLength={100} required aria-invalid={Boolean(fieldErrors.full_name)} className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 mt-1" />
          {fieldErrors.full_name && <p className="patient-profile__field-error" role="alert">{fieldErrors.full_name}</p>}
        </div>
        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-email">Registered email</label>
          <input id="admin-patient-email" value={form.email} readOnly className="w-full rounded-xl border border-outline-variant bg-surface-container-low p-3 mt-1 text-on-surface-variant" />
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-phone">Phone</label>
            <input id="admin-patient-phone" name="phone" type="tel" value={form.phone} onChange={handleChange} maxLength={24} aria-invalid={Boolean(fieldErrors.phone)} className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 mt-1" />
            {fieldErrors.phone && <p className="patient-profile__field-error" role="alert">{fieldErrors.phone}</p>}
          </div>
          <div>
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-dob">Date of birth</label>
            <input id="admin-patient-dob" name="date_of_birth" type="date" value={form.date_of_birth} onChange={handleChange} max={new Date().toISOString().slice(0, 10)} aria-invalid={Boolean(fieldErrors.date_of_birth)} className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 mt-1" />
            {fieldErrors.date_of_birth && <p className="patient-profile__field-error" role="alert">{fieldErrors.date_of_birth}</p>}
          </div>
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-gender">Gender</label>
            <input id="admin-patient-gender" name="gender" value={form.gender} onChange={handleChange} maxLength={80} placeholder="Optional; patient-recorded" aria-invalid={Boolean(fieldErrors.gender)} className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 mt-1" />
            {fieldErrors.gender && <p className="patient-profile__field-error" role="alert">{fieldErrors.gender}</p>}
          </div>
          <div>
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="admin-patient-status">Administrative status label</label>
            <select id="admin-patient-status" name="subscription_status" value={form.subscription_status} onChange={handleChange} className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-3 mt-1">
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="pending">Pending</option>
            </select>
          </div>
        </div>
        <p className="text-sm text-on-surface-variant">Every save records the administrator, timestamp, and changed field names. Previous field values are not copied into the audit trail.</p>
        {updatePatient.isError && <p className="patient-booking__submit-error" role="alert">{errorMessage(updatePatient.error)}</p>}
        {saved && <p className="patient-profile__success" role="status">Patient record updated.</p>}
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={updatePatient.isPending}>{updatePatient.isPending ? 'Saving…' : 'Save changes'}</Button>
          <Button variant="outline" onClick={() => navigate(`/admin/patients-history/${id}`)}>View history</Button>
        </div>
      </form>
    </div>
  );
}
