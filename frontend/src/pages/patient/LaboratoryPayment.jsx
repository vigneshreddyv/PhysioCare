import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { openRazorpayCheckout } from '../../services/razorpayCheckout';
import { useAuth } from '../../context/useAuth';
import { getState, setState } from './laboratoryStorageUtils';
import { Banknote, CreditCard, Smartphone, ShieldCheck, ArrowLeft, Lock } from 'lucide-react';

export default function LaboratoryPayment() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [paymentMethod, setPaymentMethod] = useState('upi');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);
  // Retry support: once a booking exists, retries must reuse it (never create
  // a second booking). Kept in a ref so re-renders cannot lose it.
  const bookingIdRef = useRef(null);

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
    if (totalAmount <= 0) {
      return;
    }

    // VERIFICATION RETRY: if a previous Checkout success was captured but
    // backend verification did not complete (transient failure, refresh,
    // network), retry verification with the SAME payment/order/signature —
    // never a new checkout, a new booking, or a new order.
    const stored = state.razorpay_payment_response;
    if (stored) {
      let captured = null;
      try {
        captured = JSON.parse(stored);
      } catch {
        captured = null;
      }
      if (
        captured &&
        captured.booking_id &&
        captured.razorpay_payment_id &&
        captured.razorpay_signature
      ) {
        setIsProcessing(true);
        setError(null);
        await verifyLaboratoryPayment(captured.booking_id, captured);
        return;
      }
    }

    setIsProcessing(true);
    setError(null);

    try {
      // 1. Create backend laboratory booking (reused on retries so a failed
      //    checkout never creates duplicate bookings).
      let bookingId = bookingIdRef.current;

      if (!bookingId) {
        const bookingPayload = {
          test_ids: selectedTests.map(t => t.test_id || t.id),
          appointment_date: state.selectedDate || '',
          time_slot: state.selectedTime || '',
          visit_type: state.visitType || 'home',
          address: state.visitType === 'home' ? (state.savedAddress || null) : null
        };

        const bookingResponse = await api.post('/laboratory/bookings', bookingPayload);
        bookingId = bookingResponse.data.id;
        bookingIdRef.current = bookingId;
      }

      // 2. Ask the backend for the Razorpay order. The backend is the sole
      //    authority for amount/currency/order id — nothing is computed here.
      const orderResponse = await api.post(
        `/laboratory/bookings/${bookingId}/payment/order`,
        {}
      );
      const { key_id, order_id, amount, currency } = orderResponse.data;

      // 3. Open real Razorpay Checkout with the backend values, unchanged.
      //    NOTE: success here is NOT backend-confirmed payment. The payment          //    response is held in memory only; backend verification (next task)
          //    will confirm it. The lab booking keeps its pending billing state.
      await openRazorpayCheckout({
        keyId: key_id,
        orderId: order_id,
        amount,
        currency,
        description: 'Laboratory tests payment',
        prefill: {
          name: user?.full_name || '',
          email: user?.email || '',
        },
        onSuccess: (paymentResponse) => {
          // Capture the Checkout response, then let the BACKEND verify it.
          // Checkout success alone is NOT a success claim: navigation only
          // happens after the backend verification response arrives.
          const captured = {
            razorpay_payment_id: paymentResponse.razorpay_payment_id || null,
            razorpay_order_id: paymentResponse.razorpay_order_id || order_id,
            razorpay_signature: paymentResponse.razorpay_signature || null,
            booking_id: bookingId,
          };
          setState({
            razorpay_payment_response: JSON.stringify(captured),
          });

          setIsProcessing(true);
          verifyLaboratoryPayment(bookingId, captured);
        },
        onDismiss: () => {
          // User closed Checkout or payment failed inside it. The booking
          // stays pending payment and the patient can retry with the SAME
          // order — no new booking, no fabricated payment state.
          setIsProcessing(false);
          setError('Payment window closed. Your booking is still pending payment — you can safely try again.');
        },
      });
    } catch (err) {
      console.error('Laboratory booking/payment error:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'We couldn\'t open secure payment. Please try again.';
      setError(errorMsg);
    } finally {
      setIsProcessing(false);
    }
  };

  /**
   * Send the captured Checkout response to the backend verification
   * endpoint. The backend response is authoritative: only a verified result
   * navigates to the success page with a confirmed payment state. Checkout
   * success alone NEVER marks the booking paid or confirmed.
   */
  const verifyLaboratoryPayment = async (bookingId, captured) => {
    if (
      !captured.razorpay_payment_id ||
      !captured.razorpay_order_id ||
      !captured.razorpay_signature
    ) {
      setIsProcessing(false);
      setError('Payment is being verified. Please try again shortly.');
      return;
    }

    try {
      const response = await api.post(
        `/laboratory/bookings/${bookingId}/payment/verify`,
        {
          razorpay_payment_id: captured.razorpay_payment_id,
          razorpay_order_id: captured.razorpay_order_id,
          razorpay_signature: captured.razorpay_signature,
        }
      );

      if (response.data?.status === 'verified') {
        // Backend-confirmed: now (and only now) show the confirmation flow.
        // Clear the captured response so a future flow can never replay it.
        setState({ razorpay_payment_response: null });
        const verifiedState = {
          selectedTests,
          visitType: state.visitType || 'home',
          selectedDate: state.selectedDate || '',
          selectedTime: state.selectedTime || '',
          savedAddress: state.savedAddress || '',
          bookingId,
          bookingStatus: 'confirmed',
          paymentStatus: 'paid',
        };
        navigate('/patient/laboratory/success', { state: verifiedState });
      } else {
        setIsProcessing(false);
        setError('Payment is being verified. Please try again shortly.');
      }
    } catch (err) {
      console.error('Laboratory payment verification error:', err);
      setIsProcessing(false);
      setError(
        err.response?.data?.detail ||
        'Payment is being verified. Please try again shortly.'
      );
      // Transient backend/Razorpay problems (5xx): keep the captured
      // response so "Pay" retries VERIFICATION with the SAME
      // payment/order/signature. Definitive backend rejections (4xx): the
      // capture is unusable — clear it so the next attempt opens a fresh
      // checkout on the SAME booking/order (backend order reuse applies).
      const status = err.response?.status;
      if (status && status < 500) {
        setState({ razorpay_payment_response: null });
      }
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
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <div className="mb-8">
          <button
            type="button"
            onClick={() => navigate('/patient/laboratory/review')}
            className="inline-flex items-center gap-2 mb-4 px-3 py-2.5 -ml-3 rounded-xl text-sm font-bold text-[#60716E] hover:text-[#1F4B45] hover:bg-[#EEF5F1]/60 transition-colors min-h-[44px]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#1E2A2B] sm:text-4xl">
            Complete Your Payment
          </h1>

          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Review your booking details and select your preferred
            payment method.
          </p>
        </div>

        {/* Progress Tracker */}
        <div className="mb-8 rounded-2xl border border-[#E5E0D6]/50 bg-white p-4 shadow-sm">
          {/* Mobile view progress tracker */}
          <div className="sm:hidden flex flex-col gap-2">
            <div className="flex justify-between items-center text-xs font-bold text-[#1E2A2B]">
              <span className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#1F4B45] text-white text-xs font-black">4</span>
                Step 4 of 4
              </span>
              <span className="text-[#1F4B45]">Payment</span>
            </div>
            <div className="w-full bg-[#E5E0D6]/40 h-1.5 rounded-full overflow-hidden flex gap-1">
              {[1, 2, 3, 4].map((s) => (
                <div 
                  key={s} 
                  className={`h-full flex-1 transition-all duration-300 ${
                    s <= 4 ? 'bg-[#1F4B45]' : 'bg-[#E5E0D6]/30'
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
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#EEF5F1]">
                <span className="w-4 h-4 text-[#1F4B45] font-bold">✓</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  STEP 3
                </p>
                <p className="text-sm font-semibold text-[#1E2A2B]">
                  Review
                </p>
              </div>
            </div>

            <div className="mx-3 h-px flex-1 bg-[#E5E0D6]/50" />

            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#1F4B45] text-white">
                <span className="text-sm font-bold">4</span>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#1F4B45]">
                  STEP 4
                </p>
                <p className="text-sm font-bold text-[#1F4B45]">
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

                <h2 className="mt-1 text-2xl font-bold text-[#1E2A2B]">
                  Laboratory Appointment
                </h2>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Collection Method
                  </p>

                  <p className="mt-2 font-bold text-[#1E2A2B]">
                    {collectionType}
                  </p>
                </div>

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Date
                  </p>

                  <p className="mt-2 font-bold text-[#1E2A2B]">
                    {formatDate(appointmentDate)}
                  </p>
                </div>

                <div className="rounded-2xl bg-[#F7F4ED]/50 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                    Appointment Time
                  </p>

                  <p className="mt-2 font-bold text-[#1E2A2B]">
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

                <h2 className="mt-1 text-2xl font-bold text-[#1E2A2B]">
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
                      ? 'border-[#1F4B45] bg-[#EEF5F1]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <Smartphone className="w-5 h-5 text-[#1F4B45]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#1E2A2B]">
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
                        ? 'border-[#1F4B45] bg-[#1F4B45]'
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
                      ? 'border-[#1F4B45] bg-[#EEF5F1]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <CreditCard className="w-5 h-5 text-[#1F4B45]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#1E2A2B]">
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
                        ? 'border-[#1F4B45] bg-[#1F4B45]'
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
                      ? 'border-[#1F4B45] bg-[#EEF5F1]'
                      : 'hover:bg-[#F7F4ED]/70'
                  }`}
                >
                  <div className="flex items-center justify-between">

                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl shadow-sm">
                      <Banknote className="w-5 h-5 text-[#1F4B45]" />
                    </div>

                    <div>
                      <p className="font-bold text-[#1E2A2B]">
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
                        ? 'border-[#1F4B45] bg-[#1F4B45]'
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

            <h2 className="mt-2 text-2xl font-bold text-[#1E2A2B]">
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

                  <p className="shrink-0 font-bold text-[#1F4B45]">
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

              <span className="text-2xl font-bold text-[#1F4B45]">
                ₹{totalAmount.toLocaleString('en-IN')}
              </span>

            </div>

            {/* Security */}
            <div className="mt-4 rounded-xl border border-[#E5E0D6]/50 bg-[#EEF5F1]/50 p-3">
              <div className="flex gap-3">

                <div className="text-xl">
                  <ShieldCheck className="w-5 h-5 text-[#1F4B45]" />
                </div>

                <div>
                  <p className="text-sm font-semibold text-[#1F4B45]">
                    Secure payment
                  </p>

                  <p className="mt-1 text-xs leading-5 text-[#1F4B45]">
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

            {/* Pay Button — prominent secure action */}
            <button
              type="button"
              onClick={handlePayment}
              disabled={isProcessing || totalAmount <= 0}
              className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#1F4B45] px-5 py-4 text-base font-extrabold text-white shadow-md transition hover:bg-[#17352F] disabled:cursor-not-allowed disabled:opacity-50 min-h-[52px]"
            >
              <Lock className="w-4 h-4" />
              {isProcessing
                ? 'Processing Payment...'
                : `Pay ₹${totalAmount.toLocaleString('en-IN')} Securely`}
            </button>

            <p className="mt-3 flex items-center justify-center gap-1.5 text-xs text-[#60716E]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#1F4B45] shrink-0" />
              Secured by Razorpay · card details never touch our servers
            </p>

            <button
              type="button"
              onClick={() =>
                navigate('/patient/laboratory/review')
              }
              disabled={isProcessing}
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