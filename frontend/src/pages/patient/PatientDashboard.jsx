import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../context/useAuth';
import {
  ArrowRight,
  CheckCircle2,
  Calendar,
  Dumbbell,
  FlaskConical,
  Activity,
  Footprints,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import api from '../../services/api';

function getGreeting() {
  const hour = new Date().getHours();
  if (hour >= 17 || hour < 5) return 'Good evening';
  if (hour < 12) return 'Good morning';
  return 'Good afternoon';
}

// Category → consistent lucide icon for exercise cards
function getCategoryIcon(category) {
  const c = (category || '').toLowerCase();
  if (c.includes('walk') || c.includes('gait') || c.includes('mobility')) return Footprints;
  if (c.includes('cardio') || c.includes('endurance')) return Activity;
  return Dumbbell;
}

// Skeleton Loader matching the Recovery Companion layout
const DashboardSkeleton = () => (
  <div className="max-w-3xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 pb-[84px]">
    <div className="flex items-center gap-4 pt-2">
      <div className="w-14 h-14 rounded-full bg-[#E5E0D6] dark:bg-zinc-800" />
      <div className="space-y-2 flex-1">
        <div className="h-7 w-56 bg-[#E5E0D6] dark:bg-zinc-800 rounded-xl" />
        <div className="h-4 w-40 bg-[#E5E0D6] dark:bg-zinc-800 rounded-lg" />
      </div>
    </div>
    <div className="h-64 bg-[#E5E0D6] dark:bg-zinc-800 rounded-[28px]" />
    <div className="h-72 bg-[#E5E0D6] dark:bg-zinc-800 rounded-[28px]" />
    <div className="h-44 bg-[#E5E0D6] dark:bg-zinc-800 rounded-[28px]" />
    <div className="h-40 bg-[#E5E0D6] dark:bg-zinc-800 rounded-[28px]" />
  </div>
);

export default function PatientDashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const patientFirstName = user?.first_name || (user?.full_name && typeof user.full_name === 'string' ? user.full_name.split(' ')[0] : '') || 'there';

  const initials = (user?.full_name || user?.first_name || 'P')
    .split(' ')
    .map((word) => word[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  // 1. Fetch appointments
  const { data: appointments = [], isLoading: isAppointmentsLoading } = useQuery({
    queryKey: ['patient-appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
  });

  // 2. Fetch care plans
  const { data: carePlans = [], isLoading: isCarePlansLoading } = useQuery({
    queryKey: ['patient-care-plans'],
    queryFn: async () => {
      const response = await api.get('/care-plans');
      return response.data;
    },
  });

  // 3. Fetch exercise assignments
  const { data: exerciseAssignments = [], isLoading: isAssignmentsLoading } = useQuery({
    queryKey: ['patient-exercise-assignments'],
    queryFn: async () => {
      const response = await api.get('/exercise-assignments');
      return response.data;
    },
  });

  // 4. Fetch adherence stats
  const { data: adherenceStats, isLoading: isStatsLoading } = useQuery({
    queryKey: ['patient-adherence-stats'],
    queryFn: async () => {
      const response = await api.get('/exercise-progress/stats');
      return response.data;
    },
  });

  // 5. Fetch catalog exercises to map titles
  const { data: catalogExercises = [], isLoading: isCatalogLoading } = useQuery({
    queryKey: ['catalogExercisesDashboard'],
    queryFn: async () => {
      const response = await api.get('/exercises');
      return response.data;
    },
  });

  // Derived Care Plan details
  const activeCarePlan = useMemo(() => {
    if (!carePlans || carePlans.length === 0) return null;
    const active = carePlans.find(p => p.status === 'active');
    if (active) return active;
    return [...carePlans].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
  }, [carePlans]);

  const activeStage = useMemo(() => {
    if (!activeCarePlan || !activeCarePlan.stages || activeCarePlan.stages.length === 0) return null;
    return activeCarePlan.stages.find(s => s.status === 'active') || activeCarePlan.stages[0];
  }, [activeCarePlan]);

  const overallProgress = useMemo(() => {
    if (!activeCarePlan || !activeCarePlan.stages || activeCarePlan.stages.length === 0) return 0;
    const total = activeCarePlan.stages.length;
    const sum = activeCarePlan.stages.reduce((acc, curr) => acc + (curr.progress || 0), 0);
    return Math.round(sum / total);
  }, [activeCarePlan]);

  // Derived assigned exercise routines for today
  const assignedExercises = useMemo(() => {
    if (!catalogExercises || !exerciseAssignments) return [];
    return exerciseAssignments.map(assign => {
      const ex = catalogExercises.find(e => String(e.id) === String(assign.exercise_id));
      if (!ex) return null;
      return {
        id: assign.id,
        title: ex.title,
        details: `${assign.sets} sets · ${assign.reps} reps`,
        completed: assign.status === 'completed',
        category: ex.category
      };
    }).filter(Boolean);
  }, [catalogExercises, exerciseAssignments]);

  const completedCount = assignedExercises.filter(e => e.completed).length;
  const totalCount = assignedExercises.length;

  const estimatedMinutes = useMemo(() => {
    if (!exerciseAssignments || exerciseAssignments.length === 0) return 0;
    const totalSecs = exerciseAssignments.reduce((acc, a) => acc + (a.duration_seconds || 300), 0);
    return Math.max(Math.round(totalSecs / 60), totalCount > 0 ? totalCount * 5 : 0);
  }, [exerciseAssignments, totalCount]);

  // Preserved Appointment Filtering & Sorting Logic
  const now = new Date();
  const candidates = [];

  for (const appt of appointments) {
    if (!(['confirmed', 'scheduled', 'in_progress'].includes(appt.status))) continue;
    try {
      const dateStr = appt.appointment_date;
      const timeStr = appt.time_slot || '';
      if (!dateStr || !timeStr) continue;
      const [timePart, modifier] = timeStr.trim().split(' ');
      let [hours, minutes] = timePart.split(':').map(Number);
      if (modifier === 'PM' && hours !== 12) hours += 12;
      if (modifier === 'AM' && hours === 12) hours = 0;
      const [year, month, day] = dateStr.split('-').map(Number);
      const apptDate = new Date(year, month - 1, day, hours, minutes, 0, 0);
      if (isNaN(apptDate.getTime())) continue;
      if (apptDate >= now) {
        candidates.push({ appointment: appt, date: apptDate });
      }
    } catch {} {
      continue;
    }
  }

  candidates.sort((a, b) => a.date - b.date);
  const nextAppointment = candidates.length > 0 ? candidates[0].appointment : null;

  const formatAppointmentDateTime = (appointment) => {
    const dateStr = appointment.appointment_date;
    const timeStr = appointment.time_slot || '';
    let formattedDate = dateStr;
    let formattedTime = timeStr;
    if (dateStr && timeStr) {
      try {
        const [timePart, modifier] = timeStr.trim().split(' ');
        let [hours, minutes] = timePart.split(':').map(Number);
        if (modifier === 'PM' && hours !== 12) hours += 12;
        if (modifier === 'AM' && hours === 12) hours = 0;
        const [year, month, day] = dateStr.split('-').map(Number);
        const apptDate = new Date(year, month - 1, day, hours, minutes, 0, 0);
        if (!isNaN(apptDate.getTime())) {
          formattedDate = apptDate.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
          });
          formattedTime = apptDate.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
          });
        }
      } catch {} {
        // fallback
      }
    }
    return { formattedDate, formattedTime };
  };

  const nextApptDetails = nextAppointment ? formatAppointmentDateTime(nextAppointment) : null;

  // Stage index for the "Stage N" label on the recovery hero
  const activeStageIndex = useMemo(() => {
    if (!activeCarePlan || !activeCarePlan.stages || !activeStage) return null;
    return activeCarePlan.stages.findIndex(s => s === activeStage);
  }, [activeCarePlan, activeStage]);

  if (isAppointmentsLoading || isCarePlansLoading || isAssignmentsLoading || isStatsLoading || isCatalogLoading) {
    return <DashboardSkeleton />;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-7 sm:space-y-9 animate-fade-in p-4 sm:p-6 pb-[84px] text-[#1E2A2B] dark:text-zinc-100">

      {/* 1. TOP GREETING */}
      <div className="flex items-center gap-4 pt-1">
        <button
          onClick={() => navigate('/patient/profile')}
          aria-label="View profile"
          className="w-14 h-14 shrink-0 rounded-full bg-[#1F4B45] text-[#F6F2EA] flex items-center justify-center text-base font-bold tracking-wide ring-2 ring-white shadow-sm cursor-pointer hover:opacity-90 transition"
        >
          {initials}
        </button>
        <div className="min-w-0">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
            {getGreeting()}, {patientFirstName} <span aria-hidden="true">👋</span>
          </h1>
          <p className="text-sm sm:text-[15px] text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
            Keep moving, you're doing great!
          </p>
        </div>
      </div>

      {/* 2. CURRENT RECOVERY STAGE — HERO */}
      <section className="relative overflow-hidden rounded-[28px] bg-[#1F4B45] dark:bg-[#17352F] text-white shadow-lg shadow-[#1F4B45]/15">
        {/* soft decorative depth */}
        <div className="pointer-events-none absolute -top-20 -right-16 w-64 h-64 rounded-full bg-[#EEF5F1]/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-10 w-56 h-56 rounded-full bg-[#C9A86A]/15 blur-3xl" />

        <div className="relative p-6 sm:p-8 space-y-6">
          <div className="flex flex-col-reverse sm:flex-row sm:items-center justify-between gap-6">
            <div className="space-y-2.5 min-w-0">
              <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-[#F6F2EA] bg-white/10 border border-white/15 px-3 py-1 rounded-full">
                <Sparkles className="w-3.5 h-3.5" />
                Current Stage
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight leading-tight">
                {activeStage?.title || activeCarePlan?.title || 'Active Rehabilitation'}
              </h2>
              <p className="text-sm text-white/70 font-medium">
                {activeStageIndex !== null && activeStage
                  ? `Stage ${activeStageIndex + 1}`
                  : 'Recovery journey'}
                {activeCarePlan?.title && activeStage?.title ? ` · ${activeCarePlan.title}` : ''}
              </p>
            </div>

            {/* Labeled progress ring */}
            <div className="flex items-center gap-5 shrink-0 self-start sm:self-auto">
              <div className="relative w-28 h-28 sm:w-32 sm:h-32 flex items-center justify-center">
                <svg className="absolute w-full h-full -rotate-90" viewBox="0 0 112 112">
                  <circle
                    cx="56" cy="56" r="48"
                    stroke="currentColor"
                    strokeWidth="9"
                    className="text-white/15"
                    fill="transparent"
                  />
                  <circle
                    cx="56" cy="56" r="48"
                    stroke="currentColor"
                    strokeWidth="9"
                    strokeLinecap="round"
                    className="text-[#C9A86A]"
                    fill="transparent"
                    strokeDasharray={2 * Math.PI * 48}
                    strokeDashoffset={2 * Math.PI * 48 * (1 - Math.min(Math.max(overallProgress, 0), 100) / 100)}
                  />
                </svg>
                <div className="text-center">
                  <span className="text-3xl font-bold block leading-none">{overallProgress}%</span>
                </div>
              </div>
              {/* adjacent textual label — never an unlabeled ring */}
              <div className="space-y-1">
                <p className="text-sm font-bold leading-tight">Overall Recovery</p>
                <p className="text-xs text-white/70 leading-snug max-w-[120px]">
                  Across {activeCarePlan?.stages?.length || 0} stages of your plan
                </p>
              </div>
            </div>
          </div>

          {/* Recovery path — real stages from the care plan */}
          {activeCarePlan?.stages?.length > 0 && (
            <div className="relative pt-2">
              <div className="absolute top-[27px] left-6 right-6 h-0.5 bg-white/15 rounded-full" />
              <div
                className="absolute top-[27px] left-6 h-0.5 bg-[#C9A86A] rounded-full transition-all"
                style={{
                  width: `calc((100% - 3rem) * ${Math.min(
                    (activeStageIndex + 1) / Math.max(activeCarePlan.stages.length - 1, 1),
                    1
                  )})`,
                }}
              />
              <div className="relative flex justify-between">
                {activeCarePlan.stages.slice(0, 5).map((stage, i) => {
                  const isDone = stage.status === 'completed';
                  const isCurrent = stage === activeStage;
                  return (
                    <div key={i} className="flex flex-col items-center gap-2 w-16 sm:w-20">
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 ${
                          isCurrent
                            ? 'bg-[#C1694A] border-[#F6F2EA] text-white shadow-md'
                            : isDone
                            ? 'bg-[#C9A86A] border-white/60 text-[#1F4B45]'
                            : 'bg-[#1F4B45] border-white/25 text-white/60'
                        }`}
                      >
                        {isDone ? <CheckCircle2 className="w-4 h-4" /> : i + 1}
                      </div>
                      <span
                        className={`text-xs font-semibold text-center leading-tight line-clamp-2 ${
                          isCurrent ? 'text-white' : 'text-white/60'
                        }`}
                      >
                        {stage.title || `Stage ${i + 1}`}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <p className="text-sm text-white/70 italic font-medium pt-1">
            "Consistent effort leads to lasting change."
          </p>
        </div>
      </section>

      {/* 3. TODAY'S RECOVERY PLAN */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
              Today's Recovery Plan
            </h3>
            <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
              {totalCount > 0
                ? `${completedCount} of ${totalCount} exercises completed · ~${estimatedMinutes} min`
                : 'Your prescribed daily movements will appear here'}
            </p>
          </div>
          {totalCount > 0 && (
            <button
              onClick={() => navigate('/patient/exercises')}
              className="shrink-0 text-sm font-bold text-[#C1694A] hover:text-[#a85538] transition cursor-pointer min-h-[44px] px-1"
            >
              View All
            </button>
          )}
        </div>

        {totalCount > 0 ? (
          <div className="space-y-3.5">
            {/* Exercise cards */}
            <div className="space-y-3">
              {assignedExercises.map((task) => {
                const Icon = getCategoryIcon(task.category);
                return (
                  <div
                    key={task.id}
                    className={`flex items-center gap-4 p-4 rounded-2xl border bg-white dark:bg-zinc-900 transition ${
                      task.completed
                        ? 'border-[#1F4B45]/15 bg-[#EEF5F1]/50 dark:bg-zinc-800/40'
                        : 'border-[#E5E0D6] dark:border-zinc-800'
                    }`}
                  >
                    <div
                      className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                        task.completed
                          ? 'bg-[#1F4B45] text-white'
                          : 'bg-[#EEF5F1] text-[#1F4B45] dark:bg-zinc-800 dark:text-[#5FC2B8]'
                      }`}
                    >
                      <Icon className="w-5 h-5" strokeWidth={2.2} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p
                        className={`text-[15px] font-bold truncate ${
                          task.completed
                            ? 'text-[#60716E] dark:text-zinc-400 line-through decoration-[#C1694A]/40'
                            : 'text-[#1E2A2B] dark:text-zinc-100'
                        }`}
                      >
                        {task.title}
                      </p>
                      <p className="text-[13px] text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
                        {task.details}
                      </p>
                    </div>
                    {task.completed ? (
                      <CheckCircle2 className="w-6 h-6 text-[#1F4B45] fill-[#1F4B45] stroke-white shrink-0" />
                    ) : (
                      <span
                        aria-label="Pending"
                        className="w-6 h-6 rounded-full border-2 border-[#E5E0D6] dark:border-zinc-700 shrink-0"
                      />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Primary CTA */}
            <button
              onClick={() => navigate('/patient/exercises')}
              className="w-full flex items-center justify-center gap-2 py-3.5 px-6 rounded-2xl bg-[#1F4B45] hover:bg-[#17352F] text-white font-bold text-[15px] shadow-md shadow-[#1F4B45]/20 transition-all cursor-pointer min-h-[48px]"
            >
              <span>{completedCount === totalCount ? 'Review Session' : 'Continue Exercise'}</span>
              <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        ) : (
          <div className="text-center py-8 px-6 space-y-3 rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60">
            <div className="w-12 h-12 rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center mx-auto text-[#1F4B45] dark:text-[#5FC2B8]">
              <Dumbbell className="w-6 h-6" />
            </div>
            <div>
              <p className="font-bold text-[15px] text-[#1E2A2B] dark:text-zinc-100">No exercises assigned for today</p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1">
                Explore your care plan or consult with your physiotherapist.
              </p>
            </div>
            <button
              onClick={() => navigate('/patient/exercises')}
              className="inline-flex items-center justify-center gap-1.5 px-5 rounded-xl bg-[#1F4B45] hover:bg-[#17352F] text-white text-sm font-bold transition cursor-pointer min-h-[48px]"
            >
              <span>Browse Exercises</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </section>

      {/* 4. NEXT APPOINTMENT */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Next Appointment
          </h3>
          {nextAppointment && (
            <button
              onClick={() => navigate('/patient/appointments')}
              className="shrink-0 text-sm font-bold text-[#C1694A] hover:text-[#a85538] transition cursor-pointer min-h-[44px] px-1"
            >
              View All
            </button>
          )}
        </div>

        {nextAppointment ? (
          <div className="flex items-center gap-4 p-4 sm:p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED] dark:bg-zinc-900">
            <div className="w-12 h-12 rounded-2xl bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center shrink-0 text-[#1F4B45] dark:text-[#5FC2B8]">
              <Calendar className="w-5 h-5" strokeWidth={2} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[15px] sm:text-base font-bold text-[#1E2A2B] dark:text-zinc-100 leading-tight truncate">
                {nextApptDetails?.formattedDate} · {nextApptDetails?.formattedTime}
              </p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 font-medium mt-1 truncate">
                {nextAppointment.doctor_name || 'Physiotherapist'}
                {nextAppointment.reason ? ` · ${nextAppointment.reason}` : ''}
              </p>
            </div>
            <button
              onClick={() => navigate('/patient/appointments')}
              className="shrink-0 inline-flex items-center justify-center px-4 py-2.5 rounded-xl bg-[#C1694A]/10 hover:bg-[#C1694A]/20 text-[#C1694A] text-[13px] font-bold transition cursor-pointer min-h-[44px]"
            >
              View Details
            </button>
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED] dark:bg-zinc-900">
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-bold text-[#1E2A2B] dark:text-zinc-100">No upcoming sessions booked.</p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-0.5 font-medium">
                Regular sessions keep your recovery on track.
              </p>
            </div>
            <button
              onClick={() => navigate('/patient/book')}
              className="inline-flex items-center justify-center gap-1.5 px-5 py-3 rounded-xl bg-[#1F4B45] hover:bg-[#17352F] text-white text-sm font-bold shadow-sm transition cursor-pointer min-h-[48px] shrink-0"
            >
              <span>Book Session</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </section>

      {/* 5. IMPORTANT CLINICAL SERVICES */}
      <section className="space-y-4">
        <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
          Clinical Services
        </h3>
        <button
          onClick={() => navigate('/patient/laboratory')}
          className="w-full flex items-center gap-4 p-4 sm:p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-[#1F4B45]/30 hover:shadow-sm transition text-left cursor-pointer group"
        >
          <div className="w-12 h-12 rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center shrink-0 text-[#1F4B45] dark:text-[#5FC2B8]">
            <FlaskConical className="w-5 h-5" strokeWidth={2} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-bold text-[#1E2A2B] dark:text-zinc-100">Laboratory Tests</p>
            <p className="text-[13px] text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
              Blood tests, panels and home sample collection
            </p>
          </div>
          <span className="w-10 h-10 rounded-full border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center shrink-0 text-[#60716E] dark:text-zinc-400 group-hover:bg-[#1F4B45] group-hover:text-white group-hover:border-[#1F4B45] transition">
            <ArrowRight className="w-4 h-4" />
          </span>
        </button>
      </section>

      {/* 6. RECOVERY AT A GLANCE */}
      <section className="space-y-4">
        <div>
          <h3 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Recovery at a Glance
          </h3>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
            Small steps, tracked with care
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="p-4 sm:p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2">
            <TrendingUp className="w-5 h-5 text-[#C1694A]" strokeWidth={2.2} />
            <p className="text-xl sm:text-2xl font-bold text-[#1E2A2B] dark:text-zinc-100 leading-none pt-1">
              {activeStage?.progress || overallProgress || 0}%
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Stage Progress
            </p>
            <div className="h-1.5 rounded-full bg-[#E5E0D6] dark:bg-zinc-800 overflow-hidden" aria-label={`Stage progress ${activeStage?.progress || overallProgress || 0}%`}>
              <div
                className="h-full rounded-full bg-[#1F4B45]"
                style={{ width: `${Math.min(activeStage?.progress || overallProgress || 0, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-4 sm:p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2">
            <Sparkles className="w-5 h-5 text-[#C9A86A]" strokeWidth={2.2} />
            <p className="text-xl sm:text-2xl font-bold text-[#1F4B45] dark:text-[#5FC2B8] leading-none pt-1">
              {adherenceStats?.percentage || 0}%
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Adherence
            </p>
            <div className="h-1.5 rounded-full bg-[#E5E0D6] dark:bg-zinc-800 overflow-hidden" aria-label={`Adherence ${adherenceStats?.percentage || 0}%`}>
              <div
                className="h-full rounded-full bg-[#C9A86A]"
                style={{ width: `${Math.min(adherenceStats?.percentage || 0, 100)}%` }}
              />
            </div>
          </div>

          <div className="p-4 sm:p-5 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2">
            <CheckCircle2 className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" strokeWidth={2.2} />
            <p className="text-xl sm:text-2xl font-bold text-[#1E2A2B] dark:text-zinc-100 leading-none pt-1">
              {adherenceStats?.completed || completedCount || 0}
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Sessions Done
            </p>
            <div className="text-xs text-[#60716E]/80 dark:text-zinc-500 font-medium pt-1">
              {totalCount > 0 ? `${completedCount}/${totalCount} today` : 'this week'}
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
