import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = async (path) => readFile(new URL(`../${path}`, import.meta.url), 'utf8');

test('unsupported administrator patient creation has no active route or launch control', async () => {
  const [app, header, actions] = await Promise.all([
    source('src/App.jsx'),
    source('src/pages/admin/dashboard/DashboardHeader.jsx'),
    source('src/pages/admin/dashboard/QuickActions.jsx'),
  ]);
  assert.doesNotMatch(app, /PatientsCreate|patients-create/);
  assert.doesNotMatch(header, /patients-create|New Patient/);
  assert.doesNotMatch(actions, /patients-create|Register New Patient/);
  assert.match(actions, /View Patient Directory/);
});

test('care plan writes submit the revision loaded by the editor', async () => {
  const carePlan = await source('src/pages/admin/CarePlanManagement.jsx');
  assert.match(carePlan, /expected_revision:\s*selectedCarePlan\.revision/g);
  assert.match(carePlan, /status === 409/);
  assert.match(carePlan, /review your unsaved inputs before retrying/);
});

test('exercise assignment and progress writes carry assignment revisions', async () => {
  const [management, patient] = await Promise.all([
    source('src/pages/admin/ExerciseAssignmentManagement.jsx'),
    source('src/pages/patient/PatientExercises.jsx'),
  ]);
  assert.match(management, /expected_revision:\s*editRevision/);
  assert.match(management, /status === 409/);
  assert.match(patient, /revision:\s*assign\.revision \|\| 0/);
  assert.match(patient, /expected_assignment_revision:\s*ex\.revision/);
  assert.match(patient, /status === 409/);
});

test('appointment cards preserve revision through each status mutation', async () => {
  const [card, admin, doctor] = await Promise.all([
    source('src/components/features/AppointmentCard.jsx'),
    source('src/pages/admin/AdminDashboard.jsx'),
    source('src/pages/doctor/DoctorDashboard.jsx'),
  ]);
  assert.match(card, /onStatusChange\(id, 'in_progress', revision\)/);
  assert.match(card, /onStatusChange\(id, 'completed', revision\)/);
  assert.match(card, /onStatusChange\(id, 'cancelled', revision\)/);
  assert.match(admin, /expected_revision:\s*revision/);
  assert.match(admin, /status === 409/);
  assert.match(doctor, /expected_revision:\s*revision/);
  assert.match(doctor, /status === 409/);
});
