import React, { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import Button from '../../components/common/Button';
import EmptyState from '../../components/common/EmptyState';
import ErrorState from '../../components/common/ErrorState';
import PatientIcon from '../../components/common/PatientIcon';
import { labCategories, labDemoCatalogue } from '../../content/labDemoCatalogue';
import { closePdfViewer, preparePdfViewer, showPdfBlob } from '../../utils/openPdfBlob';

const labels = { pending_clinic_confirmation: 'Pending clinic confirmation', approved_for_coordination: 'Approved for coordination', declined: 'Declined', withdrawn: 'Withdrawn' };

export default function LaboratoryRequests() {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState('clinic_visit');
  const [category, setCategory] = useState('All');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('az');
  const [selected, setSelected] = useState([]);
  const [address, setAddress] = useState('');
  const [saveAddress, setSaveAddress] = useState(false);
  const [locationNotice, setLocationNotice] = useState('');
  const [notice, setNotice] = useState('');
  const submissionRef = useRef(null);
  const requests = useQuery({ queryKey: ['myLabRequests'], queryFn: async () => (await api.get('/lab-requests/me')).data });
  const reports = useQuery({ queryKey: ['myReleasedLabReports'], queryFn: async () => (await api.get('/lab-requests/me/reports')).data });
  const context = useQuery({ queryKey: ['homeVisitContext'], queryFn: async () => (await api.get('/home-visit-requests/me/context')).data });
  const create = useMutation({
    mutationFn: async ({ payload, submissionKey }) => (await api.post('/lab-requests', payload, { headers: { 'Idempotency-Key': submissionKey } })).data,
    onSuccess: () => { submissionRef.current = null; queryClient.invalidateQueries({ queryKey: ['myLabRequests'] }); setSelected([]); setAddress(''); setSaveAddress(false); setNotice('Your laboratory request was sent. The clinic will contact you to confirm the next step.'); },
  });
  const withdraw = useMutation({ mutationFn: async (id) => (await api.post(`/lab-requests/${id}/withdraw`)).data, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['myLabRequests'] }) });
  const openReport = useMutation({
    mutationFn: async ({ report, viewer }) => {
      if (!viewer) throw new Error('The PDF viewer was blocked.');
      try {
        const response = await api.get(`/lab-requests/${report.request_id}/report-file`, { responseType: 'blob' });
        showPdfBlob(viewer, response.data);
      } catch (error) {
        closePdfViewer(viewer);
        throw error;
      }
    },
  });
  const visible = useMemo(() => labDemoCatalogue.filter((test) => (category === 'All' || test.category === category) && test.name.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'az' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name)), [category, query, sort]);
  const toggle = (id) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const useLocation = () => {
    setLocationNotice('');
    if (!navigator.geolocation) return setLocationNotice('Device location is unavailable. Enter the address manually.');
    navigator.geolocation.getCurrentPosition(
      () => setLocationNotice('Location access succeeded, but GPS is not treated as proof of Nellore city coverage. Enter the address for clinic verification.'),
      () => setLocationNotice('Location access was denied or unavailable. Enter the address manually.'),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 0 },
    );
  };
  const submit = () => {
    if (create.isPending) return;
    const payload = { mode, selected_tests: selected, home_address: mode === 'home_collection' ? address.trim() : null, city: mode === 'home_collection' ? 'Nellore' : null, save_address: mode === 'home_collection' && saveAddress };
    const fingerprint = JSON.stringify(payload);
    if (submissionRef.current?.fingerprint !== fingerprint) {
      submissionRef.current = { fingerprint, key: globalThis.crypto?.randomUUID?.() || `lab-${Date.now()}-${Math.random().toString(16).slice(2)}` };
    }
    create.mutate({ payload, submissionKey: submissionRef.current.key });
  };
  if (requests.error || context.error || reports.error) return <ErrorState message="Could not load laboratory requests." onRetry={() => { requests.refetch(); context.refetch(); reports.refetch(); }} />;
  return <div className="patient-lab patient-page animate-fade-in pb-28">
    <header className="patient-lab__hero patient-workflow-header"><div><Link to="/patient/services" className="patient-workflow-header__back"><PatientIcon name="back" size={18} />Services</Link><p className="patient-page__eyebrow">Laboratory services</p><h1>Request laboratory tests.</h1><p>Choose how you would like the tests collected. The clinic will confirm preparation, timing, and availability.</p></div><div className="patient-workflow-header__icon" aria-hidden="true"><PatientIcon name="lab" size={38} /></div></header>
    {notice && <div className="patient-dashboard__notice" role="status">{notice}</div>}
    <section className="patient-lab__modes" aria-labelledby="lab-mode-heading"><div><p className="patient-page__eyebrow">Step 1</p><h2 id="lab-mode-heading">How should the clinic review your request?</h2></div><div className="patient-lab__mode-grid">
      {[['home_collection','visit','Home collection','Available for Nellore city addresses.'],['clinic_visit','clinic','Clinic visit','Visit the clinic after your request is confirmed.']].map(([value, icon, title, copy]) => <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)}><PatientIcon name={icon} /><strong>{title}</strong><small>{copy}</small></button>)}
    </div></section>
    {mode === 'home_collection' && <section className="patient-lab__coverage"><h2>Home collection address</h2><p>Home collection is available in Nellore. Enter the address where collection is needed.</p><label>City<select value="Nellore" disabled><option>Nellore</option></select></label><label>Collection address<textarea value={address} minLength={10} maxLength={500} rows={3} onChange={(event) => setAddress(event.target.value)} placeholder="Enter a Nellore city address" /></label><button type="button" onClick={useLocation} className="patient-lab__location"><PatientIcon name="location" size={20} />Use device location</button>{locationNotice && <p role="status">{locationNotice}</p>}<label className="patient-lab__save"><input type="checkbox" checked={saveAddress} onChange={(event) => setSaveAddress(event.target.checked)} />Save this address for future requests</label></section>}
    <section className="patient-lab__catalogue" aria-labelledby="lab-catalogue-heading"><div className="patient-lab__catalogue-head"><div><p className="patient-page__eyebrow">Step 2</p><h2 id="lab-catalogue-heading">Select laboratory tests</h2><p>{labDemoCatalogue.length} tests available to request.</p></div><select aria-label="Sort tests" value={sort} onChange={(event) => setSort(event.target.value)}><option value="az">A–Z</option><option value="za">Z–A</option></select></div><label className="patient-lab__search"><PatientIcon name="search" size={20} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search tests" /></label><div className="patient-lab__chips" role="group" aria-label="Filter by category">{labCategories.map((item) => <button type="button" key={item} aria-pressed={category === item} onClick={() => setCategory(item)}>{item}</button>)}</div><div className="patient-lab__test-grid">{visible.map((test) => <button type="button" key={test.id} aria-pressed={selected.includes(test.id)} onClick={() => toggle(test.id)} className="patient-lab__test"><PatientIcon name="lab" /><small>{test.category}</small><strong>{test.name}</strong><p>{test.description}</p><span>{selected.includes(test.id) ? 'Selected' : 'Select test'}</span></button>)}</div></section>
    {create.isError && <p className="patient-booking__submit-error" role="alert">{create.error?.response?.data?.detail || 'The laboratory request was not submitted.'}</p>}
    <div className={`patient-lab__selection${selected.length ? '' : ' patient-lab__selection--empty'}`}><div><strong>{selected.length} selected</strong><span>Estimated total: unavailable</span></div><Button type="button" disabled={!selected.length || (mode === 'home_collection' && address.trim().length < 10) || create.isPending} onClick={submit}>{create.isPending ? 'Submitting…' : 'Continue to clinic review'}</Button></div>
    <section className="portal-section-card" aria-labelledby="lab-history-heading"><div className="portal-section-card__header"><div><p className="portal-section__eyebrow">Your requests</p><h2 id="lab-history-heading">Laboratory review status</h2></div></div>{!requests.data?.length ? <div className="p-6"><EmptyState title="No laboratory requests" message="Selected tests will appear here only after you submit them for clinic review." icon="biotech" /></div> : <div className="reception-schedule-grid">{requests.data.map((item) => <article className="portal-mobile-record" key={item.id}><strong>{labels[item.status] || item.status}</strong><span>{item.mode === 'home_collection' ? 'Home collection request' : 'Clinic visit request'} · {item.selected_tests.length} tests</span><p>{item.confirmation_message}</p>{['pending_clinic_confirmation','approved_for_coordination'].includes(item.status) && <button type="button" onClick={() => withdraw.mutate(item.id)}>Withdraw request</button>}</article>)}</div>}</section>
    <section className="portal-section-card" aria-labelledby="lab-reports-heading"><div className="portal-section-card__header"><div><p className="portal-section__eyebrow">Your records</p><h2 id="lab-reports-heading">Released laboratory reports</h2></div></div>{openReport.isError && <p className="patient-booking__submit-error" role="alert">The report could not be opened. Allow pop-ups, then try again.</p>}{reports.isLoading ? <p className="p-6" role="status">Loading reports…</p> : !reports.data?.length ? <div className="p-6"><EmptyState title="No released reports" message="Reports appear here only after they are reviewed and released to you." icon="description" /></div> : <div className="reception-schedule-grid">{reports.data.map((report) => <article className="portal-mobile-record" key={report.request_id}><strong>{report.report_file_name || 'Laboratory report'}</strong><span>{report.selected_tests.join(', ')}</span><button type="button" disabled={openReport.isPending} onClick={() => openReport.mutate({ report, viewer: preparePdfViewer() })}>{openReport.isPending && openReport.variables?.report?.request_id === report.request_id ? 'Opening…' : 'Open report'}</button></article>)}</div>}</section>
  </div>;
}
