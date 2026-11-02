import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import react from '@vitejs/plugin-react';
import { createLogger, createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let vite;
let cacheDir;
let api;
let fetchClinicalPages;
let fetchClinicalHistoryPages;
let fetchClinicalPage;
let cancelClinicalPageRequests;
let maxRetained;
let pageSize;
let maxPage;
let PatientsList;
let DoctorHomeVisits;
let LaboratoryDashboard;
let AdminLabRequestsPanel;
let Notifications;
let PatientLaboratoryRequests;
let PatientReports;
let PatientHistory;
let PatientAppointments;
let PatientDashboard;
let PatientCarePlan;
let PatientProgress;
let PatientExercises;
let Billing;
let AdminDashboard;
let AdminNotifications;
let AuthContext;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-clinical-pages-'));
  vite = await createServer({
    configFile: false,
    root,
    plugins: [react()],
    cacheDir,
    customLogger: createLogger('silent'),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  ({ default: api } = await vite.ssrLoadModule('/src/services/api.js'));
  ({ fetchClinicalPages, fetchClinicalHistoryPages, fetchClinicalPage, cancelClinicalPageRequests,
    CLINICAL_PAGE_SIZE: pageSize, MAX_RETAINED_CLINICAL_RECORDS: maxRetained,
    MAX_CLINICAL_PAGE: maxPage } = await vite.ssrLoadModule(
    '/src/services/clinicalPagination.js',
  ));
  [{ default: PatientsList }, { default: DoctorHomeVisits },
    { default: LaboratoryDashboard }, { default: AdminLabRequestsPanel }, { default: Notifications },
    { default: PatientLaboratoryRequests }, { default: PatientReports },
    { default: PatientHistory }, { default: PatientAppointments }, { default: PatientDashboard },
    { default: PatientCarePlan }, { default: PatientProgress }, { default: PatientExercises },
    { default: Billing }, { default: AdminDashboard }, { default: AdminNotifications },
    { AuthContext }] = await Promise.all([
    vite.ssrLoadModule('/src/pages/admin/PatientsList.jsx'),
    vite.ssrLoadModule('/src/pages/doctor/HomeVisits.jsx'),
    vite.ssrLoadModule('/src/pages/laboratorian/LaboratoryDashboard.jsx'),
    vite.ssrLoadModule('/src/pages/admin/AdminLabRequestsPanel.jsx'),
    vite.ssrLoadModule('/src/pages/common/Notifications.jsx'),
    vite.ssrLoadModule('/src/pages/patient/LaboratoryRequests.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientReports.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientHistory.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientAppointments.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientDashboard.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientCarePlan.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientProgress.jsx'),
    vite.ssrLoadModule('/src/pages/patient/PatientExercises.jsx'),
    vite.ssrLoadModule('/src/pages/admin/Billing.jsx'),
    vite.ssrLoadModule('/src/pages/admin/AdminDashboard.jsx'),
    vite.ssrLoadModule('/src/pages/admin/Notifications.jsx'),
    vite.ssrLoadModule('/src/context/AuthContext.jsx'),
  ]);
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

async function withPages(handler, run) {
  const original = api.get;
  api.get = handler;
  try {
    return await run();
  } finally {
    api.get = original;
  }
}

test('all bounded pages remain visible in the existing array contract', async () => {
  const first = Array.from({ length: pageSize }, (_, id) => ({ id }));
  const last = [{ id: pageSize }, { id: pageSize + 1 }];
  const calls = [];
  const result = await withPages(async (path, options) => {
    calls.push([path, options.params]);
    return { data: options.params.page === 1 ? first : last };
  }, () => fetchClinicalPages('/reports'));

  assert.deepEqual(result.data, [...first, ...last]);
  assert.deepEqual(calls, [
    ['/reports', { page: 1, page_size: pageSize }],
    ['/reports', { page: 2, page_size: pageSize }],
  ]);
  assert.equal(new Set(result.data.map((item) => item.id)).size, result.data.length);
});

test('an exact full page checks the next page instead of silently truncating', async () => {
  const pages = [];
  const result = await withPages(async (_path, { params }) => {
    pages.push(params.page);
    return { data: params.page === 1
      ? Array.from({ length: pageSize }, (_, id) => ({ id: `fictional-${id}` })) : [] };
  }, () => fetchClinicalPages('/appointments'));

  assert.equal(result.data.length, pageSize);
  assert.deepEqual(pages, [1, 2]);
});

test('empty lists retain the existing empty array state', async () => {
  const result = await withPages(async () => ({ data: [] }),
    () => fetchClinicalPages('/lab-requests/me'));
  assert.deepEqual(result, { data: [] });
});

test('patient directory keeps scanning after a sparse page until the database page is empty', async () => {
  const pages = [];
  const result = await withPages(async (_path, { params }) => {
    pages.push(params.page);
    return { data: params.page === 1 ? [{ id: 'first' }]
      : params.page === 2 ? [{ id: 'second' }] : [] };
  }, () => fetchClinicalPages('/users/reception/patients', { untilEmpty: true }));
  assert.deepEqual(result.data.map((item) => item.id), ['first', 'second']);
  assert.deepEqual(pages, [1, 2, 3]);
});

test('malformed, oversized, and failed later pages surface errors', async () => {
  await assert.rejects(withPages(async () => ({ data: {} }),
    () => fetchClinicalPages('/reports')), /invalid/);
  await assert.rejects(withPages(async () => ({ data: Array(pageSize + 1).fill({}) }),
    () => fetchClinicalPages('/reports')), /invalid/);
  await assert.rejects(withPages(async (_path, { params }) => {
    if (params.page === 1) return { data: Array(pageSize).fill({}) };
    throw new Error('Fictional API failure');
  }, () => fetchClinicalPages('/reports')), /Fictional API failure/);
});

test('patient history combines both bounded clinical arrays without losing profile metadata', async () => {
  const calls = [];
  const result = await withPages(async (path, { params }) => {
    calls.push([path, params]);
    return { data: {
      patient: { id: 'fictional-patient' },
      profile_audit: [{ changed_fields: ['phone'] }],
      appointments: params.page === 1 ? Array.from({ length: pageSize }, (_, id) => ({ id })) : [{ id: pageSize }],
      reports: params.page === 1 ? [{ id: 'report-1' }] : [],
    } };
  }, () => fetchClinicalHistoryPages('/users/patients/fictional/history'));
  assert.equal(result.data.appointments.length, pageSize + 1);
  assert.equal(result.data.reports.length, 1);
  assert.equal(result.data.patient.id, 'fictional-patient');
  assert.equal(result.data.profile_audit.length, 1);
  assert.deepEqual(calls.map(([, params]) => params.page), [1, 2]);
});

test('invalid or failed later patient-history pages surface errors', async () => {
  await assert.rejects(withPages(async () => ({ data: { appointments: [], reports: {} } }),
    () => fetchClinicalHistoryPages('/users/patients/fictional/history')), /invalid/);
  await assert.rejects(withPages(async (_path, { params }) => {
    if (params.page === 1) return { data: { appointments: Array(pageSize).fill({}), reports: [] } };
    throw new Error('Fictional history failure');
  }, () => fetchClinicalHistoryPages('/users/patients/fictional/history')), /Fictional history failure/);
});

test('overlapping static pages deduplicate stable record IDs', async () => {
  const result = await withPages(async (_path, { params }) => ({
    data: params.page === 1
      ? Array.from({ length: pageSize }, (_, id) => ({ id }))
      : [{ id: pageSize - 1 }, { id: pageSize }],
  }), () => fetchClinicalPages('/reports'));
  assert.equal(result.data.length, pageSize + 1);
  assert.equal(new Set(result.data.map((item) => item.id)).size, result.data.length);
});

test('concurrent identical clinical requests share one fetch', async () => {
  let resolve;
  let calls = 0;
  await withPages(async () => {
    calls += 1;
    return new Promise((done) => { resolve = done; });
  }, async () => {
    const first = fetchClinicalPages('/notifications');
    const second = fetchClinicalPages('/notifications');
    assert.strictEqual(first, second);
    assert.equal(calls, 1);
    resolve({ data: [] });
    assert.deepEqual(await first, { data: [] });
    assert.deepEqual(await second, { data: [] });
  });
});

test('logout cancellation blocks a stale patient response and clears the in-flight request', async () => {
  let resolve;
  let signal;
  await withPages(async (_path, options) => {
    signal = options.signal;
    return new Promise((done) => { resolve = done; });
  }, async () => {
    const pending = fetchClinicalPages('/appointments');
    cancelClinicalPageRequests();
    assert.equal(signal.aborted, true);
    resolve({ data: [{ id: 'old-patient' }] });
    await assert.rejects(pending, /cancelled/);
  });
  const fresh = await withPages(async () => ({ data: [{ id: 'new-patient' }] }),
    () => fetchClinicalPages('/appointments'));
  assert.deepEqual(fresh.data, [{ id: 'new-patient' }]);
});

test('different patient filters keep distinct in-flight results', async () => {
  const pending = new Map();
  await withPages(async (path) => new Promise((resolve) => { pending.set(path, resolve); }), async () => {
    const first = fetchClinicalPages('/care-plans/patient/fictional-a');
    const second = fetchClinicalPages('/care-plans/patient/fictional-b');
    pending.get('/care-plans/patient/fictional-b')({ data: [{ id: 'patient-b' }] });
    pending.get('/care-plans/patient/fictional-a')({ data: [{ id: 'patient-a' }] });
    assert.deepEqual((await second).data, [{ id: 'patient-b' }]);
    assert.deepEqual((await first).data, [{ id: 'patient-a' }]);
  });
});

test('browser record budget fails explicitly before retaining a larger list', async () => {
  let calls = 0;
  await assert.rejects(withPages(async (_path, { params }) => {
    calls += 1;
    return { data: Array.from({ length: pageSize }, (_, index) => ({
      id: (params.page - 1) * pageSize + index,
    })) };
  }, () => fetchClinicalPages('/users/patients')), /Too many clinical records/);
  assert.equal(maxRetained, 1000);
  assert.equal(calls, maxRetained / pageSize + 1);
});

test('history record budget includes appointments and reports', async () => {
  await assert.rejects(withPages(async (_path, { params }) => ({ data: {
    patient: { id: 'fictional' },
    appointments: Array.from({ length: pageSize }, (_, index) => ({ id: (params.page - 1) * pageSize + index })),
    reports: Array.from({ length: pageSize }, (_, index) => ({ request_id: (params.page - 1) * pageSize + index })),
  } }), () => fetchClinicalHistoryPages('/users/patients/fictional/history')),
  /Too many clinical records/);
});

test('page replacement reaches records beyond 1000 without accumulating earlier pages', async () => {
  const calls = [];
  const result = await withPages(async (_path, { params }) => {
    calls.push(params.page);
    return { data: Array.from({ length: pageSize }, (_, index) => ({
      id: (params.page - 1) * pageSize + index,
    })) };
  }, () => fetchClinicalPage('/users/patients', 21));
  assert.deepEqual(calls, [21]);
  assert.equal(result.data.length, pageSize);
  assert.equal(result.data[0].id, 1000);
  assert.equal(result.hasNext, true);
});

test('static 1250-record directory stays ordered and complete across replacement pages', async () => {
  const records = Array.from({ length: 1250 }, (_, id) => ({ id }));
  const requested = [];
  const seen = [];
  await withPages(async (_path, { params }) => {
    requested.push(params.page);
    const start = (params.page - 1) * params.page_size;
    return { data: records.slice(start, start + params.page_size) };
  }, async () => {
    for (let page = 1; page <= 25; page += 1) {
      const result = await fetchClinicalPage('/users/patients', page);
      assert.equal(result.data.length, pageSize);
      seen.push(...result.data.map((row) => row.id));
    }
  });
  assert.deepEqual(requested, Array.from({ length: 25 }, (_, index) => index + 1));
  assert.deepEqual(seen, records.map((row) => row.id));
  assert.equal(new Set(seen).size, 1250);
});

test('single-page navigation deduplicates records and validates page bounds', async () => {
  const result = await withPages(async () => ({ data: [{ id: 1 }, { id: 1 }, { id: 2 }] }),
    () => fetchClinicalPage('/users/patients', 2));
  assert.deepEqual(result.data.map((row) => row.id), [1, 2]);
  assert.equal(result.hasNext, false);
  await assert.rejects(fetchClinicalPage('/users/patients', maxPage + 1), /invalid/);
  await assert.rejects(fetchClinicalPage('/users/patients', 0), /invalid/);
});

test('released laboratory pages deduplicate by request_id', async () => {
  const result = await withPages(async () => ({ data: [
    { request_id: 'fictional-report-a' },
    { request_id: 'fictional-report-a' },
    { request_id: 'fictional-report-b' },
  ] }), () => fetchClinicalPage('/lab-requests/me/reports', 21, 'request_id'));
  assert.deepEqual(result.data.map((item) => item.request_id), [
    'fictional-report-a', 'fictional-report-b',
  ]);
});

test('single-page requests are shared and old patient results are cancelled', async () => {
  let resolve;
  let signal;
  await withPages(async (_path, options) => {
    signal = options.signal;
    return new Promise((done) => { resolve = done; });
  }, async () => {
    const first = fetchClinicalPage('/users/patients', 21);
    const shared = fetchClinicalPage('/users/patients', 21);
    assert.equal(shared, first);
    cancelClinicalPageRequests();
    assert.equal(signal.aborted, true);
    resolve({ data: [{ id: 'old-patient' }] });
    await assert.rejects(first, /cancelled/);
  });
  const fresh = await withPages(async () => ({ data: [{ id: 'new-patient' }] }),
    () => fetchClinicalPage('/users/patients', 21));
  assert.deepEqual(fresh.data, [{ id: 'new-patient' }]);
});

test('patient directory renders one bounded page with navigation', () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  const records = Array.from({ length: pageSize }, (_, index) => ({
    id: `patient-${index}`, full_name: `Fictional Patient ${index}`, email: `patient${index}@example.com`,
  }));
  client.setQueryData(['patients', 'directory', user.id, user.role, 1], {
    data: records, page: 1, hasNext: true,
  });
  const html = renderToStaticMarkup(React.createElement(
    QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientsList)),
    ),
  ));
  assert.match(html, /Patient directory pages/);
  assert.match(html, /Next page/);
  assert.match(html, /Fictional Patient 49/);
  assert.doesNotMatch(html, /Fictional Patient 50/);
});

test('a sparse administrator page still offers the next page', () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['patients', 'directory', user.id, user.role, 1], {
    data: [{ id: 'fictional-patient', full_name: 'Fictional Patient', email: 'patient@example.com' }],
    page: 1, hasNext: false,
  });
  const html = renderToStaticMarkup(React.createElement(
    QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientsList)),
    ),
  ));
  const nextButton = html.match(/<button[^>]*>Next page<\/button>/)?.[0];
  assert.ok(nextButton);
  assert.doesNotMatch(nextButton, /disabled/);
});

test('directory loading and empty states do not display stale patient rows', () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const render = (client) => renderToStaticMarkup(React.createElement(
    QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientsList)),
    ),
  ));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const loading = render(client);
  assert.match(loading, /animate-pulse/);
  assert.doesNotMatch(loading, /Fictional Patient/);
  client.setQueryData(['patients', 'directory', user.id, user.role, 1], {
    data: [], page: 1, hasNext: false,
  });
  const empty = render(client);
  assert.match(empty, /No patients registered/);
  assert.doesNotMatch(empty, /Fictional Patient/);
});

test('three clinical work queues render one page and expose page navigation', () => {
  const cases = [
    [DoctorHomeVisits, ['doctorHomeVisitRequests', 1], { id: 'visit-1', patient_name: 'Fictional Home Patient', reason: 'Fictional reason' }, /Assigned home visits pages/],
    [LaboratoryDashboard, ['laboratorianOrders', 1], { id: 'lab-1', patient_name: 'Fictional Laboratory Patient', mode: 'clinic_visit', status: 'approved_for_coordination', selected_tests: ['Synthetic test'], report_status: 'released' }, /Laboratory orders pages/],
    [AdminLabRequestsPanel, ['adminLabRequests', 1], { id: 'request-1', patient_name: 'Fictional Admin Patient', mode: 'clinic_visit', status: 'declined', selected_tests: ['Synthetic test'], report_status: 'not_started' }, /Admin laboratory requests pages/],
  ];
  for (const [Component, key, record, navPattern] of cases) {
    const user = { id: 'fictional-user' };
    const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
    client.setQueryData([key[0], user.id, key[1]], { data: [record], page: 1, hasNext: false });
    if (Component === AdminLabRequestsPanel) {
      client.setQueryData(['laboratorians', '', 1], { data: [], page: 1, hasNext: false });
    }
    const html = renderToStaticMarkup(React.createElement(
      QueryClientProvider, { client }, React.createElement(AuthContext.Provider, { value: { user } },
        React.createElement(Component)),
    ));
    assert.match(html, navPattern);
    assert.match(html, new RegExp(record.patient_name));
    assert.match(html, /1 on this page/);
    assert.match(html, /Next page/);
    if (Component === AdminLabRequestsPanel) assert.match(html, /Laboratory staff pages/);
  }
});

test('notifications use an independent unread count and current-page label', () => {
  const user = { id: 'fictional-user' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['notifications', user.id, 1], { data: [{
    id: 'fictional-notification', title: 'Fictional appointment notice',
    message: 'Synthetic message', notification_type: 'appointment', is_read: false,
  }], page: 1, hasNext: false });
  client.setQueryData(['notificationsUnreadCount'], { count: 1200 });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } }, React.createElement(Notifications))));
  assert.match(html, /Notifications pages/);
  assert.match(html, /1 on this page/);
  assert.match(html, /1200 unread/);
  assert.doesNotMatch(html, /1 total/);
});

test('patient laboratory requests and reports retain independent page controls', () => {
  const user = { id: 'fictional-patient' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['myLabRequests', user.id, 1], { data: [{
    id: 'fictional-request', status: 'declined', mode: 'clinic_visit',
    selected_tests: ['Synthetic test'], confirmation_message: 'Fictional request status',
  }] });
  client.setQueryData(['myReleasedLabReports', user.id, 1], { data: [{
    request_id: 'fictional-report', report_file_name: 'Fictional released report.pdf',
    selected_tests: ['Synthetic test'],
  }] });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientLaboratoryRequests)))));
  assert.match(html, /My laboratory requests pages/);
  assert.match(html, /My laboratory reports pages/);
  assert.match(html, /Fictional request status/);
  assert.match(html, /Fictional released report\.pdf/);
});

test('patient clinical reports render a bounded page with search and navigation', () => {
  const user = { id: 'fictional-patient' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['reports', user.id, '', 1], { data: [{
    id: 'fictional-report', title: 'Fictional assessment', category: 'assessment',
    date: '2026-11-01', description: 'Synthetic report description',
    therapist: 'Fictional clinician', content: { symptoms: '', findings: '', recommendations: '' },
    has_file: false,
  }] });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientReports)))));
  assert.match(html, /Patient reports pages/);
  assert.match(html, /Fictional assessment/);
  assert.match(html, /1 on page 1/);
  assert.match(html, /Search reports by title or type/);
});

test('patient appointment screens render bounded status pages without full-list counts', () => {
  const user = { id: 'fictional-patient', full_name: 'Fictional Patient' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['patientAppointments', user.id, 'upcoming', 1], { data: [], hasNext: false });
  client.setQueryData(['patient-appointments', user.id, 1], { data: [], hasNext: false });
  const render = (Page) => renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(Page)))));
  const history = render(PatientHistory);
  const appointments = render(PatientAppointments);
  assert.match(history, /upcoming appointments pages/);
  assert.match(history, /0 on this page/);
  assert.doesNotMatch(history, /0 total/);
  assert.match(appointments, /Patient appointments pages/);
  assert.match(appointments, /No upcoming appointments on this page/);
});

test('patient dashboard renders bounded latest-request summaries', () => {
  const user = { id: 'fictional-patient', full_name: 'Fictional Patient' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['patientAppointments', user.id, 'dashboard'], []);
  client.setQueryData(['myLabRequests', user.id, 'dashboard'], []);
  client.setQueryData(['myHomeVisitRequests', user.id, 'dashboard'], []);
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientDashboard)))));
  assert.match(html, /Good to see you, Fictional/);
  assert.match(html, /Your care at a glance/);
  assert.doesNotMatch(html, /Showing 1000/);
});

test('patient care plan history navigates independently of exact stage totals', () => {
  const user = { id: 'fictional-patient' };
  const plan = { id: 'fictional-plan', title: 'Fictional pathway', description: 'Synthetic plan',
    status: 'active', stages: [{ stage_id: 'stage-one', title: 'Stage one', status: 'active',
      progress: 0, description: 'Fictional stage' }], goals: [], recommendations: [] };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['carePlans'], [plan]);
  client.setQueryData(['carePlanHistory', user.id, plan.id, 1], { data: [], hasNext: false });
  client.setQueryData(['carePlanExerciseSummary', user.id, plan.id], [
    { stage_id: 'stage-one', prescribed: 1201, completed: 601 },
  ]);
  client.setQueryData(['adherenceStats', plan.id], {});
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientCarePlan)))));
  assert.match(html, /Care plan history pages/);
  assert.match(html, /Prescribed Exercises:.*1201/s);
  assert.match(html, /Completed assignments:.*601/s);
});

test('patient exercise lists expose independent page controls and use aggregate totals', () => {
  const user = { id: 'fictional-patient' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['catalogExercises', user.id, 'All', 1], { data: [], hasNext: false });
  client.setQueryData(['exerciseAssignments', user.id, 'All', 1], { data: [], hasNext: false });
  client.setQueryData(['patient-exercises-stats', user.id], { total: 1201, completed: 601,
    percentage: 50, recent_activity: [] });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientExercises)))));
  assert.match(html, /Prescribed exercises pages/);
  assert.match(html, /Reference exercises pages/);
  assert.match(html, /601 of 1201 completed/);
});

test('patient progress uses the selected care plan and aggregate stats without list accumulation', () => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['carePlans'], []);
  client.setQueryData(['exerciseAdherenceStats'], { total: 0, completed: 0, percentage: 100,
    log: [], exercise_breakdown: [], stage_breakdown: [], recent_activity: [] });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(MemoryRouter, null, React.createElement(PatientProgress))));
  assert.match(html, /Progress/);
  assert.doesNotMatch(html, /Showing 1000/);
});

test('admin billing renders one scoped page and independent reconciliation state', () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['capturedPaymentReviews'], { clinic_review: [] });
  client.setQueryData(['billingRecords', user.id, 1, '', '', ''], { data: [], hasNext: false });
  const html = renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(Billing)))));
  assert.match(html, /Billing records pages/);
  assert.match(html, /0 on this page/);
  assert.match(html, /Captured payment reconciliation/);
});

test('admin dashboard and alerts use aggregate day totals, not the recent page count', () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  client.setQueryData(['adminStats'], { total_patients: 0, new_patients: 0,
    total_doctors: 0, recorded_paid_total: 0, appointments_per_week: [],
    revenue_trend: [], doctor_specializations: [] });
  client.setQueryData(['adminDailyActivity'], { today_appointments: 1201,
    yesterday_appointments: 300, schedule_counts: { morning: 700, afternoon: 400, evening: 101 } });
  client.setQueryData(['appointments', 'admin-dashboard'], []);
  const render = (Page) => renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(Page)))));
  const dashboard = render(AdminDashboard);
  const alerts = render(AdminNotifications);
  assert.match(dashboard, /1201 scheduled today/);
  assert.match(dashboard, /700 appointments/);
  assert.match(alerts, /1201 appointments today/);
  assert.doesNotMatch(alerts, /patient_name/);
});

test('patient directory renders a recoverable error without stale patient rows', async () => {
  const user = { id: 'fictional-admin', role: 'admin' };
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false, refetchOnMount: false, retryOnMount: false },
  } });
  await assert.rejects(client.fetchQuery({
    queryKey: ['patients', 'directory', user.id, user.role, 1],
    queryFn: async () => { throw new Error('Fictional network failure'); },
  }));
  const html = renderToStaticMarkup(React.createElement(
    QueryClientProvider, { client },
    React.createElement(AuthContext.Provider, { value: { user } },
      React.createElement(MemoryRouter, null, React.createElement(PatientsList)),
    ),
  ));
  assert.match(html, /Could not load patient directory page 1/);
  assert.doesNotMatch(html, /Fictional Patient/);
});
