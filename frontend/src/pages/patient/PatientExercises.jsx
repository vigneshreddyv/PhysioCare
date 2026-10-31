import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../../services/api';
import {
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  Info,
  X,
  Play,
  ChevronRight,
  ClipboardCheck,
} from '../../components/common/LucideCompat';
import Button from '../../components/common/Button';

const categories = ['All', 'Mobility', 'Strength', 'Stretching', 'Posture'];

export default function PatientExercises() {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [detailExercise, setDetailExercise] = useState(null);

  // 1. Fetch general exercise catalog
  const { 
    data: catalogExercises, 
    isLoading: isCatalogLoading, 
    error: catalogError,
    refetch: refetchCatalog
  } = useQuery({
    queryKey: ['catalogExercises'],
    queryFn: async () => {
      const response = await api.get('/exercises');
      return response.data;
    },
    retry: 1
  });

  // 2. Fetch patient's prescribed exercise assignments
  const { 
    data: assignments, 
    isLoading: isAssignmentsLoading, 
    error: assignmentsError,
    refetch: refetchAssignments
  } = useQuery({
    queryKey: ['exerciseAssignments'],
    queryFn: async () => {
      const response = await api.get('/exercise-assignments');
      return response.data;
    },
    retry: 1
  });

  // 3. Fetch weekly stats (to obtain recent activity feed)
  const { data: stats } = useQuery({
    queryKey: ['patient-exercises-stats'],
    queryFn: async () => {
      const response = await api.get('/exercise-progress/stats');
      return response.data;
    },
    retry: 1
  });

  // 4. React Query Mutation to log exercise completion progress
  const logProgressMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post('/exercise-progress', payload);
      return response.data;
    },
    onSuccess: () => {
      refetchAssignments();
      refetchCatalog();
    }
  });

  // Map prescribed assignments to UI properties
  const prescribedExercises = useMemo(() => {
    if (!catalogExercises || !assignments) return [];
    return assignments.map(assign => {
      const ex = catalogExercises.find(e => String(e.id) === String(assign.exercise_id));
      if (!ex) return null;
      return {
        id: assign.id,
        exercise_id: ex.id,
        name: ex.title,
        category: ex.category.charAt(0).toUpperCase() + ex.category.slice(1),
        sets: `${assign.sets} sets`,
        reps: `${assign.reps} reps`,
        duration: `${Math.round(assign.duration_seconds / 60)} min`,
        description: ex.description,
        instructions: ex.instructions,
        safetyReminders: ex.safety_precautions || [],
        status: assign.status,
        is_assigned: true
      };
    }).filter(Boolean);
  }, [catalogExercises, assignments]);

  // Map catalog exercises to UI properties
  const generalExercises = useMemo(() => {
    if (!catalogExercises) return [];
    return catalogExercises.map(ex => {
      return {
        id: ex.id,
        name: ex.title,
        category: ex.category.charAt(0).toUpperCase() + ex.category.slice(1),
        sets: `${ex.sets} sets`,
        reps: `${ex.reps} reps`,
        duration: `${Math.round(ex.duration_seconds / 60)} min`,
        description: ex.description,
        instructions: ex.instructions,
        safetyReminders: ex.safety_precautions || [],
        status: 'not_assigned',
        is_assigned: false
      };
    });
  }, [catalogExercises]);

  const toggleCompletion = (ex) => {
    if (logProgressMutation.isPending) return;

    if (!ex.is_assigned) {
      alert("This exercise is not currently prescribed to you. You can only track completion status of prescribed exercises.");
      return;
    }
    
    if (ex.status === 'completed' || ex.status === 'cancelled') {
      return; 
    }

    const numericSets = parseInt(ex.sets) || 3;
    const numericReps = parseInt(ex.reps) || 10;
    const numericDurationSeconds = (parseInt(ex.duration) || 5) * 60;
    const isFinishing = ex.status === 'in_progress';
    const completion_status = isFinishing ? 'completed' : 'partial';

    logProgressMutation.mutate({
      assignment_id: ex.id,
      completed_sets: numericSets,
      completed_reps: numericReps,
      duration_seconds: numericDurationSeconds,
      completion_status
    });
  };

  const completedCount = useMemo(() => {
    return prescribedExercises.filter((e) => e.status === 'completed').length;
  }, [prescribedExercises]);

  const progressPercent = useMemo(() => {
    if (prescribedExercises.length === 0) return 0;
    return Math.round((completedCount / prescribedExercises.length) * 100);
  }, [completedCount, prescribedExercises.length]);

  const filteredPrescribed = useMemo(() => {
    if (selectedCategory === 'All') return prescribedExercises;
    return prescribedExercises.filter((e) => e.category.toLowerCase() === selectedCategory.toLowerCase());
  }, [prescribedExercises, selectedCategory]);

  const filteredGeneral = useMemo(() => {
    if (selectedCategory === 'All') return generalExercises;
    return generalExercises.filter((e) => e.category.toLowerCase() === selectedCategory.toLowerCase());
  }, [generalExercises, selectedCategory]);

  // Loading skeleton matching layout
  if (isCatalogLoading || isAssignmentsLoading) {
    return (
      <div className="max-w-[1500px] mx-auto space-y-8 animate-pulse p-4 sm:p-6 lg:p-8">
        <div className="h-24 bg-gray-100 rounded-3xl border border-gray-200" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="h-48 bg-gray-100 rounded-3xl border border-gray-200" />
            <div className="h-64 bg-gray-100 rounded-3xl border border-gray-200" />
          </div>
          <div className="h-80 bg-gray-100 rounded-3xl border border-gray-200" />
        </div>
      </div>
    );
  }

  // Error boundary page
  if (catalogError || assignmentsError) {
    return (
      <div className="max-w-[1000px] mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto border border-red-100">
          <AlertTriangle className="w-8 h-8 text-red-600" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#183B4A]">Failed to Load Exercises</h2>
          <p className="text-sm text-[#60716E]">
            {catalogError?.response?.data?.detail || assignmentsError?.response?.data?.detail || "An error occurred while loading your exercises. Please try again."}
          </p>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()} className="text-xs py-2 px-5">
          Retry Connection
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 border-b border-[#E5E0D6]/65 pb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Daily Movement</span>
          <h1 className="text-3xl font-extrabold text-[#183B4A] mt-1">Your Exercises</h1>
          <p className="mt-2 text-sm sm:text-base text-[#60716E] max-w-2xl leading-relaxed">
            Follow your prescribed physical therapist routines below. Completing routines supports your milestone progression checks.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#60716E] bg-white border border-[#E5E0D6] p-3 rounded-xl shadow-sm">
          <ShieldCheck className="w-5 h-5 text-[#0F6B63] shrink-0" />
          <span>Therapeutic movement plan</span>
        </div>
      </div>

      {/* 2. SPLIT LAYOUT */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: TODAY'S ROUTINES & DETAILS */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* TODAY'S EXERCISE SUMMARY */}
          {prescribedExercises.length > 0 && (
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
              <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4 pb-4 border-b border-[#E5E0D6]/60">
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">Today's Tasks</span>
                  <h2 className="text-xl font-extrabold text-[#183B4A]">Daily Routine Completion</h2>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs font-bold text-[#183B4A]">{completedCount} of {prescribedExercises.length} completed</span>
                  <span className="text-xs font-bold text-[#0F6B63] bg-[#EEF5F1] px-3.5 py-1 rounded-full border border-[#0F6B63]/10">{progressPercent}% done</span>
                </div>
              </div>

              <div className="space-y-4">
                <div className="w-full bg-[#E5E0D6]/40 rounded-full h-2.5 overflow-hidden">
                  <div 
                    className="bg-[#0F6B63] h-full rounded-full transition-all duration-500" 
                    style={{ width: `${progressPercent}%` }} 
                  />
                </div>
                
                {/* Checklist overview */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  {prescribedExercises.map((ex) => (
                    <div key={ex.id} className="flex items-center gap-2.5 text-xs sm:text-sm text-[#60716E]">
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                        ex.status === 'completed' 
                          ? 'border-[#0F6B63]/40 bg-[#EEF5F1] text-[#0F6B63]' 
                          : 'border-[#E5E0D6] bg-white'
                      }`}>
                        {ex.status === 'completed' && <span className="text-[10px] leading-none">✓</span>}
                      </div>
                      <span className={ex.status === 'completed' ? 'line-through opacity-70' : 'font-medium text-[#183B4A]'}>
                        {ex.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          )}

          {/* CATEGORY FILTERS */}
          <section className="space-y-4">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E] block">Filter Category</span>
            <div className="flex items-center gap-2 overflow-x-auto pb-1 hide-scrollbar">
              {categories.map((cat) => {
                const isSelected = selectedCategory === cat;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-4.5 py-2 rounded-full text-xs font-bold transition-all border shrink-0 focus:outline-none ${
                      isSelected
                        ? 'bg-[#0F6B63] border-[#0F6B63] text-white shadow-sm'
                        : 'bg-white border-[#E5E0D6] text-[#60716E] hover:bg-[#EEF5F1]/80 hover:text-[#0F6B63]'
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>
          </section>

          {/* PRESCRIBED ROUTINES CARDS */}
          <section className="space-y-5">
            <h3 className="font-extrabold text-[#183B4A] text-lg border-b border-[#E5E0D6]/60 pb-2.5">Prescribed Routines</h3>
            
            {filteredPrescribed.length === 0 ? (
              <div className="bg-white border border-[#E5E0D6] rounded-3xl p-8 text-center space-y-4 shadow-sm">
                <p className="text-xs text-[#60716E] max-w-xs mx-auto leading-relaxed">You currently do not have any prescribed exercises in this category.</p>
                <Button 
                  variant="outline" 
                  onClick={() => navigate('/patient/care-plan')} 
                  className="text-xs py-2 px-5 border border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#0F6B63] mx-auto font-bold"
                >
                  View Care Plan
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredPrescribed.map((ex) => {
                  const isCompleted = ex.status === 'completed';
                  const isInProgress = ex.status === 'in_progress';

                  return (
                    <div 
                      key={ex.id} 
                      className="bg-white border border-[#E5E0D6] rounded-2xl p-5 hover:shadow-[0px_3px_10px_rgba(15,107,99,0.04)] transition-all duration-200 flex flex-col justify-between min-h-[220px] shadow-sm"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <span className="inline-block px-2.5 py-0.5 rounded bg-[#EEF5F1] text-[9px] font-extrabold text-[#0F6B63] uppercase border border-[#0F6B63]/10">
                              {ex.category}
                            </span>
                            <h3 className="font-extrabold text-base text-[#183B4A] mt-2.5 leading-snug">
                              {ex.name}
                            </h3>
                          </div>
                        </div>

                        <p className="text-xs text-[#60716E] leading-relaxed line-clamp-2">
                          {ex.description}
                        </p>

                        <div className="flex flex-wrap gap-4 text-[11px] text-[#60716E] pt-1">
                          <span><strong>Prescribed:</strong> {ex.sets} · {ex.reps}</span>
                          <span><strong>Target Time:</strong> {ex.duration}</span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between border-t border-[#E5E0D6]/40 pt-4 mt-4">
                        <button
                          type="button"
                          onClick={() => setDetailExercise(ex)}
                          className="text-xs font-bold text-[#0F6B63] hover:underline flex items-center gap-0.5"
                        >
                          Instructions
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>

                        {isCompleted ? (
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[#0F6B63] bg-[#EEF5F1] border border-[#0F6B63]/15 px-3 py-1 rounded-xl">
                            Completed
                          </span>
                        ) : (
                          <button
                            onClick={() => toggleCompletion(ex)}
                            disabled={logProgressMutation.isPending}
                            className={`text-xs font-bold py-1.5 px-3 border.5 transition duration-150 rounded-xl flex items-center gap-1 ${
                              isInProgress 
                                ? 'bg-[#F7F4ED] border-[#C9A86A] text-[#C9A86A] hover:bg-[#F7F4ED]/80' 
                                : 'bg-white border-[#E5E0D6] text-[#0F6B63] hover:bg-[#F0F9F8]/40 hover:border-[#0F6B63]'
                            }`}
                          >
                            {isInProgress ? 'Log Completed Sets' : 'Start Routine'}
                            <Play className="w-3 h-3 fill-current ml-0.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          {/* GENERAL EXERCISES REFERENCE */}
          <section className="space-y-4">
            <h3 className="font-extrabold text-[#183B4A] text-lg border-b border-[#E5E0D6]/60 pb-2.5">General Reference Library</h3>
            
            {filteredGeneral.length === 0 ? (
              <p className="text-xs text-[#60716E]">No reference exercises found in this category.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredGeneral.map((ex) => (
                  <div 
                    key={ex.id} 
                    className="bg-white border border-[#E5E0D6] rounded-2xl p-5 hover:shadow-[0px_3px_10px_rgba(15,107,99,0.04)] transition-all duration-200 flex flex-col justify-between min-h-[220px] shadow-sm"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <span className="inline-block px-2.5 py-0.5 rounded bg-gray-50 text-[9px] font-extrabold text-[#60716E] uppercase border border-[#E5E0D6]/60">
                            {ex.category}
                          </span>
                          <h3 className="font-extrabold text-base text-[#183B4A] mt-2.5 leading-snug">
                            {ex.name}
                          </h3>
                        </div>
                      </div>

                      <p className="text-xs text-[#60716E] leading-relaxed line-clamp-2">
                        {ex.description}
                      </p>

                      <div className="flex flex-wrap gap-4 text-[11px] text-[#60716E] pt-1">
                        <span><strong>Standard:</strong> {ex.sets} · {ex.reps}</span>
                        <span><strong>Duration:</strong> {ex.duration}</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between border-t border-[#E5E0D6]/40 pt-4 mt-4">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">
                        Reference Catalog
                      </span>
                      <button
                        type="button"
                        onClick={() => setDetailExercise(ex)}
                        className="text-xs font-bold text-[#0F6B63] hover:underline flex items-center gap-0.5"
                      >
                        Instructions
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

        </div>

        {/* RIGHT COLUMN: PROGRESS & COMPLIANCE FEED */}
        <div className="space-y-8">
          
          {/* RECOVERY LINK */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E]">Roadmap</span>
              <h3 className="font-extrabold text-base text-[#183B4A] mt-0.5">Exercises in Recovery</h3>
            </div>

            <p className="text-xs text-[#60716E] leading-relaxed">
              Prescribed exercises load mechanical targets in stages. Log completions daily to feed metrics back to your clinician.
            </p>

            <div className="space-y-3 pt-2">
              <Button
                variant="primary"
                onClick={() => navigate('/patient/progress')}
                className="w-full text-xs py-2.5 flex items-center justify-center gap-2 border border-[#E5E0D6]/20 font-bold"
              >
                View Progress Stats
                <ArrowRight className="w-4 h-4" />
              </Button>
              <Button
                variant="outline"
                onClick={() => navigate('/patient/care-plan')}
                className="w-full text-xs py-2.5 flex items-center justify-center gap-2 border border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#0F6B63] font-bold"
              >
                View Pathway Stages
              </Button>
            </div>
          </section>

          {/* COMPLIANCE FEED */}
          {stats?.recent_activity && stats.recent_activity.length > 0 && (
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-4 shadow-sm">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#60716E] block">Compliance Feed</span>
              <h3 className="font-extrabold text-base text-[#183B4A] mt-0.5">Recent completions</h3>
              
              <div className="space-y-3">
                {stats.recent_activity.map((activity, idx) => (
                  <div key={idx} className="p-3.5 bg-[#EEF5F1]/30 border border-[#E5E0D6]/40 rounded-xl flex items-center justify-between gap-3 text-xs">
                    <div>
                      <p className="font-bold text-[#183B4A]">{activity.exercise_title}</p>
                      <p className="text-[10px] text-[#60716E] mt-0.5">Logged: {new Date(activity.completed_at).toLocaleDateString()}</p>
                    </div>
                    <span className={`inline-flex px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border ${
                      activity.status === 'completed' 
                        ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                        : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/10'
                    }`}>
                      {activity.status}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* CLINICAL CONSISTENCY ADVICE */}
          <section className="bg-[#F7F4ED]/40 border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="w-10 h-10 rounded-xl bg-white border border-[#E5E0D6] flex items-center justify-center">
              <Info className="w-5 h-5 text-[#0F6B63]" />
            </div>
            <div>
              <h4 className="font-extrabold text-sm text-[#183B4A]">Consistency Matters</h4>
              <p className="text-xs text-[#60716E] mt-1.5 leading-relaxed">
                Small, regular exercise sessions support tendon loading and joint mobility better than irregular heavy sessions. Try to complete your stretches at the same time each day to build healthy biomechanical habits.
              </p>
            </div>
          </section>

        </div>

      </div>

      {/* 3. EXERCISE INSTRUCTIONS MODAL */}
      {detailExercise && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-black/45 backdrop-blur-xs">
          <div className="relative bg-white border border-[#E5E0D6] rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6 shadow-xl animate-scale-up">
            
            {/* Modal Header */}
            <div className="flex justify-between items-start gap-4 pb-3 border-b border-[#E5E0D6]/40">
              <div>
                <span className="px-2.5 py-0.5 rounded bg-[#EEF5F1] text-[9px] font-extrabold text-[#0F6B63] uppercase border border-[#0F6B63]/10">
                  {detailExercise.category}
                </span>
                <h2 className="text-xl font-extrabold text-[#183B4A] mt-2 leading-tight">
                  {detailExercise.name}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setDetailExercise(null)}
                className="w-8 h-8 rounded-lg hover:bg-[#EEF5F1]/55 text-[#60716E] flex items-center justify-center border border-[#E5E0D6]/40 shadow-xs"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            {/* Target specifications */}
            <div className="grid grid-cols-3 gap-3 text-center bg-[#F7F4ED]/20 border border-[#E5E0D6]/50 rounded-2xl py-3 px-2">
              <div>
                <span className="text-[9px] text-[#60716E] uppercase tracking-wider block">Target Sets</span>
                <span className="text-sm font-extrabold text-[#183B4A] mt-0.5 block">
                  {String(detailExercise.sets).split(' ')[0]}
                </span>
              </div>
              <div>
                <span className="text-[9px] text-[#60716E] uppercase tracking-wider block">Target Reps</span>
                <span className="text-sm font-extrabold text-[#183B4A] mt-0.5 block">{detailExercise.reps}</span>
              </div>
              <div>
                <span className="text-[9px] text-[#60716E] uppercase tracking-wider block">Duration</span>
                <span className="text-sm font-extrabold text-[#183B4A] mt-0.5 block">{detailExercise.duration}</span>
              </div>
            </div>

            {/* Instructions list */}
            {detailExercise.instructions && detailExercise.instructions.length > 0 && (
              <div className="space-y-3">
                <h4 className="font-extrabold text-sm text-[#183B4A] flex items-center gap-1.5">
                  <ClipboardCheck className="w-4.5 h-4.5 text-[#0F6B63]" />
                  Movement Guidelines
                </h4>
                <ol className="space-y-2.5 text-xs text-[#60716E] list-decimal pl-4.5 leading-relaxed">
                  {detailExercise.instructions.map((step, idx) => (
                    <li key={idx} className="pl-1">
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {/* Safety Alerts block */}
            {detailExercise.safetyReminders && detailExercise.safetyReminders.length > 0 && (
              <div className="bg-red-50/40 border border-red-200/50 p-4.5 rounded-2xl space-y-2.5">
                <h4 className="font-extrabold text-xs text-red-800 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
                  Clinician Safety Precautions
                </h4>
                <ul className="list-disc pl-4 text-[11px] text-red-700/90 space-y-1.5 leading-normal">
                  {detailExercise.safetyReminders.map((reminder, idx) => (
                    <li key={idx}>
                      {reminder}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Actions panel */}
            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => setDetailExercise(null)}
                className="flex-1 py-2.5 text-xs border border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#0F6B63] font-bold"
              >
                Close Guidelines
              </Button>
              {detailExercise.is_assigned && detailExercise.status !== 'completed' && (
                <Button
                  variant="primary"
                  disabled={logProgressMutation.isPending}
                  onClick={() => {
                    toggleCompletion(detailExercise);
                    setDetailExercise(null);
                  }}
                  className="flex-1 py-2.5 text-xs border border-[#E5E0D6]/20 font-bold"
                >
                  {detailExercise.status === 'in_progress' ? 'Log Completed' : 'Start Routine'}
                </Button>
              )}
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
