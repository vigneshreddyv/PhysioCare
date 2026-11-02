import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = async (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('patient and administrator clinic booking share the authoritative 500-character reason ceiling', async () => {
  const [patient, admin] = await Promise.all([
    source('src/pages/patient/BookAppointment.jsx'),
    source('src/pages/admin/AppointmentBooking.jsx'),
  ]);
  assert.match(patient, /maxLength=\{500\}/);
  assert.match(patient, /\{reason\.length\}\/500/);
  assert.match(admin, /id="reason"[\s\S]*maxLength=\{500\}/);
});

test('frontend limits remain usability hints while backend requests remain authoritative', async () => {
  const booking = await source('src/pages/admin/AppointmentBooking.jsx');
  assert.match(booking, /api\.post\([\s\S]*'\/appointments\/admin'[\s\S]*appointmentData/);
  assert.doesNotMatch(booking, /slice\(0,\s*500\)/);
});
