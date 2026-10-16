import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import AppointmentCard from '../../components/features/AppointmentCard';
import { Beaker, Calendar, Clock, MapPin, ShieldCheck, AlertTriangle } from 'lucide-react';
import Button from '../../components/common/Button';

// Local skeletons for clinical history loading states
const HistorySkeleton = () => (
  <div className="space-y-4 animate-pulse">
    <div className="h-16 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-28 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-28 bg-gray-100 rounded-2xl border border-gray-200" />
  </div>
);

export default function PatientHistory() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('consultations');

  // Fetch consultation appointments
  const {
    data: appointments = [],
    isLoading: isApptsLoading,
    error: apptsError,
    refetch: refetchAppts
  } = useQuery({
    queryKey: ['patientHistory'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
    retry: 1
  });

  // Fetch laboratory bookings
  const {
    data: labBookings = [],
    isLoading: isLabsLoading,
    error: labsError,
    refetch: refetchLabs
  } = useQuery({
    queryKey: ['patientLabHistory'],
    queryFn: async () => {
      const response = await api.get('/laboratory/bookings');
      return response.data;
    },
    retry: 1
  });

  // Filter completed and cancelled visits for consultations
  const history = appointments?.filter(
    (a) => a.status === 'completed' || a.status === 'cancelled'
  ) || [];

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 border-b border-[#E5E0D6]/65 pb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Logs Feed</span>
          <h1 className="text-3xl font-extrabold text-[#1E2A2B] mt-1">Visit History</h1>
          <p className="mt-2 text-sm sm:text-base text-[#60716E] max-w-2xl leading-relaxed">
            Review past consultations, prescriptions, and laboratory records.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#60716E] bg-white border border-[#E5E0D6] p-3 rounded-xl shadow-sm">
          <ShieldCheck className="w-5 h-5 text-[#1F4B45] shrink-0" />
          <span>Patient clinical log archives</span>
        </div>
      </div>

      {/* 2. NAVIGATION TABS */}
      <div className="flex overflow-x-auto hide-scrollbar border-b border-[#E5E0D6]">
        <button
          onClick={() => setActiveTab('consultations')}
          className={`pb-3 px-4 pt-2 text-xs font-bold uppercase tracking-wider transition-all border-b-2 shrink-0 min-h-[44px] ${
            activeTab === 'consultations'
              ? 'border-[#1F4B45] text-[#1F4B45]'
              : 'border-transparent text-[#60716E] hover:text-[#1E2A2B]'
          }`}
        >
          Consultations ({history.length})
        </button>
        <button
          onClick={() => setActiveTab('laboratory')}
          className={`pb-3 px-4 pt-2 text-xs font-bold uppercase tracking-wider transition-all border-b-2 shrink-0 min-h-[44px] ${
            activeTab === 'laboratory'
              ? 'border-[#1F4B45] text-[#1F4B45]'
              : 'border-transparent text-[#60716E] hover:text-[#1E2A2B]'
          }`}
        >
          Laboratory Bookings ({labBookings.length})
        </button>
      </div>

      {/* 3. TABS CONTAINER */}
      {activeTab === 'consultations' ? (
        <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 pb-4 border-b border-[#E5E0D6]/60">
            <div className="space-y-1">
              <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider">Clinical Consults</span>
              <h2 className="text-xl font-extrabold text-[#1E2A2B]">Consultation Logs</h2>
            </div>
            <span className="bg-[#EEF5F1] text-[#1F4B45] text-xs font-bold px-3.5 py-1 rounded-full border border-[#1F4B45]/10">
              {history.length} Visits Logged
            </span>
          </div>

          {isApptsLoading ? (
            <HistorySkeleton />
          ) : apptsError ? (
            <div className="p-6 text-center border border-red-200/50 rounded-2xl bg-red-50/20 space-y-3">
              <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
              <p className="text-sm font-bold text-[#1E2A2B]">Could not load consult history</p>
              <Button variant="outline" onClick={() => refetchAppts()} className="text-xs py-1.5 px-4">
                Retry Connection
              </Button>
            </div>
          ) : history.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#E5E0D6] bg-[#F7F4ED]/20 p-12 text-center max-w-md mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-[#EEF5F1] flex items-center justify-center mx-auto border border-[#E5E0D6]/40">
                <Calendar className="w-5.5 h-5.5 text-[#60716E]" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-extrabold text-[#1E2A2B]">No consultation history</h3>
                <p className="text-xs text-[#60716E] leading-relaxed">
                  Your consultation logs are empty. Completed diagnostic sessions or follow-ups will populate here.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {history.map((appt) => (
                <div key={appt.id} className="bg-[#F7F4ED]/15 rounded-2xl border border-[#E5E0D6]/60 p-4">
                  <AppointmentCard
                    appointment={appt}
                    displayRole="patient"
                  />
                </div>
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 pb-4 border-b border-[#E5E0D6]/60">
            <div className="space-y-1">
              <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider">Diagnostic Tests</span>
              <h2 className="text-xl font-extrabold text-[#1E2A2B]">Laboratory Orders</h2>
            </div>
            <span className="bg-[#EEF5F1] text-[#1F4B45] text-xs font-bold px-3.5 py-1 rounded-full border border-[#1F4B45]/10">
              {labBookings.length} Bookings Recorded
            </span>
          </div>

          {isLabsLoading ? (
            <HistorySkeleton />
          ) : labsError ? (
            <div className="p-6 text-center border border-red-200/50 rounded-2xl bg-red-50/20 space-y-3">
              <AlertTriangle className="w-8 h-8 text-red-600 mx-auto" />
              <p className="text-sm font-bold text-[#1E2A2B]">Could not load laboratory bookings</p>
              <Button variant="outline" onClick={() => refetchLabs()} className="text-xs py-1.5 px-4">
                Retry Connection
              </Button>
            </div>
          ) : labBookings.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[#E5E0D6] bg-[#F7F4ED]/20 p-12 text-center max-w-md mx-auto space-y-4">
              <div className="w-12 h-12 rounded-full bg-[#EEF5F1] flex items-center justify-center mx-auto border border-[#E5E0D6]/40">
                <Beaker className="w-5.5 h-5.5 text-[#1F4B45]" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-extrabold text-[#1E2A2B]">No laboratory bookings</h3>
                <p className="text-xs text-[#60716E] leading-relaxed">
                  You haven't scheduled any diagnostic panels yet. Search and book lab tests using the scheduler tool.
                </p>
              </div>
              <Button
                onClick={() => navigate('/patient/laboratory/tests')}
                className="text-xs py-2 px-5 font-bold shadow-xs mx-auto block"
              >
                Book Diagnostic Panel
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {labBookings.map((booking) => (
                <div key={booking.id} className="rounded-2xl border border-[#E5E0D6] bg-white p-5 space-y-4 shadow-sm hover:shadow-md transition">
                  <div className="flex justify-between items-start gap-2 pb-3 border-b border-[#E5E0D6]/40">
                    <div>
                      <p className="text-xs uppercase tracking-wider font-bold text-[#60716E]">Booking Ref</p>
                      <p className="font-mono text-xs font-bold text-[#1E2A2B]">{booking.id}</p>
                    </div>
                    <div className="flex flex-wrap gap-1.5 justify-end">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider border ${
                        booking.status === 'completed'
                          ? 'bg-[#EEF5F1] text-[#1F4B45] border-[#1F4B45]/10'
                          : booking.status === 'cancelled' || booking.status === 'failed'
                          ? 'bg-red-50 text-red-700 border-red-200/50'
                          : booking.status === 'confirmed'
                          ? 'bg-[#EEF5F1] text-[#1F4B45] border-[#1F4B45]/10'
                          : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20'
                      }`}>
                        {booking.status ? booking.status.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : 'Pending'}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider border ${
                        booking.billing_status === 'paid'
                          ? 'bg-[#EEF5F1] text-[#1F4B45] border-[#1F4B45]/10'
                          : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20'
                      }`}>
                        {booking.billing_status === 'paid' ? 'Paid' : 'Pending'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="flex items-center gap-2 text-[#60716E]">
                      <Calendar className="w-4 h-4 text-[#1F4B45]" />
                      <span>
                        {new Date(booking.appointment_date).toLocaleDateString('en-IN', {
                          weekday: 'short', day: 'numeric', month: 'short'
                        })}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 text-[#60716E]">
                      <Clock className="w-4 h-4 text-[#1F4B45]" />
                      <span>{booking.time_slot}</span>
                    </div>
                  </div>

                  {booking.visit_type === 'home' && booking.address && (
                    <div className="flex items-start gap-2 text-xs text-[#60716E] bg-[#F7F4ED]/50 p-3 rounded-xl border border-[#E5E0D6]/30">
                      <MapPin className="w-4 h-4 text-[#1F4B45] shrink-0 mt-0.5" />
                      <span className="leading-relaxed line-clamp-1">{booking.address}</span>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <p className="text-xs uppercase tracking-wider font-bold text-[#60716E]">Tests</p>
                    <div className="divide-y divide-[#E5E0D6]/30 bg-[#EEF5F1]/30 rounded-xl p-2.5 border border-[#E5E0D6]/30 text-xs">
                      {booking.selected_tests.map((test, index) => (
                        <div key={test.test_id || index} className="flex justify-between items-center py-1">
                          <span className="text-[#1E2A2B] font-bold">{test.name}</span>
                          <span className="text-[#60716E] shrink-0">₹{test.price}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex justify-between items-center gap-3 pt-3 border-t border-[#E5E0D6]/40">
                    <button
                      onClick={() => navigate(`/patient/laboratory/bookings/${booking.id}`)}
                      className="text-xs font-bold text-[#1F4B45] hover:text-[#1F4B45]/80 hover:underline transition"
                    >
                      View Details →
                    </button>
                    <div className="text-right">
                      <span className="text-xs uppercase tracking-wider font-bold text-[#60716E] block">Total</span>
                      <span className="text-sm font-extrabold text-[#1F4B45]">₹{booking.billing_amount}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}