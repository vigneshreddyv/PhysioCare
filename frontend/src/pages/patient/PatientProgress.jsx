import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
  Activity,
  ArrowRight,
  ShieldCheck,
  Calendar,
  Dumbbell,
  AlertTriangle,
  History,
} from '../../components/common/LucideCompat';
import Button from '../../components/common/Button';

// Skeletons for independent loading blocks
const CardSkeleton = () => (
  <div className="h-28 bg-gray-100 rounded-2xl border border-gray-200/50 animate-pulse w-full" />
);

const BlockSkeleton = ({ height = "h-48" }) => (
  <div className={`${height} bg-gray-100 rounded-3xl border border-gray-200/50 animate-pulse w-full`} />
);

export default function PatientProgress() {
  const navigate = useNavigate();

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

  const overallProgress = useMemo(() => {
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return null;
    const total = carePlan.stages.length;
    const sum = carePlan.stages.reduce((acc, curr) => acc + (curr.progress || 0), 0);
    return Math.round(sum / total);
  }, [carePlan]);

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return isoString;
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      });
    } catch {
      return isoString;
    }
  };

  // Main Page wrapper
  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. RECOVERY PROGRESS HEADER & HERO (Independent Care Plan Query Boundary) */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E5E0D6] bg-gradient-to-br from-[#EEF5F1] via-[#F7F4ED] to-[#DDEFEA]/20 p-6 sm:p-10 lg:p-12 shadow-sm">
        {isCarePlansLoading ? (
          <div className="space-y-4">
            <div className="h-6 w-32 bg-gray-200 rounded animate-pulse" />
            <div className="h-10 w-96 bg-gray-200 rounded animate-pulse" />
            <div className="h-6 w-64 bg-gray-200 rounded animate-pulse" />
          </div>
        ) : carePlansError ? (
          <div className="flex items-start gap-3 bg-white/70 backdrop-blur-xs p-5 rounded-2xl border border-red-200/50">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold text-sm text-[#183B4A]">Pathway details temporarily unavailable</p>
              <p className="text-xs text-[#60716E]">We could not retrieve your Care Plan configuration. Basic pathway progress labels will load as fallbacks.</p>
            </div>
          </div>
        ) : !carePlan ? (
          <div className="space-y-4">
            <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Recovery Vitals</span>
            <h2 className="text-2xl font-extrabold text-[#183B4A]">No Active Care Plan Found</h2>
            <p className="text-xs sm:text-sm text-[#60716E] max-w-lg leading-relaxed">
              You do not have an active rehabilitation pathway. Please configure your milestones with your physical therapist to initiate progress compliance scores.
            </p>
            <Button variant="primary" onClick={() => navigate('/patient/care-plan')} className="text-xs py-2 px-5">
              Review Pathways
            </Button>
          </div>
        ) : (
          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-8">
            <div className="space-y-4 max-w-2xl">
              <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Recovery Vitals</span>
              <div className="space-y-2">
                <h1 className="text-3xl font-black tracking-tight text-[#183B4A]">{carePlan.title} Progress</h1>
                <p className="text-xs sm:text-sm text-[#60716E] leading-relaxed">
                  Your milestone compliance and exercise compliance statistics are derived below.
                </p>
              </div>
              {activeStage && (
                <div className="flex items-center gap-2 bg-white border border-[#E5E0D6]/70 px-3.5 py-1.5 rounded-xl shadow-xs text-xs text-[#60716E] w-fit">
                  <Calendar className="w-4 h-4 text-[#0F6B63]" />
                  <span>Active Milestone stage: <strong className="text-[#183B4A]">{activeStage.title}</strong></span>
                </div>
              )}
            </div>

            {overallProgress !== null && (
              <div className="w-full md:w-80 bg-white border border-[#E5E0D6] p-6 rounded-2xl shadow-sm space-y-3 shrink-0">
                <div className="flex justify-between items-center text-xs font-bold text-[#183B4A]">
                  <span className="uppercase tracking-wider text-[#60716E] text-[10px]">Pathway Progress</span>
                  <span className="text-lg text-[#0F6B63] font-bold">{overallProgress}%</span>
                </div>
                <div className="w-full bg-[#E5E0D6]/40 h-2.5 rounded-full overflow-hidden">
                  <div 
                    className="bg-[#0F6B63] h-full rounded-full transition-all duration-500" 
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>
                <span className="text-[9px] text-[#60716E] block text-right font-medium">Derived stage weight average</span>
              </div>
            )}
          </div>
        )}
      </section>

      {/* 2. KEY METRICS ROW (Independent Query Skeletons) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {isCarePlansLoading ? (
          <CardSkeleton />
        ) : (
          <div className="bg-white border border-[#E5E0D6] rounded-2xl p-5 shadow-sm space-y-1.5">
            <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Pathway Progress</span>
            <p className="text-2xl font-black text-[#183B4A]">
              {overallProgress !== null ? `${overallProgress}%` : 'N/A'}
            </p>
            <span className="text-[9px] text-[#60716E] block font-medium">Derived milestones average</span>
          </div>
        )}

        {isStatsLoading ? (
          <CardSkeleton />
        ) : statsError ? (
          <div className="bg-white border border-red-150 rounded-2xl p-5 shadow-sm flex flex-col justify-center text-center">
            <span className="text-[10px] font-bold text-red-700 uppercase tracking-wider block">Weekly Adherence</span>
            <p className="text-sm font-medium text-[#60716E] mt-1">Unavailable</p>
          </div>
        ) : (
          <div className="bg-white border border-[#E5E0D6] rounded-2xl p-5 shadow-sm space-y-1.5">
            <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Weekly Adherence</span>
            <p className="text-2xl font-black text-[#0F6B63]">
              {adherenceStats?.percentage || 0}%
            </p>
            <span className="text-[9px] text-[#60716E] block font-medium">Exercise compliance rate</span>
          </div>
        )}

        {isStatsLoading ? (
          <CardSkeleton />
        ) : statsError ? (
          <div className="bg-white border border-red-150 rounded-2xl p-5 shadow-sm flex flex-col justify-center text-center">
            <span className="text-[10px] font-bold text-red-700 uppercase tracking-wider block">Completed Weekly</span>
            <p className="text-sm font-medium text-[#60716E] mt-1">Unavailable</p>
          </div>
        ) : (
          <div className="bg-white border border-[#E5E0D6] rounded-2xl p-5 shadow-sm space-y-1.5">
            <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Completed Weekly</span>
            <p className="text-2xl font-black text-[#183B4A]">
              {adherenceStats?.completed || 0}
            </p>
            <span className="text-[9px] text-[#60716E] block font-medium">Prescribed sessions finished</span>
          </div>
        )}

        {isStatsLoading ? (
          <CardSkeleton />
        ) : statsError ? (
          <div className="bg-white border border-red-150 rounded-2xl p-5 shadow-sm flex flex-col justify-center text-center">
            <span className="text-[10px] font-bold text-red-700 uppercase tracking-wider block">Active Exercises</span>
            <p className="text-sm font-medium text-[#60716E] mt-1">Unavailable</p>
          </div>
        ) : (
          <div className="bg-white border border-[#E5E0D6] rounded-2xl p-5 shadow-sm space-y-1.5">
            <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Active Exercises</span>
            <p className="text-2xl font-black text-[#183B4A]">
              {adherenceStats?.active_assignments || 0}
            </p>
            <span className="text-[9px] text-[#60716E] block font-medium">Assigned active routines</span>
          </div>
        )}
      </div>

      {/* 3. SPLIT CONTENT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: ROADMAPS & TABLES */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* RECOVERY MILESTONES (Care Plan stages pathway visualization) */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Pathway Status</span>
              <h3 className="text-xl font-extrabold text-[#183B4A] mt-0.5">Recovery Milestones</h3>
            </div>

            {isCarePlansLoading ? (
              <div className="space-y-4">
                <BlockSkeleton height="h-10" />
                <BlockSkeleton height="h-10" />
                <BlockSkeleton height="h-10" />
              </div>
            ) : carePlansError ? (
              <p className="text-xs text-[#60716E]">Recovery milestones are temporarily unavailable.</p>
            ) : !carePlan ? (
              <p className="text-xs text-[#60716E]">Configure pathway stages to review milestone parameters.</p>
            ) : (
              <div className="space-y-5">
                {carePlan.stages.map((stage, idx) => (
                  <div key={stage.stage_id || idx} className="space-y-2">
                    <div className="flex justify-between items-center text-xs font-bold text-[#183B4A]">
                      <span>Stage {idx + 1}: {stage.title}</span>
                      <span className="text-[#0F6B63] font-black">{stage.progress || 0}%</span>
                    </div>
                    <div className="w-full bg-[#E5E0D6]/40 h-3 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full transition-all duration-500 ${
                          stage.status === 'completed' 
                            ? 'bg-[#0F6B63]' 
                            : stage.status === 'active' 
                              ? 'bg-[#0F6B63]/85' 
                              : 'bg-gray-300'
                        }`}
                        style={{ width: `${stage.progress || 0}%` }}
                      />
                    </div>
                    <p className="text-[10px] text-[#60716E] leading-normal">{stage.description}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* EXERCISE PERFORMANCE TABLE & MOBILITY CARDS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Adherence Analytics</span>
              <h3 className="text-xl font-extrabold text-[#183B4A] mt-0.5">Exercise Performance Compliance</h3>
            </div>

            {isStatsLoading ? (
              <div className="space-y-3">
                <BlockSkeleton height="h-8" />
                <BlockSkeleton height="h-24" />
              </div>
            ) : statsError ? (
              <div className="flex items-center gap-3 bg-red-50/50 p-4 border border-red-150 rounded-2xl">
                <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
                <div className="space-y-1">
                  <p className="text-xs font-bold text-[#183B4A]">Stats log failed to load</p>
                  <button onClick={() => refetchStats()} className="text-[10px] text-[#0F6B63] font-bold hover:underline">
                    Click to retry calculations
                  </button>
                </div>
              </div>
            ) : !adherenceStats?.exercise_breakdown || adherenceStats.exercise_breakdown.length === 0 ? (
              <div className="text-center py-10 border border-dashed border-[#E5E0D6] rounded-2xl bg-[#F7F4ED]/20 space-y-3">
                <Dumbbell className="w-8 h-8 text-[#60716E]/70 mx-auto" />
                <p className="text-xs text-[#60716E] max-w-sm mx-auto leading-relaxed">
                  Exercise compliance analytics will appear here after completing and logging your prescribed routines.
                </p>
                <Button 
                  variant="outline" 
                  onClick={() => navigate('/patient/exercises')}
                  className="text-xs py-1.5 px-4 font-bold"
                >
                  Start Exercises
                </Button>
              </div>
            ) : (
              <>
                {/* Desktop View Table */}
                <div className="hidden sm:block overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-[#E5E0D6]/60 text-[#60716E] font-bold">
                        <th className="py-2.5 pr-4">Exercise Name</th>
                        <th className="py-2.5 pr-4">Prescribed Target</th>
                        <th className="py-2.5 text-center">Sessions Logged</th>
                        <th className="py-2.5 text-center">Completed</th>
                        <th className="py-2.5 text-center">Partial</th>
                        <th className="py-2.5 text-right pl-4">Latest Log</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adherenceStats.exercise_breakdown.map((item, index) => (
                        <tr key={index} className="border-b border-[#E5E0D6]/30 hover:bg-[#F7F4ED]/20 text-[#183B4A]">
                          <td className="py-3 pr-4 font-bold text-sm">{item.exercise_name}</td>
                          <td className="py-3 pr-4 text-[#60716E]">{item.prescribed_target || 'N/A'}</td>
                          <td className="py-3 text-center font-semibold">{item.performance_count}</td>
                          <td className="py-3 text-center text-[#0F6B63] font-bold">{item.completed_sessions}</td>
                          <td className="py-3 text-center text-[#C9A86A] font-bold">{item.partial_sessions}</td>
                          <td className="py-3 text-right text-[10px] text-[#60716E] pl-4">{formatDateTime(item.latest_completion)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile View Cards */}
                <div className="block sm:hidden space-y-4">
                  {adherenceStats.exercise_breakdown.map((item, index) => (
                    <div key={index} className="p-4 rounded-2xl border border-[#E5E0D6]/60 bg-white space-y-3">
                      <div className="pb-2 border-b border-[#E5E0D6]/40">
                        <h4 className="font-bold text-sm text-[#183B4A]">{item.exercise_name}</h4>
                        <p className="text-[10px] text-[#60716E] mt-0.5">Target: {item.prescribed_target || 'N/A'}</p>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center text-xs">
                        <div>
                          <span className="text-[9px] text-[#60716E] block">Logged</span>
                          <span className="font-bold text-[#183B4A] block mt-0.5">{item.performance_count}</span>
                        </div>
                        <div>
                          <span className="text-[9px] text-[#60716E] block">Completed</span>
                          <span className="font-bold text-[#0F6B63] block mt-0.5">{item.completed_sessions}</span>
                        </div>
                        <div>
                          <span className="text-[9px] text-[#60716E] block">Partial</span>
                          <span className="font-bold text-[#C9A86A] block mt-0.5">{item.partial_sessions}</span>
                        </div>
                      </div>
                      <p className="text-[9px] text-[#60716E] text-right pt-1 border-t border-[#E5E0D6]/20">
                        Latest: {formatDateTime(item.latest_completion)}
                      </p>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>

          {/* STAGE BREAKDOWN */}
          {adherenceStats?.stage_breakdown && adherenceStats.stage_breakdown.length > 0 && (
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Stage Execution</span>
                <h3 className="text-xl font-extrabold text-[#183B4A] mt-0.5">Stage Execution Analytics</h3>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {adherenceStats.stage_breakdown.map((item, idx) => (
                  <div key={idx} className="p-4 rounded-2xl border border-[#E5E0D6]/60 bg-[#F7F4ED]/25 space-y-2.5">
                    <h4 className="font-bold text-sm text-[#183B4A]">{item.stage_title}</h4>
                    <div className="grid grid-cols-2 gap-2 text-[10px] text-[#60716E]">
                      <div>
                        <span>Prescribed Exercises: <strong>{item.assigned_exercise_count}</strong></span>
                      </div>
                      <div>
                        <span>Active Routines: <strong>{item.exercises_with_activity}</strong></span>
                      </div>
                      <div>
                        <span>Completed Logs: <strong>{item.completed_sessions}</strong></span>
                      </div>
                      <div>
                        <span>Latest Completion: <strong>{formatDateTime(item.latest_completion).split(',')[0]}</strong></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>

        {/* RIGHT COLUMN: ADHERENCE COMPLIANCE LOGS & SIDEBAR INFO */}
        <div className="space-y-8">
          
          {/* WEEKLY ADHERENCE TRACKER CARD */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#DDEFEA] flex items-center justify-center border border-[#0F6B63]/15">
                <Activity className="w-5 h-5 text-[#0F6B63]" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-[#183B4A]">Exercise Adherence</h3>
                {isStatsLoading ? (
                  <div className="h-4 w-32 bg-gray-200 rounded mt-1 animate-pulse" />
                ) : statsError ? (
                  <p className="text-xs text-red-600">Calculations unavailable</p>
                ) : (
                  <p className="text-xs text-[#60716E]">{adherenceStats?.completed || 0} of {adherenceStats?.total || 0} completed this week</p>
                )}
              </div>
            </div>

            {isStatsLoading ? (
              <BlockSkeleton height="h-14" />
            ) : statsError ? (
              <p className="text-xs text-[#60716E]">Weekly adherence rate unavailable.</p>
            ) : (
              <div className="flex justify-between items-center bg-[#F7F4ED]/40 border border-[#E5E0D6]/60 p-4 rounded-2xl">
                <span className="text-xs font-bold text-[#60716E]">Weekly Compliance Rate</span>
                <span className="text-lg font-black text-[#0F6B63]">{adherenceStats?.percentage || 0}%</span>
              </div>
            )}

            {/* Calendar list */}
            {isStatsLoading ? (
              <div className="grid grid-cols-7 gap-1 text-center">
                {[...Array(7)].map((_, i) => <div key={i} className="w-7 h-7 bg-gray-100 rounded-lg animate-pulse" />)}
              </div>
            ) : statsError ? (
              <p className="text-xs text-[#60716E]">Logs temporarily offline.</p>
            ) : adherenceStats?.log ? (
              <div className="grid grid-cols-7 gap-1.5 text-center pt-2">
                {adherenceStats.log.map((item, i) => (
                  <div key={i} className="flex flex-col items-center gap-1.5">
                    <span className="text-[10px] font-bold text-[#60716E]">{item.day}</span>
                    <div className={`w-7 h-7 rounded-lg border flex items-center justify-center text-xs font-bold ${
                      item.completed === true 
                        ? 'bg-[#0F6B63] border-[#0F6B63] text-white shadow-xs'
                        : item.completed === false 
                          ? 'bg-[#F7F4ED] border-[#C9A86A]/25 text-[#C9A86A]'
                          : 'bg-white border-[#E5E0D6]/60 text-[#60716E]'
                    }`}>
                      {item.completed === true ? '✓' : item.completed === false ? '✗' : '-'}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="pt-2">
              <Button
                variant="primary"
                onClick={() => navigate('/patient/exercises')}
                className="w-full text-xs py-2.5 flex items-center justify-center gap-2 border border-[#E5E0D6]/20 font-bold"
              >
                Log Daily Routines
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </section>

          {/* RECENT ACTIVITY COMPLETED LOGS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center gap-2.5 border-b border-[#E5E0D6]/45 pb-3">
              <History className="w-5 h-5 text-[#0F6B63] shrink-0" />
              <h3 className="font-extrabold text-[#183B4A] text-base">Recent Activity Logs</h3>
            </div>

            {isStatsLoading ? (
              <div className="space-y-3">
                <BlockSkeleton height="h-16" />
                <BlockSkeleton height="h-16" />
              </div>
            ) : statsError ? (
              <p className="text-xs text-[#60716E]">Logs feed temporarily unavailable.</p>
            ) : !adherenceStats?.recent_activity || adherenceStats.recent_activity.length === 0 ? (
              <p className="text-xs text-[#60716E] text-center py-4">No recent activity logged yet.</p>
            ) : (
              <div className="space-y-3.5">
                {adherenceStats.recent_activity.map((item, index) => (
                  <div key={index} className="p-4 bg-[#F7F4ED]/20 border border-[#E5E0D6]/50 rounded-2xl space-y-2">
                    <div className="flex justify-between items-start gap-2">
                      <p className="text-xs font-bold text-[#183B4A]">{item.exercise_name}</p>
                      <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-bold uppercase border ${
                        item.completion_status === 'completed' 
                          ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                          : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                      }`}>
                        {item.completion_status}
                      </span>
                    </div>
                    <p className="text-[10px] text-[#60716E]">
                      Logged: {item.completed_sets} sets x {item.completed_reps} reps | Duration: {Math.round(item.duration_seconds / 60)}m
                    </p>
                    {item.notes && (
                      <p className="text-[9px] text-[#60716E] italic bg-white border border-[#E5E0D6]/50 p-2 rounded-lg">
                        Note: {item.notes}
                      </p>
                    )}
                    <span className="text-[8px] text-[#60716E] block text-right">
                      {formatDateTime(item.completed_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* CLINICAL INTEGRITY DISCLAIMER CARD */}
          <section className="bg-[#EEF5F1] border border-[#0F6B63]/15 rounded-3xl p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#E5E0D6] flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-[#0F6B63]" />
            </div>
            <div>
              <h4 className="font-extrabold text-sm text-[#183B4A]">Data Integrity Note</h4>
              <p className="text-xs text-[#60716E] leading-relaxed">
                Biomechanical assessment scores and self-reported pain levels are updated by clinicians during clinic assessments. Adherence scores reflect completed sessions mapped from patient logs.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => navigate('/patient/care-plan')}
              className="w-full text-xs py-2.5 flex items-center justify-center gap-2 border border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#0F6B63] font-bold"
            >
              Review Care Journey Pathway
            </Button>
          </section>

        </div>

      </div>

    </div>
  );
}
