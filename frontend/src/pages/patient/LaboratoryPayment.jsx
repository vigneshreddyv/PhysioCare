import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function LaboratoryPayment() {
  const navigate = useNavigate();

  const [paymentMethod, setPaymentMethod] = useState('upi');
  const [isProcessing, setIsProcessing] = useState(false);

  const selectedTests = useMemo(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem('selected_lab_tests') || '[]'
      );
    } catch {
      return [];
    }
  }, []);

  const appointmentDate =
  sessionStorage.getItem('laboratory_selected_date') || '';

  const appointmentTime =
  sessionStorage.getItem('laboratory_selected_time') || '';

  const collectionType =
    sessionStorage.getItem('laboratory_visit_type') ||
    sessionStorage.getItem('lab_visit_type') ||
    'Home Sample Collection';

  const savedAddress =
    sessionStorage.getItem('laboratory_saved_address') || '';

  const totalAmount = selectedTests.reduce(
    (total, test) => total + Number(test.price || 0),
    0
  );

  const handlePayment = async () => {
    if (totalAmount <= 0) {
      return;
    }

    setIsProcessing(true);

    try {
      /*
       * TEMPORARY PAYMENT SUCCESS FLOW
       *
       * We will replace this section with the real
       * backend payment API after the UI is confirmed.
       */

      await new Promise((resolve) =>
        setTimeout(resolve, 1500)
      );

      sessionStorage.setItem(
        'laboratory_payment_status',
        'success'
      );

      sessionStorage.setItem(
        'laboratory_payment_method',
        paymentMethod
      );

      sessionStorage.setItem(
        'laboratory_payment_amount',
        String(totalAmount)
      );

      navigate('/patient/laboratory/success');
    } catch (error) {
      console.error('Payment error:', error);
    } finally {
      setIsProcessing(false);
    }
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
    <div className="min-h-screen bg-surface-container-low p-6">
      <div className="mx-auto max-w-6xl">

        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-bold uppercase tracking-wide text-cyan-700">
            Laboratory Services
          </p>

          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Complete Your Payment
          </h1>

          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Review your booking details and select your preferred
            payment method.
          </p>
        </div>

        {/* Progress */}
        <div className="mb-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <span className="text-sm font-semibold text-slate-700">
                Tests
              </span>
            </div>

            <div className="mx-3 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <span className="text-sm font-semibold text-slate-700">
                Date & Time
              </span>
            </div>

            <div className="mx-3 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <span className="text-sm font-semibold text-slate-700">
                Review
              </span>
            </div>

            <div className="mx-3 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                4
              </div>

              <span className="text-sm font-semibold text-cyan-700">
                Payment
              </span>
            </div>

          </div>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">

          {/* Left */}
          <div className="space-y-6">

            {/* Booking Details */}
            <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">

              <div className="mb-6">
                <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
                  Booking Details
                </p>

                <h2 className="mt-1 text-2xl font-bold text-slate-900">
                  Laboratory Appointment
                </h2>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

                <div className="rounded-2xl bg-slate-50 p-5">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                    Collection Method
                  </p>

                  <p className="mt-2 font-bold text-slate-900">
                    {collectionType}
                  </p>
                </div>

                <div className="rounded-2xl bg-slate-50 p-5">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                    Appointment Date
                  </p>

                  <p className="mt-2 font-bold text-slate-900">
                    {formatDate(appointmentDate)}
                  </p>
                </div>

                <div className="rounded-2xl bg-slate-50 p-5">
                  <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                    Appointment Time
                  </p>

                  <p className="mt-2 font-bold text-slate-900">
                    {appointmentTime || 'Not selected'}
                  </p>
                </div>

                {savedAddress && (
                  <div className="rounded-2xl bg-slate-50 p-5">
                    <p className="text-xs font-bold uppercase tracking-wide text-slate-400">
                      Home Address
                    </p>

                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {savedAddress}
                    </p>
                  </div>
                )}

              </div>
            </div>

            {/* Payment Methods */}
            <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">

              <div className="mb-6">
                <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
                  Payment Method
                </p>

                <h2 className="mt-1 text-2xl font-bold text-slate-900">
                  Choose how you want to pay
                </h2>
              </div>

              <div className="space-y-3">

                {/* UPI */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('upi')}
                  className={`w-full rounded-2xl border p-5 text-left transition ${
                    paymentMethod === 'upi'
                      ? 'border-cyan-500 bg-cyan-50'
                      : 'border-slate-200 hover:border-cyan-300'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex items-center gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                        📱
                      </div>

                      <div>
                        <p className="font-bold text-slate-900">
                          UPI
                        </p>

                        <p className="text-sm text-slate-500">
                          Google Pay, PhonePe, Paytm and more
                        </p>
                      </div>
                    </div>

                    <div
                      className={`h-5 w-5 rounded-full border-2 ${
                        paymentMethod === 'upi'
                          ? 'border-cyan-600 bg-cyan-600'
                          : 'border-slate-300'
                      }`}
                    />
                  </div>
                </button>

                {/* Card */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('card')}
                  className={`w-full rounded-2xl border p-5 text-left transition ${
                    paymentMethod === 'card'
                      ? 'border-cyan-500 bg-cyan-50'
                      : 'border-slate-200 hover:border-cyan-300'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex items-center gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                        💳
                      </div>

                      <div>
                        <p className="font-bold text-slate-900">
                          Credit / Debit Card
                        </p>

                        <p className="text-sm text-slate-500">
                          Visa, Mastercard and RuPay
                        </p>
                      </div>
                    </div>

                    <div
                      className={`h-5 w-5 rounded-full border-2 ${
                        paymentMethod === 'card'
                          ? 'border-cyan-600 bg-cyan-600'
                          : 'border-slate-300'
                      }`}
                    />
                  </div>
                </button>

                {/* Net Banking */}
                <button
                  type="button"
                  onClick={() => setPaymentMethod('netbanking')}
                  className={`w-full rounded-2xl border p-5 text-left transition ${
                    paymentMethod === 'netbanking'
                      ? 'border-cyan-500 bg-cyan-50'
                      : 'border-slate-200 hover:border-cyan-300'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex items-center gap-4">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                        🏦
                      </div>

                      <div>
                        <p className="font-bold text-slate-900">
                          Net Banking
                        </p>

                        <p className="text-sm text-slate-500">
                          Pay directly through your bank
                        </p>
                      </div>
                    </div>

                    <div
                      className={`h-5 w-5 rounded-full border-2 ${
                        paymentMethod === 'netbanking'
                          ? 'border-cyan-600 bg-cyan-600'
                          : 'border-slate-300'
                      }`}
                    />
                  </div>
                </button>

              </div>
            </div>

          </div>

          {/* Right Payment Summary */}
          <div className="lg:sticky lg:top-6 lg:self-start">

            <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm">

              <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
                Payment Summary
              </p>

              <h2 className="mt-1 text-2xl font-bold text-slate-900">
                Booking Total
              </h2>

              <div className="mt-6 space-y-4">

                {selectedTests.map((test, index) => (
                  <div
                    key={test.id || index}
                    className="flex items-start justify-between gap-4"
                  >
                    <p className="text-sm leading-6 text-slate-600">
                      {test.name || test.test_name}
                    </p>

                    <p className="shrink-0 font-bold text-slate-900">
                      ₹{Number(test.price || 0).toLocaleString('en-IN')}
                    </p>
                  </div>
                ))}

              </div>

              <div className="my-6 h-px bg-slate-200" />

              <div className="flex items-center justify-between">
                <span className="text-lg font-bold text-slate-700">
                  Total
                </span>

                <span className="text-3xl font-bold text-cyan-700">
                  ₹{totalAmount.toLocaleString('en-IN')}
                </span>
              </div>

              {/* Security */}
              <div className="mt-6 rounded-2xl bg-emerald-50 p-5">
                <div className="flex gap-3">

                  <span className="text-xl">
                    🔒
                  </span>

                  <div>
                    <p className="font-bold text-emerald-700">
                      Secure payment
                    </p>

                    <p className="mt-1 text-sm leading-5 text-emerald-600">
                      Your payment information is securely
                      processed and protected.
                    </p>
                  </div>

                </div>
              </div>

              {/* Pay Button */}
              <button
                type="button"
                onClick={handlePayment}
                disabled={isProcessing || totalAmount <= 0}
                className="mt-6 w-full rounded-xl bg-cyan-600 px-5 py-4 text-sm font-bold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {isProcessing
                  ? 'Processing Payment...'
                  : `Pay ₹${totalAmount.toLocaleString('en-IN')} →`}
              </button>

              <button
                type="button"
                onClick={() =>
                  navigate('/patient/laboratory/review')
                }
                disabled={isProcessing}
                className="mt-3 w-full rounded-xl border border-slate-200 px-5 py-3.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
              >
                ← Back to Review
              </button>

            </div>
          </div>

        </div>
      </div>
    </div>
  );
}