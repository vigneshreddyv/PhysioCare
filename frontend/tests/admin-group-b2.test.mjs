import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import react from '@vitejs/plugin-react';
import { createLogger, createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let vite;
let cacheDir;
let ClinicalEntityPicker;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-b2-ui-'));
  vite = await createServer({ configFile: false, root, plugins: [react()], cacheDir,
    customLogger: createLogger('silent'), server: { middlewareMode: true, hmr: false },
    appType: 'custom' });
  ({ default: ClinicalEntityPicker } = await vite.ssrLoadModule('/src/pages/admin/ClinicalEntityPicker.jsx'));
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

async function source(name) {
  return readFile(join(root, 'src/pages/admin', name), 'utf8');
}

test('a selection beyond the current page remains visible without loading all records', () => {
  const client = new QueryClient();
  const page = Array.from({ length: 50 }, (_, index) => ({ id: `fictional-${index}`, full_name: `Fictional ${index}` }));
  client.setQueryData(['clinicalEntityPicker', '/users/patients', '', 1],
    { data: page, page: 1, hasNext: true });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(ClinicalEntityPicker, {
      path: '/users/patients', label: 'Patient',
      selected: { id: 'fictional-1201', full_name: 'Fictional 1201' },
      onSelect: () => {}, describe: (patient) => patient.full_name,
    })));
  assert.match(html, /Fictional 1201/);
  assert.match(html, /value="fictional-1201" selected=""/);
  assert.equal((html.match(/<option /g) || []).length, 52);
  assert.match(html, /Search patient/);
  assert.match(html, /Patient pages/);
});

test('admin history requests one bounded patient and date-scoped page', async () => {
  const text = await source('AdminPatientHistory.jsx');
  assert.match(text, /params: \{ page, page_size: CLINICAL_PAGE_SIZE, start_date:/);
  assert.match(text, /<ClinicalPageNav label="Patient history"/);
  assert.match(text, /activePatientRef\.current !== patientIdAtOpen/);
  assert.match(text, /patientIdAtOpen: id/);
  assert.match(text, /if \(viewerRef\.current\) closePdfViewer\(viewerRef\.current\)/);
  assert.doesNotMatch(text, /fetchClinicalHistoryPages/);
});

test('booking selectors search server-side and final mutation stays authoritative', async () => {
  const text = await source('AppointmentBooking.jsx');
  assert.match(text, /<ClinicalEntityPicker path=\{isReceptionist \? '\/users\/reception\/patients' : '\/users\/patients'\}/);
  assert.match(text, /<ClinicalEntityPicker path=\{isReceptionist \? '\/users\/reception\/doctors' : '\/users\/doctors'\}/);
  assert.match(text, /api\.get\('\/appointments\/availability'/);
  assert.match(text, /api\.post\(/);
  assert.doesNotMatch(text, /fetchClinicalPages/);
});

test('care plans and exercise assignments use independent pages', async () => {
  const care = await source('CarePlanManagement.jsx');
  const exercise = await source('ExerciseAssignmentManagement.jsx');
  assert.match(care, /fetchClinicalPage\(`\/care-plans\/patient\/\$\{patientId\}`, plansPage\)/);
  assert.match(care, /selectedPlanSnapshot/);
  assert.match(exercise, /include_labels=true/);
  assert.match(exercise, /<ClinicalEntityPicker path="\/exercises\?active_only=true"/);
  assert.match(exercise, /<ClinicalPageNav label="Prescribed routines"/);
  assert.doesNotMatch(exercise, /fetchClinicalPages/);
});

test('demo queues and clinician choices are server-filtered before pagination', async () => {
  const text = await source('DemoServices.jsx');
  assert.match(text, /fetchClinicalPage\('\/home-visit-bookings\/admin\/scheduled', bookingPage\)/);
  assert.match(text, /home_visits_only=true&search=/);
  assert.match(text, /<ClinicalPageNav label="Demo entitlements"/);
  assert.match(text, /<ClinicalPageNav label="Home-visit requests"/);
  assert.doesNotMatch(text, /appointments\.data \|\| \[\]\)\.filter/);
});

test('report authoring searches scoped patients and retains the private upload contract', async () => {
  const text = await source('ReportAuthoring.jsx');
  assert.match(text, /<ClinicalEntityPicker path="\/users\/patients"/);
  assert.match(text, /body\.append\('report_data_str', JSON\.stringify\(payload\)\)/);
  assert.match(text, /api\.post\('\/reports', body/);
  assert.doesNotMatch(text, /fetchClinicalPages/);
});
