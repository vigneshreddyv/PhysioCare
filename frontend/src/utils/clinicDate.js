const CLINIC_TIMEZONE = 'Asia/Kolkata';

export function clinicDateKey(instant = new Date()) {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: CLINIC_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(instant);
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function calendarDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function isBeforeClinicToday(date) {
  return calendarDateKey(date) < clinicDateKey();
}

export function isOutsideBookingWindow(date, bookingWindow) {
  if (!bookingWindow) return true;
  const selectedKey = calendarDateKey(date);
  return selectedKey < bookingWindow.earliest_date || selectedKey > bookingWindow.latest_date;
}
