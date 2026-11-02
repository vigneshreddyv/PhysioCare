import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import { getHomeVisitReviewIssues } from '../src/utils/homeVisitBooking.js';


const completeNoPreferenceForm = {
  preferred_doctor_id: 'no_preference',
  appointment_date: '2040-04-12',
  time_slot: '10:00 AM',
  home_address: '12 Fictional Road, Nellore',
  city: 'Nellore',
  body_regions: ['Knee'],
  symptoms: ['Pain'],
  duration_days: 2,
};

const available = { slots: [{ time_slot: '10:00 AM', available: true }] };
const componentUrl = new URL('../src/pages/patient/HomeVisitRequests.jsx', import.meta.url);


test('no-preference remains a valid selection without a selected clinician object', () => {
  assert.deepEqual(getHomeVisitReviewIssues({
    form: completeNoPreferenceForm,
    selectedDoctor: null,
    availability: available,
  }), []);
});


test('availability requests remain keyed by preference and date to isolate stale responses', async () => {
  const source = await readFile(componentUrl, 'utf8');
  assert.match(source, /queryKey:\['homeVisitAvailability',form\.preferred_doctor_id,form\.appointment_date\]/);
  assert.match(source, /enabled:Boolean\(entitlement\.data\?\.active&&form\.preferred_doctor_id&&form\.appointment_date\)/);
  assert.match(source, /params:\{doctor_id:form\.preferred_doctor_id,appointment_date:form\.appointment_date\}/);
});


test('preference or date changes clear the previous selected slot', async () => {
  const source = await readFile(componentUrl, 'utf8');
  assert.match(source, /setForm\(\(current\)=>\(\{\.\.\.current,time_slot:''\}\)\);},\[form\.preferred_doctor_id,form\.appointment_date\]/);
});


test('loading, empty availability, and API error states remain explicit', async () => {
  const source = await readFile(componentUrl, 'utf8');
  assert.match(source, /Checking home-visit slots/);
  assert.match(source, /No home-visit times are listed for this date/);
  assert.match(source, /We could not load available times/);
  assert.match(source, /availability\.refetch\(\)/);
});


test('no-preference submission keeps the existing nullable doctor contract', async () => {
  const source = await readFile(componentUrl, 'utf8');
  assert.match(source, /preferred_doctor_id:form\.preferred_doctor_id===NO_PREFERENCE\?null:form\.preferred_doctor_id/);
  assert.match(source, /api\.post\('\/home-visit-bookings',payload\)/);
  assert.match(source, /booking\.doctor_assignment_pending/);
});


test('the component has a single availability request and introduces no polling request loop', async () => {
  const source = await readFile(componentUrl, 'utf8');
  assert.equal((source.match(/api\.get\('\/home-visit-bookings\/availability'/g) || []).length, 1);
  assert.doesNotMatch(source, /refetchInterval|setInterval/);
});
