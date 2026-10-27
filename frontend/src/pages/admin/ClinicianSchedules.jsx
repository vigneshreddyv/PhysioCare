import React, { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import api from '../../services/api';
import ErrorState from '../../components/common/ErrorState';
import Skeleton from '../../components/common/Skeleton';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const MODES = { clinic: 'Clinic', home_visit: 'Home visit' };
const emptyBlock = (day = 0) => ({ day_of_week: day, service_mode: 'clinic', start_time: '09:00', end_time: '12:00' });
const weekdayIndex = (dateValue) => {
  const day = new Date(`${dateValue}T12:00:00`).getDay();
  return day === 0 ? 6 : day - 1;
};

function minutes(value) {
  const [hour, minute] = value.split(':').map(Number);
  return (hour * 60) + minute;
}

function overlapError(blocks, context) {
  const grouped = new Map();
  for (const block of blocks) {
    if (minutes(block.start_time) >= minutes(block.end_time)) return `${context}: end time must be after start time.`;
    const list = grouped.get(block.day_of_week) || [];
    list.push([minutes(block.start_time), minutes(block.end_time)]);
    grouped.set(block.day_of_week, list);
  }
  for (const ranges of grouped.values()) {
    const ordered = ranges.sort((a, b) => a[0] - b[0]);
    if (ordered.some((range, index) => index > 0 && range[0] < ordered[index - 1][1])) {
      return `${context}: clinic and home-visit blocks cannot overlap.`;
    }
  }
  return '';
}

function statusCopy(status) {
  if (status === 'published') return 'Published';
  if (status === 'draft_changes') return 'Unpublished changes';
  if (status === 'draft') return 'Draft only';
  return 'Not configured';
}

export default function ClinicianSchedules() {
  const { doctorId } = useParams();
  const queryClient = useQueryClient();
  const [weeklyBlocks, setWeeklyBlocks] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [previewDate, setPreviewDate] = useState('');
  const [previewMode, setPreviewMode] = useState('clinic');
  const [formError, setFormError] = useState('');
  const [savedRevision, setSavedRevision] = useState(0);

  const schedule = useQuery({
    queryKey: ['clinicianSchedule', doctorId],
    queryFn: async () => (await api.get(`/clinician-schedules/admin/${doctorId}`)).data,
  });
  const bookingWindow = useQuery({
    queryKey: ['bookingWindow'],
    queryFn: async () => (await api.get('/appointments/booking-window')).data,
  });

  useEffect(() => {
    if (!schedule.data) return;
    setWeeklyBlocks(schedule.data.weekly_blocks || []);
    setExceptions(schedule.data.date_exceptions || []);
    setSavedRevision(schedule.data.draft_revision || 0);
  }, [schedule.data]);

  useEffect(() => {
    if (!previewDate && bookingWindow.data?.earliest_date) setPreviewDate(bookingWindow.data.earliest_date);
  }, [bookingWindow.data, previewDate]);

  const validationError = useMemo(() => {
    const weekly = overlapError(weeklyBlocks, 'Weekly schedule');
    if (weekly) return weekly;
    for (const exception of exceptions) {
      const normalized = (exception.blocks || []).map((block) => ({ ...block, day_of_week: weekdayIndex(exception.date) }));
      const error = overlapError(normalized, `Exception on ${exception.date}`);
      if (error) return error;
    }
    return '';
  }, [weeklyBlocks, exceptions]);

  const saveDraft = useMutation({
    mutationFn: async () => (await api.put(`/clinician-schedules/admin/${doctorId}/draft`, {
      weekly_blocks: weeklyBlocks,
      date_exceptions: exceptions,
    })).data,
    onSuccess: (data) => {
      queryClient.setQueryData(['clinicianSchedule', doctorId], data);
      setSavedRevision(data.draft_revision);
      setFormError('');
    },
    onError: (error) => setFormError(error?.response?.data?.detail || 'The draft could not be saved.'),
  });

  const publish = useMutation({
    mutationFn: async () => (await api.post(`/clinician-schedules/admin/${doctorId}/publish`, { expected_revision: savedRevision })).data,
    onSuccess: (data) => {
      queryClient.setQueryData(['clinicianSchedule', doctorId], data);
      setFormError('');
    },
    onError: (error) => setFormError(error?.response?.data?.detail || 'The schedule could not be published.'),
  });

  const preview = useQuery({
    queryKey: ['clinicianSchedulePreview', doctorId, previewDate, previewMode, savedRevision],
    queryFn: async () => (await api.get(`/clinician-schedules/admin/${doctorId}/preview`, { params: { appointment_date: previewDate, service_mode: previewMode } })).data,
    enabled: Boolean(previewDate && savedRevision > 0),
    retry: false,
  });

  const updateBlock = (index, field, value) => setWeeklyBlocks((current) => current.map((block, itemIndex) => (
    itemIndex === index ? { ...block, [field]: field === 'day_of_week' ? Number(value) : value } : block
  )));

  const addException = () => {
    const start = bookingWindow.data?.earliest_date;
    const end = bookingWindow.data?.latest_date;
    if (!start || !end) return;
    const candidate = new Date(`${start}T12:00:00`);
    const last = new Date(`${end}T12:00:00`);
    while (candidate <= last) {
      const value = candidate.toISOString().slice(0, 10);
      if (!exceptions.some((item) => item.date === value)) {
        setExceptions((current) => [...current, { date: value, blocks: [] }]);
        return;
      }
      candidate.setDate(candidate.getDate() + 1);
    }
  };

  if (schedule.isLoading) return <div className="portal-page"><Skeleton variant="row" count={5} /></div>;
  if (schedule.isError) return <ErrorState message="Could not load this clinician's schedule." onRetry={() => schedule.refetch()} />;

  const scheduleStatus = schedule.data?.status || 'unconfigured';
  const busy = saveDraft.isPending || publish.isPending;

  return (
    <div className="portal-page clinician-schedule animate-fade-in">
      <header className="clinician-schedule__header">
        <div>
          <Link className="clinician-schedule__back" to="/admin/doctors"><span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>Clinical team</Link>
          <p className="portal-section__eyebrow">Administrator · clinician availability</p>
          <h1>{schedule.data.doctor_name}</h1>
          <p>Define 30-minute clinic and home-visit availability without changing existing appointments.</p>
        </div>
        <span className={`clinician-schedule__status clinician-schedule__status--${scheduleStatus}`}>{statusCopy(scheduleStatus)}</span>
      </header>

      <div className="clinician-schedule__notice" role="note">
        <span className="material-symbols-outlined" aria-hidden="true">info</span>
        <div><strong>Drafts never change patient booking availability.</strong><span>Review the slot preview, then publish deliberately. Home visits still require an operational travel-time policy.</span></div>
      </div>

      <section className="portal-section-card clinician-schedule__section" aria-labelledby="weekly-heading">
        <div className="portal-section-card__header">
          <div><span className="portal-section__eyebrow">Weekly pattern</span><h2 id="weekly-heading">Clinic and home blocks</h2></div>
          <button type="button" className="clinician-schedule__secondary" onClick={() => setWeeklyBlocks((current) => [...current, emptyBlock()])}>Add block</button>
        </div>
        {!weeklyBlocks.length ? (
          <div className="clinician-schedule__empty"><span className="material-symbols-outlined" aria-hidden="true">event_busy</span><strong>No weekly hours configured</strong><p>Add only client-approved clinician hours. Nothing here is assumed from the demonstration fallback.</p></div>
        ) : (
          <div className="clinician-schedule__blocks">
            {weeklyBlocks.map((block, index) => (
              <div className="clinician-schedule__block" key={`${block.day_of_week}-${block.service_mode}-${index}`}>
                <label>Day<select value={block.day_of_week} onChange={(event) => updateBlock(index, 'day_of_week', event.target.value)}>{DAYS.map((day, dayIndex) => <option key={day} value={dayIndex}>{day}</option>)}</select></label>
                <label>Care mode<select value={block.service_mode} onChange={(event) => updateBlock(index, 'service_mode', event.target.value)}><option value="clinic">Clinic</option><option value="home_visit">Home visit</option></select></label>
                <label>Starts<input type="time" step="1800" value={block.start_time} onChange={(event) => updateBlock(index, 'start_time', event.target.value)} /></label>
                <label>Ends<input type="time" step="1800" value={block.end_time} onChange={(event) => updateBlock(index, 'end_time', event.target.value)} /></label>
                <button type="button" className="clinician-schedule__remove" aria-label={`Remove ${DAYS[block.day_of_week]} ${MODES[block.service_mode]} block`} onClick={() => setWeeklyBlocks((current) => current.filter((_, itemIndex) => itemIndex !== index))}><span className="material-symbols-outlined" aria-hidden="true">delete</span></button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="portal-section-card clinician-schedule__section" aria-labelledby="exceptions-heading">
        <div className="portal-section-card__header">
          <div><span className="portal-section__eyebrow">Date exceptions</span><h2 id="exceptions-heading">Leave and changed hours</h2><p>An empty exception closes the clinician for that date.</p></div>
          <button type="button" className="clinician-schedule__secondary" onClick={addException} disabled={!bookingWindow.data}>Add closed date</button>
        </div>
        {!exceptions.length ? <p className="clinician-schedule__muted">No date exceptions in the current booking window.</p> : (
          <div className="clinician-schedule__exceptions">
            {exceptions.map((exception, exceptionIndex) => (
              <article key={`${exception.date}-${exceptionIndex}`} className="clinician-schedule__exception">
                <div className="clinician-schedule__exception-head">
                  <label>Date<input type="date" min={bookingWindow.data?.earliest_date} max={bookingWindow.data?.latest_date} value={exception.date} onChange={(event) => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, date: event.target.value } : item))} /></label>
                  <span>{exception.blocks.length ? 'Custom hours' : 'Closed all day'}</span>
                  <button type="button" aria-label={`Remove exception for ${exception.date}`} onClick={() => setExceptions((current) => current.filter((_, index) => index !== exceptionIndex))}><span className="material-symbols-outlined" aria-hidden="true">close</span></button>
                </div>
                {exception.blocks.map((block, blockIndex) => (
                  <div className="clinician-schedule__exception-block" key={`${block.service_mode}-${blockIndex}`}>
                    <select aria-label="Exception care mode" value={block.service_mode} onChange={(event) => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, blocks: item.blocks.map((entry, inner) => inner === blockIndex ? { ...entry, service_mode: event.target.value } : entry) } : item))}><option value="clinic">Clinic</option><option value="home_visit">Home visit</option></select>
                    <input aria-label="Exception start time" type="time" step="1800" value={block.start_time} onChange={(event) => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, blocks: item.blocks.map((entry, inner) => inner === blockIndex ? { ...entry, start_time: event.target.value } : entry) } : item))} />
                    <input aria-label="Exception end time" type="time" step="1800" value={block.end_time} onChange={(event) => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, blocks: item.blocks.map((entry, inner) => inner === blockIndex ? { ...entry, end_time: event.target.value } : entry) } : item))} />
                    <button type="button" aria-label="Remove exception hours" onClick={() => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, blocks: item.blocks.filter((_, inner) => inner !== blockIndex) } : item))}><span className="material-symbols-outlined" aria-hidden="true">delete</span></button>
                  </div>
                ))}
                <button type="button" className="clinician-schedule__text-action" onClick={() => setExceptions((current) => current.map((item, index) => index === exceptionIndex ? { ...item, blocks: [...item.blocks, { ...emptyBlock(weekdayIndex(item.date)) }] } : item))}>Add custom hours</button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="portal-section-card clinician-schedule__section" aria-labelledby="preview-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Draft preview</span><h2 id="preview-heading">Patient-visible slots</h2></div></div>
        <div className="clinician-schedule__preview-controls">
          <label>Date<input type="date" min={bookingWindow.data?.earliest_date} max={bookingWindow.data?.latest_date} value={previewDate} onChange={(event) => setPreviewDate(event.target.value)} /></label>
          <label>Care mode<select value={previewMode} onChange={(event) => setPreviewMode(event.target.value)}><option value="clinic">Clinic</option><option value="home_visit">Home visit</option></select></label>
        </div>
        {!savedRevision ? <p className="clinician-schedule__muted">Save a draft to preview its slots.</p> : preview.isLoading ? <p role="status">Loading draft slots…</p> : preview.isError ? <div className="clinician-schedule__inline-error" role="alert"><span>{preview.error?.response?.data?.detail || 'Could not preview this date.'}</span><button type="button" onClick={() => preview.refetch()}>Try again</button></div> : (
          <div className="clinician-schedule__slots" aria-label={`${MODES[previewMode]} draft slots`}>
            {preview.data?.slots?.length ? preview.data.slots.map((slot) => <span key={slot.time_slot} className={`clinician-schedule__slot clinician-schedule__slot--${slot.availability_state}`}><strong>{slot.time_slot}</strong><small>{slot.availability_state}</small></span>) : <p className="clinician-schedule__muted">Closed for this date and care mode.</p>}
          </div>
        )}
      </section>

      <section className="portal-section-card clinician-schedule__section" aria-labelledby="audit-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Audit trail</span><h2 id="audit-heading">Recent schedule activity</h2></div></div>
        {!schedule.data.audit_history?.length ? <p className="clinician-schedule__muted">No schedule changes recorded yet.</p> : <ol className="clinician-schedule__audit">{[...schedule.data.audit_history].reverse().map((entry, index) => <li key={`${entry.occurred_at}-${index}`}><span className="material-symbols-outlined" aria-hidden="true">{entry.action === 'published' ? 'publish' : 'edit_note'}</span><div><strong>{entry.action === 'published' ? 'Schedule published' : 'Draft saved'}</strong><small>Revision {entry.revision} · {new Date(entry.occurred_at).toLocaleString('en-IN', { timeZone: schedule.data.timezone })}</small></div></li>)}</ol>}
      </section>

      {(validationError || formError) && <p className="clinician-schedule__form-error" role="alert">{validationError || formError}</p>}
      <div className="clinician-schedule__actions">
        <button type="button" className="clinician-schedule__secondary" disabled={busy} onClick={() => { setWeeklyBlocks(schedule.data.weekly_blocks || []); setExceptions(schedule.data.date_exceptions || []); setFormError(''); }}>Discard local edits</button>
        <button type="button" className="clinician-schedule__save" disabled={busy || Boolean(validationError)} onClick={() => saveDraft.mutate()}>{saveDraft.isPending ? 'Saving…' : 'Save draft'}</button>
        <button type="button" className="clinician-schedule__publish" disabled={busy || !savedRevision || savedRevision === schedule.data.published_revision} onClick={() => publish.mutate()}>{publish.isPending ? 'Publishing…' : 'Publish availability'}</button>
      </div>
    </div>
  );
}
