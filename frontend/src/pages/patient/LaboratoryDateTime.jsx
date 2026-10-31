import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getState, setState } from './laboratoryStorageUtils';
import { ArrowRight, Building2, Home } from 'lucide-react';

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

  // Initialize selectedDate and selectedTime from storage on mount
  useEffect(() => {
    const state = getState();
    if (state) {
      if (state.selectedDate) setSelectedDate(state.selectedDate);
      if (state.selectedTime) setSelectedTime(state.selectedTime);
    }
  }, []);

  // Persist selectedDate and selectedTime to storage whenever they change
  useEffect(() => {
    setState({ selectedDate, selectedTime });
  }, [selectedDate, selectedTime]);

  const state = getState() || {};
  const visitType = state.visitType || 'home';

  const dates = useMemo(() => getAvailableDates(), []);

  const formatDateForStorage = (date) => {
    return date.toISOString().split('T')[0];
  };

  const handleContinue = () => {
    if (!selectedDate || !selectedTime) {
      return;
    }

    navigate('/patient/laboratory/review');
  };

  return (
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#183B4A] sm:text-4xl">
            Choose Date & Time
          </h1>

          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Select a convenient date and time for your laboratory
            sample collection.
          </p>
        </div>

        {/* Progress */}
        <div className="mb-8 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <span className="w-4 h-4" stroke="currentColor" fill="none">
                  <line x1="3" y1="12" x2="7" y2="16" strokeWidth="2"></line>
                  <line x1="7" y1="16" x2="13" y2="10" strokeWidth="2"></line>
                </span>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 1
                </p>

                <p className="text-sm font-semibold text-[#183B4A]">
                  Tests
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <span className="w-4 h-4" stroke="currentColor" fill="none">
                  <line x1="3" y1="5" x2="7" y2="9" strokeWidth="2"></line>
                  <line x1="7" y1="9" x2="13" y2="3" strokeWidth="2"></line>
                </span>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 2
                </p>

                <p className="text-sm font-semibold text-[#183B4A]">
                  Date & Time
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="hidden items-center gap-3 sm:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <span className="w-4 h-4" stroke="currentColor" fill="none">
                  <line x1="3" y1="5" x2="7" y2="9" strokeWidth="2"></line>
                  <line x1="7" y1="9" x2="13" y2="3" strokeWidth="2"></line>
                </span>
              </div>

              <p className="text-sm font-semibold text-[#60716E]">
                Review
              </p>
            </div>
          </div>
        </div>

        {/* Visit Type */}
        <div className="mb-6 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
          <div className="flex items-center gap-4">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#DDEFEA]">
              {visitType === 'clinic' ? (
                <Building2 className="w-5 h-5 text-[#0F6B63]" />
              ) : (
                <Home className="w-5 h-5 text-[#0F6B63]" />
              )}
            </div>

            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                Collection Method
              </p>

              <h2 className="mt-1 text-lg font-bold text-[#183B4A]">
                {visitType === 'clinic'
                  ? 'Clinic Visit'
                  : 'Home Sample Collection'}
              </h2>

              <p className="mt-1 text-sm text-[#60716E]">
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
            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
              <div className="mb-3">
                <h2 className="text-xl font-bold text-[#183B4A]">
                  Select a Date
                </h2>

                <p className="mt-1 text-sm text-[#60716E]">
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
                      className={`w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-3 text-left transition-all duration-200 ${
                        selected
                          ? 'border-[#0F6B63] bg-[#DDEFEA]/50'
                          : 'hover:bg-[#F7F4ED]/70'
                      }`}
                    >
                      <div className="flex flex-col items-start gap-1">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                          {date.toLocaleDateString('en-IN', {
                            weekday: 'short',
                          })}
                        </p>

                        <p className="mt-1 text-lg font-bold text-[#183B4A]">
                          {date.getDate()}
                        </p>

                        <p className="text-xs text-[#60716E]">
                          {date.toLocaleDateString('en-IN', {
                            month: 'short',
                          })}
                        </p>
                      </div>

                      {selected && (
                        <div className="absolute inset-0 pointer-events-none rounded-xl border-[#0F6B63] bg-[#0F6B63]/10" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Time */}
            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
              <div className="mb-3">
                <h2 className="text-xl font-bold text-[#183B4A]">
                  Select a Time
                </h2>

                <p className="mt-1 text-sm text-[#60716E]">
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
                      className={`w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-3 text-center transition-all duration-200 ${
                        selected
                          ? 'border-[#0F6B63] bg-[#DDEFEA]/50'
                          : 'hover:bg-[#F7F4ED]/70'
                      }`}
                    >
                      {slot}
                      {selected && (
                        <div className="absolute inset-0 pointer-events-none rounded-xl border-[#0F6B63] bg-[#0F6B63]/10" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Summary */}
          <div>
            <div className="sticky top-4 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-3">

              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-[#183B4A]">
                  Booking Summary
                </h2>

                {state.selectedTests && state.selectedTests.length > 0 && (
                  <span className="rounded-full bg-[#DDEFEA] px-2 py-1 text-xs font-semibold text-[#183B4A]">
                    {state.selectedTests.length} test
                    {state.selectedTests.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              {state.selectedTests && state.selectedTests.length > 0 && (
                <div className="mt-3 space-y-2">
                  {state.selectedTests.map((test) => (
                    <div
                      key={test.id}
                      className="flex items-start justify-between gap-2 border-t border-[#E5E0D6]/50 pt-2 pb-1"
                    >
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-[#183B4A]">
                          {test.name}
                        </p>

                        <p className="mt-1 text-xs text-[#60716E]">
                          {test.sample}
                        </p>
                      </div>

                      <p className="shrink-0 text-sm font-bold text-[#183B4A]">
                        ₹{test.price}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-3 border-t border-[#E5E0D6]/50 pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-[#60716E]">
                    Total
                  </span>

                  <span className="text-xl font-bold text-[#0F6B63]">
                    {(((state || {}).selectedTests || []).reduce((sum, test) => sum + Number(test.price || 0), 0))}
                  </span>
                </div>
              </div>

              {selectedDate && selectedTime && (
                <div className="mt-3 rounded-xl border border-[#E5E0D6]/50 bg-[#DDEFEA]/50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Selected Slot
                  </p>

                  <p className="mt-1 text-sm font-bold text-[#183B4A]">
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

                  <p className="mt-1 text-sm font-semibold text-[#0F6B63]">
                    {selectedTime}
                  </p>
                </div>
              )}

              <button
                type="button"
                disabled={!selectedDate || !selectedTime}
                onClick={handleContinue}
                className="mt-4 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#0F6B63] transition hover:bg-[#F7F4ED]/70 disabled:cursor-not-allowed disabled:bg-[#F7F4ED]/30"
              >
                Continue to Review →
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => navigate('/patient/laboratory/tests')}
                className="mt-2 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-2 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
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