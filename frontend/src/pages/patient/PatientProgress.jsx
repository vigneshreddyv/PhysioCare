import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
  Calendar,
  AlertTriangle,
  History,
  CheckCircle2,
  TrendingUp,
  Check,
  Flag,
} from 'lucide-react';
import Button from '../../components/common/Button';

// Skeleton Loader matching the Recovery Analytics layout
const ProgressSkeleton = () => (
  <div className="max-w-3xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12">
    <div className="h-64 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-56 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4">
      <div className="h-28 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
      <div className="h-28 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
      <div className="h-28 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
    </div>
    <div className="h-48 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-40 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
  </div>
);

export default function PatientProgress() {

  // 1. Fetch Care Plans (Independent)
  const { 
    data: carePlans, 
    isLoading: isCarePlansLoading, 
    error: carePlansError 
  } = useQuery({
    queryKey: ['carePlans'],
    queryFn: async () => {
      const response = await api.get('/care-plans');
      return response.data;
    },
    retry: 1
  });

  // 2. Fetch Exercise Progress Adherence stats (Independent)
  const { 
    data: adherenceStats, 
    isLoading: isStatsLoading, 
    error: statsError,
    refetch: refetchStats
  } = useQuery({
    queryKey: ['exerciseAdherenceStats'],
    queryFn: async () => {
      const response = await api.get('/exercise-progress/stats');
      return response.data;
    },
    retry: 1
  });

  // Derived Care Plan details
  const carePlan = useMemo(() => {
    if (!carePlans || carePlans.length === 0) return null;
    const active = carePlans.find(p => p.status === 'active');
    if (active) return active;
    return [...carePlans].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
  }, [carePlans]);

  const activeStage = useMemo(() => {
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return null;
    return carePlan.stages.find(s => s.status === 'active') || carePlan.stages[0];
  }, [carePlan]);

  const activeStageIndex = useMemo(() => {
    if (!carePlan || !carePlan.stages || !activeStage) return 0;
    return carePlan.stages.findIndex(s => s.stage_id === activeStage.stage_id);
  }, [carePlan, activeStage]);

  const overallProgress = useMemo(() => {
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return 0;
    const total = carePlan.stages.length;
    const sum = carePlan.stages.reduce((acc, curr) => acc + (curr.progress || 0), 0);
    return Math.round(sum / total);
  }, [carePlan]);

  // Display-only transform: never expose raw snake_case enum values in the UI
  const formatSessionStatus = (status) => {
    const labels = { completed: 'Completed', partial: 'Partial', in_progress: 'In progress', assigned: 'Assigned' };
    return labels[status] || String(status || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return isoString;
    }
  };

  // Recovery milestones derived ONLY from real application data
  // (completed stages + achieved/in-progress goals from the care plan)
  const milestones = useMemo(() => {
    if (!carePlan) return [];
    const items = [];

    (carePlan.stages || []).forEach((stg, index) => {
      if (stg.status === 'completed') {
        items.push({
          id: `stage-${stg.stage_id || index}`,
          title: stg.title || `Stage ${index + 1} completed`,
          meta: 'Pathway stage',
          status: 'done',
        });
      }
    });

    (carePlan.goals || []).forEach((goal, index) => {
      if (!goal?.title) return;
      if (goal.status === 'achieved') {
        items.push({
          id: `goal-${goal.goal_id || index}`,
          title: goal.title,
          meta: 'Recovery goal',
          status: 'done',
        });
      } else {
        items.push({
          id: `goal-${goal.goal_id || index}`,
          title: goal.title,
          meta: 'Recovery goal',
          status: goal.status === 'in_progress' ? 'in_progress' : 'upcoming',
        });
      }
    });

    return items;
  }, [carePlan]);

  if (isCarePlansLoading || isStatsLoading) {
    return <ProgressSkeleton />;
  }

  if (carePlansError || statsError) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-full flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#1E2A2B] dark:text-zinc-100">Failed to Load Progress Stats</h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 max-w-md mx-auto">
            We could not fetch your longitudinal progress calculations. Please check your network and try again.
          </p>
        </div>
        <Button variant="outline" onClick={() => refetchStats()} className="text-xs py-2 px-5 font-bold cursor-pointer">
          Retry Connection
        </Button>
      </div>
    );
  }

  const weeklyLog = adherenceStats?.log || [];
  const hasLog = weeklyLog.length > 0;

  return (
    <div className="max-w-3xl mx-auto space-y-7 sm:space-y-9 animate-fade-in p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12 text-[#1E2A2B] dark:text-zinc-100">

      {/* 0. PAGE HEADER (root tab — no back navigation) */}
      <header className="space-y-1 pt-1">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
          My Progress
        </h1>
        <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium">
          Track your recovery
        </p>
      </header>

      {/* 1. OVERALL RECOVERY */}
      <section className="relative overflow-hidden rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#1F4B45]/10 dark:border-zinc-800 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row items-center gap-6 sm:gap-8">
          {/* Labeled ring — dominant, with adjacent caption (never unlabeled) */}
          <div className="relative w-40 h-40 sm:w-44 sm:h-44 flex items-center justify-center shrink-0">
            <svg className="absolute w-full h-full -rotate-90" viewBox="0 0 160 160">
              <circle
                cx="80" cy="80" r="66"
                stroke="currentColor"
                strokeWidth="13"
                className="text-[#E5E0D6] dark:text-zinc-800"
                fill="transparent"
              />
              <circle
                cx="80" cy="80" r="66"
                stroke="currentColor"
                strokeWidth="13"
                strokeLinecap="round"
                className="text-[#C1694A]"
                fill="transparent"
                strokeDasharray={2 * Math.PI * 66}
                strokeDashoffset={2 * Math.PI * 66 * (1 - Math.min(Math.max(overallProgress, 0), 100) / 100)}
              />
            </svg>
            <div className="text-center">
              <span className="text-4xl font-bold text-[#1E2A2B] dark:text-zinc-100 block leading-none tracking-tight">
                {overallProgress}%
              </span>
              <span className="text-xs font-semibold text-[#60716E] dark:text-zinc-400 block mt-1.5">
                completed
              </span>
            </div>
          </div>

          <div className="space-y-2 text-center sm:text-left min-w-0">
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#1F4B45] dark:text-[#5FC2B8]">
              Overall Recovery
            </p>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
              {overallProgress >= 70
                ? 'On track with your current plan'
                : 'Every logged session moves you forward'}
            </h2>
            {activeStage && (
              <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium inline-flex items-center gap-1.5 flex-wrap justify-center sm:justify-start">
                <Calendar className="w-3.5 h-3.5 text-[#1F4B45] dark:text-[#5FC2B8]" />
                <span>
                  Current stage: <strong className="text-[#1E2A2B] dark:text-zinc-200 font-bold">{activeStage.title}</strong>
                  {activeStageIndex >= 0 && (
                    <span className="text-[#60716E] dark:text-zinc-400"> · stage {activeStageIndex + 1} of {carePlan.stages?.length || 1}</span>
                  )}
                </span>
              </p>
            )}
          </div>
        </div>
      </section>

      {/* 2. WEEKLY ADHERENCE — real daily log, labeled bars */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
              This Week
            </p>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
              Weekly Adherence
            </h2>
          </div>
          <span className="shrink-0 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] bg-[#EEF5F1] dark:bg-zinc-800 border border-[#1F4B45]/10 dark:border-zinc-700 px-3 py-1.5 rounded-full">
            {adherenceStats?.percentage || 0}% logged
          </span>
        </div>

        <div className="rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 sm:p-8">
          {hasLog ? (
            <>
              <div className="flex items-end justify-between gap-2 sm:gap-3 h-36" role="img" aria-label="Daily adherence for this week">
                {weeklyLog.map((item, idx) => {
                  const isDone = item.completed === true;
                  const isPartial = item.completed === false;
                  // Bar heights: complete = full, partial = half, rest = minimal
                  const height = isDone ? '100%' : isPartial ? '52%' : '10%';
                  const barColor = isDone
                    ? 'bg-[#1F4B45] dark:bg-[#5FC2B8]'
                    : isPartial
                    ? 'bg-[#C9A86A]'
                    : 'bg-[#E5E0D6] dark:bg-zinc-700/60';
                  const stateLabel = isDone ? 'Complete' : isPartial ? 'Partial' : 'Rest';
                  return (
                    <div key={idx} className="flex-1 flex flex-col items-center justify-end gap-2 h-full min-w-0">
                      <div
                        className={`w-full max-w-[34px] rounded-lg ${barColor} transition-all`}
                        style={{ height }}
                        title={`${item.day}: ${stateLabel}`}
                      />
                      <span className="text-xs font-semibold text-[#60716E] dark:text-zinc-400 truncate max-w-full">
                        {item.day}
                      </span>
                    </div>
                  );
                })}
              </div>
              {/* labeled legend — colors always explained */}
              <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 pt-5 mt-5 border-t border-[#E5E0D6]/60 dark:border-zinc-800">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#60716E] dark:text-zinc-400">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#1F4B45] dark:bg-[#5FC2B8]" /> Complete
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#60716E] dark:text-zinc-400">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#C9A86A]" /> Partial
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#60716E] dark:text-zinc-400">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#E5E0D6] dark:bg-zinc-700" /> Rest
                </span>
              </div>
            </>
          ) : (
            <div className="text-center py-6 space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center mx-auto text-[#1F4B45] dark:text-[#5FC2B8]">
                <TrendingUp className="w-6 h-6" />
              </div>
              <p className="font-bold text-[15px] text-[#1E2A2B] dark:text-zinc-100">No logged activity this week</p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400">
                Complete your prescribed exercises and your daily rhythm will appear here.
              </p>
            </div>
          )}
        </div>
      </section>

      {/* 3. KEY RECOVERY METRICS */}
      <section className="space-y-4">
        <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
          Key Recovery Metrics
        </h2>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div className="rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 sm:p-5 space-y-2">
            <CheckCircle2 className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" strokeWidth={2.2} />
            <p className="text-2xl sm:text-3xl font-bold text-[#1E2A2B] dark:text-zinc-100 leading-none pt-1">
              {adherenceStats?.completed || 0}
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Sessions Completed
            </p>
          </div>

          <div className="rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 sm:p-5 space-y-2">
            <ClipboardIcon />
            <p className="text-2xl sm:text-3xl font-bold text-[#1E2A2B] dark:text-zinc-100 leading-none pt-1">
              {adherenceStats?.active_assignments || 0}
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Active Prescriptions
            </p>
          </div>

          <div className="rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 sm:p-5 space-y-2 col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between">
              <TrendingUp className="w-5 h-5 text-[#C1694A]" strokeWidth={2.2} />
              <span className="text-xs font-bold text-[#C1694A]">{overallProgress}%</span>
            </div>
            <p className="text-2xl sm:text-3xl font-bold text-[#1E2A2B] dark:text-zinc-100 leading-none pt-1">
              {carePlan?.stages?.length || 0}
            </p>
            <p className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold leading-tight">
              Pathway Stages
            </p>
            <div className="h-1.5 rounded-full bg-[#E5E0D6]/60 dark:bg-zinc-800 overflow-hidden" aria-label={`Pathway progress ${overallProgress}%`}>
              <div className="h-full rounded-full bg-[#C1694A]" style={{ width: `${Math.min(overallProgress, 100)}%` }} />
            </div>
          </div>
        </div>
      </section>

      {/* 4. RECOVERY MILESTONES — from real stages & goals */}
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Recovery Milestones
          </h2>
        </div>

        {milestones.length === 0 ? (
          <div className="text-center py-8 px-6 space-y-3 rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60">
            <div className="w-12 h-12 rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center mx-auto text-[#1F4B45] dark:text-[#5FC2B8]">
              <Flag className="w-6 h-6" />
            </div>
            <div>
              <p className="font-bold text-[15px] text-[#1E2A2B] dark:text-zinc-100">No milestones yet</p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1">
                Completed stages and achieved goals will be celebrated here.
              </p>
            </div>
          </div>
        ) : (
          <div className="rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-2 sm:p-3">
            <div className="space-y-1">
              {milestones.map((m) => (
                <div key={m.id} className="p-3 rounded-2xl flex items-center gap-3.5">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 border-2 ${
                      m.status === 'done'
                        ? 'bg-[#1F4B45] border-[#1F4B45] text-white'
                        : m.status === 'in_progress'
                        ? 'bg-[#C1694A]/10 border-[#C1694A] text-[#C1694A]'
                        : 'bg-[#F7F4ED] dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-700 text-transparent'
                    }`}
                  >
                    {m.status === 'done' ? (
                      <Check className="w-4 h-4" strokeWidth={3} />
                    ) : m.status === 'in_progress' ? (
                      <span className="w-2 h-2 rounded-full bg-[#C1694A]" />
                    ) : null}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 truncate">
                      {m.title}
                    </p>
                    <p className="text-xs text-[#60716E] dark:text-zinc-400 font-medium">
                      {m.meta}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-xs font-bold ${
                      m.status === 'done'
                        ? 'text-[#1F4B45] dark:text-[#5FC2B8]'
                        : m.status === 'in_progress'
                        ? 'text-[#C1694A]'
                        : 'text-[#60716E] dark:text-zinc-400'
                    }`}
                  >
                    {m.status === 'done' ? 'Achieved' : m.status === 'in_progress' ? 'In progress' : 'Upcoming'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 5. RECENT ACTIVITY */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]" />
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
            Recent Activity
          </h2>
        </div>

        {adherenceStats?.recent_activity && adherenceStats.recent_activity.length > 0 ? (
          <div className="space-y-3">
            {adherenceStats.recent_activity.slice(0, 5).map((item, index) => (
              <div key={index} className="p-4 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-1.5">
                <div className="flex justify-between items-start gap-2">
                  <h3 className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 truncate">
                    {item.exercise_name}
                  </h3>
                  <span className="text-xs text-[#60716E] dark:text-zinc-400 font-semibold shrink-0">
                    {formatDateTime(item.completed_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs text-[#60716E] dark:text-zinc-400 font-medium">
                  <span>Sets completed: <strong className="text-[#1E2A2B] dark:text-zinc-200">{item.completed_sets}</strong></span>
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-bold border ${
                    item.completion_status === 'completed'
                      ? 'bg-[#EEF5F1] text-[#1F4B45] dark:text-[#5FC2B8] border-[#1F4B45]/10 dark:border-zinc-700'
                      : 'bg-[#C9A86A]/10 text-[#C9A86A] border-[#C9A86A]/20'
                  }`}>
                    {formatSessionStatus(item.completion_status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 px-6 rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60">
            <p className="font-bold text-[15px] text-[#1E2A2B] dark:text-zinc-100">No recent activity</p>
            <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1">
              Your completed exercise sessions will be listed here.
            </p>
          </div>
        )}
      </section>

    </div>
  );
}

// Small clipboard icon kept local to avoid another import churn
function ClipboardIcon() {
  return (
    <svg
      className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8]"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect width="8" height="4" x="8" y="2" rx="1" ry="1" />
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
    </svg>
  );
}
