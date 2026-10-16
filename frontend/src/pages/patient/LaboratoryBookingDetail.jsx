import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { Calendar, Clock, MapPin, ArrowLeft, AlertCircle, ShieldCheck } from 'lucide-react';

export default function LaboratoryBookingDetail() {
  const { bookingId } = useParams();
  const navigate = useNavigate();

  const {
    data: booking,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['laboratoryBookingDetail', bookingId],
    queryFn: async () => {
      if (!bookingId) throw new Error("Missing booking ID");
      const response = await api.get(`/laboratory/bookings/${bookingId}`);
      return response.data;
    },
    enabled: !!bookingId,
    retry: 1
  });

  const handleBack = () => {
    navigate('/patient/history');
  };

  const handleBookAnother = () => {
    navigate('/patient/laboratory/tests');
  };

  // 1. Loading state with polished skeleton
  if (isLoading) {
    return (
      <div className="p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
        <div className="h-6 w-32 bg-gray-200 rounded animate-pulse" />
        <div className="rounded-xl border border-[#E5E0D6] bg-white p-6 space-y-6">
          <div className="h-10 w-2/3 bg-gray-200 rounded animate-pulse" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="h-12 bg-gray-200 rounded animate-pulse" />
            <div className="h-12 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="h-32 bg-gray-200 rounded animate-pulse" />
          <div className="h-16 bg-gray-200 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  // 2. 404 / Unauthorized/ Not Found state
  const is404 = error?.response?.status === 404 || error?.message === "Missing booking ID";
  if (is404) {
    return (
      <div className="p-6 lg:p-8 max-w-xl mx-auto">
        <div className="rounded-xl border border-[#E5E0D6] bg-white p-12 text-center shadow-sm">
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-6">
            <AlertCircle className="w-5 h-5 text-red-600" />
          </div>
          <h2 className="text-xl font-extrabold text-[#1E2A2B]">Booking not found</h2>
          <p className="mt-2 text-xs text-[#60716E] leading-5">
            The requested laboratory booking could not be found or you do not have permission to view it.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={handleBack}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E0D6] px-5 py-2.5 text-xs font-bold text-[#60716E] transition hover:bg-[#F7F4ED]"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to History
            </button>
            <button
              onClick={handleBookAnother}
              className="inline-flex items-center justify-center rounded-xl bg-[#1F4B45] px-5 py-2.5 text-xs font-bold text-white transition hover:bg-[#1F4B45]/90 shadow-sm"
            >
              Book Another Test
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. Network or other errors
  if (error) {
    return (
      <div className="p-6 lg:p-8 max-w-xl mx-auto">
        <div className="rounded-xl border border-[#E5E0D6] bg-white p-12 text-center shadow-sm">
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-6">
            <AlertCircle className="w-5 h-5 text-red-600" />
          </div>
          <h2 className="text-xl font-extrabold text-[#1E2A2B]">Unable to load booking details</h2>
          <p className="mt-2 text-xs text-[#60716E] leading-5">
            There was a problem communicating with the server. Please try again.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => refetch()}
              className="inline-flex items-center justify-center rounded-xl bg-[#1F4B45] px-5 py-2.5 text-xs font-bold text-white transition hover:bg-[#1F4B45]/90 shadow-sm"
            >
              Try Again
            </button>
            <button
              onClick={handleBack}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#E5E0D6] px-5 py-2.5 text-xs font-bold text-[#60716E] transition hover:bg-[#F7F4ED]"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to History
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto space-y-6">
      {/* Back Button */}
      <button
        onClick={handleBack}
        className="inline-flex items-center gap-2 text-sm font-semibold text-[#60716E] hover:text-[#1F4B45] transition"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to History
      </button>

      {/* Main card */}
      <div className="rounded-2xl border border-[#E5E0D6] bg-white shadow-sm overflow-hidden">
        {/* Header section */}
        <div className="bg-[#EEF5F1]/30 p-6 md:p-8 border-b border-[#E5E0D6] space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-[#60716E]">
                Laboratory Booking
              </p>
              <h1 className="text-2xl font-extrabold text-[#1E2A2B] mt-1">
                Booking Reference Details
              </h1>
              <p className="font-mono text-xs text-[#60716E] mt-1">
                Ref ID: {booking.id}
              </p>
            </div>
            <div className="flex gap-2">
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
                booking.status === 'completed'
                  ? 'bg-green-50 text-green-700 border-green-200'
                  : booking.status === 'cancelled'
                  ? 'bg-red-50 text-red-700 border-red-200'
                  : booking.status === 'confirmed'
                  ? 'bg-blue-50 text-blue-750 border-blue-200'
                  : booking.status === 'failed'
                  ? 'bg-red-50 text-red-755 border-red-200'
                  : 'bg-yellow-50 text-yellow-700 border-yellow-200'
              }`}>
                {booking.status ? booking.status.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : 'Pending Payment'}
              </span>
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                booking.billing_status === 'paid'
                  ? 'bg-[#EEF5F1] text-[#1F4B45] border border-[#1F4B45]/20'
                  : 'bg-[#F7F4ED] text-[#C9A86A] border border-[#C9A86A]/20'
              }`}>
                {booking.billing_status === 'paid' ? 'Paid' : 'Pending Payment'}
              </span>
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${
                booking.visit_type === 'home'
                  ? 'bg-[#EEF5F1] text-[#1F4B45] border border-[#1F4B45]/20'
                  : 'bg-blue-50 text-blue-700 border border-blue-200'
              }`}>
                {booking.visit_type === 'home' ? 'Home Visit' : 'Clinic Visit'}
              </span>
            </div>
          </div>
        </div>

        {/* Content body */}
        <div className="p-6 md:p-8 space-y-8">
          {/* Appointment Details Grid */}
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[#1E2A2B] mb-4">
              Appointment Details
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="flex items-center gap-3 bg-[#F7F4ED]/50 p-4 rounded-xl border border-[#E5E0D6]/40">
                <Calendar className="w-5 h-5 text-[#1F4B45] shrink-0" />
                <div>
                  <p className="text-xs uppercase font-bold text-[#60716E]">Date</p>
                  <p className="text-sm font-bold text-[#1E2A2B] mt-0.5">
                    {new Date(booking.appointment_date).toLocaleDateString('en-IN', {
                      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
                    })}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3 bg-[#F7F4ED]/50 p-4 rounded-xl border border-[#E5E0D6]/40">
                <Clock className="w-5 h-5 text-[#1F4B45] shrink-0" />
                <div>
                  <p className="text-xs uppercase font-bold text-[#60716E]">Time Slot</p>
                  <p className="text-sm font-bold text-[#1E2A2B] mt-0.5">{booking.time_slot}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Collection / Visit Address */}
          {booking.visit_type === 'home' && booking.address && (
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-[#1E2A2B] mb-4">
                Collection Address
              </h2>
              <div className="flex items-start gap-3 bg-[#F7F4ED]/50 p-4 rounded-xl border border-[#E5E0D6]/40">
                <MapPin className="w-5 h-5 text-[#1F4B45] shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs uppercase font-bold text-[#60716E]">Home Address</p>
                  <p className="text-sm leading-6 text-[#60716E] mt-1">{booking.address}</p>
                </div>
              </div>
            </div>
          )}

          {booking.visit_type === 'clinic' && (
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-[#1E2A2B] mb-4">
                Visit Location
              </h2>
              <div className="flex items-start gap-3 bg-[#F7F4ED]/50 p-4 rounded-xl border border-[#E5E0D6]/40">
                <MapPin className="w-5 h-5 text-[#1F4B45] shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs uppercase font-bold text-[#60716E]">Clinic Location</p>
                  <p className="text-sm leading-6 text-[#1E2A2B] font-bold mt-1">PhysioCare Wellness Center</p>
                  <p className="text-xs text-[#60716E] mt-0.5">Please walk in during your scheduled time slot.</p>
                </div>
              </div>
            </div>
          )}

          {/* Selected Tests List */}
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[#1E2A2B] mb-4">
              Selected Tests ({booking.selected_tests.length})
            </h2>
            <div className="border border-[#E5E0D6] rounded-xl overflow-hidden divide-y divide-[#E5E0D6]">
              {booking.selected_tests.map((test, index) => (
                <div key={test.test_id || index} className="p-4 flex justify-between items-start gap-4 hover:bg-[#F7F4ED]/20 transition">
                  <div>
                    <p className="text-sm font-bold text-[#1E2A2B]">{test.name}</p>
                    <p className="text-xs text-[#60716E] mt-1">Sample: {test.sample}</p>
                  </div>
                  <span className="text-sm font-bold text-[#1F4B45] shrink-0">
                    ₹{test.price.toLocaleString('en-IN')}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Payment & Transaction Info */}
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-[#1E2A2B] mb-4">
              Payment & Billing Info
            </h2>
            <div className="bg-[#EEF5F1]/30 rounded-xl border border-[#E5E0D6] p-6 space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                <div>
                  <p className="font-bold text-[#60716E]">Payment Method</p>
                  <p className="font-semibold text-[#1E2A2B] mt-1 capitalize">
                    {booking.payment_method || 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="font-bold text-[#60716E]">Payment Status</p>
                  <p className="font-semibold text-[#1E2A2B] mt-1 capitalize">
                    {booking.payment_status || 'Pending'}
                  </p>
                </div>
                {booking.payment_id && (
                  <div className="col-span-2 sm:col-span-1">
                    <p className="font-bold text-[#60716E]">Transaction ID</p>
                    <p className="font-mono text-xs text-[#1E2A2B] mt-1 break-all">
                      {booking.payment_id}
                    </p>
                  </div>
                )}
                {booking.payment_order_id && (
                  <div className="col-span-2 sm:col-span-1">
                    <p className="font-bold text-[#60716E]">Order ID</p>
                    <p className="font-mono text-xs text-[#1E2A2B] mt-1 break-all">
                      {booking.payment_order_id}
                    </p>
                  </div>
                )}
              </div>

              <div className="border-t border-[#E5E0D6] pt-4 flex justify-between items-center">
                <span className="text-xs text-[#60716E]">
                  Booked on {new Date(booking.created_at).toLocaleString('en-IN', {
                    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                  })}
                </span>
                <div className="text-right">
                  <span className="text-xs font-bold text-[#60716E] block text-xs uppercase tracking-wider">Total Amount</span>
                  <span className="text-xl font-extrabold text-[#1F4B45]">
                    ₹{booking.billing_amount.toLocaleString('en-IN')}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Security / Verification footer */}
        <div className="bg-[#F7F4ED]/50 p-4 border-t border-[#E5E0D6] flex items-center gap-2 justify-center text-xs text-[#60716E]">
          <ShieldCheck className="w-4 h-4 text-[#1F4B45]" />
          <span>Secured and verified laboratory appointment</span>
        </div>
      </div>

      {/* Book another button */}
      <div className="flex justify-end">
        <button
          onClick={handleBookAnother}
          className="rounded-xl bg-[#1F4B45] px-6 py-3 text-xs font-bold text-white transition hover:bg-[#1F4B45]/90 shadow-sm"
        >
          Book Another Test
        </button>
      </div>
    </div>
  );
}
