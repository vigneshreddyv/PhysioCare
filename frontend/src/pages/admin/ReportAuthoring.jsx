import React, { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import Button from '../../components/common/Button';
import ErrorState from '../../components/common/ErrorState';

const initialForm = {
  patient_id: '',
  title: '',
  category: 'assessment',
  date: new Date().toISOString().slice(0, 10),
  description: '',
  therapist: '',
  symptoms: '',
  findings: '',
  recommendations: '',
  file: null,
};

export default function ReportAuthoring() {
  const [form, setForm] = useState(initialForm);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const patients = useQuery({
    queryKey: ['patients', 'report-authoring'],
    queryFn: async () => (await api.get('/users/patients')).data,
  });

  const selectedPatient = useMemo(
    () => patients.data?.find((patient) => patient.id === form.patient_id),
    [form.patient_id, patients.data],
  );

  const createReport = useMutation({
    mutationFn: async () => {
      const payload = {
        patient_id: form.patient_id,
        title: form.title.trim(),
        category: form.category,
        date: new Date(`${form.date}T12:00:00`).toISOString(),
        description: form.description.trim(),
        therapist: form.therapist.trim(),
        content: {
          symptoms: form.symptoms.trim(),
          findings: form.findings.trim(),
          recommendations: form.recommendations.trim(),
        },
      };
      const body = new FormData();
      body.append('report_data_str', JSON.stringify(payload));
      if (form.file) body.append('file', form.file);
      return (await api.post('/reports', body, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
    },
    onSuccess: () => {
      setSuccessMessage('Clinical report created. The patient can now view it in Reports.');
      setErrorMessage('');
      setForm((current) => ({ ...initialForm, patient_id: current.patient_id, therapist: current.therapist }));
    },
    onError: (error) => {
      setSuccessMessage('');
      setErrorMessage(error.response?.data?.detail || 'The clinical report could not be created.');
    },
  });

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
    setSuccessMessage('');
    setErrorMessage('');
  };

  const submit = (event) => {
    event.preventDefault();
    setSuccessMessage('');
    setErrorMessage('');
    if (!form.patient_id || !form.title.trim() || !form.date || !form.description.trim() || !form.therapist.trim()
      || !form.symptoms.trim() || !form.findings.trim() || !form.recommendations.trim()) {
      setErrorMessage('Complete the patient, report details, and all clinical content fields before saving.');
      return;
    }
    createReport.mutate();
  };

  if (patients.isLoading) return <p role="status">Loading patients…</p>;
  if (patients.error) return <ErrorState message="Could not load authorized patients." onRetry={() => patients.refetch()} />;

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">description</span>Clinical records</span>
        <h1>Author a clinical report</h1>
        <p>Create a general clinical report for an authorized patient. Laboratory report upload and publication remain a separate workflow.</p>
      </header>

      <form onSubmit={submit} className="portal-section-card grid gap-5" noValidate>
        {errorMessage && <p className="patient-booking__submit-error" role="alert">{errorMessage}</p>}
        {successMessage && <p className="portal-trust-note" role="status">{successMessage}</p>}

        <div className="grid gap-2">
          <label htmlFor="report-patient" className="font-semibold">Patient</label>
          <select id="report-patient" value={form.patient_id} onChange={updateField('patient_id')} required className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3">
            <option value="">Select an authorized patient</option>
            {patients.data?.map((patient) => <option key={patient.id} value={patient.id}>{patient.full_name}</option>)}
          </select>
          {selectedPatient && <p className="text-sm text-on-surface-variant">Report will be attached to {selectedPatient.full_name}.</p>}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="grid gap-2 font-semibold">Title<input value={form.title} onChange={updateField('title')} required maxLength={200} className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3" /></label>
          <label className="grid gap-2 font-semibold">Category<select value={form.category} onChange={updateField('category')} className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3"><option value="assessment">Assessment</option><option value="summary">Summary</option><option value="diagnostic">Diagnostic</option></select></label>
          <label className="grid gap-2 font-semibold">Report date<input type="date" value={form.date} onChange={updateField('date')} required className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3" /></label>
          <label className="grid gap-2 font-semibold">Clinician name<input value={form.therapist} onChange={updateField('therapist')} required maxLength={200} className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3" /></label>
        </div>

        <label className="grid gap-2 font-semibold">Summary<textarea value={form.description} onChange={updateField('description')} required maxLength={2000} rows={3} className="rounded-xl border border-outline-variant bg-surface px-3 py-2" /></label>
        <div className="grid gap-4 md:grid-cols-3">
          <label className="grid gap-2 font-semibold">Symptoms<textarea value={form.symptoms} onChange={updateField('symptoms')} required rows={5} className="rounded-xl border border-outline-variant bg-surface px-3 py-2" /></label>
          <label className="grid gap-2 font-semibold">Findings<textarea value={form.findings} onChange={updateField('findings')} required rows={5} className="rounded-xl border border-outline-variant bg-surface px-3 py-2" /></label>
          <label className="grid gap-2 font-semibold">Recommendations<textarea value={form.recommendations} onChange={updateField('recommendations')} required rows={5} className="rounded-xl border border-outline-variant bg-surface px-3 py-2" /></label>
        </div>
        <label className="grid gap-2 font-semibold">Optional PDF attachment<input type="file" accept="application/pdf,.pdf" onChange={(event) => setForm((current) => ({ ...current, file: event.target.files?.[0] || null }))} className="min-h-11 rounded-xl border border-outline-variant bg-surface px-3 py-2" /></label>
        <div><Button type="submit" disabled={createReport.isPending}>{createReport.isPending ? 'Saving report…' : 'Create clinical report'}</Button></div>
      </form>
    </div>
  );
}
