import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getState } from './laboratoryStorageUtils';
import { CheckCircle2, ArrowRight } from 'lucide-react';

export default function LaboratorySuccess() {
  const navigate = useNavigate();
  const location = useLocation();

  // Prefer route state (passed from payment) if available, else fallback to storage
  const routeState = location.state || {};
  const storageState = getState() || {};

  // Merge: routeState overrides storageState for safety
  const state = { ...storageState, ...routeState };

  // Extract values from state with fallbacks
  const selectedTests = Array.isArray(state.selectedTests) ? state.selectedTests : [];
  const visitType = state.visitType || 'home';
  const selectedDate = state.selectedDate || '';
  const selectedTime = state.selectedTime || '';
  const savedAddress = state.savedAddress || '';

  // Helper to format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    const parsed = new Date(dateStr);
    if (Number.isNaN(parsed.getTime())) return dateStr;
    return parsed.toLocaleDateString('en-IN', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  // Helper to format time (assuming HH:MM format)
  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    return timeStr; // already in HH:MM format from the picker
  };

  return (
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#DDEFEA] text-[#0F6B63] mx-auto mb-6">
            <CheckCircle2 className="w-5 h-5" />
          </div>

          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#183B4A] sm:text-4xl">
            Your laboratory booking is confirmed
          </h1>

          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Your payment was successful and your booking is complete.
          </p>
        </div>

        {/* Summary Section - show if we have meaningful data from route state or storage */}
        {Object.keys(state).length > 0 && (
          <div className="space-y-8">
            {/* Tests - only if we have test data */}
            {selectedTests.length > 0 && (
              <div>
                <h2 className="mb-5 text-2xl font-bold text-[#183B4A]">
                  Your Tests
                </h2>
                <div className="space-y-3">
                  {selectedTests.map((test, index) => (
                    <div key={test.id || index} className="flex items-start justify-between gap-4 border-t border-[#E5E0D6]/50 pt-3 pb-2">
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-[#183B4A]">
                          {index + 1}. {test.name}
                        </p>
                        <p className="mt-1 text-sm text-[#60716E]">
                          {test.sample}
                        </p>
                      </div>
                      <p className="shrink-0 text-sm font-bold text-[#0F6B63]">
                        ₹{Number(test.price || 0).toLocaleString('en-IN')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Visit Info - only if we have visit details */}
            {(selectedDate || selectedTime || visitType || savedAddress || state.bookingId) && (
              <div>
                <h2 className="mb-5 text-2xl font-bold text-[#183B4A]">
                  Booking Details
                </h2>
                {state.bookingId && (
                  <div className="mb-5 p-4 rounded-2xl border border-[#E5E0D6]/50 bg-white">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                      Booking Reference ID
                    </p>
                    <p className="mt-1 font-mono text-sm font-bold text-[#183B4A]">
                      {state.bookingId}
                    </p>
                  </div>
                )}
                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                      Collection Method
                    </p>
                    <p className="mt-2 text-lg font-bold text-[#183B4A]">
                      {visitType === 'clinic' ? 'Clinic Visit' : 'Home Sample Collection'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                      Appointment Date
                    </p>
                    <p className="mt-2 text-lg font-bold text-[#183B4A]">
                      {selectedDate ? formatDate(selectedDate) : 'Not selected'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                      Appointment Time
                    </p>
                    <p className="mt-2 text-lg font-bold text-[#183B4A]">
                      {selectedTime ? formatTime(selectedTime) : 'Not selected'}
                    </p>
                  </div>
                  {visitType === 'home' && savedAddress && (
                    <div className="col-span-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                        Home Address
                      </p>
                      <p className="mt-2 text-sm leading-6 text-[#60716E] break-words">
                        {savedAddress}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div className="mt-8">
          <div className="space-y-4">
            <button
              onClick={() => navigate('/patient/dashboard', { replace: true })}
              disabled={false}
              className="w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#0F6B63] transition hover:bg-[#F7F4ED]/70 flex items-center justify-center gap-3"
            >
              <ArrowRight className="w-4 h-4" />
              Back to Dashboard
            </button>

            <button
              onClick={() => navigate('/patient/appointments')}
              disabled={false}
              className="w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#0F6B63] transition hover:bg-[#F7F4ED]/70 flex items-center justify-center gap-3"
            >
              <ArrowRight className="w-4 h-4" />
              View Appointments
            </button>

            <button
              onClick={() => navigate('/patient/laboratory/tests')}
              disabled={false}
              className="w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70 flex items-center justify-center gap-3"
            >
              <ArrowRight className="w-4 h-4" />
              Book Another Test
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}