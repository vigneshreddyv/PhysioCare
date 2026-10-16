import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
  ShieldCheck,
  ClipboardCheck,
  History,
  Calendar,
  Check,
  Leaf,
} from 'lucide-react';
import Button from '../../components/common/Button';

// Skeleton Loader matching the Recovery Journey layout
const CarePlanSkeleton = () => (
  <div className="max-w-3xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12">
    <div className="h-24 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-64 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-56 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-48 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
  </div>
);

export default function PatientCarePlan() {
  const navigate = useNavigate();

  // 1. Fetch care plans from the backend
  const { data: carePlans, isLoading, error } = useQuery({
    queryKey: ['carePlans'],
    queryFn: async () => {
      const response = await api.get('/care-plans');
      return response.data;
    },
    retry: 1
  });

  // 2. Select the appropriate active or newest care plan
  const carePlan = useMemo(() => {
    if (!carePlans || carePlans.length === 0) return null;
    const activePlans = carePlans.filter(p => p.status === 'active');
    if (activePlans.length > 0) {
      return activePlans.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
    }
    return [...carePlans].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
  }, [carePlans]);

  // 3. Fetch patient-safe clinical log history
  const carePlanId = carePlan?.id;
  const {
    data: historyLogs,
    isLoading: isHistoryLoading,
    error: historyError
  } = useQuery({
    queryKey: ['carePlanHistory', carePlanId],
    queryFn: async () => {
      const response = await api.get(`/care-plans/${carePlanId}/history`);
      return response.data;
    },
    enabled: !!carePlanId,
    retry: 1
  });

  // 4. Select active stage
  const activeStage = useMemo(() => {
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return null;
    return carePlan.stages.find(s => s.status === 'active') || carePlan.stages[0];
  }, [carePlan]);

  // Overall progression calculation (average of stages progress)
  const overallProgress = useMemo(() => {
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return 0;
    const total = carePlan.stages.length;
    const sum = carePlan.stages.reduce((acc, curr) => acc + (curr.progress || 0), 0);
    return Math.round(sum / total);
  }, [carePlan]);

  const activeStageIndex = useMemo(() => {
    if (!carePlan || !carePlan.stages || !activeStage) return 0;
    return carePlan.stages.findIndex(s => s.stage_id === activeStage.stage_id);
  }, [carePlan, activeStage]);

  // Translate clinical action slugs to friendly titles
  const formatHistoryAction = (action) => {
    const maps = {
      plan_created: 'Care Plan Initialized',
      stage_activated: 'Treatment Stage Started',
      stage_completed: 'Treatment Stage Completed',
      goal_updated: 'Recovery Goal Progress Logged',
      goal_achieved: 'Recovery Goal Achieved!',
      plan_paused: 'Rehabilitation Plan Paused',
      plan_active: 'Rehabilitation Plan Resumed',
      plan_completed: 'Rehabilitation Plan Completed',
      plan_cancelled: 'Rehabilitation Plan Cancelled'
    };
    return maps[action] || action.replace(/_/g, ' ');
  };

  // Display-only transform: never expose raw snake_case enum values in the UI
  const formatGoalStatus = (status) => {
    const labels = { achieved: 'Achieved', in_progress: 'In progress', pending: 'Pending', upcoming: 'Upcoming' };
    return labels[status] || String(status || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  };

  const formatHistoryDetail = (log) => {
    const human = (v) => formatGoalStatus(v);
    if (log.action === 'goal_updated') {
      return `Progress updated to ${human(log.new_value)}`;
    }
    if (log.action === 'stage_activated' || log.action === 'stage_completed') {
      return `Status changed from '${human(log.previous_value)}' to '${human(log.new_value)}'`;
    }
    if (log.previous_value && log.new_value) {
      return `State adjusted from '${human(log.previous_value)}' to '${human(log.new_value)}'`;
    }
    return '';
  };

  // Per-stage journey status (derived from real stage.status only)
  const getStageState = (stg) => {
    if (stg.status === 'completed') return 'completed';
    if (stg.status === 'active' || stg === activeStage) return 'current';
    return 'upcoming';
  };

  if (isLoading) {
    return <CarePlanSkeleton />;
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-full flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <ShieldCheck className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#1E2A2B] dark:text-zinc-100">Failed to Load Care Plan</h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 max-w-md mx-auto">
            {error.response?.data?.detail || "An error occurred while fetching your care plan. Please try again later."}
          </p>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()} className="text-xs py-2 px-5 font-bold cursor-pointer">
          Retry Connection
        </Button>
      </div>
    );
  }

  if (!carePlan) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-[#EEF5F1] dark:bg-zinc-900 rounded-full flex items-center justify-center mx-auto border border-[#E5E0D6]/40 dark:border-zinc-800">
          <ClipboardCheck className="w-8 h-8 text-[#1F4B45] dark:text-[#5FC2B8]" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-extrabold text-[#1E2A2B] dark:text-zinc-100">No Active Care Plan</h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 max-w-md mx-auto leading-relaxed">
            You currently do not have a clinically assigned care plan. Please consult with your therapist or book an appointment to set up your rehabilitation roadmap.
          </p>
        </div>
        <div className="flex justify-center gap-4">
          <Button variant="primary" onClick={() => navigate('/patient/book')} className="text-xs py-2.5 px-6 font-bold cursor-pointer min-h-[48px]">
            Book Appointment
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-7 sm:space-y-9 animate-fade-in p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12 text-[#1E2A2B] dark:text-zinc-100">

      {/* 0. PAGE HEADER (root tab — no back navigation) */}
      <header className="space-y-1 pt-1">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
          My Care Plan
        </h1>
        <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium">
          Your recovery journey
        </p>
      </header>

      {/* 1. CONNECTED RECOVERY JOURNEY */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
              Recovery Pathway
            </p>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
              {carePlan.title}
            </h2>
          </div>
          <span className="shrink-0 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] bg-[#EEF5F1] dark:bg-zinc-800 border border-[#1F4B45]/10 dark:border-zinc-700 px-3 py-1.5 rounded-full">
            {overallProgress}% overall
          </span>
        </div>

        <div className="relative">
          {/* the connecting line of the journey */}
          <div className="absolute top-5 bottom-5 left-[26px] w-0.5 bg-[#E5E0D6] dark:bg-zinc-800 rounded-full" aria-hidden="true" />
          {activeStageIndex > 0 && (
            <div
              className="absolute top-5 w-0.5 bg-[#1F4B45] dark:bg-[#5FC2B8] rounded-full left-[26px] transition-all"
              style={{ height: `calc(${(activeStageIndex / Math.max(carePlan.stages.length - 1, 1)) * 100}% - 1.25rem)` }}
              aria-hidden="true"
            />
          )}

          <div className="space-y-3">
            {carePlan.stages.map((stg, index) => {
              const state = getStageState(stg);
              const isCompleted = state === 'completed';
              const isCurrent = state === 'current';

              return (
                <div key={stg.stage_id || index} className="flex items-stretch gap-3 sm:gap-4">
                  {/* journey node */}
                  <div className="relative z-10 pt-5 sm:pt-6 shrink-0">
                    <div
                      className={`w-[26px] h-[26px] sm:w-[30px] sm:h-[30px] rounded-full flex items-center justify-center border-2 transition-all ${
                        isCompleted
                          ? 'bg-[#1F4B45] border-[#1F4B45] text-white'
                          : isCurrent
                          ? 'bg-[#C1694A] border-[#F6F2EA] dark:border-zinc-950 text-white shadow-md ring-4 ring-[#C1694A]/15'
                          : 'bg-[#F7F4ED] dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-700 text-[#60716E] dark:text-zinc-400'
                      }`}
                    >
                      {isCompleted ? (
                        <Check className="w-3.5 h-3.5" strokeWidth={3} />
                      ) : (
                        <span className="text-xs font-bold">{index + 1}</span>
                      )}
                    </div>
                  </div>

                  {/* stage card */}
                  <div
                    className={`flex-1 min-w-0 rounded-2xl border p-4 sm:p-5 transition ${
                      isCurrent
                        ? 'bg-[#C1694A]/[0.07] dark:bg-[#C1694A]/10 border-[#C1694A]/30'
                        : isCompleted
                        ? 'bg-white dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-800'
                        : 'bg-white/60 dark:bg-zinc-900/60 border-[#E5E0D6]/70 dark:border-zinc-800/70'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`text-xs font-extrabold uppercase tracking-widest ${isCurrent ? 'text-[#C1694A]' : 'text-[#60716E] dark:text-zinc-400'}`}>
                          Stage {index + 1}
                        </p>
                        <h3 className={`text-[15px] sm:text-base font-bold mt-0.5 leading-snug ${isCurrent || isCompleted ? 'text-[#1E2A2B] dark:text-zinc-100' : 'text-[#60716E] dark:text-zinc-400'}`}>
                          {stg.title || `Stage ${index + 1}`}
                        </h3>
                      </div>
                      <span
                        className={`shrink-0 inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold border ${
                          isCurrent
                            ? 'bg-[#C1694A] border-[#C1694A] text-white'
                            : isCompleted
                            ? 'bg-[#EEF5F1] dark:bg-zinc-800 border-[#1F4B45]/15 dark:border-zinc-700 text-[#1F4B45] dark:text-[#5FC2B8]'
                            : 'bg-[#F7F4ED] dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-700 text-[#60716E] dark:text-zinc-400'
                        }`}
                      >
                        {isCurrent ? 'Current' : isCompleted ? 'Completed' : 'Upcoming'}
                      </span>
                    </div>

                    {stg.description && (
                      <p className={`text-xs sm:text-[13px] mt-1.5 leading-relaxed ${isCurrent ? 'text-[#1E2A2B]/80 dark:text-zinc-200' : 'text-[#60716E] dark:text-zinc-400'}`}>
                        {stg.description}
                      </p>
                    )}

                    {/* labeled progress for current stage */}
                    {isCurrent && typeof stg.progress === 'number' && (
                      <div className="mt-3 space-y-1.5">
                        <div className="flex justify-between text-xs font-semibold">
                          <span className="text-[#1E2A2B] dark:text-zinc-200">Stage progress</span>
                          <span className="text-[#C1694A] font-bold">{stg.progress}%</span>
                        </div>
                        <div className="h-2 rounded-full bg-[#E5E0D6]/60 dark:bg-zinc-800 overflow-hidden" aria-label={`Current stage progress ${stg.progress}%`}>
                          <div className="h-full rounded-full bg-[#C1694A]" style={{ width: `${Math.min(Math.max(stg.progress, 0), 100)}%` }} />
                        </div>
                      </div>
                    )}
                    {isCompleted && typeof stg.progress === 'number' && (
                      <p className="text-xs font-semibold text-[#60716E] dark:text-zinc-400 mt-2">
                        Finished at {stg.progress}%
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 2. CURRENT STAGE FOCUS */}
      {activeStage && (
        <section className="rounded-3xl bg-[#1F4B45] dark:bg-[#17352F] text-white p-6 sm:p-8 space-y-5 shadow-lg shadow-[#1F4B45]/15">
          <div className="pointer-events-none absolute" aria-hidden="true" />
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-[#F6F2EA] bg-white/10 border border-white/15 px-3 py-1 rounded-full">
              <Calendar className="w-3.5 h-3.5" />
              Current Stage · {activeStageIndex + 1} of {carePlan.stages?.length || 1}
            </span>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight leading-tight">
              {activeStage.title}
            </h2>
            {carePlan.description && (
              <p className="text-sm text-white/70 font-medium max-w-lg">
                {carePlan.description}
              </p>
            )}
          </div>

          {/* dates (only when the plan actually has them) */}
          {(carePlan.start_date || carePlan.target_date) && (
            <div className="flex flex-wrap gap-2 text-xs font-semibold">
              {carePlan.start_date && (
                <span className="flex items-center gap-1.5 bg-white/10 border border-white/15 px-3 py-1.5 rounded-full">
                  <Calendar className="w-3.5 h-3.5" />
                  Start: {new Date(carePlan.start_date).toLocaleDateString()}
                </span>
              )}
              {carePlan.target_date && (
                <span className="flex items-center gap-1.5 bg-white/10 border border-white/15 px-3 py-1.5 rounded-full">
                  <Calendar className="w-3.5 h-3.5" />
                  Target: {new Date(carePlan.target_date).toLocaleDateString()}
                </span>
              )}
            </div>
          )}

          {activeStage.focus_areas && activeStage.focus_areas.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-widest text-white/70">
                Stage Focus Areas
              </p>
              <div className="flex flex-wrap gap-2">
                {activeStage.focus_areas.map((fa, i) => (
                  <span key={i} className="px-3 py-1 bg-white/10 border border-white/15 text-[#F6F2EA] text-xs font-semibold rounded-full">
                    {fa}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-2 pt-2 border-t border-white/15">
            <div className="flex justify-between text-xs font-bold">
              <span>Current Stage Completion</span>
              <span className="text-[#C9A86A] font-bold">{activeStage.progress || 0}%</span>
            </div>
            <div className="w-full bg-white/15 h-2.5 rounded-full overflow-hidden" aria-label={`Stage completion ${activeStage.progress || 0}%`}>
              <div
                className="bg-[#C9A86A] h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(Math.max(activeStage.progress || 0, 0), 100)}%` }}
              />
            </div>
          </div>
        </section>
      )}

      {/* 3. RECOVERY GOALS & BENCHMARKS */}
      <section className="space-y-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
            Benchmarks
          </p>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
            Recovery Goals
          </h2>
        </div>

        {!carePlan.goals || carePlan.goals.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60 p-6 text-center">
            <p className="text-sm text-[#60716E] dark:text-zinc-400 italic">
              No recovery goals have been assigned yet.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {carePlan.goals.map((item, index) => {
              const isAchieved = item.status === 'achieved';
              const percentage = item.target_value > 0 ? Math.min(100, Math.round(((item.progress_value || 0) / item.target_value) * 100)) : 0;

              return (
                <div
                  key={item.goal_id || index}
                  className={`p-4 sm:p-5 rounded-2xl border bg-white dark:bg-zinc-900 flex items-start gap-3.5 ${
                    isAchieved
                      ? 'border-[#1F4B45]/20 bg-[#EEF5F1]/50 dark:bg-zinc-800/40'
                      : 'border-[#E5E0D6] dark:border-zinc-800'
                  }`}
                >
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 border-2 ${
                      isAchieved
                        ? 'bg-[#1F4B45] border-[#1F4B45] text-white'
                        : 'border-[#E5E0D6] dark:border-zinc-700 text-transparent'
                    }`}
                  >
                    <Check className="w-4 h-4" strokeWidth={3} />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-100 leading-snug">
                        {item.title}
                      </h4>
                      <span
                        className={`shrink-0 text-xs font-bold px-2 py-0.5 rounded-full border ${
                          isAchieved
                            ? 'bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8] border-[#1F4B45]/15 dark:border-zinc-700'
                            : 'bg-[#C9A86A]/10 text-[#C9A86A] border-[#C9A86A]/20'
                        }`}
                      >
                        {formatGoalStatus(item.status)}
                      </span>
                    </div>
                    {item.description && (
                      <p className="text-xs text-[#60716E] dark:text-zinc-400 leading-relaxed">
                        {item.description}
                      </p>
                    )}

                    {item.target_value > 0 && item.progress_value !== undefined && item.progress_value !== null && (
                      <div className="space-y-1.5 pt-1">
                        <div className="w-full bg-[#E5E0D6]/50 dark:bg-zinc-800 h-2 rounded-full overflow-hidden" aria-label={`Goal progress ${percentage}%`}>
                          <div
                            className="bg-[#1F4B45] dark:bg-[#5FC2B8] h-full rounded-full transition-all duration-300"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                        <div className="flex justify-between items-center text-xs text-[#60716E] dark:text-zinc-400 font-semibold">
                          <span>Current: <strong className="text-[#1E2A2B] dark:text-zinc-200">{item.progress_value} {item.unit}</strong></span>
                          <span className="flex items-center gap-1">
                            Target: <strong className="text-[#1E2A2B] dark:text-zinc-200">{item.target_value} {item.unit}</strong>
                            <span title="Clinician target locked">🔒</span>
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4. CARE INSTRUCTIONS */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Care Instructions
          </h2>
        </div>

        {!carePlan.recommendations || carePlan.recommendations.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60 p-6 text-center">
            <p className="text-sm text-[#60716E] dark:text-zinc-400 italic">
              No therapist recommendations configured yet.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {carePlan.recommendations.map((rec, index) => {
              const isHighPriority = rec.priority === 'high';
              return (
                <div key={rec.recommendation_id || index} className="p-4 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 flex items-start gap-3.5">
                  <span
                    className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 ${
                      isHighPriority
                        ? 'bg-[#C9A86A]/15 text-[#C9A86A] border border-[#C9A86A]/30'
                        : 'bg-[#EEF5F1] dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8] border border-[#1F4B45]/10 dark:border-zinc-700'
                    }`}
                  >
                    {index + 1}
                  </span>
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <h4 className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100">
                        {rec.title}
                      </h4>
                      <span
                        className={`inline-flex items-center text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                          isHighPriority
                            ? 'bg-[#C9A86A]/10 text-[#C9A86A] border-[#C9A86A]/25'
                            : 'bg-[#F7F4ED] dark:bg-zinc-900 text-[#60716E] dark:text-zinc-400 border-[#E5E0D6] dark:border-zinc-700'
                        }`}
                      >
                        {rec.priority || 'Normal'} Priority
                      </span>
                    </div>
                    {rec.description && (
                      <p className="text-xs sm:text-[13px] text-[#60716E] dark:text-zinc-400 leading-relaxed">
                        {rec.description}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 5. CARE PLAN HISTORY */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Care Plan History
          </h2>
        </div>

        {isHistoryLoading ? (
          <div className="py-2 space-y-3">
            <div className="h-14 bg-[#E5E0D6]/60 dark:bg-zinc-800 rounded-2xl animate-pulse" />
            <div className="h-14 bg-[#E5E0D6]/60 dark:bg-zinc-800 rounded-2xl animate-pulse" />
          </div>
        ) : historyError ? (
          <p className="text-xs text-red-600 bg-red-50 dark:bg-red-950/20 p-3 rounded-xl border border-red-100 dark:border-red-900/30">
            Clinical history logs are temporarily unavailable.
          </p>
        ) : !historyLogs || historyLogs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60 p-6 text-center">
            <p className="text-sm text-[#60716E] dark:text-zinc-400 italic">
              No clinical updates logged yet.
            </p>
          </div>
        ) : (
          <div className="rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-2 sm:p-3">
            <div className="space-y-1 max-h-[320px] overflow-y-auto pr-1">
              {historyLogs.map((log, index) => (
                <div key={index} className="p-3 rounded-2xl flex items-start gap-3 hover:bg-[#F7F4ED]/60 dark:hover:bg-zinc-800/40 transition">
                  <div className="w-7 h-7 rounded-full bg-[#EEF5F1] dark:bg-zinc-800 border border-[#1F4B45]/10 dark:border-zinc-700 flex items-center justify-center shrink-0">
                    <Check className="w-3.5 h-3.5 text-[#1F4B45] dark:text-[#5FC2B8]" strokeWidth={3} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start gap-2">
                      <p className="text-[13px] font-bold text-[#1E2A2B] dark:text-zinc-100 truncate">
                        {formatHistoryAction(log.action)}
                      </p>
                      <span className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold shrink-0">
                        {new Date(log.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {formatHistoryDetail(log) && (
                      <p className="text-xs text-[#60716E] dark:text-zinc-400 mt-0.5 font-medium">
                        {formatHistoryDetail(log)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 6. ENCOURAGEMENT FOOTER */}
      <section className="relative overflow-hidden rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#1F4B45]/10 dark:border-zinc-800 p-6 sm:p-8">
        <div className="flex items-center gap-5">
          <div className="w-12 h-12 rounded-2xl bg-white/80 dark:bg-zinc-800 border border-[#1F4B45]/10 dark:border-zinc-700 flex items-center justify-center shrink-0">
            <Leaf className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
          </div>
          <p className="text-base sm:text-lg font-semibold italic text-[#1F4B45] dark:text-[#5FC2B8] leading-snug">
            "You are stronger than you think."
          </p>
        </div>
      </section>

    </div>
  );
}
