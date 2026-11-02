import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = async (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('patient payment history replaces one bounded page and exposes server filters', async () => {
  const text = await source('src/pages/patient/PatientPaymentHistory.jsx');
  assert.match(text, /fetchClinicalPage\(historyPath, page\)/);
  assert.match(text, /queryKey: \['patientPaymentHistory', page, paymentStatus, startDate, endDate\]/);
  assert.match(text, /filters\.set\('payment_status', paymentStatus\)/);
  assert.match(text, /filters\.set\('start_date', startDate\)/);
  assert.match(text, /filters\.set\('end_date', endDate\)/);
  assert.match(text, /<ClinicalPageNav label="Payment history"/);
  assert.match(text, /Loading payment history/);
  assert.match(text, /Could not load payment history/);
  assert.match(text, /No payment history/);
  assert.doesNotMatch(text, /api\.get\('\/payments\/history'\)/);
  assert.doesNotMatch(text, /fetchClinicalPages/);
});

test('staff directory searches and filters one server page without client accumulation', async () => {
  const text = await source('src/pages/admin/StaffManagement.jsx');
  assert.match(text, /fetchClinicalPage\(staffPath, page\)/);
  assert.match(text, /staffFilters\.set\('search', deferredQuery\.trim\(\)\)/);
  assert.match(text, /staffFilters\.set\('role', roleFilter\)/);
  assert.match(text, /staffFilters\.set\('account_status', statusFilter\)/);
  assert.match(text, /<ClinicalPageNav label="Staff accounts"/);
  assert.match(text, /Could not load staff accounts/);
  assert.match(text, /No matching staff/);
  assert.doesNotMatch(text, /filterStaff\(staffQuery\.data/);
  assert.doesNotMatch(text, /fetchClinicalPages/);
});

test('demo entitlement directory retains bounded page replacement for blank searches', async () => {
  const text = await source('src/pages/admin/DemoServices.jsx');
  assert.match(text, /fetchClinicalPage\(`\/demo-services\/entitlements\?search=/);
  assert.match(text, /queryKey: \['demoEntitlements', entitlementPage, deferredEntitlementSearch\]/);
  assert.match(text, /<ClinicalPageNav label="Demo entitlements"/);
  assert.doesNotMatch(text, /fetchClinicalPages/);
});

test('shared page loader rejects stale sessions and never retains prior pages', async () => {
  const text = await source('src/services/clinicalPagination.js');
  assert.match(text, /generation !== sessionGeneration/);
  assert.match(text, /controller\.abort\(\)/);
  assert.match(text, /params: \{ page, page_size: CLINICAL_PAGE_SIZE \}/);
  assert.match(text, /return \{ data, page, hasNext:/);
});
