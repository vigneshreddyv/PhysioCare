import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  filterStaff,
  getStaffCreateError,
  staffRoles,
  validateStaffForm,
} from '../src/utils/staffManagement.js';

const source = async (relativePath) => readFile(new URL(`../${relativePath}`, import.meta.url), 'utf8');

const staff = [
  { id: '1', full_name: 'Alex Lab', email: 'alex@example.com', role: 'laboratorian', is_active: true },
  { id: '2', full_name: 'Rae Doctor', email: 'rae@example.com', role: 'doctor', is_active: false },
  { id: '3', full_name: 'Sam Reception', email: 'sam@example.com', role: 'receptionist', is_active: true },
];

test('staff form validation requires name, valid email, supported role, and matching eight-character password', () => {
  assert.deepEqual(validateStaffForm({
    full_name: ' ',
    email: 'bad',
    password: 'short',
    confirm_password: 'different',
    role: 'patient',
  }), {
    full_name: 'Enter a name with at least 2 characters.',
    email: 'Enter a valid email address.',
    password: 'Password must be at least 8 characters.',
    confirm_password: 'Passwords do not match.',
    role: 'Choose a supported staff role.',
  });

  assert.deepEqual(validateStaffForm({
    full_name: ' Fictional Staff ',
    email: 'staff@example.com',
    password: 'safe-demo-password',
    confirm_password: 'safe-demo-password',
    role: 'laboratorian',
  }), {});
});

test('staff search and role/status filters can be combined', () => {
  assert.deepEqual(filterStaff(staff, { query: 'ALEX', role: 'laboratorian', status: 'active' }), [staff[0]]);
  assert.deepEqual(filterStaff(staff, { query: 'rae@example', role: 'doctor', status: 'inactive' }), [staff[1]]);
  assert.deepEqual(filterStaff(staff, { query: 'lab', status: 'inactive' }), []);
});

test('all backend-supported staff roles including Laboratory Staff are available', () => {
  assert.deepEqual(staffRoles.map(({ value }) => value), [
    'doctor',
    'admin',
    'receptionist',
    'laboratorian',
  ]);
});

test('staff creation errors are displayed safely without echoing server details', () => {
  assert.equal(getStaffCreateError({ response: { status: 400, data: { detail: 'duplicate' } } }), 'An account with this email address already exists.');
  assert.equal(getStaffCreateError({ response: { status: 403, data: { detail: 'private server detail' } } }), 'Your Admin session is no longer authorized. Sign in again and retry.');
  assert.equal(getStaffCreateError({ response: { status: 422 } }), 'Check the account details and choose a supported role.');
  assert.equal(getStaffCreateError({ message: 'network failure' }), 'The staff account could not be created. Check your connection and try again.');
});

test('staff management route is nested under the Admin-only protected route', async () => {
  const [appSource, sidebarSource, pageSource] = await Promise.all([
    source('src/App.jsx'),
    source('src/components/common/Sidebar.jsx'),
    source('src/pages/admin/StaffManagement.jsx'),
  ]);

  assert.match(appSource, /StaffManagement = lazy\(\(\) => import\('\.\/pages\/admin\/StaffManagement'\)\)/);
  assert.match(appSource, /allowedRoles=\{\['admin'\]\}[\s\S]*?<Route path="staff" element=\{<StaffManagement \/>} \/>/);
  assert.match(sidebarSource, /path: '\/admin\/staff', label: 'Staff Management'/);
  assert.match(pageSource, /api\.get\('\/users\/staff'\)/);
  assert.match(pageSource, /api\.post\('\/users\/staff', payload\)/);
  assert.match(pageSource, /disabled=\{createStaff\.isPending\}/);
  assert.match(pageSource, /queryClient\.invalidateQueries\(\{ queryKey: \['staff'\] \}\)/);
  assert.match(pageSource, /role="alert"/);
  assert.match(pageSource, /Account status/);
  assert.doesNotMatch(pageSource, /hashed_password/);
});
