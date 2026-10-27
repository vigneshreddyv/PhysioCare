import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import api from '../src/services/api';
import ClinicianSchedules from '../src/pages/admin/ClinicianSchedules';
import '../src/index.css';

const state = new URLSearchParams(window.location.search).get('state') || 'draft';
const doctorId = 'fictional-clinician-schedule';
const response = (config, data) => ({ data, status: 200, statusText: 'OK', headers: {}, config });
const dateISO = (offset) => {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
};
const previewDate = dateISO(2);
const previewDay = (() => { const day = new Date(`${previewDate}T12:00:00Z`).getUTCDay(); return day === 0 ? 6 : day - 1; })();

const schedule = {
  doctor_id: doctorId,
  doctor_name: 'Dr Arjun Mehta',
  timezone: 'Asia/Kolkata',
  slot_minutes: 30,
  status: 'draft_changes',
  draft_revision: 4,
  published_revision: 3,
  published_at: new Date(Date.now() - 86400000).toISOString(),
  weekly_blocks: [
    { day_of_week: previewDay, service_mode: 'clinic', start_time: '09:00', end_time: '12:00' },
    { day_of_week: previewDay, service_mode: 'home_visit', start_time: '14:00', end_time: '17:00' },
    { day_of_week: (previewDay + 2) % 7, service_mode: 'clinic', start_time: '10:00', end_time: '15:00' },
  ],
  date_exceptions: [
    { date: dateISO(6), blocks: [] },
    { date: dateISO(9), blocks: [{ day_of_week: (previewDay + 2) % 7, service_mode: 'clinic', start_time: '11:00', end_time: '13:00' }] },
  ],
  published_weekly_blocks: [
    { day_of_week: previewDay, service_mode: 'clinic', start_time: '09:00', end_time: '12:00' },
    { day_of_week: previewDay, service_mode: 'home_visit', start_time: '14:00', end_time: '17:00' },
  ],
  published_date_exceptions: [],
  audit_history: [
    { action: 'published', revision: 3, occurred_at: new Date(Date.now() - 86400000).toISOString() },
    { action: 'draft_saved', revision: 4, occurred_at: new Date(Date.now() - 3600000).toISOString() },
  ],
};

api.defaults.adapter = async (config) => {
  if (config.method !== 'get') {
    return Promise.reject({ response: { status: 409, data: { detail: state === 'conflict' ? 'This draft excludes one existing appointment slot. Adjust the schedule before publishing.' : 'Preview changes are disabled.' } } });
  }
  if (config.url === `/clinician-schedules/admin/${doctorId}`) {
    if (state === 'error') return Promise.reject({ response: { status: 503, data: { detail: 'Fictional preview error.' } } });
    if (state === 'empty') return response(config, { ...schedule, status: 'unconfigured', draft_revision: 0, published_revision: null, weekly_blocks: [], date_exceptions: [], published_weekly_blocks: [], published_date_exceptions: [], audit_history: [] });
    return response(config, schedule);
  }
  if (config.url === '/appointments/booking-window') {
    return response(config, { clinic_timezone: 'Asia/Kolkata', earliest_date: dateISO(0), latest_date: dateISO(29), horizon_days: 30 });
  }
  if (config.url === `/clinician-schedules/admin/${doctorId}/preview`) {
    const mode = config.params?.service_mode || 'clinic';
    const times = mode === 'home_visit' ? ['02:00 PM', '02:30 PM', '03:00 PM', '03:30 PM'] : ['09:00 AM', '09:30 AM', '10:00 AM', '10:30 AM', '11:00 AM', '11:30 AM'];
    return response(config, {
      doctor_id: doctorId,
      appointment_date: config.params?.appointment_date || previewDate,
      clinic_timezone: 'Asia/Kolkata',
      demo_configuration: true,
      configuration_label: 'Fictional draft preview',
      slot_minutes: 30,
      window_start: times[0],
      window_end: times.at(-1),
      slots: times.map((time, index) => ({ time_slot: time, available: index !== 2, availability_state: index === 2 ? 'occupied' : 'available' })),
    });
  }
  return Promise.reject({ response: { status: 404, data: { detail: 'Preview route not configured.' } } });
};

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } });
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/admin/schedules/${doctorId}`]}>
        <main className="portal-layout min-h-screen bg-background p-4 md:p-8">
          <Routes>
            <Route path="/admin/schedules/:doctorId" element={<ClinicianSchedules />} />
          </Routes>
        </main>
      </MemoryRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
