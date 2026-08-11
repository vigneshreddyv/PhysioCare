import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const availableSlots = [
  '08:00 AM',
  '09:00 AM',
  '10:00 AM',
  '11:00 AM',
  '12:00 PM',
  '02:00 PM',
  '03:00 PM',
  '04:00 PM',
  '05:00 PM',
];

function getAvailableDates() {
  const dates = [];

  for (let i = 1; i <= 14; i += 1) {
    const date = new Date();
    date.setDate(date.getDate() + i);

    dates.push(date);
  }

  return dates;
}

export default function LaboratoryDateTime() {
  const navigate = useNavigate();

  const [selectedDate, setSelectedDate] = useState('');
  const [selectedTime, setSelectedTime] = useState('');

  const selectedTests = useMemo(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem('selected_lab_tests') || '[]'
      );
    } catch {
      return [];
    }
  }, []);

  const total = Number(
    sessionStorage.getItem('selected_lab_tests_total') || 0
  );

  const visitType =
    sessionStorage.getItem('laboratory_visit_type') || 'home';

  const dates = useMemo(() => getAvailableDates(), []);

  const formatDate = (date) => {
    return date.toLocaleDateString('en-IN', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    });
  };

  const formatDateForStorage = (date) => {
    return date.toISOString().split('T')[0];
  };

  const handleContinue = () => {
    if (!selectedDate || !selectedTime) {
      return;
    }

    sessionStorage.setItem(
      'laboratory_selected_date',
      selectedDate
    );

    sessionStorage.setItem(
      'laboratory_selected_time',
      selectedTime
    );

    navigate('/patient/laboratory/review');
  };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">

        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-bold uppercase tracking-wide text-cyan-700">
            Laboratory Services
          </p>

          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Choose Date & Time 📅
          </h1>

          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Select a convenient date and time for your laboratory
            sample collection.
          </p>
        </div>

        {/* Progress */}
        <div className="mb-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <div>
                <p className="text-xs font-semibold text-slate-400">
                  STEP 1
                </p>

                <p className="text-sm font-bold text-slate-700">
                  Tests
                </p>
              </div>
            </div>

            <div className="mx-4 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                2
              </div>

              <div>
                <p className="text-xs font-semibold text-cyan-600">
                  STEP 2
                </p>

                <p className="text-sm font-bold text-slate-900">
                  Date & Time
                </p>
              </div>
            </div>

            <div className="mx-4 h-px flex-1 bg-slate-200" />

            <div className="hidden items-center gap-3 sm:flex">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-400">
                3
              </div>

              <p className="text-sm font-semibold text-slate-400">
                Review
              </p>
            </div>
          </div>
        </div>

        {/* Visit Type */}
        <div className="mb-6 rounded-3xl border border-cyan-100 bg-cyan-50 p-5">
          <div className="flex items-center gap-4">

            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-2xl shadow-sm">
              {visitType === 'clinic' ? '🏥' : '🏠'}
            </div>

            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
                Collection Method
              </p>

              <h2 className="mt-1 text-lg font-bold text-slate-900">
                {visitType === 'clinic'
                  ? 'Clinic Visit'
                  : 'Home Sample Collection'}
              </h2>

              <p className="mt-1 text-sm text-slate-600">
                {visitType === 'clinic'
                  ? 'Visit the clinic at your selected time.'
                  : 'Our lab assistant will visit your saved address.'}
              </p>
            </div>

          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">

          {/* Date and Time */}
          <div className="lg:col-span-2 space-y-6">

            {/* Date */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-5">
                <h2 className="text-xl font-bold text-slate-900">
                  Select a Date
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  Choose a date that works for you.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-5">
                {dates.map((date) => {
                  const value = formatDateForStorage(date);
                  const selected = selectedDate === value;

                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setSelectedDate(value);
                        setSelectedTime('');
                      }}
                      className={`rounded-2xl border p-4 text-center transition ${
                        selected
                          ? 'border-cyan-600 bg-cyan-600 text-white shadow-md'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-cyan-300 hover:bg-cyan-50'
                      }`}
                    >
                      <p className="text-xs font-semibold">
                        {date.toLocaleDateString('en-IN', {
                          weekday: 'short',
                        })}
                      </p>

                      <p className="mt-1 text-lg font-bold">
                        {date.getDate()}
                      </p>

                      <p className="text-xs">
                        {date.toLocaleDateString('en-IN', {
                          month: 'short',
                        })}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Time */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-5">
                <h2 className="text-xl font-bold text-slate-900">
                  Select a Time
                </h2>

                <p className="mt-1 text-sm text-slate-500">
                  {selectedDate
                    ? 'Choose an available time slot.'
                    : 'Select a date first.'}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
                {availableSlots.map((slot) => {
                  const selected = selectedTime === slot;

                  return (
                    <button
                      key={slot}
                      type="button"
                      disabled={!selectedDate}
                      onClick={() => setSelectedTime(slot)}
                      className={`rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
                        selected
                          ? 'border-cyan-600 bg-cyan-600 text-white'
                          : selectedDate
                            ? 'border-slate-200 bg-white text-slate-700 hover:border-cyan-300 hover:bg-cyan-50'
                            : 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300'
                      }`}
                    >
                      {slot}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Summary */}
          <div>
            <div className="sticky top-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">

              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-slate-900">
                  Booking Summary
                </h2>

                <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-bold text-cyan-700">
                  {selectedTests.length} tests
                </span>
              </div>

              <div className="mt-5 space-y-3">
                {selectedTests.map((test) => (
                  <div
                    key={test.id}
                    className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3"
                  >
                    <div>
                      <p className="text-sm font-semibold text-slate-700">
                        {test.name}
                      </p>

                      <p className="mt-1 text-xs text-slate-400">
                        {test.sample}
                      </p>
                    </div>

                    <p className="shrink-0 text-sm font-bold text-slate-700">
                      ₹{test.price}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-5 border-t border-slate-200 pt-5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-500">
                    Total
                  </span>

                  <span className="text-2xl font-bold text-cyan-700">
                    ₹{total}
                  </span>
                </div>
              </div>

              {selectedDate && selectedTime && (
                <div className="mt-5 rounded-2xl bg-emerald-50 p-4">
                  <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">
                    Selected Slot
                  </p>

                  <p className="mt-1 text-sm font-bold text-slate-800">
                    {new Date(`${selectedDate}T00:00:00`).toLocaleDateString(
                      'en-IN',
                      {
                        weekday: 'long',
                        day: 'numeric',
                        month: 'long',
                        year: 'numeric',
                      }
                    )}
                  </p>

                  <p className="mt-1 text-sm font-semibold text-emerald-700">
                    {selectedTime}
                  </p>
                </div>
              )}

              <button
                type="button"
                disabled={!selectedDate || !selectedTime}
                onClick={handleContinue}
                className="mt-6 w-full rounded-xl bg-cyan-600 px-5 py-3.5 text-sm font-bold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Continue to Review →
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/laboratory/tests')}
                className="mt-3 w-full rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-600 hover:bg-slate-50"
              >
                ← Change Tests
              </button>

            </div>
          </div>

        </div>
      </div>
    </div>
  );
}