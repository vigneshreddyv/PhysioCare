import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('legacy booking detail does not render internal provider identifiers', async () => {
  const source = await read('src/pages/patient/LaboratoryBookingDetail.jsx');

  assert.doesNotMatch(source, /booking\.payment_id/);
  assert.doesNotMatch(source, /booking\.payment_order_id/);
  assert.doesNotMatch(source, />Transaction ID</);
  assert.doesNotMatch(source, />Order ID</);
  assert.match(source, /booking\.payment_status/);
  assert.match(source, /booking\.billing_amount/);
});

test('legacy laboratory screens remain outside the active patient router', async () => {
  const app = await read('src/App.jsx');

  assert.doesNotMatch(app, /LaboratoryBookingDetail/);
  assert.doesNotMatch(app, /LaboratoryTestSelection/);
  assert.doesNotMatch(app, /path="laboratory\/tests"/);
  assert.match(app, /path="laboratory" element={<LaboratoryRequests \/>}/);
});

