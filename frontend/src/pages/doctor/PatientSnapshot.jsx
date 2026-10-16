import React, { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { format } from 'date-fns';
import {
  ArrowLeft,
  Mail,
  Phone,
  Calendar,
  ClipboardList,
  Dumbbell,
  Clock,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  ChevronRight,
  RefreshCw,
  Lock,
} from 'lucide-react';

// Lightweight skeleton matching clinical snapshot layout
const SnapshotSkeleton = () => (
  <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12">
    <div className="h-6 w-36 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
    <div className="h-44 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 h-52 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
      <div className="h-52 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    </div>
    <div className="h-44 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="h-72 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
      <div className="h-72 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    </div>
  </div>
);

export default function PatientSnapshot() {
  const { patientId } = useParams();
  const navigate = useNavigate();

  // 1. Core Patient Clinical Snapshot (backend enforces doctor caseload verification)
  const { 
    data: snapshot, 
    isLoading: isSnapshotLoading, 
    error: snapshotError, 
    refetch: refetchSnapshot 
  } = useQuery({
    queryKey: ['doctorPatientSnapshot', patientId],
    queryFn: async () => {
      const response = await api.get(`/users/patients/${patientId}/snapshot`);
      return response.data;
    },
    retry: 1
  });

  // 2. Exercise assignments query (prescriptions)
  const {
    data: assignments = [],
  } = useQuery({
    queryKey: ['patientExerciseAssignments', patientId],
    queryFn: async () => {
      try {
        const response = await api.get(`/exercise-assignments?patient_id=${patientId}`);
        return response.data;
      } catch {
        return [];
      }
    },
    enabled: Boolean(patientId),
    retry: 1,
  });

  // 3. Exercise catalog query (to map exercise names/categories)
  const { data: exercisesCatalog = [] } = useQuery({
    queryKey: ['exercisesCatalog'],
    queryFn: async () => {
      try {
        const response = await api.get('/exercises');
        return response.data;
      } catch {
        return [];
      }
    },
    retry: 1,
  });

  // 4. Care plans query (for start date, target date, and plan descriptions)
  const { data: carePlans = [] } = useQuery({
    queryKey: ['patientCarePlans', patientId],
    queryFn: async () => {
      try {
        const response = await api.get(`/care-plans/patient/${patientId}`);
        return response.data;
      } catch {
        return [];
      }
    },
    enabled: Boolean(patientId),
    retry: 1,
  });

  const activePlan = useMemo(() => {
    if (!carePlans || carePlans.length === 0) return null;
    return carePlans.find(cp => cp.status === 'active') || carePlans[0];
  }, [carePlans]);

  // Merge assignments with exercise catalog for real prescription details
  const enrichedAssignments = useMemo(() => {
    if (!assignments || assignments.length === 0) return [];
    const catMap = new Map(exercisesCatalog.map(e => [e.id, e]));
    return assignments.map(a => {
      const details = catMap.get(a.exercise_id);
      return {
        ...a,
        title: details?.title || `Exercise #${a.exercise_id?.slice(-4) || a.exercise_id}`,
        category: details?.category || 'Rehabilitation',
      };
    });
  }, [assignments, exercisesCatalog]);

  // Derive overall recovery progress percentage
  const overallProgress = useMemo(() => {
    if (!snapshot?.stages || snapshot.stages.length === 0) {
      return snapshot?.adherence_percentage || 0;
    }
    const total = snapshot.stages.length;
    const completedStages = snapshot.stages.filter(s => s.status === 'completed').length;
    const activeStage = snapshot.stages.find(s => s.status === 'active');
    const activeProgress = activeStage?.progress || 0;
    return Math.min(100, Math.round(((completedStages * 100) + activeProgress) / total));
  }, [snapshot]);

  if (isSnapshotLoading) {
    return <SnapshotSkeleton />;
  }

  if (snapshotError) {
    const is404 = snapshotError.response?.status === 404;
    return (
      <div className="max-w-xl mx-auto text-center py-20 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-2xl flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-black text-[#183B4A] dark:text-zinc-100">
            {is404 ? 'Access Restricted' : 'Unable to Load Patient Snapshot'}
          </h2>
          <p className="text-xs sm:text-sm text-[#60716E] dark:text-zinc-400 leading-relaxed max-w-md mx-auto">
            {is404
              ? 'This patient record does not belong to your authorized clinical caseload, or the profile is incomplete.'
              : 'We could not retrieve the clinical snapshot at this time. Please check your connection and retry.'}
          </p>
        </div>
        <div className="flex justify-center gap-3">
          <button
            onClick={() => navigate('/doctor/patients')}
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs font-bold text-[#60716E] dark:text-zinc-300 hover:text-[#0F6B63] transition cursor-pointer min-h-[48px]"
          >
            Back to Caseload
          </button>
          {!is404 && (
            <button
              onClick={() => refetchSnapshot()}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs font-bold transition cursor-pointer min-h-[48px]"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  const initials = snapshot.full_name
    ?.split(' ')
    ?.map(w => w[0])
    ?.join('')
    ?.slice(0, 2)
    ?.toUpperCase() || 'PT';

  // Observational alerts based strictly on existing data rules
  const clinicalAlerts = [];
  if (snapshot.status === 'No recent activity') {
    clinicalAlerts.push('No home exercise activity recorded within the last 7 days.');
  } else if (snapshot.status === 'Low recent activity') {
    clinicalAlerts.push('Adherence compliance rate is currently below the 50% threshold.');
  }
  if (!snapshot.active_program) {
    clinicalAlerts.push('Patient does not currently have an active care plan assigned.');
  }
  if (!snapshot.upcoming_appointment) {
    clinicalAlerts.push('No upcoming physiotherapy appointments are currently scheduled.');
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12 text-[#183B4A] dark:text-zinc-100">
      
      {/* 1. TOP NAVIGATION / BREADCRUMB */}
      <div className="flex items-center justify-between gap-4">
        <button 
          onClick={() => navigate('/doctor/patients')}
          className="inline-flex items-center gap-2 text-xs font-bold text-[#60716E] dark:text-zinc-400 hover:text-[#0F6B63] dark:hover:text-zinc-200 transition cursor-pointer min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Patients</span>
        </button>

        <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#0F6B63] dark:text-[#EEF5F1] bg-[#EEF5F1] dark:bg-zinc-800 px-3 py-1 rounded-full border border-[#0F6B63]/10 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-[#0F6B63]" />
          <span>Caseload Verified</span>
        </span>
      </div>

      {/* 2. PATIENT HEADER / IDENTITY HERO */}
      <section className="relative overflow-hidden rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#0F6B63]/10 p-6 sm:p-8 lg:p-10 shadow-xs flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
          <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-white dark:bg-zinc-800 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center font-black text-2xl sm:text-3xl border border-[#0F6B63]/15 shrink-0 shadow-2xs">
            {initials}
          </div>
          <div className="space-y-1.5">
            <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#0F6B63] dark:text-[#EEF5F1] bg-[#0F6B63]/10 dark:bg-zinc-800 px-2.5 py-0.5 rounded-full border border-[#0F6B63]/10 inline-block">
              PATIENT SNAPSHOT
            </span>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#183B4A] dark:text-zinc-50 leading-tight">
                {snapshot.full_name}
              </h1>
              <span className={`inline-flex px-2.5 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border ${
                snapshot.status === 'Active' 
                  ? 'bg-white dark:bg-zinc-800 text-[#0F6B63] dark:text-[#EEF5F1] border-[#0F6B63]/20' 
                  : 'bg-[#F7F4ED] text-[#C9A86A] dark:bg-zinc-800 border-[#C9A86A]/30'
              }`}>
                {snapshot.status}
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#60716E] dark:text-zinc-400 font-medium pt-0.5">
              <span>Patient ID: <strong className="font-mono text-[#183B4A] dark:text-zinc-200">{snapshot.id?.slice(-8) || snapshot.id}</strong></span>
              {snapshot.date_of_birth && <span>• DOB: <strong className="text-[#183B4A] dark:text-zinc-200">{snapshot.date_of_birth}</strong></span>}
              <span>• Account: <strong className="text-[#183B4A] dark:text-zinc-200 capitalize">{snapshot.subscription_status}</strong></span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[#60716E] dark:text-zinc-400 font-medium pt-0.5">
              {snapshot.email && (
                <span className="flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-[#0F6B63]" /> {snapshot.email}
                </span>
              )}
              {snapshot.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-[#0F6B63]" /> {snapshot.phone}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2.5 w-full md:w-auto shrink-0">
          <button
            onClick={() => navigate(`/doctor/care-plans/${snapshot.id}`)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] hover:border-[#0F6B63]/30 transition cursor-pointer min-h-[48px] shadow-2xs"
          >
            <ClipboardList className="w-4 h-4 text-[#0F6B63]" />
            <span>Care Plan</span>
          </button>
          <button
            onClick={() => navigate(`/doctor/exercises/${snapshot.id}`)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs font-bold shadow-xs transition cursor-pointer min-h-[48px]"
          >
            <Dumbbell className="w-4 h-4" />
            <span>Exercises</span>
          </button>
        </div>
      </section>

      {/* 3. RECOVERY OVERVIEW & OBSERVATIONAL ATTENTION */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
        
        {/* RECOVERY OVERVIEW */}
        <section className="lg:col-span-2 bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xs flex flex-col justify-between">
          <div className="space-y-1 pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
            <div>
              <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                Progression Milestone
              </span>
              <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                Recovery Overview
              </h2>
            </div>
            {snapshot.current_stage && (
              <span className="text-[9px] font-extrabold uppercase tracking-widest text-[#0F6B63] dark:text-[#EEF5F1] bg-[#EEF5F1] dark:bg-zinc-800 px-2.5 py-1 rounded-full border border-[#0F6B63]/10">
                Stage {snapshot.current_stage}
              </span>
            )}
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-6 sm:gap-8 py-1">
            {/* Circular Progress Gauge */}
            <div className="relative w-32 h-32 sm:w-36 sm:h-36 flex items-center justify-center shrink-0">
              <svg className="absolute w-full h-full transform -rotate-90">
                <circle
                  cx="72"
                  cy="72"
                  r="58"
                  stroke="currentColor"
                  strokeWidth="9"
                  className="text-[#E5E0D6] dark:text-zinc-800"
                  fill="transparent"
                />
                <circle
                  cx="72"
                  cy="72"
                  r="58"
                  stroke="currentColor"
                  strokeWidth="9"
                  strokeLinecap="round"
                  className="text-[#0F6B63]"
                  fill="transparent"
                  strokeDasharray={2 * Math.PI * 58}
                  strokeDashoffset={2 * Math.PI * 58 * (1 - Math.min(Math.max(overallProgress, 0), 100) / 100)}
                />
              </svg>
              <div className="text-center space-y-0.5">
                <span className="text-3xl font-black text-[#0F6B63] dark:text-[#EEF5F1] block">
                  {overallProgress}%
                </span>
                <span className="text-[9px] uppercase tracking-wider font-extrabold text-[#60716E] dark:text-zinc-400 block">
                  Recovery
                </span>
              </div>
            </div>

            {/* Stage and pathway details */}
            <div className="space-y-3.5 flex-1 w-full text-center sm:text-left">
              <div>
                <p className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest">
                  Active Care Pathway
                </p>
                <p className="text-base sm:text-lg font-black text-[#183B4A] dark:text-zinc-100 mt-0.5">
                  {snapshot.active_program || 'No Active Care Pathway Assigned'}
                </p>
                {activePlan?.description && (
                  <p className="text-xs text-[#60716E] dark:text-zinc-400 mt-1 font-medium leading-relaxed">
                    {activePlan.description}
                  </p>
                )}
              </div>
              
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#E5E0D6]/50 dark:border-zinc-800 text-xs">
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-[#60716E] dark:text-zinc-400 font-bold block">Start Date</span>
                  <span className="font-bold text-[#183B4A] dark:text-zinc-200">
                    {activePlan?.start_date ? format(new Date(activePlan.start_date), 'MMM d, yyyy') : 'Pending'}
                  </span>
                </div>
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-[#60716E] dark:text-zinc-400 font-bold block">Target Date</span>
                  <span className="font-bold text-[#183B4A] dark:text-zinc-200">
                    {activePlan?.target_date ? format(new Date(activePlan.target_date), 'MMM d, yyyy') : 'Flexible'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CLINICAL ATTENTION / OBSERVATIONAL STATUS */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xs flex flex-col justify-between">
          <div className="space-y-1 pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800">
            <span className="text-[10px] font-extrabold text-[#C9A86A] uppercase tracking-widest block">
              Observational Status
            </span>
            <h3 className="font-extrabold text-base text-[#183B4A] dark:text-zinc-50 mt-0.5 flex items-center gap-2">
              <span>Clinical Attention</span>
              {clinicalAlerts.length > 0 && (
                <span className="w-2 h-2 rounded-full bg-[#C9A86A]" />
              )}
            </h3>
          </div>

          <div className="flex-1 flex flex-col justify-center py-2">
            {clinicalAlerts.length > 0 ? (
              <ul className="space-y-3">
                {clinicalAlerts.map((alert, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-xs text-[#60716E] dark:text-zinc-400 leading-relaxed font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#C9A86A] mt-1.5 shrink-0" />
                    <span>{alert}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-center py-4 space-y-1.5">
                <CheckCircle2 className="w-8 h-8 text-[#0F6B63] mx-auto" />
                <p className="text-xs text-[#0F6B63] font-black uppercase tracking-wider">Caseload Adherence Healthy</p>
                <p className="text-[11px] text-[#60716E] dark:text-zinc-400">
                  All indicators normal with consistent routine logging and no active alerts.
                </p>
              </div>
            )}
          </div>

          <p className="text-[9px] text-[#60716E] dark:text-zinc-500 pt-2 border-t border-[#E5E0D6]/40 dark:border-zinc-800 italic">
            * Observations reflect logged session compliance over the preceding 7 days.
          </p>
        </section>

      </div>

      {/* 4. ADHERENCE / ACTIVITY SUMMARY METRICS */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl p-4 sm:p-5 shadow-2xs space-y-1">
          <span className="text-[9px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
            Adherence Rate
          </span>
          <p className="text-2xl sm:text-3xl font-black text-[#0F6B63] dark:text-[#EEF5F1]">
            {snapshot.adherence_percentage}%
          </p>
          <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block font-medium">
            Overall log compliance
          </span>
        </div>

        <div className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl p-4 sm:p-5 shadow-2xs space-y-1">
          <span className="text-[9px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
            Prescriptions
          </span>
          <p className="text-2xl sm:text-3xl font-black text-[#183B4A] dark:text-zinc-100">
            {enrichedAssignments.length}
          </p>
          <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block font-medium">
            Active exercise routines
          </span>
        </div>

        <div className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl p-4 sm:p-5 shadow-2xs space-y-1">
          <span className="text-[9px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
            Recent Sessions
          </span>
          <p className="text-2xl sm:text-3xl font-black text-[#183B4A] dark:text-zinc-100">
            {snapshot.recent_activity?.length || 0}
          </p>
          <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block font-medium">
            Completions logged
          </span>
        </div>

        <div className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl p-4 sm:p-5 shadow-2xs space-y-1">
          <span className="text-[9px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
            Last Activity
          </span>
          <p className="text-base sm:text-lg font-black text-[#183B4A] dark:text-zinc-100 truncate pt-1">
            {snapshot.recent_activity && snapshot.recent_activity.length > 0
              ? format(new Date(snapshot.recent_activity[0].completed_at), 'MMM d')
              : 'Never'}
          </p>
          <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block font-medium">
            Most recent exercise
          </span>
        </div>
      </div>

      {/* 5. CURRENT CARE PLAN PATHWAY TIMELINE */}
      <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6 shadow-xs">
        <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
          <div>
            <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
              Clinical Pathway
            </span>
            <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
              Care Plan Treatment Stages
            </h2>
          </div>
          <button
            onClick={() => navigate(`/doctor/care-plans/${snapshot.id}`)}
            className="text-xs font-bold text-[#0F6B63] hover:underline flex items-center gap-0.5 cursor-pointer"
          >
            <span>Edit Pathway</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {snapshot.stages && snapshot.stages.length > 0 ? (
          <div>
            {/* Desktop Stage Track */}
            <div className="hidden md:grid grid-cols-3 gap-6 relative pt-2">
              <div className="absolute top-[27px] left-[15%] right-[15%] h-0.5 bg-[#E5E0D6] dark:bg-zinc-800 z-0" />

              {snapshot.stages.map((stg, index) => {
                const isCompleted = stg.status === 'completed';
                const isActive = stg.status === 'active';

                return (
                  <div key={index} className="flex flex-col items-center text-center space-y-3 z-10">
                    <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition ${
                      isCompleted 
                        ? 'bg-[#0F6B63] border-[#0F6B63] text-white shadow-2xs' 
                        : isActive 
                        ? 'bg-[#EEF5F1] dark:bg-zinc-800 border-[#0F6B63] text-[#0F6B63] ring-4 ring-[#EEF5F1] dark:ring-zinc-800 shadow-xs' 
                        : 'bg-[#F7F4ED] dark:bg-zinc-800 border-[#E5E0D6] dark:border-zinc-700 text-[#60716E]'
                    }`}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-4.5 h-4.5 text-white" />
                      ) : (
                        <span className="text-xs font-black">{index + 1}</span>
                      )}
                    </div>
                    <div>
                      <p className={`text-xs font-black ${isActive ? 'text-[#0F6B63] dark:text-[#EEF5F1]' : 'text-[#183B4A] dark:text-zinc-200'}`}>
                        {stg.title}
                      </p>
                      {isActive && (
                        <span className="inline-block mt-1 text-[8px] font-black uppercase tracking-widest text-[#0F6B63] bg-[#EEF5F1] dark:bg-zinc-800 px-2 py-0.5 rounded-full border border-[#0F6B63]/10">
                          Active Phase
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Mobile Vertical Track */}
            <div className="md:hidden space-y-5 relative pl-6">
              <div className="absolute top-3 bottom-3 left-[11px] w-0.5 bg-[#E5E0D6] dark:bg-zinc-800" />

              {snapshot.stages.map((stg, index) => {
                const isCompleted = stg.status === 'completed';
                const isActive = stg.status === 'active';

                return (
                  <div key={index} className="flex items-start gap-4 relative">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center border-2 shrink-0 z-10 -ml-[21px] ${
                      isCompleted 
                        ? 'bg-[#0F6B63] border-[#0F6B63] text-white' 
                        : isActive 
                        ? 'bg-[#EEF5F1] dark:bg-zinc-800 border-[#0F6B63] text-[#0F6B63] ring-4 ring-[#EEF5F1] dark:ring-zinc-800' 
                        : 'bg-[#F7F4ED] dark:bg-zinc-800 border-[#E5E0D6] dark:border-zinc-700 text-[#60716E]'
                    }`}>
                      {isCompleted ? (
                        <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                      ) : (
                        <span className="text-[10px] font-black">{index + 1}</span>
                      )}
                    </div>
                    <div>
                      <p className={`text-xs font-black ${isActive ? 'text-[#0F6B63] dark:text-[#EEF5F1]' : 'text-[#183B4A] dark:text-zinc-200'}`}>
                        {stg.title}
                      </p>
                      {isActive && (
                        <span className="inline-block mt-0.5 text-[8px] font-bold uppercase tracking-wider text-[#0F6B63] bg-[#EEF5F1] px-1.5 py-0.5 rounded">
                          Active Stage
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-xs text-[#60716E] italic py-3 text-center">
            No treatment staging configured for this care plan.
          </p>
        )}
      </section>

      {/* 6. CLINICIAN BENCHMARKS / RECOVERY GOALS & EXERCISE PRESCRIPTIONS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
        
        {/* CLINICIAN BENCHMARKS / RECOVERY GOALS */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Target Values (Clinician Owned)
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                  Recovery Goals
                </h2>
              </div>
              <span className="text-xs font-bold text-[#60716E] dark:text-zinc-400">
                {snapshot.goals?.length || 0} Goals
              </span>
            </div>

            {snapshot.goals && snapshot.goals.length > 0 ? (
              <div className="space-y-3.5 max-h-[380px] overflow-y-auto pr-1">
                {snapshot.goals.map((goal, index) => {
                  const isAchieved = goal.status === 'achieved';
                  const percentage = goal.target_value > 0 ? Math.min(100, Math.round(((goal.progress_value || 0) / goal.target_value) * 100)) : 0;
                  
                  return (
                    <div key={goal.goal_id || index} className="p-4 rounded-2xl border border-[#E5E0D6]/70 dark:border-zinc-800 bg-[#F7F4ED]/30 dark:bg-zinc-850/40 space-y-2.5">
                      <div className="flex justify-between items-start gap-2">
                        <h3 className="font-extrabold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100">
                          {goal.title}
                        </h3>
                        <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border shrink-0 ${
                          isAchieved 
                            ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                            : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                        }`}>
                          {goal.status}
                        </span>
                      </div>

                      {goal.target_value > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <div className="w-full bg-[#E5E0D6]/40 dark:bg-zinc-800 h-2 rounded-full overflow-hidden">
                            <div 
                              className="bg-[#0F6B63] h-full rounded-full transition-all duration-300" 
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                          <div className="flex justify-between text-[10px] text-[#60716E] dark:text-zinc-400 font-semibold">
                            <span>Current: <strong className="text-[#183B4A] dark:text-zinc-200">{goal.progress_value || 0} {goal.unit}</strong> ({percentage}%)</span>
                            <span className="flex items-center gap-1">
                              Target: <strong className="text-[#183B4A] dark:text-zinc-200">{goal.target_value} {goal.unit}</strong>
                              <Lock className="w-2.5 h-2.5 text-[#60716E]" />
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-[#60716E] italic py-6 text-center">
                No clinical recovery goals configured for this plan.
              </p>
            )}
          </div>

          <div className="pt-3 border-t border-[#E5E0D6]/60 dark:border-zinc-800">
            <button
              onClick={() => navigate(`/doctor/care-plans/${snapshot.id}`)}
              className="w-full text-center text-xs font-bold text-[#0F6B63] hover:underline cursor-pointer min-h-[36px]"
            >
              Configure Milestones & Benchmarks →
            </button>
          </div>
        </section>

        {/* EXERCISE PRESCRIPTIONS */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Assigned Regimen
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                  Exercise Prescriptions
                </h2>
              </div>
              <span className="text-xs font-bold text-[#60716E] dark:text-zinc-400">
                {enrichedAssignments.length} Active
              </span>
            </div>

            {enrichedAssignments.length > 0 ? (
              <div className="space-y-3.5 max-h-[380px] overflow-y-auto pr-1">
                {enrichedAssignments.map((assignment, index) => (
                  <div 
                    key={assignment.id || index}
                    className="p-4 rounded-2xl border border-[#E5E0D6]/70 dark:border-zinc-800 bg-[#F7F4ED]/30 dark:bg-zinc-850/40 space-y-2"
                  >
                    <div className="flex justify-between items-start gap-2">
                      <div>
                        <h3 className="font-extrabold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100">
                          {assignment.title}
                        </h3>
                        <span className="inline-block mt-0.5 text-[8px] font-black uppercase tracking-wider text-[#0F6B63] bg-[#EEF5F1] dark:bg-zinc-800 px-1.5 py-0.5 rounded border border-[#0F6B63]/10">
                          {assignment.category}
                        </span>
                      </div>
                      <span className="text-[10px] font-extrabold text-[#0F6B63] bg-[#EEF5F1] dark:bg-zinc-800 px-2 py-0.5 rounded-md border border-[#0F6B63]/10 shrink-0">
                        {assignment.sets} sets × {assignment.reps} reps
                      </span>
                    </div>

                    <div className="flex justify-between items-center text-[10px] text-[#60716E] dark:text-zinc-400 pt-1 font-medium">
                      <span>Frequency: <strong>{assignment.frequency || 'Daily'}</strong></span>
                      <span>Status: <strong className="capitalize">{assignment.status}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#60716E] italic py-6 text-center">
                No exercise prescriptions currently assigned for this patient.
              </p>
            )}
          </div>

          <div className="pt-3 border-t border-[#E5E0D6]/60 dark:border-zinc-800">
            <button
              onClick={() => navigate(`/doctor/exercises/${snapshot.id}`)}
              className="w-full text-center text-xs font-bold text-[#0F6B63] hover:underline cursor-pointer min-h-[36px]"
            >
              Manage Prescriptions in Exercise Studio →
            </button>
          </div>
        </section>

      </div>

      {/* 7. RECENT RECOVERY ACTIVITY & APPOINTMENT STATUS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 sm:gap-8">
        
        {/* RECENT RECOVERY ACTIVITY TIMELINE */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Patient Workout Logs
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                  Recent Recovery Activity
                </h2>
              </div>
              <span className="text-xs font-bold text-[#60716E] dark:text-zinc-400">
                Verified logs
              </span>
            </div>

            {snapshot.recent_activity && snapshot.recent_activity.length > 0 ? (
              <div className="space-y-4 relative pl-6 pr-1 max-h-[360px] overflow-y-auto">
                <div className="absolute top-2 bottom-2 left-[7px] w-0.5 bg-[#E5E0D6] dark:bg-zinc-800" />

                {snapshot.recent_activity.map((activity, index) => (
                  <div key={index} className="relative space-y-1.5">
                    <div className="absolute -left-[23px] top-1.5 w-2.5 h-2.5 rounded-full bg-[#0F6B63] ring-4 ring-[#EEF5F1] dark:ring-zinc-900" />
                    
                    <div className="flex justify-between items-start gap-2">
                      <h3 className="font-bold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100">
                        {activity.exercise_name}
                      </h3>
                      <span className="text-[10px] text-[#60716E] dark:text-zinc-400 font-semibold shrink-0">
                        {format(new Date(activity.completed_at), 'MMM d, h:mm a')}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-[#60716E] dark:text-zinc-400 font-medium">
                      <span>Logged: <strong className="text-[#183B4A] dark:text-zinc-200">{activity.completed_sets} sets × {activity.completed_reps} reps</strong></span>
                      <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border ${
                        activity.completion_status === 'completed'
                          ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                          : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                      }`}>
                        {activity.completion_status}
                      </span>
                    </div>

                    {activity.notes && (
                      <p className="text-[10px] text-[#60716E] dark:text-zinc-400 italic bg-[#F7F4ED]/40 dark:bg-zinc-800/40 p-2.5 border border-[#E5E0D6]/40 dark:border-zinc-800 rounded-xl leading-relaxed">
                        "{activity.notes}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-[#60716E] italic py-8 text-center">
                No recent exercise completions logged by this patient.
              </p>
            )}
          </div>
        </section>

        {/* RECENT / NEXT APPOINTMENTS */}
        <section className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-5 shadow-xs flex flex-col justify-between">
          <div className="space-y-4">
            <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800 flex justify-between items-center">
              <div>
                <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
                  Consultation Schedule
                </span>
                <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
                  Upcoming Appointment
                </h2>
              </div>
              <Calendar className="w-4 h-4 text-[#0F6B63]" />
            </div>

            <div className="flex-1 flex flex-col justify-center py-2">
              {snapshot.upcoming_appointment ? (
                <div className="p-5 bg-[#F7F4ED]/40 dark:bg-zinc-850/40 border border-[#E5E0D6]/70 dark:border-zinc-800 rounded-2xl space-y-3.5 shadow-2xs">
                  <div className="flex justify-between items-start gap-2">
                    <div>
                      <h3 className="font-extrabold text-sm sm:text-base text-[#183B4A] dark:text-zinc-100">
                        {snapshot.upcoming_appointment.doctor_name}
                      </h3>
                      <p className="text-[11px] text-[#60716E] dark:text-zinc-400 mt-0.5">
                        Consultation: {snapshot.upcoming_appointment.reason || 'Physiotherapy Review'}
                      </p>
                    </div>
                    <span className="inline-flex px-2.5 py-1 rounded-full text-[8px] font-black uppercase tracking-wider bg-[#EEF5F1] text-[#0F6B63] border border-[#0F6B63]/10">
                      {snapshot.upcoming_appointment.status}
                    </span>
                  </div>

                  <div className="flex gap-4 text-xs text-[#60716E] dark:text-zinc-400 pt-3 border-t border-[#E5E0D6]/50 dark:border-zinc-800 font-semibold">
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-[#0F6B63]" />
                      {snapshot.upcoming_appointment.appointment_date}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-[#0F6B63]" />
                      {snapshot.upcoming_appointment.time_slot}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 space-y-1.5">
                  <Clock className="w-8 h-8 text-[#60716E] mx-auto" />
                  <p className="font-bold text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100">
                    No upcoming appointments scheduled
                  </p>
                  <p className="text-[11px] text-[#60716E] dark:text-zinc-400">
                    No future consultation sessions are currently on the calendar for this patient.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-[#E5E0D6]/60 dark:border-zinc-800">
            <button
              onClick={() => navigate('/doctor/dashboard')}
              className="w-full text-center text-xs font-bold text-[#0F6B63] hover:underline cursor-pointer min-h-[36px]"
            >
              View Full Clinical Agenda on Dashboard →
            </button>
          </div>
        </section>

      </div>

      {/* 8. QUICK ACTIONS WORKSPACES */}
      <section className="bg-[#F7F4ED] dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-4 shadow-xs">
        <div className="pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800">
          <span className="text-[10px] font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-widest block">
            Clinician Shortcuts
          </span>
          <h2 className="text-lg sm:text-xl font-black text-[#183B4A] dark:text-zinc-50 mt-0.5">
            Quick Clinical Actions
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
          <button
            onClick={() => navigate(`/doctor/care-plans/${snapshot.id}`)}
            className="flex items-center justify-between p-4 bg-white dark:bg-zinc-800 rounded-2xl border border-[#E5E0D6] dark:border-zinc-700 hover:border-[#0F6B63]/40 transition text-left cursor-pointer min-h-[48px] shadow-2xs group"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#EEF5F1] dark:bg-zinc-700 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center shrink-0">
                <ClipboardList className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold text-[#183B4A] dark:text-zinc-100 block">Edit Care Plan</span>
                <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block">Stages & milestones</span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] transition" />
          </button>

          <button
            onClick={() => navigate(`/doctor/exercises/${snapshot.id}`)}
            className="flex items-center justify-between p-4 bg-white dark:bg-zinc-800 rounded-2xl border border-[#E5E0D6] dark:border-zinc-700 hover:border-[#0F6B63]/40 transition text-left cursor-pointer min-h-[48px] shadow-2xs group"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#EEF5F1] dark:bg-zinc-700 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center shrink-0">
                <Dumbbell className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold text-[#183B4A] dark:text-zinc-100 block">Manage Exercises</span>
                <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block">Prescription routine</span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] transition" />
          </button>

          <button
            onClick={() => navigate('/doctor/patients')}
            className="flex items-center justify-between p-4 bg-white dark:bg-zinc-800 rounded-2xl border border-[#E5E0D6] dark:border-zinc-700 hover:border-[#0F6B63]/40 transition text-left cursor-pointer min-h-[48px] shadow-2xs group"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#EEF5F1] dark:bg-zinc-700 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center shrink-0">
                <ArrowLeft className="w-4 h-4" />
              </div>
              <div>
                <span className="text-xs font-bold text-[#183B4A] dark:text-zinc-100 block">Patient Directory</span>
                <span className="text-[10px] text-[#60716E] dark:text-zinc-400 block">Return to caseload</span>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#60716E] group-hover:text-[#0F6B63] transition" />
          </button>
        </div>
      </section>

    </div>
  );
}
