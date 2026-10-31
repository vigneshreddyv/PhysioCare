export const staffRoles = [
  { value: 'doctor', label: 'Doctor' },
  { value: 'admin', label: 'Administrator' },
  { value: 'receptionist', label: 'Receptionist' },
  { value: 'laboratorian', label: 'Laboratory Staff' },
];

export const staffRoleLabels = Object.fromEntries(
  staffRoles.map(({ value, label }) => [value, label]),
);

export function getStaffCreateError(error) {
  const status = error?.response?.status;
  if (status === 400 || status === 409) return 'An account with this email address already exists.';
  if (status === 401 || status === 403) return 'Your Admin session is no longer authorized. Sign in again and retry.';
  if (status === 422) return 'Check the account details and choose a supported role.';
  return 'The staff account could not be created. Check your connection and try again.';
}

export function validateStaffForm({ full_name, email, password, confirm_password, role }) {
  const errors = {};
  const name = (full_name || '').trim();
  const address = (email || '').trim();

  if (name.length < 2) errors.full_name = 'Enter a name with at least 2 characters.';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(address)) errors.email = 'Enter a valid email address.';
  if ((password || '').length < 8) errors.password = 'Password must be at least 8 characters.';
  if (password !== confirm_password) errors.confirm_password = 'Passwords do not match.';
  if (!staffRoles.some((item) => item.value === role)) errors.role = 'Choose a supported staff role.';

  return errors;
}

export function filterStaff(staff, { query = '', role = 'all', status = 'all' } = {}) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return (staff || []).filter((person) => {
    const matchesQuery = !normalizedQuery
      || person.full_name.toLocaleLowerCase().includes(normalizedQuery)
      || person.email.toLocaleLowerCase().includes(normalizedQuery);
    const matchesRole = role === 'all' || person.role === role;
    const matchesStatus = status === 'all'
      || (status === 'active' ? person.is_active : !person.is_active);
    return matchesQuery && matchesRole && matchesStatus;
  });
}
