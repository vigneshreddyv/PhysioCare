import React, { useState, useMemo, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '../../services/api';
import {
  AlertTriangle,
  X,
  Play,
  ChevronRight,
  ClipboardCheck,
  CheckCircle2,
  Dumbbell,
  ShieldCheck,
  Check,
  Activity,
  Footprints,
} from 'lucide-react';
import Button from '../../components/common/Button';

const categories = ['All', 'Mobility', 'Strength', 'Stretching', 'Posture'];

// Category → consistent lucide icon (one icon family across the app)
function getCategoryIcon(category) {
  const c = (category || '').toLowerCase();
  if (c.includes('walk') || c.includes('gait') || c.includes('mobility')) return Footprints;
  if (c.includes('cardio') || c.includes('endurance')) return Activity;
  return Dumbbell;
}

// Loading skeleton matching the layout
const ExercisesSkeleton = () => (
  <div className="max-w-3xl mx-auto space-y-6 sm:space-y-8 animate-pulse p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12">
    <div className="h-24 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-56 bg-[#E5E0D6] dark:bg-zinc-800 rounded-3xl" />
    <div className="h-10 w-64 bg-[#E5E0D6] dark:bg-zinc-800 rounded-full" />
    <div className="space-y-3">
      <div className="h-20 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
      <div className="h-20 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
      <div className="h-20 bg-[#E5E0D6] dark:bg-zinc-800 rounded-2xl" />
    </div>
  </div>
);

export default function PatientExercises() {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [detailExercise, setDetailExercise] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [currentSet, setCurrentSet] = useState(1);
  const [sessionNotes, setSessionNotes] = useState('');
  const [exitConfirm, setExitConfirm] = useState(false);
  const [completedSetsLocal, setCompletedSetsLocal] = useState([]);

  // P3 affordance: right-edge fade over the filter row while more chips are off-screen
  const filterScrollRef = useRef(null);
  const updateFilterFade = useCallback(() => {
    const el = filterScrollRef.current;
    if (!el) return;
    const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 2;
    el.classList.toggle('at-end', atEnd);
  }, []);

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

  // 3. Fetch weekly stats
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
        duration: `${Math.round((assign.duration_seconds || 300) / 60)} min`,
        raw_sets: assign.sets,
        raw_reps: assign.reps,
        raw_duration_seconds: assign.duration_seconds,
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
        duration: `${Math.round((ex.duration_seconds || 300) / 60)} min`,
        description: ex.description,
        instructions: ex.instructions,
        safetyReminders: ex.safety_precautions || [],
        status: 'not_assigned',
        is_assigned: false
      };
    });
  }, [catalogExercises]);

  const startSession = (ex) => {
    if (!ex.is_assigned) {
      alert("This exercise is not currently prescribed to you.");
      return;
    }
    if (ex.status === 'completed' || ex.status === 'cancelled') {
      return;
    }
    setActiveSession(ex);
    setCurrentSet(1);
    setCompletedSetsLocal([]);
    setSessionNotes('');
    setExitConfirm(false);
  };

  const startRoutine = () => {
    const nextIncomplete = prescribedExercises.find(ex => ex.status !== 'completed');
    if (nextIncomplete) {
      startSession(nextIncomplete);
    } else if (prescribedExercises.length > 0) {
      startSession(prescribedExercises[0]);
    }
  };

  const submitSession = (completionStatus) => {
    if (logProgressMutation.isPending || !activeSession) return;
    
    const completedSets = completionStatus === 'completed' 
      ? activeSession.raw_sets 
      : currentSet - 1;
      
    logProgressMutation.mutate({
      assignment_id: activeSession.id,
      completed_sets: completedSets,
      completed_reps: activeSession.raw_reps,
      duration_seconds: activeSession.raw_duration_seconds,
      completion_status: completionStatus,
      notes: sessionNotes || undefined
    }, {
      onSuccess: () => {
        setActiveSession(null);
      }
    });
  };

  // Display-only transform: never expose raw snake_case enum values in the UI
  const formatSessionStatus = (status) => {
    const labels = { completed: 'Completed', partial: 'Partial', in_progress: 'In progress', assigned: 'Assigned' };
    return labels[status] || String(status || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
  };

  const completedCount = useMemo(() => {
    return prescribedExercises.filter((e) => e.status === 'completed').length;
  }, [prescribedExercises]);

  const progressPercent = useMemo(() => {
    if (prescribedExercises.length === 0) return 0;
    return Math.round((completedCount / prescribedExercises.length) * 100);
  }, [completedCount, prescribedExercises.length]);

  const estimatedMinutes = useMemo(() => {
    if (!assignments || assignments.length === 0) return 0;
    const totalSecs = assignments.reduce((acc, a) => acc + (a.duration_seconds || 300), 0);
    return Math.max(Math.round(totalSecs / 60), prescribedExercises.length > 0 ? prescribedExercises.length * 5 : 0);
  }, [assignments, prescribedExercises.length]);

  const filteredPrescribed = useMemo(() => {
    if (selectedCategory === 'All') return prescribedExercises;
    return prescribedExercises.filter((e) => e.category.toLowerCase() === selectedCategory.toLowerCase());
  }, [prescribedExercises, selectedCategory]);

  const filteredGeneral = useMemo(() => {
    if (selectedCategory === 'All') return generalExercises;
    return generalExercises.filter((e) => e.category.toLowerCase() === selectedCategory.toLowerCase());
  }, [generalExercises, selectedCategory]);

  if (isCatalogLoading || isAssignmentsLoading) {
    return <ExercisesSkeleton />;
  }

  if (catalogError || assignmentsError) {
    return (
      <div className="max-w-3xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-full flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#1E2A2B] dark:text-zinc-100">Failed to Load Exercises</h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400">
            {catalogError?.response?.data?.detail || assignmentsError?.response?.data?.detail || "An error occurred while loading your exercises. Please try again."}
          </p>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()} className="text-xs py-2 px-5 font-bold cursor-pointer">
          Retry Connection
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-7 sm:space-y-9 animate-fade-in p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12 text-[#1E2A2B] dark:text-zinc-100">
      
      {/* 0. PAGE HEADER (root tab — no back navigation) */}
      <header className="space-y-1 pt-1">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
          Exercises
        </h1>
        <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium">
          Your prescribed daily movement
        </p>
      </header>

      {/* 1. TODAY'S MOVEMENT HERO */}
      <section className="rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#1F4B45]/10 dark:border-zinc-800 p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="space-y-3 min-w-0 flex-1">
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#1F4B45] dark:text-[#5FC2B8]">
              Today's Movement
            </p>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 leading-tight">
              {prescribedExercises.length === 0
                ? 'Nothing prescribed right now'
                : progressPercent === 100
                ? 'Today\'s movement complete'
                : `${completedCount} of ${prescribedExercises.length} exercises done`}
            </h2>
            <p className="text-sm text-[#60716E] dark:text-zinc-400 font-medium">
              {prescribedExercises.length > 0
                ? `~${estimatedMinutes} minutes · guided by your therapist's plan`
                : 'New prescriptions from your physiotherapist will appear here.'}
            </p>

            {/* labeled completion bar — never an unlabeled indicator */}
            {prescribedExercises.length > 0 && (
              <div className="space-y-1.5 max-w-xs">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-[#60716E] dark:text-zinc-400">Session completion</span>
                  <span className="text-[#1F4B45] dark:text-[#5FC2B8] font-bold">{progressPercent}%</span>
                </div>
                <div className="h-2 rounded-full bg-[#E5E0D6]/70 dark:bg-zinc-800 overflow-hidden" aria-label={`Session completion ${progressPercent}%`}>
                  <div
                    className="h-full rounded-full bg-[#1F4B45] dark:bg-[#5FC2B8] transition-all duration-500"
                    style={{ width: `${Math.min(Math.max(progressPercent, 0), 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Primary action */}
            {prescribedExercises.length === 0 ? (
              <button
                onClick={() => navigate('/patient/care-plan')}
                className="inline-flex items-center gap-2 py-3 px-6 text-sm font-bold text-[#1F4B45] dark:text-[#5FC2B8] bg-white dark:bg-zinc-800 border border-[#1F4B45]/15 dark:border-zinc-700 rounded-2xl hover:bg-[#F7F4ED] dark:hover:bg-zinc-700 transition-all cursor-pointer min-h-[48px]"
              >
                View Care Plan Journey
                <ChevronRight className="w-4 h-4" />
              </button>
            ) : progressPercent === 100 ? (
              <div className="inline-flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-[#1F4B45] text-white text-xs font-bold shadow-sm">
                <CheckCircle2 className="w-4 h-4" />
                <span>All prescribed exercises completed</span>
              </div>
            ) : (
              <button
                onClick={startRoutine}
                className="inline-flex items-center gap-2 py-3 px-6 text-sm font-bold text-white bg-[#1F4B45] hover:bg-[#17352F] rounded-2xl shadow-md shadow-[#1F4B45]/20 transition-all cursor-pointer min-h-[48px]"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>{completedCount > 0 ? 'Continue Routine' : 'Start Routine'}</span>
              </button>
            )}
          </div>

          {/* Completion ring — always paired with the % + label */}
          <div className="relative w-28 h-28 sm:w-32 sm:h-32 flex items-center justify-center shrink-0 mx-auto sm:mx-0">
            <svg className="absolute w-full h-full -rotate-90" viewBox="0 0 112 112">
              <circle
                cx="56" cy="56" r="48"
                stroke="currentColor"
                strokeWidth="9"
                className="text-[#E5E0D6] dark:text-zinc-800"
                fill="transparent"
              />
              <circle
                cx="56" cy="56" r="48"
                stroke="currentColor"
                strokeWidth="9"
                strokeLinecap="round"
                className="text-[#1F4B45] dark:text-[#5FC2B8]"
                fill="transparent"
                strokeDasharray={2 * Math.PI * 48}
                strokeDashoffset={2 * Math.PI * 48 * (1 - Math.min(Math.max(progressPercent, 0), 100) / 100)}
              />
            </svg>
            <div className="text-center">
              <span className="text-2xl sm:text-3xl font-bold text-[#1E2A2B] dark:text-zinc-100 block leading-none">{progressPercent}%</span>
              <span className="text-xs font-semibold text-[#60716E] dark:text-zinc-400 block mt-1">done</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. EXERCISE CATEGORY FILTERS */}
      <div className="relative">
        <div
          ref={filterScrollRef}
          onScroll={updateFilterFade}
          className="flex items-center gap-2 overflow-x-auto pb-1 hide-scrollbar filter-scroll"
        >
        {categories.map((cat) => {
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-full text-[13px] font-bold transition border shrink-0 focus:outline-none cursor-pointer min-h-[44px] ${
                isSelected
                  ? 'bg-[#1F4B45] border-[#1F4B45] text-white shadow-sm'
                  : 'bg-white dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-800 text-[#60716E] dark:text-zinc-400 hover:bg-[#EEF5F1] dark:hover:bg-zinc-800 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8]'
              }`}
            >
              {cat}
            </button>
          );
        })}
        </div>
        {/* right-edge fade — subtle cue that more chips exist off-screen */}
        <div
          aria-hidden="true"
          className="filter-fade-right pointer-events-none absolute inset-y-0 right-0 w-10 z-10"
        />
      </div>

      {/* 3. PRESCRIBED EXERCISES — compact, scannable cards */}
      <section className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
              Daily Prescriptions
            </p>
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
              Prescribed Exercises
            </h2>
          </div>
          {prescribedExercises.length > 0 && (
            <span className="shrink-0 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] bg-[#EEF5F1] dark:bg-zinc-800 border border-[#1F4B45]/10 dark:border-zinc-700 px-3 py-1.5 rounded-full">
              {completedCount} / {prescribedExercises.length} done
            </span>
          )}
        </div>

        {filteredPrescribed.length === 0 ? (
          <div className="text-center py-10 px-6 space-y-4 rounded-2xl border border-dashed border-[#E5E0D6] dark:border-zinc-800 bg-white/60 dark:bg-zinc-900/60">
            <div className="w-12 h-12 rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800 flex items-center justify-center mx-auto text-[#1F4B45] dark:text-[#5FC2B8]">
              <Dumbbell className="w-6 h-6" />
            </div>
            <div>
              <p className="font-bold text-[15px] text-[#1E2A2B] dark:text-zinc-100">No prescribed routines in this category</p>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1">
                Your therapist's prescribed movements will appear here.
              </p>
            </div>
            <button
              onClick={() => navigate('/patient/care-plan')}
              className="inline-flex items-center justify-center gap-1.5 px-5 rounded-xl border border-[#1F4B45]/15 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[13px] font-bold text-[#1F4B45] dark:text-[#5FC2B8] hover:bg-[#EEF5F1] dark:hover:bg-zinc-700 transition cursor-pointer min-h-[44px]"
            >
              View Care Plan Journey
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredPrescribed.map((ex) => {
              const isCompleted = ex.status === 'completed';
              const isInProgress = ex.status === 'in_progress';
              const Icon = getCategoryIcon(ex.category);

              return (
                <div
                  key={ex.id}
                  className={`flex items-center gap-4 p-4 rounded-2xl border transition bg-white dark:bg-zinc-900 ${
                    isCompleted
                      ? 'border-[#1F4B45]/15 bg-[#EEF5F1]/50 dark:bg-zinc-800/40'
                      : 'border-[#E5E0D6] dark:border-zinc-800'
                  }`}
                >
                  <div
                    className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${
                      isCompleted
                        ? 'bg-[#1F4B45] text-white'
                        : 'bg-[#EEF5F1] text-[#1F4B45] dark:bg-zinc-800 dark:text-[#5FC2B8]'
                    }`}
                  >
                    {isCompleted ? <Check className="w-5 h-5" strokeWidth={2.6} /> : <Icon className="w-5 h-5" strokeWidth={2.2} />}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className={`text-[15px] font-bold line-clamp-2 ${isCompleted ? 'text-[#60716E] dark:text-zinc-400' : 'text-[#1E2A2B] dark:text-zinc-100'}`}>
                        {ex.name}
                      </p>
                      <span className="shrink-0 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] bg-[#EEF5F1]/80 dark:bg-zinc-800 px-2 py-0.5 rounded-full">
                        {ex.category}
                      </span>
                    </div>
                    <p className="text-[13px] text-[#60716E] dark:text-zinc-400 font-medium mt-0.5">
                      {ex.raw_sets} sets × {ex.raw_reps} reps · {ex.duration}
                    </p>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => setDetailExercise(ex)}
                      aria-label={`Guidelines for ${ex.name}`}
                      className="w-11 h-11 rounded-xl flex items-center justify-center text-[#60716E] dark:text-zinc-400 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8] hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 transition cursor-pointer"
                    >
                      <ClipboardCheck className="w-4.5 h-4.5" />
                    </button>

                    {isCompleted ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-[#1F4B45] dark:text-[#5FC2B8] px-3 min-h-[44px]">
                        <CheckCircle2 className="w-4 h-4" />
                        Done
                      </span>
                    ) : (
                      <button
                        onClick={() => startSession(ex)}
                        className={`text-[13px] font-bold py-2 px-4 border transition rounded-xl flex items-center gap-1 cursor-pointer min-h-[44px] ${
                          isInProgress
                            ? 'bg-[#C9A86A]/10 border-[#C9A86A]/40 text-[#C9A86A] hover:bg-[#C9A86A]/20'
                            : 'bg-[#1F4B45] border-[#1F4B45] text-white hover:bg-[#17352F]'
                        }`}
                      >
                        {isInProgress ? 'Resume' : 'Start'}
                        <Play className="w-3 h-3 fill-current" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4. REFERENCE CATALOG */}
      <section className="space-y-4">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
            Movement Library
          </p>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
            Reference Catalog
          </h2>
        </div>

        {filteredGeneral.length === 0 ? (
          <p className="text-[13px] text-[#60716E] dark:text-zinc-400 italic py-2">No reference catalog items found.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {filteredGeneral.map((ex) => {
              const Icon = getCategoryIcon(ex.category);
              return (
                <div
                  key={ex.id}
                  className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl p-4 flex items-start gap-3.5"
                >
                  <div className="w-10 h-10 rounded-xl bg-[#F7F4ED] dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center shrink-0 text-[#60716E] dark:text-zinc-400">
                    <Icon className="w-4.5 h-4.5" strokeWidth={2} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-100 leading-snug line-clamp-2">
                        {ex.name}
                      </h3>
                      <span className="shrink-0 text-xs font-semibold text-[#60716E] dark:text-zinc-400 px-2 py-0.5 rounded-full bg-[#F7F4ED] dark:bg-zinc-800">
                        {ex.category}
                      </span>
                    </div>
                    <p className="text-xs text-[#60716E] dark:text-zinc-400 mt-0.5 font-medium">
                      {ex.raw_sets ?? ex.sets} · {ex.reps} · {ex.duration}
                    </p>
                    <button
                      type="button"
                      onClick={() => setDetailExercise(ex)}
                      className="mt-1 inline-flex items-center gap-0.5 self-start px-2 -mx-2 text-[13px] font-bold text-[#C1694A] hover:text-[#a85538] cursor-pointer min-h-[44px]"
                    >
                      Guidelines
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 5. RECENT COMPLETIONS & PRESCRIPTION GUIDANCE */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">

        {/* RECENT COMPLETIONS */}
        <section className="rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 space-y-4">
          <div>
            <p className="text-xs font-extrabold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
              Home Session Logs
            </p>
            <h3 className="font-bold text-base text-[#1E2A2B] dark:text-zinc-50 mt-0.5">
              Recent Completions
            </h3>
          </div>

          {stats?.recent_activity && stats.recent_activity.length > 0 ? (
            <div className="space-y-2.5">
              {stats.recent_activity.slice(0, 3).map((activity, idx) => (
                <div key={idx} className="p-3 bg-[#F7F4ED]/60 dark:bg-zinc-800/40 border border-[#E5E0D6]/40 dark:border-zinc-800 rounded-xl flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-bold text-[#1E2A2B] dark:text-zinc-100 truncate">{activity.exercise_name || activity.exercise_title}</p>
                    <p className="text-xs text-[#60716E] dark:text-zinc-400 mt-0.5">Logged: {new Date(activity.completed_at).toLocaleDateString()}</p>
                  </div>
                  <span className={`shrink-0 inline-flex px-2 py-0.5 rounded-full text-xs font-bold border ${
                    activity.completion_status === 'completed' || activity.status === 'completed'
                      ? 'bg-[#EEF5F1] text-[#1F4B45] dark:text-[#5FC2B8] border-[#1F4B45]/10 dark:border-zinc-700'
                      : 'bg-[#C9A86A]/10 text-[#C9A86A] border-[#C9A86A]/20'
                  }`}>
                    {formatSessionStatus(activity.completion_status || activity.status)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[13px] text-[#60716E] dark:text-zinc-400 italic py-2">No exercise sessions logged yet.</p>
          )}
        </section>

        {/* PRESCRIPTION GUIDANCE */}
        <section className="rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED] dark:bg-zinc-900 p-6 space-y-4 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="w-10 h-10 rounded-2xl bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center text-[#1F4B45] dark:text-[#5FC2B8]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-100">Prescription Guidance</h4>
              <p className="text-[13px] text-[#60716E] dark:text-zinc-400 mt-1.5 leading-relaxed">
                Exercises configured here are prescribed directly by your physical therapist. Perform them with proper form and adhere to target repetitions.
              </p>
            </div>
          </div>
          <div className="pt-3 text-xs text-[#60716E] dark:text-zinc-400 font-semibold border-t border-[#E5E0D6]/40 dark:border-zinc-800">
            <span>Clinical target locks are maintained for safety. 🔒</span>
          </div>
        </section>

      </div>

      {/* 6. EXERCISE INSTRUCTIONS GUIDELINE MODAL */}
      {detailExercise && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="relative bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6 shadow-xl animate-scale-up">

            <div className="flex justify-between items-start gap-4 pb-3 border-b border-[#E5E0D6]/40 dark:border-zinc-800">
              <div>
                <span className="px-2.5 py-0.5 rounded-full bg-[#EEF5F1] dark:bg-zinc-800 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] border border-[#1F4B45]/10 dark:border-zinc-700">
                  {detailExercise.category}
                </span>
                <h3 className="text-xl font-bold text-[#1E2A2B] dark:text-zinc-50 mt-2 leading-tight">
                  {detailExercise.name}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setDetailExercise(null)}
                aria-label="Close guidelines"
                className="w-11 h-11 rounded-xl hover:bg-[#F7F4ED] dark:hover:bg-zinc-800 text-[#60716E] dark:text-zinc-400 flex items-center justify-center border border-[#E5E0D6] dark:border-zinc-700 cursor-pointer shrink-0"
              >
                <X className="w-4.5 h-4.5" />
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center bg-[#F7F4ED]/50 dark:bg-zinc-800/40 border border-[#E5E0D6]/50 dark:border-zinc-800 rounded-2xl py-3 px-2">
              <div>
                <span className="text-xs text-[#60716E] dark:text-zinc-400 uppercase tracking-wider block font-semibold">Sets</span>
                <span className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 mt-0.5 block">
                  {String(detailExercise.sets).split(' ')[0]}
                </span>
              </div>
              <div>
                <span className="text-xs text-[#60716E] dark:text-zinc-400 uppercase tracking-wider block font-semibold">Reps</span>
                <span className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 mt-0.5 block">{detailExercise.reps}</span>
              </div>
              <div>
                <span className="text-xs text-[#60716E] dark:text-zinc-400 uppercase tracking-wider block font-semibold">Duration</span>
                <span className="text-sm font-bold text-[#1E2A2B] dark:text-zinc-100 mt-0.5 block">{detailExercise.duration}</span>
              </div>
            </div>

            {detailExercise.instructions && detailExercise.instructions.length > 0 && (
              <div className="space-y-3">
                <h4 className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-100 flex items-center gap-1.5">
                  <ClipboardCheck className="w-4.5 h-4.5 text-[#1F4B45] dark:text-[#5FC2B8]" />
                  Movement Guidelines
                </h4>
                <ol className="space-y-2 text-[13px] text-[#60716E] dark:text-zinc-400 list-decimal pl-4.5 leading-relaxed">
                  {detailExercise.instructions.map((step, idx) => (
                    <li key={idx} className="pl-1">
                      {step}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {detailExercise.safetyReminders && detailExercise.safetyReminders.length > 0 && (
              <div className="bg-red-50/40 dark:bg-red-950/20 border border-red-200/50 dark:border-red-900/30 p-4 rounded-2xl space-y-2">
                <h4 className="font-bold text-[13px] text-red-800 dark:text-red-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0" />
                  Clinician Safety Precautions
                </h4>
                <ul className="list-disc pl-4 text-[13px] text-red-700 dark:text-red-400/90 space-y-1 leading-normal">
                  {detailExercise.safetyReminders.map((reminder, idx) => (
                    <li key={idx}>
                      {reminder}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setDetailExercise(null)}
                className="flex-1 py-2.5 text-[13px] border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[#60716E] dark:text-zinc-300 font-bold rounded-xl cursor-pointer min-h-[48px]"
              >
                Close Guidelines
              </button>
              {detailExercise.is_assigned && detailExercise.status !== 'completed' && (
                <button
                  onClick={() => {
                    setDetailExercise(null);
                    startSession(detailExercise);
                  }}
                  className="flex-1 py-2.5 text-[13px] font-bold text-white bg-[#1F4B45] hover:bg-[#17352F] rounded-xl cursor-pointer min-h-[48px]"
                >
                  {detailExercise.status === 'in_progress' ? 'Resume Session' : 'Start Session'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 7. ACTIVE WORKOUT SESSION (DEDICATED IMMERSIVE WORKOUT EXPERIENCE) */}
      {activeSession && (
        <div className="fixed inset-0 z-50 bg-[#F6F2EA] dark:bg-zinc-950 overflow-y-auto flex flex-col p-4 sm:p-6 md:p-8 animate-fade-in text-[#1E2A2B] dark:text-zinc-100">
          <div className="max-w-xl w-full mx-auto flex-1 flex flex-col justify-between space-y-6">

            {/* Header */}
            <div className="flex justify-between items-start border-b border-[#E5E0D6] dark:border-zinc-800 pb-4">
              <div>
                <span className="inline-block px-2.5 py-0.5 rounded-full bg-[#EEF5F1] dark:bg-zinc-800 text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] border border-[#1F4B45]/10 dark:border-zinc-700">
                  Active Staged Exercise
                </span>
                <h2 className="text-xl sm:text-2xl font-bold text-[#1E2A2B] dark:text-zinc-50 mt-1.5 leading-tight">
                  {activeSession.name}
                </h2>
              </div>

              <button
                type="button"
                onClick={() => {
                  if (currentSet > 1 && currentSet <= activeSession.raw_sets) {
                    setExitConfirm(true);
                  } else {
                    setActiveSession(null);
                  }
                }}
                aria-label="Exit workout session"
                className="w-11 h-11 rounded-2xl bg-white dark:bg-zinc-800 hover:bg-[#F7F4ED] dark:hover:bg-zinc-700 text-[#60716E] dark:text-zinc-400 flex items-center justify-center border border-[#E5E0D6] dark:border-zinc-700 cursor-pointer shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Workout Body */}
            <div className="flex-1 space-y-6 py-2">

              {currentSet <= activeSession.raw_sets ? (
                <div className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-6 sm:p-8 text-center space-y-6">

                  {/* Set number */}
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-[#1F4B45] dark:text-[#5FC2B8] uppercase tracking-widest">
                      Set {currentSet} of {activeSession.raw_sets}
                    </p>
                    <div className="w-full bg-[#E5E0D6]/30 dark:bg-zinc-800 h-2.5 rounded-full overflow-hidden mt-2" aria-label={`Set ${currentSet} of ${activeSession.raw_sets}`}>
                      <div
                        className="bg-[#1F4B45] dark:bg-[#5FC2B8] h-full rounded-full transition-all duration-300"
                        style={{ width: `${((currentSet - 1) / activeSession.raw_sets) * 100}%` }}
                      />
                    </div>
                  </div>

                  {/* Large Central Metric */}
                  <div className="py-6 bg-[#F7F4ED]/50 dark:bg-zinc-800/40 rounded-2xl border border-[#E5E0D6]/50 dark:border-zinc-700/50 space-y-1">
                    <p className="text-5xl sm:text-6xl font-bold text-[#1F4B45] dark:text-[#5FC2B8] tracking-tight">
                      {activeSession.raw_reps}
                    </p>
                    <span className="text-xs font-bold uppercase tracking-widest text-[#60716E] dark:text-zinc-400">
                      Reps
                    </span>
                  </div>

                  {/* Rest Info */}
                  <div className="text-[13px] text-[#60716E] dark:text-zinc-400 font-semibold flex items-center justify-center gap-1.5">
                    <span>Rest before next set: <strong>60 sec</strong></span>
                  </div>

                  {/* Set progression indicators */}
                  <div className="flex items-center justify-center gap-3 pt-1">
                    {[...Array(activeSession.raw_sets)].map((_, idx) => {
                      const setNum = idx + 1;
                      const isPast = setNum < currentSet;
                      const isCurr = setNum === currentSet;
                      return (
                        <div
                          key={setNum}
                          className={`w-10 h-10 rounded-xl flex items-center justify-center text-[13px] font-bold border transition-all ${
                            isPast
                              ? 'bg-[#1F4B45] text-white border-[#1F4B45]'
                              : isCurr
                              ? 'bg-[#EEF5F1] text-[#1F4B45] dark:text-[#5FC2B8] border-[#1F4B45] dark:border-[#5FC2B8] ring-2 ring-[#1F4B45]/20'
                              : 'bg-white dark:bg-zinc-800 text-[#60716E] dark:text-zinc-400 border-[#E5E0D6] dark:border-zinc-700'
                          }`}
                        >
                          {isPast ? <Check className="w-4 h-4" strokeWidth={3} /> : setNum}
                        </div>
                      );
                    })}
                  </div>

                  {/* Complete Set CTA */}
                  <button
                    onClick={() => {
                      setCompletedSetsLocal([...completedSetsLocal, { set: currentSet, reps: activeSession.raw_reps }]);
                      setCurrentSet(currentSet + 1);
                    }}
                    className="w-full py-4 text-sm font-bold text-white bg-[#1F4B45] hover:bg-[#17352F] rounded-2xl shadow-md shadow-[#1F4B45]/20 transition-all cursor-pointer min-h-[48px]"
                  >
                    Complete Set {currentSet}
                  </button>

                  <button
                    type="button"
                    onClick={() => setDetailExercise(activeSession)}
                    className="text-[13px] font-bold text-[#60716E] dark:text-zinc-400 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8] cursor-pointer"
                  >
                    View Instructions
                  </button>
                </div>
              ) : (
                <div className="bg-[#EEF5F1]/40 dark:bg-zinc-900/60 border border-[#1F4B45]/15 dark:border-zinc-800 rounded-3xl p-6 sm:p-8 space-y-6">
                  <div className="text-center space-y-2">
                    <ClipboardCheck className="w-12 h-12 text-[#1F4B45] dark:text-[#5FC2B8] mx-auto" />
                    <h3 className="text-2xl font-bold text-[#1E2A2B] dark:text-zinc-50">Exercise Complete!</h3>
                    <p className="text-[13px] sm:text-sm text-[#60716E] dark:text-zinc-400 max-w-sm mx-auto">
                      All {activeSession.raw_sets} prescribed sets completed. Add any discomfort or performance notes below.
                    </p>
                  </div>

                  <div className="bg-white dark:bg-zinc-900 border border-[#E5E0D6]/70 dark:border-zinc-800 rounded-2xl p-4 space-y-2 text-[13px]">
                    <div className="flex justify-between font-semibold text-[#1E2A2B] dark:text-zinc-200">
                      <span>Prescription:</span>
                      <span>{activeSession.raw_sets} sets × {activeSession.raw_reps} reps</span>
                    </div>
                    <div className="flex justify-between font-semibold text-[#1F4B45] dark:text-[#5FC2B8]">
                      <span>Performance:</span>
                      <span>{completedSetsLocal.length} sets completed</span>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[13px] font-bold text-[#1E2A2B] dark:text-zinc-200 block">
                      Session Notes / Pain feedback (optional)
                    </label>
                    <textarea
                      value={sessionNotes}
                      onChange={(e) => setSessionNotes(e.target.value)}
                      placeholder="Add pain levels or biomechanical sensations..."
                      className="w-full h-24 p-3 text-[13px] bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 rounded-xl focus:outline-none focus:ring-1 focus:ring-[#1F4B45] resize-none text-[#1E2A2B] dark:text-zinc-100"
                    />
                  </div>

                  {logProgressMutation.isError && (
                    <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-[13px] rounded-xl">
                      {logProgressMutation.error?.response?.data?.detail || "Failed to submit session. Please check connection and retry."}
                    </div>
                  )}

                  <button
                    disabled={logProgressMutation.isPending}
                    onClick={() => submitSession('completed')}
                    className="w-full py-4 text-sm font-bold text-white bg-[#1F4B45] hover:bg-[#17352F] rounded-2xl shadow-md shadow-[#1F4B45]/20 transition-all cursor-pointer min-h-[48px] disabled:opacity-60"
                  >
                    {logProgressMutation.isPending ? 'Saving Workout...' : 'Finish & Submit Exercise'}
                  </button>
                </div>
              )}

              {/* Safety banner */}
              <div className="p-4 bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl flex items-center gap-3">
                <ShieldCheck className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8] shrink-0" />
                <p className="text-[13px] text-[#60716E] dark:text-zinc-400">
                  Discontinue the set immediately if sharp pain occurs and notify your physical therapist.
                </p>
              </div>

            </div>

            {/* Exit confirmation modal */}
            {exitConfirm && (
              <div className="fixed inset-0 z-[55] flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
                <div className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
                  <h4 className="font-bold text-sm text-[#1E2A2B] dark:text-zinc-50">Exit Workout Session?</h4>
                  <p className="text-[13px] text-[#60716E] dark:text-zinc-400 leading-relaxed">
                    You have performed {currentSet - 1} sets. Would you like to log this as a partial session or discard?
                  </p>

                  <div className="flex flex-col gap-2 pt-2">
                    <button
                      disabled={logProgressMutation.isPending}
                      onClick={() => submitSession('partial')}
                      className="w-full py-2.5 text-[13px] font-bold bg-[#1F4B45] text-white rounded-xl cursor-pointer min-h-[44px] disabled:opacity-60"
                    >
                      {logProgressMutation.isPending ? 'Submitting...' : 'Submit Partial Completion'}
                    </button>
                    <button
                      onClick={() => setActiveSession(null)}
                      className="w-full py-2.5 text-[13px] font-bold border border-red-200 bg-red-50 text-red-600 hover:bg-red-100 rounded-xl transition cursor-pointer min-h-[44px]"
                    >
                      Discard & Exit
                    </button>
                    <button
                      onClick={() => setExitConfirm(false)}
                      className="w-full py-2.5 text-[13px] font-bold border border-[#E5E0D6] bg-white text-[#60716E] hover:bg-[#F7F4ED] rounded-xl transition cursor-pointer min-h-[44px]"
                    >
                      Resume Workout
                    </button>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>
      )}

    </div>
  );
}
