export function getHomeVisitReviewIssues({ form, selectedDoctor, availability, serviceCity = 'Nellore' }) {
  const issues = [];
  const noPreference = form.preferred_doctor_id === 'no_preference';

  if (!form.preferred_doctor_id) {
    issues.push('Choose a clinician or select no preference.');
  } else if (!noPreference && !selectedDoctor) {
    issues.push('The selected clinician is no longer available. Choose another clinician.');
  }

  if (!form.appointment_date) issues.push('Choose a visit date.');

  if (!form.time_slot) {
    issues.push('Choose an available visit time.');
  } else if (!availability) {
    issues.push('Wait for availability to load, then select an available time.');
  } else {
    const selectedSlot = availability.slots?.find((slot) => slot.time_slot === form.time_slot);
    if (!selectedSlot) {
      issues.push('This time is no longer listed. Refresh availability and choose another time.');
    } else if (!selectedSlot.available) {
      issues.push('This time is no longer available. Choose another time.');
    }
  }

  if ((form.home_address || '').trim().length < 10) {
    issues.push('Enter a full visit address of at least 10 characters; include house/building, street or locality, and landmark where possible.');
  }
  const allowedCity = (serviceCity || 'Nellore').trim();
  if ((form.city || '').trim().toLocaleLowerCase() !== allowedCity.toLocaleLowerCase()) {
    issues.push(`Home visits are currently available only in ${allowedCity}.`);
  }
  if (!form.body_regions?.length) issues.push('Choose at least one body area.');
  if (!form.symptoms?.length) issues.push('Choose at least one symptom.');
  if (!Number.isInteger(Number(form.duration_days)) || Number(form.duration_days) < 1 || Number(form.duration_days) > 3650) {
    issues.push('Enter a visit duration from 1 to 3650 days.');
  }
  return issues;
}
