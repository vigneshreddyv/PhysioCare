import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
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
let DoctorsList;
let fetchClinicalPage;
let cancelClinicalPageRequests;
let pageSize;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-admin-clinicians-'));
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
  ({
    fetchClinicalPage,
    cancelClinicalPageRequests,
    CLINICAL_PAGE_SIZE: pageSize,
  } = await vite.ssrLoadModule('/src/services/clinicalPagination.js'));
  ({ default: DoctorsList } = await vite.ssrLoadModule('/src/pages/admin/DoctorsList.jsx'));
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

async function withApiGet(handler, run) {
  const original = api.get;
  api.get = handler;
  try {
    return await run();
  } finally {
    api.get = original;
  }
}

function renderDirectory(client) {
  return renderToStaticMarkup(React.createElement(
    QueryClientProvider,
    { client },
    React.createElement(MemoryRouter, null, React.createElement(DoctorsList)),
  ));
}

function clinician(index) {
  return {
    id: `clinician-${index}`,
    full_name: `Fictional Clinician ${index}`,
    email: `clinician${index}@example.invalid`,
    specialization: 'Fictional rehabilitation',
    specialties: [],
    is_active_today: true,
    accepts_home_visits: true,
  };
}

test('admin directory fetches one searchable page beyond the former browser limit', async () => {
  const calls = [];
  const result = await withApiGet(async (path, { params }) => {
    calls.push([path, params]);
    return { data: Array.from({ length: pageSize }, (_, index) => clinician(1200 + index)) };
  }, () => fetchClinicalPage('/users/doctors?search=rehabilitation', 25));

  assert.deepEqual(calls, [[
    '/users/doctors?search=rehabilitation', { page: 25, page_size: pageSize },
  ]]);
  assert.equal(result.data.length, pageSize);
  assert.equal(result.data[0].id, 'clinician-1200');
  assert.equal(result.hasNext, true);
});

test('identical directory requests are shared and logout rejects stale results', async () => {
  let calls = 0;
  let resolve;
  let signal;
  await withApiGet(async (_path, options) => {
    calls += 1;
    signal = options.signal;
    return new Promise((done) => { resolve = done; });
  }, async () => {
    const first = fetchClinicalPage('/users/doctors?search=fictional', 2);
    const duplicate = fetchClinicalPage('/users/doctors?search=fictional', 2);
    assert.strictEqual(first, duplicate);
    assert.equal(calls, 1);
    cancelClinicalPageRequests();
    assert.equal(signal.aborted, true);
    resolve({ data: [clinician(51)] });
    await assert.rejects(first, /cancelled/);
  });
});

test('an older search response cannot replace a newer search result', async () => {
  const pending = new Map();
  await withApiGet(async (path) => new Promise((resolve) => pending.set(path, resolve)), async () => {
    const older = fetchClinicalPage('/users/doctors?search=older', 1);
    const newer = fetchClinicalPage('/users/doctors?search=newer', 1);
    pending.get('/users/doctors?search=newer')({ data: [clinician(2)] });
    pending.get('/users/doctors?search=older')({ data: [clinician(1)] });
    assert.equal((await newer).data[0].id, 'clinician-2');
    assert.equal((await older).data[0].id, 'clinician-1');
  });
});

test('admin directory renders only the current bounded page and navigation', () => {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  client.setQueryData(['doctors', 'directory', '', 1], {
    data: Array.from({ length: pageSize }, (_, index) => clinician(index)),
    page: 1,
    hasNext: true,
  });

  const html = renderDirectory(client);
  assert.match(html, /Search clinician directory/);
  assert.match(html, /Clinician directory pages/);
  assert.match(html, /50 practitioners on this page/);
  assert.match(html, /Fictional Clinician 49/);
  assert.doesNotMatch(html, /Fictional Clinician 50/);
  assert.match(html, /Edit profile/);
  assert.match(html, /Manage schedule/);
});

test('admin directory preserves loading, empty, and recoverable error states', async () => {
  const loadingClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const loading = renderDirectory(loadingClient);
  assert.match(loading, /animate-pulse/);
  assert.doesNotMatch(loading, /Fictional Clinician/);

  const emptyClient = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  emptyClient.setQueryData(['doctors', 'directory', '', 1], {
    data: [], page: 1, hasNext: false,
  });
  const empty = renderDirectory(emptyClient);
  assert.match(empty, /No doctors added/);
  assert.match(empty, /Clinician directory pages/);

  const errorClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  await assert.rejects(errorClient.fetchQuery({
    queryKey: ['doctors', 'directory', '', 1],
    queryFn: async () => { throw new Error('Synthetic directory failure'); },
    retry: false,
  }), /Synthetic directory failure/);
  const error = renderDirectory(errorClient);
  assert.match(error, /Could not load medical staff records/);
  assert.match(error, /Try Again/);
});

test('component contract resets page on search and retains an editing snapshot', async () => {
  const source = await readFile(join(root, 'src/pages/admin/DoctorsList.jsx'), 'utf8');
  assert.match(source, /useDeferredValue\(search\)/);
  assert.match(source, /fetchClinicalPage\(queryPath, page\)/);
  assert.match(source, /queryKey: \['doctors', 'directory', deferredSearch, page\]/);
  assert.match(source, /setSearch\(event\.target\.value\); setPage\(1\)/);
  assert.match(source, /const doctors = searchSettled \? directory\.data\?\.data \|\| \[\] : \[\]/);
  assert.match(source, /gcTime: 0/);
  assert.match(source, /editingDoctor &&/);
  assert.match(source, /api\.patch\(`\/users\/doctors\/\$\{doctorId\}`/);
  assert.doesNotMatch(source, /api\.get\('\/users\/doctors'\)/);
});

test('public registration policy remains intentionally unresolved and visible in source', async () => {
  const register = await readFile(join(root, 'src/pages/common/Register.jsx'), 'utf8');
  assert.match(register, /password: z\.string\(\)\.min\(8, 'Use at least 8 characters'\)/);
  assert.match(register, /autoComplete="new-password"/);
});
