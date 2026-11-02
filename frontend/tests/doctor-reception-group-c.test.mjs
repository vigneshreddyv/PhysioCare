import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { after, before, test } from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import react from '@vitejs/plugin-react';
import { createLogger, createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
let vite;
let cacheDir;
let DoctorDashboard;
let DoctorPatientHistory;
let ReceptionistDashboard;

before(async () => {
  cacheDir = await mkdtemp(join(tmpdir(), 'physiocare-group-c-ui-'));
  vite = await createServer({ configFile: false, root, plugins: [react()], cacheDir,
    customLogger: createLogger('silent'), server: { middlewareMode: true, hmr: false },
    appType: 'custom' });
  ({ default: DoctorDashboard } = await vite.ssrLoadModule('/src/pages/doctor/DoctorDashboard.jsx'));
  ({ default: DoctorPatientHistory } = await vite.ssrLoadModule('/src/pages/doctor/DoctorPatientHistory.jsx'));
  ({ default: ReceptionistDashboard } = await vite.ssrLoadModule('/src/pages/receptionist/ReceptionistDashboard.jsx'));
});

after(async () => {
  await vite?.close();
  if (cacheDir) await rm(cacheDir, { recursive: true, force: true });
});

function renderScreen(component, client, path = '/') {
  return renderToStaticMarkup(React.createElement(QueryClientProvider, { client },
    React.createElement(MemoryRouter, { initialEntries: [path] },
      React.createElement(Routes, null,
        React.createElement(Route, { path: path.startsWith('/doctor/patients/') ? '/doctor/patients/:patientId' : '/', element: React.createElement(component) }),
      ))));
}

test('doctor dashboard renders aggregate totals independently of a bounded empty page', () => {
  const client = new QueryClient();
  client.setQueryData(['doctorDashboardSummary'], {
    open_visits: 1201, completed_sessions: 601, assigned_patients: 1001,
  });
  client.setQueryData(['doctorAppointments', 1, 'all', '', ''], { data: [], page: 1, hasNext: false });
  client.setQueryData(['doctorReleasedLabReports', 1], { data: [], page: 1, hasNext: false });
  const html = renderScreen(DoctorDashboard, client);
  assert.match(html, /Open Assigned Visits/);
  assert.match(html, /1,201|1201/);
  assert.match(html, /Assigned Patients/);
  assert.match(html, /Doctor agenda pages/);
  assert.match(html, /Doctor reports pages/);
  assert.match(html, /Agenda is clear/);
});

test('doctor patient history shows only the current patient page and page-local counts', () => {
  const client = new QueryClient();
  const patientId = 'fictional-patient-a';
  client.setQueryData(['doctorPatientHistory', patientId, 'all', 1, '', ''], {
    patient: { full_name: 'Fictional Patient A', date_of_birth: '2000-01-01', phone: null, gender: null },
    appointments: [], reports: [],
  });
  const html = renderScreen(DoctorPatientHistory, client, `/doctor/patients/${patientId}`);
  assert.match(html, /Fictional Patient A/);
  assert.match(html, /Visits on this page/);
  assert.match(html, /Doctor patient history pages/);
  assert.match(html, /History date filters/);
  assert.doesNotMatch(html, /Fictional Patient B/);
});

test('reception schedule renders database total and separate bounded queues', () => {
  const client = new QueryClient();
  client.setQueryData(['receptionSchedule', 1, '', ''], { data: [], page: 1, hasNext: false });
  client.setQueryData(['receptionScheduleSummary', '', ''], { active_appointments: 1201 });
  client.setQueryData(['receptionHomeVisitRequests', 1], { data: [], page: 1, hasNext: false });
  const html = renderScreen(ReceptionistDashboard, client);
  assert.match(html, /1201 active appointments/);
  assert.match(html, /Reception schedule pages/);
  assert.match(html, /Reception home-visit requests pages/);
  assert.match(html, /No active appointments/);
  assert.doesNotMatch(html, /clinical reason for fictional patient/i);
});

test('all three screens replace pages and keep patient-switch requests keyed and cancellable', async () => {
  const [dashboard, history, reception] = await Promise.all([
    readFile(join(root, 'src/pages/doctor/DoctorDashboard.jsx'), 'utf8'),
    readFile(join(root, 'src/pages/doctor/DoctorPatientHistory.jsx'), 'utf8'),
    readFile(join(root, 'src/pages/receptionist/ReceptionistDashboard.jsx'), 'utf8'),
  ]);
  assert.match(dashboard, /fetchClinicalPage\(`\/appointments\?\$\{agendaParams\}`, agendaPage\)/);
  assert.match(dashboard, /fetchClinicalPage\('\/lab-requests\/doctor\/reports', reportPage, 'request_id'\)/);
  assert.match(history, /queryKey: \['doctorPatientHistory', patientId, filter, page, startDate, endDate\]/);
  assert.match(history, /signal,/);
  assert.match(history, /activePatientRef\.current !== patientIdAtOpen/);
  assert.match(history, /gcTime: 0/);
  assert.match(reception, /fetchClinicalPage\(schedulePath, schedulePage\)/);
  assert.match(reception, /fetchClinicalPage\('\/home-visit-requests\/reception', requestPage\)/);
  assert.doesNotMatch(`${dashboard}\n${history}\n${reception}`, /fetchClinicalPages|fetchClinicalHistoryPages/);
});
