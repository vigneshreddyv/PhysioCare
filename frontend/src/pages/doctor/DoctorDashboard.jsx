import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import {
  ShieldCheck,
  RefreshCw,
  Users,
  AlertTriangle,
  Clock,
  ClipboardList,
  Dumbbell,
  Calendar,
  ArrowRight,
  ChevronRight,
  CheckCircle2,
} from 'lucide-react';
import { format } from 'date-fns';

// Dense, professional clinician skeleton loader
const ClinicianSkeleton = () => (
  <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 lg:p-8">
    <div className="h-32 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
      <div className="h-64 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    </div>
    <div className="h-72 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
  </div>
);

export default function DoctorDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const currentDate = new Date();

  const doctorFirstName = user?.first_name || (user?.full_name && typeof user.full_name === 'string' ? user.full_name.split(' ')[0] : '') || 'Doctor';

  // 1. Fetch Today's Appointments (Agenda)
  const { 
    data: appointments = [], 
    isLoading: isAppointmentsLoading, 
    error: appointmentsError, 
    refetch: refetchAppointments 
  } = useQuery({
    queryKey: ['doctorAppointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
    retry: 1
  });

  // 2. Fetch Caseload Recovery Monitoring Data
  const { 
    data: monitoringData = [], 
    isLoading: isMonitoringLoading, 
    error: monitoringError, 
    refetch: refetchMonitoring 
  } = useQuery({
    queryKey: ['clinicianPatientMonitoring'],
    queryFn: async () => {
      const response = await api.get('/users/patients/monitoring');
      return response.data;
    },
    retry: 1
  });

  const handleRefresh = async () => {
    await Promise.all([refetchAppointments(), refetchMonitoring()]);
  };

  // Derive Greetings
  const hours = currentDate.getHours();
  let greetingPrefix = 'GOOD MORNING';
  if (hours >= 12 && hours < 17) {
    greetingPrefix = 'GOOD AFTERNOON';
  } else if (hours >= 17) {
    greetingPrefix = 'GOOD EVENING';
  }

  // Derive caseload metrics
  const caseloadStats = useMemo(() => {
    const total = monitoringData.length;
    const activePrograms = monitoringData.filter(p => p.active_program).length;
    const needsAttention = monitoringData.filter(p => p.status === 'No recent activity' || p.status === 'Low recent activity').length;
    const healthyAdherence = monitoringData.filter(p => p.status === 'Active').length;

    return { total, activePrograms, needsAttention, healthyAdherence };
  }, [monitoringData]);

  // Derive attention list (observational only)
  const attentionPatients = useMemo(() => {
    return monitoringData
      .filter(p => p.status === 'No recent activity' || p.status === 'Low recent activity')
      .slice(0, 5);
  }, [monitoringData]);

  // Aggregate recent activities from all caseload patients into one chronologically sorted feed
  const combinedRecentActivity = useMemo(() => {
    const allActivities = [];
    for (const patient of monitoringData) {
      if (patient.recent_activity) {
        for (const act of patient.recent_activity) {
          allActivities.push({
            ...act,
            patientName: patient.full_name,
            patientId: patient.id
          });
        }
      }
    }
    return allActivities.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at)).slice(0, 6);
  }, [monitoringData]);

  // Filter and sort today's appointments
  const todayAgenda = useMemo(() => {
    return [...appointments].sort((a, b) => {
      // Sort completed/cancelled towards the bottom, active/scheduled on top
      const aDone = a.status === 'completed' || a.status === 'cancelled';
      const bDone = b.status === 'completed' || b.status === 'cancelled';
      if (aDone && !bDone) return 1;
      if (!aDone && bDone) return -1;
      return (a.time_slot || '').localeCompare(b.time_slot || '');
    });
  }, [appointments]);

  const isLoading = isAppointmentsLoading || isMonitoringLoading;

  if (isLoading) {
    return <ClinicianSkeleton />;
  }

  if (appointmentsError || monitoringError) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-full flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-black text-[#183B4A] dark:text-zinc-100">Unable to Load Clinician Workspace</h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 max-w-md mx-auto">
            We encountered an authentication or communication error retrieving your clinical caseload data.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs font-bold shadow-xs transition cursor-pointer min-h-[48px]"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Retry Connection</span>
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8 text-[#183B4A] dark:text-zinc-100">
      
      {/* 1. CLINICIAN HERO */}
      <section className="relative overflow-hidden rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#0F6B63]/10 p-6 sm:p-8 lg:p-10 shadow-xs flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div className="space-y-3.5 max-w-2xl">
          <span className="text-[11px] font-extrabold uppercase tracking-widest text-[#0F6B63] dark:text-[#EEF5F1] bg-[#0F6B63]/10 dark:bg-zinc-800 px-3 py-1 rounded-full border border-[#0F6B63]/10 inline-block">
            Clinical Recovery Center
          </span>
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#183B4A] dark:text-zinc-50 leading-tight">
              {greetingPrefix}, DR. {doctorFirstName.toUpperCase()}
            </h1>
            <p className="text-xs sm:text-sm font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-wider">
              {caseloadStats.total} Patients in your caseload · {todayAgenda.length} Appointments today
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-1 text-xs text-[#60716E] dark:text-zinc-400 font-semibold">
            <span className="flex items-center gap-1.5 bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 px-3 py-1.5 rounded-xl shadow-2xs">
              <Calendar className="w-3.5 h-3.5 text-[#0F6B63]" />
              {format(currentDate, 'EEEE, MMMM d, yyyy')}
            </span>
            <span className="flex items-center gap-1.5 bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 px-3 py-1.5 rounded-xl shadow-2xs">
              <ShieldCheck className="w-3.5 h-3.5 text-[#0F6B63]" />
              Caseload Verified
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-center">
          <button 
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs font-bold text-[#60716E] dark:text-zinc-300 hover:text-[#0F6B63] hover:bg-[#EEF5F1]/40 transition cursor-pointer min-h-[48px]"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Workspace</span>
          </button>
        </div>
      </section>

      {/* 2. TODAY'S CLINICAL AGENDA */}
      <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800">
          <div>
            <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block font-semibold">
              Daily Schedule
            </span>
            <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
              Today's Clinical Agenda
            </h2>
          </div>
          <span className="text-xs font-extrabold text-[#0F6B63] dark:text-[#EEF5F1] bg-[#EEF5F1] dark:bg-zinc-800 px-3 py-1 rounded-full border border-[#0F6B63]/10 w-fit">
            {todayAgenda.length} Consultations
          </span>
        </div>

        {todayAgenda.length === 0 ? (
          <div className="text-center py-8 space-y-2">
            <Clock className="w-8 h-8 text-[#60716E] mx-auto" />
            <p className="font-bold text-sm text-[#183B4A] dark:text-zinc-100">No appointments scheduled for today</p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400">Your clinical calendar is clear for the current date.</p>
          </div>
        ) : (
          <div className="space-y-6 relative pl-6">
            {todayAgenda.map((appt, idx) => {
              const isCompleted = appt.status === 'completed';
              const isCancelled = appt.status === 'cancelled';
              const isDone = isCompleted || isCancelled;
              const isLast = idx === todayAgenda.length - 1;

              return (
                <div 
                  key={appt.id} 
                  className={`flex items-start gap-4 relative transition-opacity ${isDone ? 'opacity-65' : 'opacity-100'}`}
                >
                  {/* Connecting thin vertical line */}
                  {!isLast && (
                    <div className="absolute top-6 bottom-[-24px] left-[-9px] w-0.5 bg-[#E5E0D6] dark:bg-zinc-800" />
                  )}

                  {/* Dot / Status Indicator */}
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center border-2 shrink-0 z-10 -ml-[22px] transition-all ${
                    isCompleted
                      ? 'bg-[#0F6B63] border-[#0F6B63] text-white shadow-xs'
                      : isCancelled
                      ? 'bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-zinc-400'
                      : 'bg-[#EEF5F1] dark:bg-zinc-800 border-[#0F6B63] text-[#0F6B63] ring-4 ring-[#EEF5F1] dark:ring-zinc-800/40 shadow-xs'
                  }`}>
                    {isCompleted ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-[#0F6B63]" />
                    )}
                  </div>

                  {/* Card row container */}
                  <div className="flex-1 bg-[#F7F4ED]/40 dark:bg-zinc-850/40 border border-[#E5E0D6]/70 dark:border-zinc-800 p-4 sm:p-5 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-black text-[#0F6B63] dark:text-[#EEF5F1] bg-white dark:bg-zinc-800 px-2.5 py-0.5 rounded-lg border border-[#E5E0D6] dark:border-zinc-700 font-mono">
                          {appt.time_slot || 'All Day'}
                        </span>
                        <h3 className="font-extrabold text-sm sm:text-base text-[#183B4A] dark:text-zinc-100">
                          {appt.patient_name || appt.patient?.full_name || 'Patient'}
                        </h3>
                      </div>
                      <p className="text-xs text-[#60716E] dark:text-zinc-400 font-medium pl-0.5">
                        {appt.reason || appt.service_type || 'Physiotherapy Consultation'}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-center">
                      <span className={`inline-flex px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider border ${
                        isCompleted
                          ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/15'
                          : isCancelled
                          ? 'bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-800 dark:border-zinc-700'
                          : 'bg-white dark:bg-zinc-800 text-[#0F6B63] border-[#0F6B63]/30 font-bold'
                      }`}>
                        {appt.status}
                      </span>

                      {appt.patient_id && (
                        <button
                          onClick={() => navigate(`/doctor/snapshot/${appt.patient_id}`)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs font-bold text-[#0F6B63] hover:bg-[#EEF5F1] transition cursor-pointer min-h-[48px]"
                        >
                          <span>Snapshot</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 3. CASELOAD SUMMARY & CLINICAL ATTENTION */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
        
        {/* CASELOAD SUMMARY & QUICK ACTIONS */}
        <section className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Caseload Registry
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                  My Patients
                </h2>
              </div>
              <button
                onClick={() => navigate('/doctor/patients')}
                className="text-xs font-extrabold text-[#0F6B63] hover:underline flex items-center gap-0.5 cursor-pointer"
              >
                <span>Directory</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* 3 Key Metrics */}
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-4 bg-white dark:bg-zinc-800/60 rounded-2xl border border-[#E5E0D6]/70 dark:border-zinc-700/60 space-y-1">
                <p className="text-2xl sm:text-3xl font-black text-[#183B4A] dark:text-zinc-100">
                  {caseloadStats.total}
                </p>
                <p className="text-[10px] sm:text-xs text-[#60716E] dark:text-zinc-400 font-semibold uppercase">
                  Total Patients
                </p>
              </div>

              <div className="p-4 bg-white dark:bg-zinc-800/60 rounded-2xl border border-[#E5E0D6]/70 dark:border-zinc-700/60 space-y-1">
                <p className="text-2xl sm:text-3xl font-black text-[#0F6B63] dark:text-[#EEF5F1]">
                  {caseloadStats.activePrograms}
                </p>
                <p className="text-[10px] sm:text-xs text-[#60716E] dark:text-zinc-400 font-semibold uppercase">
                  Active Patients
                </p>
              </div>

              <div className="p-4 bg-white dark:bg-zinc-800/60 rounded-2xl border border-[#E5E0D6]/70 dark:border-zinc-700/60 space-y-1">
                <p className={`text-2xl sm:text-3xl font-black ${caseloadStats.needsAttention > 0 ? 'text-[#C9A86A]' : 'text-[#183B4A] dark:text-zinc-100'}`}>
                  {caseloadStats.needsAttention}
                </p>
                <p className="text-[10px] sm:text-xs text-[#60716E] dark:text-zinc-400 font-semibold uppercase">
                  Needs Attention
                </p>
              </div>
            </div>
          </div>

          {/* Quick Clinical Actions */}
          <div className="pt-4 border-t border-[#E5E0D6]/60 dark:border-zinc-800 space-y-2">
            <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
              Quick Clinical Actions
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              <button
                onClick={() => navigate('/doctor/patients')}
                className="flex items-center justify-center gap-2 p-3 bg-white dark:bg-zinc-800 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] hover:border-[#0F6B63]/30 transition cursor-pointer min-h-[48px]"
              >
                <Users className="w-4 h-4 text-[#0F6B63]" />
                <span>My Patients</span>
              </button>

              <button
                onClick={() => navigate('/doctor/patients')}
                className="flex items-center justify-center gap-2 p-3 bg-white dark:bg-zinc-800 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] hover:border-[#0F6B63]/30 transition cursor-pointer min-h-[48px]"
              >
                <ClipboardList className="w-4 h-4 text-[#0F6B63]" />
                <span>Care Plans</span>
              </button>

              <button
                onClick={() => navigate('/doctor/patients')}
                className="flex items-center justify-center gap-2 p-3 bg-white dark:bg-zinc-800 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] hover:border-[#0F6B63]/30 transition cursor-pointer min-h-[48px]"
              >
                <Dumbbell className="w-4 h-4 text-[#0F6B63]" />
                <span>Prescriptions</span>
              </button>
            </div>
          </div>
        </section>

        {/* CLINICAL ATTENTION (OBSERVATIONAL PANEL) */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Observational Flag
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5 flex items-center gap-2">
                  <span>Clinical Attention</span>
                  {attentionPatients.length > 0 && (
                    <span className="w-2 h-2 rounded-full bg-[#C9A86A]" />
                  )}
                </h2>
              </div>
              <span className="text-xs font-bold text-[#60716E] dark:text-zinc-400">
                {attentionPatients.length} Flags
              </span>
            </div>

            {attentionPatients.length === 0 ? (
              <div className="text-center py-8 space-y-2">
                <ShieldCheck className="w-8 h-8 text-[#0F6B63] mx-auto" />
                <p className="font-bold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100">
                  Caseload Adherence Healthy
                </p>
                <p className="text-xs text-[#60716E] dark:text-zinc-400">
                  All patients in your caseload are currently maintaining active rehabilitation logs.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-[#E5E0D6]/40 dark:divide-zinc-800">
                {attentionPatients.map((patient) => (
                  <div key={patient.id} className="py-3 flex items-center justify-between gap-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 space-y-0.5">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100 truncate">
                          {patient.full_name}
                        </h3>
                        <span className="text-[8px] font-black uppercase px-2 py-0.5 rounded bg-[#F7F4ED] dark:bg-zinc-800 text-[#C9A86A] border border-[#C9A86A]/20 shrink-0">
                          {patient.status}
                        </span>
                      </div>
                      <p className="text-[10px] text-[#60716E] dark:text-zinc-400">
                        Adherence: <strong className="text-[#183B4A] dark:text-zinc-200">{patient.adherence_percentage}%</strong> · Last Active: {patient.last_activity ? format(new Date(patient.last_activity), 'MMM d') : 'Never'}
                      </p>
                    </div>

                    <button
                      onClick={() => navigate(`/doctor/snapshot/${patient.id}`)}
                      className="inline-flex items-center gap-1 px-3 py-2 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-[#F7F4ED]/40 dark:bg-zinc-800 text-xs font-bold text-[#0F6B63] dark:text-[#EEF5F1] hover:bg-[#EEF5F1] transition cursor-pointer min-h-[48px] shrink-0"
                    >
                      <span>Snapshot</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-2 text-[10px] text-[#60716E] dark:text-zinc-400 border-t border-[#E5E0D6]/40 dark:border-zinc-800 italic">
            * Flags are derived strictly from absence of logged exercise sessions over the past 7 days.
          </div>
        </section>

      </div>

      {/* 4. RECENT RECOVERY ACTIVITY */}
      <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xs">
        <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
          <div>
            <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
              Performance Feed
            </span>
            <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
              Recent Recovery Activity
            </h2>
          </div>
          <span className="text-xs font-bold text-[#60716E] dark:text-zinc-400">
            Across Assigned Caseload
          </span>
        </div>

        {combinedRecentActivity.length === 0 ? (
          <p className="text-xs text-[#60716E] dark:text-zinc-400 text-center py-6">
            No patient exercise progress has been logged recently.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {combinedRecentActivity.map((activity, index) => (
              <div 
                key={index} 
                className="p-4 sm:p-5 bg-[#F7F4ED]/25 dark:bg-zinc-850/40 border border-[#E5E0D6]/60 dark:border-zinc-800 rounded-2xl space-y-3 flex flex-col justify-between shadow-2xs"
              >
                <div className="space-y-2">
                  <div className="flex justify-between items-start gap-2">
                    <h3 className="font-bold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100 truncate">
                      {activity.patientName}
                    </h3>
                    <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border shrink-0 ${
                      activity.completion_status === 'completed' 
                        ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                        : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                    }`}>
                      {activity.completion_status}
                    </span>
                  </div>
                  
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-[#0F6B63] dark:text-[#EEF5F1] flex items-center gap-1.5 truncate">
                      <Dumbbell className="w-3.5 h-3.5 shrink-0" />
                      <span>{activity.exercise_name}</span>
                    </p>
                    <p className="text-[11px] text-[#60716E] dark:text-zinc-400 font-medium">
                      Logged: {activity.completed_sets} sets · {activity.completed_reps} reps
                    </p>
                    {activity.notes && (
                      <p className="text-[10px] text-[#60716E] dark:text-zinc-400 italic bg-white dark:bg-zinc-800 border border-[#E5E0D6]/50 dark:border-zinc-700 p-2 rounded-xl mt-1 leading-relaxed">
                        "{activity.notes}"
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex justify-between items-center text-[10px] text-[#60716E] dark:text-zinc-400 pt-2 border-t border-[#E5E0D6]/40 dark:border-zinc-700/40 font-semibold">
                  <span>{format(new Date(activity.completed_at), 'MMM d, h:mm a')}</span>
                  {activity.patientId && (
                    <button
                      onClick={() => navigate(`/doctor/snapshot/${activity.patientId}`)}
                      className="text-[#0F6B63] dark:text-[#EEF5F1] hover:underline flex items-center gap-0.5 cursor-pointer min-h-[36px]"
                    >
                      <span>Snapshot</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

    </div>
  );
}
