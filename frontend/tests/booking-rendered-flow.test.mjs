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
const bookingWindow = { earliest_date: '2040-04-12', latest_date: '2040-05-11', horizon_days: 30 };
let vite;
let cacheDir;
let BookAppointment;
let HomeVisitRequests;
let AuthContext;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-booking-render-'));
  vite = await createServer({
    configFile: false,
    root,
    plugins: [react()],
    cacheDir,
    customLogger: createLogger('silent'),
    server: { middlewareMode: true, hmr: false },
    appType: 'custom',
  });
  [{ default: BookAppointment }, { default: HomeVisitRequests }] = await Promise.all([
    vite.ssrLoadModule('/src/pages/patient/BookAppointment.jsx'),
    vite.ssrLoadModule('/src/pages/patient/HomeVisitRequests.jsx'),
  ]);
  ({ AuthContext } = await vite.ssrLoadModule('/src/context/AuthContext.jsx'));
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

function renderPage(Page, data) {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  for (const [key, value] of Object.entries(data)) {
    if (key === 'bookingDoctors') client.setQueryData([key, '', 1], { data: value, page: 1, hasNext: false });
    else if (key === 'homeVisitDoctors') client.setQueryData([key, '', 1], { data: value, page: 1, hasNext: false });
    else client.setQueryData([key], value);
  }
  if (Page === HomeVisitRequests) {
    client.setQueryData(['myHomeVisitRequests', 'fictional-patient', 1], { data: [], page: 1, hasNext: false });
    client.setQueryData(['patientHomeBookings', 'fictional-patient', 1], { data: data.patientAppointments || [], page: 1, hasNext: false });
  }
  return renderToStaticMarkup(React.createElement(
    QueryClientProvider,
    { client },
    React.createElement(AuthContext.Provider, { value: { user: { id: 'fictional-patient' } } },
      React.createElement(MemoryRouter, null, React.createElement(Page))),
  ));
}

function renderClinic(doctors) {
  return renderPage(BookAppointment, { bookingDoctors: doctors, bookingWindow });
}

function renderHomeVisit(entitlement, appointments = []) {
  return renderPage(HomeVisitRequests, {
    demoHomeVisitEntitlement: entitlement,
    homeVisitContext: { coverage_city: 'Nellore' },
    homeVisitDoctors: [],
    myHomeVisitRequests: [],
    patientAppointments: appointments,
    bookingWindow,
  });
}

test('clinic booking shows a fictional clinician while later steps remain unavailable', () => {
  const html = renderClinic([{ id: 'fictional-clinician', full_name: 'Dr. Fictional', specialization: 'Physiotherapy' }]);

  assert.match(html, /Select a specialist/);
  assert.match(html, /Dr\. Fictional/);
  assert.match(html, /1 shown/);
  for (const [number, label] of [[2, 'Date'], [3, 'Time'], [4, 'Review'], [5, 'Payment']]) {
    assert.match(html, new RegExp(`<button type="button" disabled=""><span>${number}</span>${label}</button>`));
  }
});

test('clinic booking with no clinician does not suggest an appointment was requested', () => {
  const html = renderClinic([]);

  assert.match(html, /No specialists are available to book right now/);
  assert.match(html, /No appointment request has been sent/);
  assert.doesNotMatch(html, /Dr\. Fictional/);
});

test('payment resume requests only the authorized appointment ID', async () => {
  const source = await readFile(new URL('../src/pages/patient/BookAppointment.jsx', import.meta.url), 'utf8');
  assert.match(source, /api\.get\(`\/appointments\/\$\{encodeURIComponent\(paymentAppointmentId\)\}`\)/);
  assert.match(source, /appointment\.id !== paymentAppointmentId/);
  assert.match(source, /fetchClinicalPage\([\s\S]*?\/users\/public\/doctors\?search=/);
  assert.match(source, /<ClinicalPageNav label="Booking clinicians"/);
  assert.doesNotMatch(source, /fetchClinicalPages\('\/appointments'\)/);
});

test('home-visit form blocks confirmation until required visit details are complete', () => {
  const html = renderHomeVisit({ active: true, requests_enabled: true });

  assert.match(html, /Choose a home-visit slot/);
  assert.match(html, /See what is needed to confirm/);
  assert.match(html, /Home-visit fees and online payment are not configured/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Confirm home visit<\/button>/);
});

test('home-visit access denial renders recovery without a booking form', () => {
  const html = renderHomeVisit({ active: false, requests_enabled: true });

  assert.match(html, /Home-visit access is not enabled/);
  assert.match(html, /Check access again/);
  assert.doesNotMatch(html, /Confirm home visit<\/button>/);
});

test('an existing home visit with unconfigured fees is not shown as paid', () => {
  const html = renderHomeVisit({ active: true, requests_enabled: true }, [{
    id: 'fictional-home-visit',
    service_mode: 'home_visit',
    status: 'scheduled',
    doctor_assignment_pending: true,
    appointment_date: '2040-04-12',
    time_slot: '10:00 AM',
    city: 'Nellore',
    billing_status: 'unconfigured',
  }]);

  assert.match(html, /Clinician assignment pending/);
  assert.match(html, /Fee and online payment not configured; the clinic will confirm/);
  assert.doesNotMatch(html, /<strong>Paid<\/strong>/);
});

test('home-visit bookings and requests use separate bounded page navigation', () => {
  const html = renderHomeVisit({ active: true, requests_enabled: true });
  assert.match(html, /Home-visit clinicians pages/);
  assert.match(html, /Home-visit appointments pages/);
  assert.match(html, /Earlier home-visit requests pages/);
  assert.match(html, /Showing 0 on page 1/);
});
