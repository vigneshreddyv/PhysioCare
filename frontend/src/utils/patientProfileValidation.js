export function validatePatientProfile(values) {
  const errors = {};
  const name = (values.full_name || '').trim();
  const phone = (values.phone || '').trim();
  const gender = (values.gender || '').trim();

  if (name.length < 2) errors.full_name = 'Enter a name with at least 2 characters.';
  else if (name.length > 100) errors.full_name = 'Name must be 100 characters or fewer.';

  if (phone) {
    if (phone.length > 24) errors.phone = 'Phone number must be 24 characters or fewer.';
    else if (!/^[+0-9()\- ]+$/.test(phone)) errors.phone = 'Use only digits, spaces, +, parentheses, or hyphens.';
    else {
      const digits = phone.replace(/\D/g, '').length;
      if (digits < 7 || digits > 15) errors.phone = 'Enter between 7 and 15 digits.';
    }
  }

  if (gender.length > 80) errors.gender = 'Gender must be 80 characters or fewer.';
  return errors;
}
