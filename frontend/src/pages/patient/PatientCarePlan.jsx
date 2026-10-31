import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
  CheckCircle,
  Play,
  Circle,
  ArrowRight,
  Dumbbell,
  ShieldCheck,
  ClipboardCheck,
  History,
  Activity,
  Calendar,
} from '../../components/common/LucideCompat';
import Button from '../../components/common/Button';

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

  // Fetch exercises assignments linked to the care plan
  const { data: stageExercises } = useQuery({
    queryKey: ['carePlanExercises', carePlanId],
    queryFn: async () => {
      const response = await api.get(`/care-plans/${carePlanId}/exercises`);
      return response.data;
    },
    enabled: !!carePlanId,
    retry: 1
  });

  // Fetch adherence stats
  const { data: adherenceStats } = useQuery({
    queryKey: ['adherenceStats', carePlanId],
    queryFn: async () => {
      const response = await api.get('/exercise-progress/stats');
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
    if (!carePlan || !carePlan.stages || carePlan.stages.length === 0) return null;
    const total = carePlan.stages.length;
    const sum = carePlan.stages.reduce((acc, curr) => acc + (curr.progress || 0), 0);
    return Math.round(sum / total);
  }, [carePlan]);

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

  // Helper to format values details
  const formatHistoryDetail = (log) => {
    if (log.action === 'goal_updated') {
      return `Progress updated to ${log.new_value}`;
    }
    if (log.action === 'stage_activated' || log.action === 'stage_completed') {
      return `Status changed from '${log.previous_value}' to '${log.new_value}'`;
    }
    if (log.previous_value && log.new_value) {
      return `State adjusted from '${log.previous_value}' to '${log.new_value}'`;
    }
    return '';
  };

  // Loading skeleton state matching final layout
  if (isLoading) {
    return (
      <div className="max-w-[1500px] mx-auto space-y-8 animate-pulse p-4 sm:p-6 lg:p-8">
        <div className="h-48 bg-gray-100 rounded-3xl border border-gray-200" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="h-64 bg-gray-100 rounded-3xl border border-gray-200" />
            <div className="h-80 bg-gray-100 rounded-3xl border border-gray-200" />
          </div>
          <div className="space-y-6">
            <div className="h-32 bg-gray-100 rounded-3xl border border-gray-200" />
            <div className="h-64 bg-gray-100 rounded-3xl border border-gray-200" />
          </div>
        </div>
      </div>
    );
  }

  // Error page state
  if (error) {
    return (
      <div className="max-w-[1000px] mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto border border-red-100">
          <ShieldCheck className="w-8 h-8 text-red-600" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#183B4A]">Failed to Load Care Plan</h2>
          <p className="text-sm text-[#60716E] max-w-md mx-auto">
            {error.response?.data?.detail || "An error occurred while fetching your care plan. Please try again later."}
          </p>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()} className="text-xs py-2 px-5">
          Retry Connection
        </Button>
      </div>
    );
  }

  // Empty state handling
  if (!carePlan) {
    return (
      <div className="max-w-[1000px] mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-[#EEF5F1] rounded-full flex items-center justify-center mx-auto border border-[#E5E0D6]/40">
          <ClipboardCheck className="w-8 h-8 text-[#0F6B63]" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-extrabold text-[#183B4A]">No Active Care Plan</h2>
          <p className="text-sm text-[#60716E] max-w-md mx-auto leading-relaxed">
            You currently do not have a clinically assigned care plan. Please consult with your therapist or book an appointment to set up your rehabilitation roadmap.
          </p>
        </div>
        <div className="flex justify-center gap-4">
          <Button variant="primary" onClick={() => navigate('/patient/book')} className="text-xs py-2.5 px-6">
            Book Appointment
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. HERO - CLINICAL CARE PLAN BANNER */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E5E0D6] bg-gradient-to-br from-[#EEF5F1] via-[#F7F4ED] to-[#DDEFEA]/20 p-6 sm:p-10 lg:p-12 shadow-sm">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-8">
          <div className="space-y-4 max-w-3xl">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-[#0F6B63]/15 bg-[#DDEFEA] text-[#0F6B63] text-xs font-bold w-fit shadow-sm">
              <ClipboardCheck className="w-3.5 h-3.5" />
              <span>{carePlan.status === 'active' ? 'Active Pathway' : 'Completed Plan'}</span>
            </div>
            
            <div className="space-y-2">
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black tracking-tight text-[#183B4A]">{carePlan.title}</h1>
              <p className="text-sm sm:text-base text-[#60716E] leading-relaxed max-w-2xl">{carePlan.description}</p>
            </div>

            <div className="flex flex-wrap gap-4 text-xs text-[#60716E] pt-2">
              <div className="flex items-center gap-2 bg-white/80 border border-[#E5E0D6]/70 px-3 py-1.5 rounded-xl shadow-xs">
                <Calendar className="w-4 h-4 text-[#0F6B63]" />
                <span>Start Date: <strong className="text-[#183B4A]">{carePlan.start_date ? new Date(carePlan.start_date).toLocaleDateString() : 'N/A'}</strong></span>
              </div>
              <div className="flex items-center gap-2 bg-white/80 border border-[#E5E0D6]/70 px-3 py-1.5 rounded-xl shadow-xs">
                <Calendar className="w-4 h-4 text-[#0F6B63]" />
                <span>Target Date: <strong className="text-[#183B4A]">{carePlan.target_date ? new Date(carePlan.target_date).toLocaleDateString() : 'N/A'}</strong></span>
              </div>
            </div>
          </div>

          {overallProgress !== null && (
            <div className="w-full md:w-80 bg-white border border-[#E5E0D6] p-6 rounded-2xl shadow-sm space-y-3 shrink-0">
              <div className="flex justify-between items-center text-xs font-bold text-[#183B4A]">
                <span className="uppercase tracking-wider text-[#60716E] text-[10px]">Pathway Progress</span>
                <span className="text-lg text-[#0F6B63]">{overallProgress}%</span>
              </div>
              <div className="w-full bg-[#E5E0D6]/40 h-2.5 rounded-full overflow-hidden">
                <div 
                  className="bg-[#0F6B63] h-full rounded-full transition-all duration-500 ease-out" 
                  style={{ width: `${overallProgress}%` }}
                />
              </div>
              <span className="text-[10px] text-[#60716E] block text-right">Average of completed milestone weights</span>
            </div>
          )}
        </div>
      </section>

      {/* 2. SPLIT LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: ACTIVE STAGE HERO & TIMELINE */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* CURRENT RECOVERY STAGE HERO */}
          {carePlan.status !== 'completed' && activeStage && (
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
              <div className="flex justify-between items-start gap-4">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Current Milestone</span>
                  <h2 className="text-xl sm:text-2xl font-extrabold text-[#183B4A]">{activeStage.title}</h2>
                </div>
                <span className="text-xs font-bold text-[#0F6B63] bg-[#EEF5F1] border border-[#0F6B63]/10 px-3.5 py-1 rounded-full shrink-0">
                  Active Stage
                </span>
              </div>

              <p className="text-sm text-[#60716E] leading-relaxed">{activeStage.description}</p>

              {activeStage.focus_areas && activeStage.focus_areas.length > 0 && (
                <div className="space-y-2">
                  <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider block">Stage Focus Areas</span>
                  <div className="flex flex-wrap gap-2">
                    {activeStage.focus_areas.map((fa, i) => (
                      <span key={i} className="px-3 py-1 bg-[#EEF5F1] text-[#0F6B63] text-xs font-semibold rounded-lg border border-[#0F6B63]/10">
                        {fa}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-3 pt-2 border-t border-[#E5E0D6]/60">
                <div className="flex justify-between text-xs font-bold text-[#183B4A]">
                  <span>Stage Progress</span>
                  <span>{activeStage.progress || 0}%</span>
                </div>
                <div className="w-full bg-[#E5E0D6]/40 h-2.5 rounded-full overflow-hidden">
                  <div 
                    className="bg-[#0F6B63] h-full rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${activeStage.progress || 0}%` }}
                  />
                </div>
                {activeStage.target_date && (
                  <p className="text-[10px] text-[#60716E] mt-1 text-right">
                    Estimated Stage Completion: <strong className="text-[#183B4A]">{new Date(activeStage.target_date).toLocaleDateString()}</strong>
                  </p>
                )}
              </div>
            </section>
          )}

          {/* TREATMENT MILESTONES TIMELINE */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-8 shadow-sm">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Roadmap</span>
              <h3 className="font-extrabold text-[#183B4A] text-xl mt-0.5">Rehabilitation Pathway Stages</h3>
            </div>

            {!carePlan.stages || carePlan.stages.length === 0 ? (
              <p className="text-sm text-[#60716E] py-4 text-center">Treatment stages have not been configured yet.</p>
            ) : (
              <div className="relative pl-8 border-l-2 border-[#E5E0D6] ml-4 space-y-8">
                {carePlan.stages.map((stage, index) => {
                  const isCompleted = stage.status === 'completed';
                  const isCurrent = stage.status === 'active';
                  
                  let dateText = '';
                  if (isCompleted && stage.target_date) {
                    dateText = `Completed ${new Date(stage.target_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
                  } else if (isCurrent && stage.target_date) {
                    dateText = `Target completion ${new Date(stage.target_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
                  } else if (stage.start_date) {
                    dateText = `Est. start ${new Date(stage.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
                  }

                  const countStagePrescribed = stageExercises ? stageExercises.filter(e => e.stage_id === stage.stage_id).length : 0;
                  const countStageCompleted = stageExercises ? stageExercises.filter(e => e.stage_id === stage.stage_id && e.status === 'completed').length : 0;

                  return (
                    <div key={stage.stage_id || index} className="relative group">
                      
                      <div className="absolute -left-[43px] top-1.5 z-10">
                        {isCompleted ? (
                          <div className="w-7 h-7 rounded-full bg-[#0F6B63] flex items-center justify-center ring-4 ring-white shadow-sm transition duration-150">
                            <CheckCircle className="w-4 h-4 text-white" />
                          </div>
                        ) : isCurrent ? (
                          <div className="w-7 h-7 rounded-full bg-white border-2 border-[#0F6B63] flex items-center justify-center ring-4 ring-white shadow-sm transition duration-150">
                            <Play className="w-3.5 h-3.5 text-[#0F6B63] fill-current animate-pulse" />
                          </div>
                        ) : (
                          <div className="w-7 h-7 rounded-full bg-white border-2 border-[#E5E0D6] flex items-center justify-center ring-4 ring-white transition duration-150">
                            <Circle className="w-3.5 h-3.5 text-[#60716E]" />
                          </div>
                        )}
                      </div>

                      <div className={`p-5 sm:p-6 rounded-2xl border transition-all duration-200 ${
                        isCurrent 
                          ? 'border-[#0F6B63] bg-[#EEF5F1]/10 shadow-sm' 
                          : isCompleted
                            ? 'border-[#E5E0D6]/70 bg-gray-50/50'
                            : 'border-[#E5E0D6]/40 bg-white'
                      }`}>
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#E5E0D6]/40">
                          <h3 className={`font-extrabold text-sm sm:text-base ${isCurrent ? 'text-[#0F6B63]' : 'text-[#183B4A]'}`}>
                            Stage {index + 1}: {stage.title}
                          </h3>
                          <span className={`text-[10px] sm:text-xs font-bold shrink-0 ${isCompleted ? 'text-[#0F6B63]' : 'text-[#60716E]'}`}>
                            {dateText}
                          </span>
                        </div>
                        <p className="text-xs sm:text-sm text-[#60716E] mt-3 leading-relaxed">
                          {stage.description}
                        </p>
                        
                        {stage.focus_areas && stage.focus_areas.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-4">
                            {stage.focus_areas.map((fa, i) => (
                              <span key={i} className="px-2 py-0.5 bg-white border border-[#E5E0D6] rounded text-[10px] text-[#60716E] font-medium">
                                {fa}
                              </span>
                            ))}
                          </div>
                        )}

                        {countStagePrescribed > 0 && (
                          <div className="mt-4 text-xs text-[#60716E] flex items-center gap-2 pt-3 border-t border-[#E5E0D6]/30">
                            <Dumbbell className="w-4 h-4 text-[#0F6B63]" />
                            <span>
                              Prescribed Exercises: <strong className="text-[#183B4A]">{countStagePrescribed}</strong> | Completed today: <strong className="text-[#183B4A]">{countStageCompleted}</strong>
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* CLINICAL TIMELINE & HISTORY LOGS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-2.5 border-b border-[#E5E0D6]/60 pb-4">
              <History className="w-5 h-5 text-[#0F6B63] shrink-0" />
              <h3 className="font-extrabold text-[#183B4A] text-lg">Care Plan History</h3>
            </div>

            {isHistoryLoading ? (
              <div className="py-4 space-y-3">
                <div className="h-10 bg-gray-100 rounded animate-pulse" />
                <div className="h-10 bg-gray-100 rounded animate-pulse" />
              </div>
            ) : historyError ? (
              <p className="text-xs text-red-600 bg-red-50 p-3 rounded-lg border border-red-100">Clinical history log is temporarily unavailable.</p>
            ) : !historyLogs || historyLogs.length === 0 ? (
              <p className="text-xs text-[#60716E] py-4 text-center">No clinical updates yet.</p>
            ) : (
              <div className="space-y-4">
                {historyLogs.map((log, index) => (
                  <div key={index} className="p-4 bg-[#F7F4ED]/20 border border-[#E5E0D6]/50 rounded-2xl flex items-start gap-3.5">
                    <div className="w-8 h-8 rounded-xl bg-white border border-[#E5E0D6]/65 flex items-center justify-center shrink-0 shadow-xs">
                      <Activity className="w-4 h-4 text-[#0F6B63]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start gap-2">
                        <p className="text-xs font-bold text-[#183B4A]">{formatHistoryAction(log.action)}</p>
                        <span className="text-[10px] text-[#60716E] font-medium shrink-0">
                          {new Date(log.created_at).toLocaleDateString()} {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      {formatHistoryDetail(log) && (
                        <p className="text-[10px] text-[#60716E] mt-1 italic font-medium">{formatHistoryDetail(log)}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* RIGHT COLUMN: RECOMMENDATIONS, METRICS, EXERCISES */}
        <div className="space-y-8">
          
          {/* CLINICAL RECOVERY METRICS */}
          <section className="grid grid-cols-3 gap-3">
            <div className="bg-white border border-[#E5E0D6] rounded-2xl p-4 text-center flex flex-col justify-center min-h-[100px] shadow-sm">
              <span className="text-[9px] font-bold text-[#60716E] uppercase tracking-wider block">Reported Pain</span>
              <span className="text-base font-extrabold text-[#183B4A] mt-1.5 block">3 / 10</span>
              <span className="text-[8px] text-[#60716E] block mt-0.5">Self-reported</span>
            </div>
            <div className="bg-white border border-[#E5E0D6] rounded-2xl p-4 text-center flex flex-col justify-center min-h-[100px] shadow-sm">
              <span className="text-[9px] font-bold text-[#60716E] uppercase tracking-wider block">Stage Progress</span>
              <span className="text-base font-extrabold text-[#183B4A] mt-1.5 block">
                {activeStage ? `${activeStage.progress}%` : '0%'}
              </span>
              <span className="text-[8px] text-[#60716E] block mt-0.5">Active stage index</span>
            </div>
            <div className="bg-white border border-[#E5E0D6] rounded-2xl p-4 text-center flex flex-col justify-center min-h-[100px] shadow-sm">
              <span className="text-[9px] font-bold text-[#60716E] uppercase tracking-wider block">Weekly Adherence</span>
              <span className="text-base font-extrabold text-[#183B4A] mt-1.5 block">
                {adherenceStats !== undefined && adherenceStats !== null ? `${adherenceStats.percentage}%` : '87%'}
              </span>
              <span className="text-[8px] text-[#60716E] block mt-0.5">Exercise rate</span>
            </div>
          </section>

          {/* GUIDED ROUTINES LINK */}
          <section className="bg-[#EEF5F1] border-2 border-[#0F6B63]/20 rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="w-10 h-10 rounded-xl bg-[#DDEFEA] border border-[#0F6B63]/25 flex items-center justify-center shadow-sm">
              <Dumbbell className="w-5 h-5 text-[#0F6B63]" />
            </div>
            <div className="space-y-1.5">
              <h3 className="font-extrabold text-[#183B4A] text-sm">Guided Recovery Routine</h3>
              <p className="text-xs text-[#60716E] leading-relaxed">
                Complete and log your assigned exercises to stay on track with your physical milestones.
              </p>
            </div>
            <Button
              variant="primary"
              onClick={() => navigate('/patient/exercises')}
              className="w-full text-xs py-2.5 flex items-center justify-center gap-2 border border-[#E5E0D6]/20 font-bold"
            >
              Start Daily Routine
              <ArrowRight className="w-4 h-4" />
            </Button>
          </section>

          {/* KEY FOCUS AREAS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Targets</span>
              <h3 className="font-extrabold text-[#183B4A] text-base mt-0.5">Key Focus Areas</h3>
            </div>

            {!carePlan.goals || carePlan.goals.length === 0 ? (
              <p className="text-xs text-[#60716E] py-2">No recovery goals have been assigned yet.</p>
            ) : (
              <div className="space-y-3.5">
                {carePlan.goals.map((item, index) => {
                  const isAchieved = item.status === 'achieved';
                  return (
                    <div key={item.goal_id || index} className="p-4 rounded-2xl border border-[#E5E0D6]/60 bg-[#F7F4ED]/20 space-y-3 shadow-xs">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full shrink-0 ${isAchieved ? 'bg-[#0F6B63]' : 'bg-[#C9A86A]'}`} />
                          <p className="font-bold text-xs text-[#183B4A]">{item.title}</p>
                        </div>
                        <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${
                          isAchieved 
                            ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                            : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                        }`}>
                          {item.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#60716E] leading-relaxed">{item.description}</p>
                      
                      <div className="flex justify-between items-center text-[10px] text-[#60716E] pt-2 border-t border-[#E5E0D6]/20">
                        <span>Target: <strong>{item.target_value > 0 ? `${item.target_value} ${item.unit}` : 'N/A'}</strong></span>
                        <span>Current: <strong>{item.progress_value !== undefined && item.progress_value !== null ? `${item.progress_value} ${item.unit}` : 'N/A'}</strong></span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* CARE INSTRUCTIONS / RECOMMENDATIONS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center gap-2 pb-3 border-b border-[#E5E0D6]/40">
              <ClipboardCheck className="w-5 h-5 text-[#0F6B63] shrink-0" />
              <h3 className="font-extrabold text-[#183B4A] text-base">Care Instructions</h3>
            </div>

            {!carePlan.recommendations || carePlan.recommendations.length === 0 ? (
              <p className="text-xs text-[#60716E] py-2">No therapist recommendations configured yet.</p>
            ) : (
              <div className="space-y-3.5">
                {carePlan.recommendations.map((rec, index) => {
                  const isHighPriority = rec.priority === 'high';
                  return (
                    <div key={rec.recommendation_id || index} className="flex items-start gap-3">
                      <span className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[9px] shrink-0 mt-0.5 ${
                        isHighPriority 
                          ? 'bg-[#F7F4ED] text-[#C9A86A] border border-[#C9A86A]/20' 
                          : 'bg-[#EEF5F1] text-[#0F6B63] border border-[#0F6B63]/10'
                      }`}>
                        {index + 1}
                      </span>
                      <div className="space-y-1">
                        <p className="text-xs font-bold text-[#183B4A]">{rec.title}</p>
                        <p className="text-[11px] text-[#60716E] leading-relaxed">{rec.description}</p>
                        <span className={`inline-flex items-center text-[8px] font-bold uppercase tracking-wider ${
                          isHighPriority ? 'text-[#C9A86A]' : 'text-[#60716E]'
                        }`}>
                          {rec.priority} Priority
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

      </div>
    </div>
  );
}
