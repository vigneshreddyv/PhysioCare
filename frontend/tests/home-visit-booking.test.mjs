import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { getHomeVisitReviewIssues } from '../src/utils/homeVisitBooking.js';

const completeForm = {
  preferred_doctor_id: 'doctor-1',
  appointment_date: '2030-04-12',
  time_slot: '10:00 AM',
  home_address: '12 Fictional Road, Nellore',
  city: 'Nellore',
  body_regions: ['Knee'],
  symptoms: ['Pain'],
  duration_days: 2,
  reason: '',
};

const selectedDoctor = { id: 'doctor-1', full_name: 'Dr. Fictional', specialization: 'Physiotherapy' };
const available = { slots: [{ time_slot: '10:00 AM', available: true }] };

test('review blocks confirmation and explains missing required information', () => {
  const issues = getHomeVisitReviewIssues({
    form: { ...completeForm, preferred_doctor_id: '', appointment_date: '', time_slot: '', home_address: '', symptoms: [], duration_days: '' },
    availability: undefined,
  });

  assert.ok(issues.some((issue) => issue.includes('clinician')));
  assert.ok(issues.some((issue) => issue.includes('date')));
  assert.ok(issues.some((issue) => issue.includes('available visit time')));
  assert.ok(issues.some((issue) => issue.includes('full visit address')));
  assert.ok(issues.some((issue) => issue.includes('symptom')));
  assert.ok(issues.some((issue) => issue.includes('duration')));
});

test('complete review with a server-listed available slot can be confirmed', () => {
  assert.deepEqual(getHomeVisitReviewIssues({ form: completeForm, selectedDoctor, availability: available }), []);
});

test('review blocks a slot absent from or marked unavailable by the latest availability response', () => {
  const absent = getHomeVisitReviewIssues({ form: completeForm, selectedDoctor, availability: { slots: [] } });
  const occupied = getHomeVisitReviewIssues({
    form: completeForm,
    selectedDoctor,
    availability: { slots: [{ time_slot: '10:00 AM', available: false }] },
  });

  assert.ok(absent.some((issue) => issue.includes('no longer listed')));
  assert.ok(occupied.some((issue) => issue.includes('no longer available')));
});

test('confirmation submits through the backend booking route and reports server validation failures', async () => {
  const component = await readFile(new URL('../src/pages/patient/HomeVisitRequests.jsx', import.meta.url), 'utf8');

  assert.match(component, /api\.post\('\/home-visit-bookings',payload\)/);
  assert.match(component, /if\(reviewIssues\.length\)return/);
  assert.match(component, /create\.error\?\.response\?\.data\?\.detail/);
  assert.match(component, /Anything else the physiotherapist should know\? \(Optional\)/);
  assert.doesNotMatch(component, /textarea required minLength=\{5\} maxLength=\{1000\} rows=\{4\} value=\{form\.reason\}/);
  assert.match(component, /See what is needed to confirm/);
  assert.match(component, /patient-home-visit-card__details/);
});
