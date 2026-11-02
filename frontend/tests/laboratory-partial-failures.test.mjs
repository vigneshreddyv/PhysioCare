import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import react from '@vitejs/plugin-react';
import { createLogger, createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let vite;
let cacheDir;
let LaboratoryRequestHistory;
let ReleasedLaboratoryReports;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-lab-render-'));
  vite = await createServer({
    configFile: false,
    root,
    plugins: [react()],
    cacheDir,
    customLogger: createLogger('silent'),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  ({ LaboratoryRequestHistory, ReleasedLaboratoryReports } = await vite.ssrLoadModule(
    '/src/pages/patient/LaboratoryRequests.jsx',
  ));
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

const fictionalRequest = {
  id: 'fictional-request',
  status: 'pending_clinic_confirmation',
  mode: 'clinic_visit',
  selected_tests: ['fictional-test'],
  confirmation_message: 'Fictional clinic review is pending.',
};
const fictionalReport = {
  request_id: 'fictional-report',
  report_file_name: 'Fictional released report.pdf',
  selected_tests: ['Fictional test'],
};

function renderSections(requests, reports) {
  return renderToStaticMarkup(React.createElement(React.Fragment, null,
    React.createElement(LaboratoryRequestHistory, { requests, withdraw: { mutate() {} } }),
    React.createElement(ReleasedLaboratoryReports, {
      reports,
      openReport: { isError: false, isPending: false, mutate() {} },
    }),
  ));
}

function findErrorState(node) {
  if (Array.isArray(node)) return node.map(findErrorState).find(Boolean);
  if (!React.isValidElement(node)) return null;
  if (node.props.message?.startsWith('Could not load your')) return node;
  return findErrorState(node.props.children);
}

test('report loading failure leaves request history visible', () => {
  const html = renderSections(
    { data: [fictionalRequest] },
    { isError: true, refetch() {} },
  );

  assert.match(html, /Fictional clinic review is pending/);
  assert.match(html, /Could not load your released laboratory reports/);
  assert.match(html, /Try Again/);
  assert.doesNotMatch(html, /No released reports/);
});

test('request loading failure leaves released reports visible', () => {
  const html = renderSections(
    { isError: true, refetch() {} },
    { data: [fictionalReport] },
  );

  assert.match(html, /Could not load your laboratory requests/);
  assert.match(html, /Fictional released report\.pdf/);
  assert.doesNotMatch(html, /No laboratory requests/);
});

test('each error retries only its own query', () => {
  let requestRetries = 0;
  let reportRetries = 0;
  const requests = { isError: true, refetch: () => { requestRetries += 1; } };
  const reports = { isError: true, refetch: () => { reportRetries += 1; } };
  const requestError = findErrorState(LaboratoryRequestHistory({ requests, withdraw: { mutate() {} } }));
  const reportError = findErrorState(ReleasedLaboratoryReports({
    reports,
    openReport: { isError: false },
  }));

  assert.ok(requestError);
  assert.ok(reportError);
  requestError.props.onRetry();
  assert.deepEqual([requestRetries, reportRetries], [1, 0]);
  reportError.props.onRetry();
  assert.deepEqual([requestRetries, reportRetries], [1, 1]);
});

test('loading and empty states do not claim a query failure is an empty history', () => {
  const html = renderSections({ isLoading: true }, { data: [] });

  assert.match(html, /Loading laboratory requests/);
  assert.match(html, /No released reports/);
  assert.doesNotMatch(html, /No laboratory requests/);
});

test('the page keeps the request form and omits the unused home-visit context query', async () => {
  const source = await readFile(new URL('../src/pages/patient/LaboratoryRequests.jsx', import.meta.url), 'utf8');

  assert.match(source, /<LaboratoryRequestHistory requests=\{requests\}/);
  assert.match(source, /<ReleasedLaboratoryReports reports=\{reports\}/);
  assert.match(source, /Continue to clinic review/);
  assert.doesNotMatch(source, /homeVisitContext|\/home-visit-requests\/me\/context/);
  assert.doesNotMatch(source, /if \(requests\.error \|\|/);
});
