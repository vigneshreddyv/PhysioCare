import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { getState, setState } from './laboratoryStorageUtils';
import { ArrowRight, Building2, Home, ShieldCheck, TestTube, ArrowLeft } from 'lucide-react';

export default function LaboratoryReview() {
  const navigate = useNavigate();

  const [savedAddress, setSavedAddress] = useState('');
  const [_addressLoading, setAddressLoading] = useState(true);

  // Load address from backend and store it in our storage
  useEffect(() => {
    const loadAddress = async () => {
      const state = getState() || {};
      // If we already have a saved address in lab state (from HomeVisitLab), use it
      if (state.savedAddress) {
        setSavedAddress(state.savedAddress);
        setAddressLoading(false);
        return;
      }
      // Otherwise fetch from backend
      try {
        const response = await api.get('/users/me/address');

        console.log('ADDRESS API STATUS:', response.status);
        console.log('ADDRESS API RESPONSE:', response.data);

        const data = response.data;

        const address = data
          ? [
              data.building_name,
              data.door_number,
              data.area,
              data.street,
              data.landmark,
              data.pincode,
            ]
              .filter(Boolean)
              .join(', ')
          : '';

        setSavedAddress(address);
        // Store the address in our laboratory booking state
        setState({ savedAddress: address });

      } catch (error) {
        console.error('Failed to load saved address:', error);
        setSavedAddress('');
        setState({ savedAddress: '' });
      } finally {
        setAddressLoading(false);
      }
    };

    loadAddress();
  }, []);

  // Get the current laboratory booking state from our storage
  const state = getState() || {};

  // Extract values from state with fallbacks
  const selectedTests = Array.isArray(state.selectedTests) ? state.selectedTests : [];
  const visitType = state.visitType || 'home';
  const selectedDate = state.selectedDate || '';
  const selectedTime = state.selectedTime || '';
  const [_bookingReady, _setBookingReady] = useState(state.bookingReady || false);

  // Calculate total from selectedTests
  const total = selectedTests.reduce((sum, test) => sum + Number(test.price || 0), 0);

  const [_formattedDate, _setFormattedDate] = useState(selectedDate
    ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString(
        'en-IN',
        {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        }
      )
    : 'Not selected');

  const handleContinue = () => {
    // Mark booking as ready in our storage
    setState({ bookingReady: true });
    navigate('/patient/laboratory/payment');
  };

  return (
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <div className="mb-8">
          <button
            type="button"
            onClick={() => navigate('/patient/laboratory/date-time')}
            className="inline-flex items-center gap-2 mb-4 px-3 py-2.5 -ml-3 rounded-xl text-sm font-bold text-[#60716E] hover:text-[#1F4B45] hover:bg-[#EEF5F1]/60 transition-colors min-h-[44px]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#1E2A2B] sm:text-4xl">
            Review your booking
          </h1>

          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Check your laboratory tests, collection method, date and
            time before proceeding to payment.
          </p>
        </div>

        {/* Progress Tracker */}
        <div className="mb-8 rounded-2xl border border-[#E5E0D6]/50 bg-white p-4 shadow-sm">
          {/* Mobile view progress tracker */}
          <div className="sm:hidden flex flex-col gap-2">
            <div className="flex justify-between items-center text-xs font-bold text-[#1E2A2B]">
              <span className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#1F4B45] text-white text-xs font-black">3</span>
                Step 3 of 4
              </span>
              <span className="text-[#1F4B45]">Review</span>
            </div>
            <div className="w-full bg-[#E5E0D6]/40 h-1.5 rounded-full overflow-hidden flex gap-1">
              {[1, 2, 3, 4].map((s) => (
                <div 
                  key={s} 
                  className={`h-full flex-1 transition-all duration-300 ${
                    s <= 3 ? 'bg-[#1F4B45]' : 'bg-[#E5E0D6]/30'
                  }`} 
                />
              ))}
            </div>
          </div>

          {/* Desktop view progress tracker */}
          <div className="hidden sm:flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#EEF5F1]">
                <span className="w-4 h-4 text-[#1F4B45] font-bold">✓</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 1
                </p>
                <p className="text-sm font-semibold text-[#1E2A2B]">
                  Select Tests
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#EEF5F1]">
                <span className="w-4 h-4 text-[#1F4B45] font-bold">✓</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 2
                </p>
                <p className="text-sm font-semibold text-[#1E2A2B]">
                  Date & Time
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#1F4B45] text-white">
                <span className="text-sm font-bold">3</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#1F4B45]">
                  STEP 3
                </p>
                <p className="text-sm font-bold text-[#1F4B45]">
                  Review
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#EEF5F1] text-[#60716E]">
                <span className="text-sm font-semibold">4</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 4
                </p>
                <p className="text-sm font-semibold text-[#60716E]">
                  Payment
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="grid w-full gap-6 lg:grid-cols-2">

          {/* ================= LEFT SIDE (Booking Details) ================= */}
          <div className="lg:col-span-1">

            {/* Collection Details */}
            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">

              <div className="mb-6 flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Collection Details
                  </p>

                  <h2 className="mt-2 text-2xl font-bold text-[#1E2A2B]">
                    Laboratory Appointment
                  </h2>
                </div>

                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEF5F1]">
                  {visitType === 'clinic' ? (
                    <Building2 className="w-5 h-5 text-[#1F4B45]" />
                  ) : (
                    <Home className="w-5 h-5 text-[#1F4B45]" />
                  )}
                </div>
              </div>

              {/* Appointment information */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">

                {/* Collection Method */}
                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Collection Method
                  </p>

                  <p className="mt-3 text-lg font-bold text-[#1E2A2B]">
                    {visitType === 'clinic'
                      ? 'Clinic Visit'
                      : 'Home Sample Collection'}
                  </p>

                  <p className="mt-1 text-sm text-[#60716E]">
                    {visitType === 'clinic'
                      ? 'Complete your tests at the clinic'
                      : 'Lab assistant visits your home'}
                  </p>
                </div>

                {/* Date */}
                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Date
                  </p>

                  <p className="mt-3 text-lg font-bold text-[#1E2A2B]">
                    {selectedDate
                      ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString(
                          'en-IN',
                          {
                            weekday: 'long',
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric',
                          }
                        )
                      : 'Not selected'}
                  </p>
                </div>

                {/* Time */}
                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Time
                  </p>

                  <p className="mt-3 text-lg font-bold text-[#1E2A2B]">
                    {selectedTime || 'Not selected'}
                  </p>
                </div>

                {/* Location */}
                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">

                  <div className="flex items-start justify-between gap-3">

                    <div className="min-w-0">

                      <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                        Location
                      </p>

                      <p className="mt-3 text-lg font-bold text-[#1E2A2B]">
                        {visitType === 'clinic'
                          ? 'PhysioCare Clinic'
                          : 'Home Address'}
                      </p>

                      {visitType === 'clinic' ? (
                        <p className="mt-1 text-sm text-[#60716E]">
                          Laboratory testing facility
                        </p>
                      ) : (
                        <p className="mt-2 text-sm leading-6 text-[#60716E]">
                          {savedAddress || 'No saved address found.'}
                        </p>
                      )}
                    </div>

                    {/* Edit Address */}
                    {visitType !== 'clinic' && (
                      <button
                        type="button"
                        onClick={() =>
                          navigate('/patient/profile?returnTo=laboratory-review')
                        }
                        className="shrink-0 rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-3 py-2 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
                      >
                        ✎ Edit Address
                      </button>
                    )}

                    {/* Add Address if no saved address */}
                    {visitType !== 'clinic' && !savedAddress && (
                      <button
                        type="button"
                        onClick={() =>
                          navigate('/patient/profile?returnTo=laboratory-review')
                        }
                        className="mt-3 rounded-xl bg-[#1F4B45] px-4 py-2 text-sm font-semibold text-[#F7F4ED] transition hover:bg-[#F7F4ED]/70"
                      >
                        Add Address
                      </button>
                    )}

                  </div>

                </div>

              </div>

            </div>

            {/* ================= SELECTED TESTS ================= */}
            <div className="border-t border-[#E5E0D6]/50 pt-4">

              <div className="mb-5 flex items-center justify-between">

                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Selected Tests
                  </p>

                  <h2 className="mt-2 text-2xl font-bold text-[#1E2A2B]">
                    Your Laboratory Tests
                  </h2>
                </div>

                {state.selectedTests && state.selectedTests.length > 0 && (
                  <span className="rounded-full bg-[#EEF5F1] px-2 py-1 text-xs font-semibold text-[#1E2A2B]">
                    {state.selectedTests.length} test
                    {state.selectedTests.length !== 1 ? 's' : ''}
                  </span>
                )}

              </div>

              {/* Wide test list */}
              <div className="space-y-2">

                {selectedTests.map((test, index) => (

                  <div
                    key={test.id}
                    className="flex items-start justify-between gap-2 border-t border-[#E5E0D6]/50 pt-2 pb-1"
                  >

                    {/* Icon */}
                    <div className="flex-shrink-0">
                      <TestTube className="w-5 h-5 text-[#1F4B45]" />
                    </div>

                    {/* Test information */}
                    <div className="flex-1">

                      <p className="text-sm font-semibold text-[#1E2A2B]">
                        {index + 1}. {test.name}
                      </p>

                      <p className="mt-1 text-sm text-[#60716E]">
                        {test.sample}
                      </p>

                    </div>

                    {/* Price */}
                    <p className="shrink-0 text-sm font-bold text-[#1F4B45]">
                      ₹{test.price}
                    </p>

                  </div>

                ))}

              </div>

              {/* Change selected tests */}
              {selectedTests.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    navigate('/patient/laboratory/tests')
                  }
                  className="mt-3 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-2 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
                >
                  ← Change selected tests
                </button>
              )}

            </div>

          </div>

          {/* ================= RIGHT SIDE (Payment Summary) ================= */}
          <div className="lg:col-span-1 sticky top-4 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">

            <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
              Payment Summary
            </p>

            <h2 className="mt-2 text-2xl font-bold text-[#1E2A2B]">
              Booking Total
            </h2>


            {/* Test prices */}
            <div className="mt-6 space-y-4">

              {selectedTests.map((test) => (

                <div
                  key={test.id}
                  className="flex items-start justify-between gap-4"
                >

                  <p className="text-sm leading-6 text-[#60716E]">
                    {test.name}
                  </p>

                  <p className="shrink-0 text-sm font-bold text-[#1E2A2B]">
                    ₹{test.price}
                  </p>

                </div>

              ))}

            </div>

            {/* Divider */}
            <div className="my-6 border-t border-[#E5E0D6]/50" />

            {/* Total */}
            <div className="flex items-center justify-between">

              <span className="text-sm font-semibold text-[#60716E]">
                Total
              </span>

              <span className="text-2xl font-bold text-[#1F4B45]">
                ₹{total}
              </span>

            </div>

            {/* Secure booking */}
            <div className="mt-4 rounded-xl border border-[#E5E0D6]/50 bg-[#EEF5F1]/50 p-3">

              <div className="flex gap-3">

                <div className="text-xl">
                  <ShieldCheck className="w-5 h-5 text-[#1F4B45]" />
                </div>

                <div>
                  <p className="text-sm font-semibold text-[#1F4B45]">
                    Secure booking
                  </p>

                  <p className="mt-1 text-xs leading-5 text-[#1F4B45]">
                    Your booking information is securely processed
                    and shared only with the relevant healthcare team.
                  </p>

                </div>

              </div>

            </div>

            {/* Payment button */}
            <button
              type="button"
              onClick={handleContinue}
              disabled={
                selectedTests.length === 0 ||
                !selectedDate ||
                !selectedTime ||
                (visitType !== 'clinic' && !savedAddress)
              }
              className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#1F4B45] px-5 py-3.5 text-sm font-extrabold text-white shadow-sm transition hover:bg-[#17352F] disabled:cursor-not-allowed disabled:opacity-50 min-h-[48px]"
            >
              Proceed to Payment
              <ArrowRight className="w-4 h-4" />
            </button>

            {/* Change Date & Time */}
            <button
              type="button"
              onClick={() =>
                navigate('/patient/laboratory/date-time')
              }
              className="mt-2 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-2 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
            >
              ← Change Date & Time
            </button>

          </div>

        </div>

      </div>
    </div>
  );
}