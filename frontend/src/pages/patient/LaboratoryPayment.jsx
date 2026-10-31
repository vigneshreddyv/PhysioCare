import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getState } from './laboratoryStorageUtils';
import { ArrowRight, Banknote, CreditCard, Smartphone, ShieldCheck } from 'lucide-react';

export default function LaboratoryPayment() {
  const navigate = useNavigate();

  const [paymentMethod, setPaymentMethod] = useState('upi');
  const [error, setError] = useState(null);

  // Get laboratory booking state from our storage
  const state = getState() || {};

  // Extract values from state with fallbacks
  const selectedTests = Array.isArray(state.selectedTests) ? state.selectedTests : [];
  const appointmentDate = state.laboratory_selected_date || state.selectedDate || '';
  const appointmentTime = state.laboratory_selected_time || state.selectedTime || '';
  const collectionType =
    state.laboratory_visit_type ||
    state.lab_visit_type ||
    state.visitType ||
    'Home Sample Collection';

  // Handle savedAddress: may be stored as 'savedAddress' in state
  const savedAddress = state.savedAddress || '';

  const totalAmount = selectedTests.reduce(
    (total, test) => total + Number(test.price || 0),
    0
  );

  const handlePayment = async () => {
    setError(
      'Laboratory checkout is temporarily unavailable because this legacy payment flow does not support verified Razorpay payments.'
    );
  };

  const formatDate = (date) => {
    if (!date) return 'Not selected';

    const parsedDate = new Date(date);

    if (Number.isNaN(parsedDate.getTime())) {
      return date;
    }

    return parsedDate.toLocaleDateString('en-IN', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
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
            Complete Your Payment
          </h1>

          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Review your booking details and select your preferred
            payment method.
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
                  <line x1="3" y1="12" x2="7" y2="16" strokeWidth="2"></line>
                  <line x1="7" y1="16" x2="13" y2="10" strokeWidth="2"></line>
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

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <span className="w-4 h-4" stroke="currentColor" fill="none">
                  <line x1="3" y1="12" x2="7" y2="16" strokeWidth="2"></line>
                  <line x1="7" y1="16" x2="13" y2="10" strokeWidth="2"></line>
                </span>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 3
                </p>

                <p className="text-sm font-semibold text-[#183B4A]">
                  Review
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#0F6B63]">
                <p className="text-sm font-bold text-[#F7F4ED]">
                  4
                </p>
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 4
                </p>

                <p className="text-sm font-semibold text-[#183B4A]">
                  Payment
                </p>
              </div>
            </div>

          </div>
        </div>

        {/* Main Grid */}
        <div className="grid w-full gap-6 lg:grid-cols-2">

          {/* Left */}
          <div className="lg:col-span-1 space-y-6">

            {/* Booking Details */}
            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">

              <div className="mb-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  Booking Details
                </p>

                <h2 className="mt-1 text-2xl font-bold text-[#183B4A]">
                  Laboratory Appointment
                </h2>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Collection Method
                  </p>

                  <p className="mt-2 font-bold text-[#183B4A]">
                    {collectionType}
                  </p>
                </div>

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Date
                  </p>

                  <p className="mt-2 font-bold text-[#183B4A]">
                    {formatDate(appointmentDate)}
                  </p>
                </div>

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Time
                  </p>

                  <p className="mt-2 font-bold text-[#183B4A]">
                    {appointmentTime || 'Not selected'}
                  </p>
                </div>

                {savedAddress && (
                  <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                      Home Address
                    </p>

                    <p className="mt-2 text-sm leading-6 text-[#60716E]">
                      {savedAddress}
                    </p>
                  </div>
                )}

              </div>
            </div>

            {/* Payment Methods */}
            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">

              <div className="mb-6">
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  Payment Method
                </p>

                <h2 className="mt-1 text-2xl font-bold text-[#183B4A]">
                  Choose how you want to pay
                </h2>
              </div>

              <div className="space-y-3">

                {/* UPI */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('upi')}
                  className={`w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-left transition-all duration-200 ${
                    paymentMethod === 'upi'
                      ? 'border-[#0F6B63] bg-[#DDEFEA]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <Smartphone className="w-5 h-5 text-[#0F6B63]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#183B4A]">
                        UPI
                      </p>

                      <p className="text-sm text-[#60716E]">
                        Google Pay, PhonePe, Paytm and more
                      </p>
                    </div>

                  </div>

                  <div
                    className={`h-5 w-5 rounded-full border-2 ${
                      paymentMethod === 'upi'
                        ? 'border-[#0F6B63] bg-[#0F6B63]'
                        : 'border-[#E5E0D6]/50'
                    }`}
                  />
                </button>

                {/* Card */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('card')}
                  className={`w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-left transition-all duration-200 ${
                    paymentMethod === 'card'
                      ? 'border-[#0F6B63] bg-[#DDEFEA]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <CreditCard className="w-5 h-5 text-[#0F6B63]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#183B4A]">
                        Credit / Debit Card
                      </p>

                      <p className="text-sm text-[#60716E]">
                        Visa, Mastercard and RuPay
                      </p>
                    </div>

                  </div>

                  <div
                    className={`h-5 w-5 rounded-full border-2 ${
                      paymentMethod === 'card'
                        ? 'border-[#0F6B63] bg-[#0F6B63]'
                        : 'border-[#E5E0D6]/50'
                    }`}
                  />
                </button>

                {/* Net Banking */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('netbanking')}
                  className={`w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-left transition-all duration-200 ${
                    paymentMethod === 'netbanking'
                      ? 'border-[#0F6B63] bg-[#DDEFEA]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <Banknote className="w-5 h-5 text-[#0F6B63]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#183B4A]">
                        Net Banking
                      </p>

                      <p className="text-sm text-[#60716E]">
                        Pay directly through your bank
                      </p>
                    </div>

                  </div>

                  <div
                    className={`h-5 w-5 rounded-full border-2 ${
                      paymentMethod === 'netbanking'
                        ? 'border-[#0F6B63] bg-[#0F6B63]'
                        : 'border-[#E5E0D6]/50'
                    }`}
                  />
                </button>

              </div>
            </div>

          </div>

          {/* Right Payment Summary */}
          <div className="lg:col-span-1 sticky top-4 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">

            <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
              Payment Summary
            </p>

            <h2 className="mt-2 text-2xl font-bold text-[#183B4A]">
              Booking Total
            </h2>

            <div className="mt-6 space-y-4">

              {selectedTests.map((test, index) => (
                <div
                  key={test.id || index}
                  className="flex items-start justify-between gap-4"
                >
                  <p className="text-sm leading-6 text-[#60716E]">
                    {test.name || test.test_name}
                  </p>

                  <p className="shrink-0 font-bold text-[#0F6B63]">
                    ₹{Number(test.price || 0).toLocaleString('en-IN')}
                  </p>
                </div>
              ))}

            </div>

            <div className="my-6 h-px bg-[#E5E0D6]/50" />

            <div className="flex items-center justify-between">

              <span className="text-sm font-semibold text-[#60716E]">
                Total
              </span>

              <span className="text-2xl font-bold text-[#0F6B63]">
                ₹{totalAmount.toLocaleString('en-IN')}
              </span>

            </div>

            {/* Security */}
            <div className="mt-4 rounded-xl border border-[#E5E0D6]/50 bg-[#DDEFEA]/50 p-3">
              <div className="flex gap-3">

                <div className="text-xl">
                  <ShieldCheck className="w-5 h-5 text-[#0F6B63]" />
                </div>

                <div>
                  <p className="text-sm font-semibold text-[#0F6B63]">
                    Secure payment
                  </p>

                  <p className="mt-1 text-xs leading-5 text-[#0F6B63]">
                    Your payment information is securely
                    processed and protected.
                  </p>

                </div>

              </div>
            </div>

            {error && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-600 font-semibold shadow-sm">
                ⚠️ {error}
              </div>
            )}

            {/* Pay Button */}
            <button
              type="button"
              onClick={handlePayment}
              disabled={totalAmount <= 0}
              className="mt-4 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#0F6B63] transition hover:bg-[#F7F4ED]/70 disabled:cursor-not-allowed disabled:bg-[#F7F4ED]/30"
            >
              {`Pay ₹${totalAmount.toLocaleString('en-IN')} →`}
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              type="button"
              onClick={() =>
                navigate('/patient/laboratory/review')
              }
              className="mt-2 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-4 py-2 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
            >
              ← Back to Review
            </button>

          </div>

        </div>

      </div>
    </div>
  );
}