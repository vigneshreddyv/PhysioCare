import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import Button from '../../components/common/Button';
import ErrorState from '../../components/common/ErrorState';
import {
  Dumbbell,
  ClipboardList,
  Plus,
  Save,
  CheckCircle2,
  ArrowLeft,
  AlertTriangle,
  HeartPulse,
} from '../../components/common/LucideCompat';

// Custom lightweight skeleton for loading state
const AssignmentListSkeleton = () => (
  <div className="space-y-4 animate-pulse">
    <div className="h-16 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-28 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-28 bg-gray-100 rounded-2xl border border-gray-200" />
  </div>
);

export default function ExerciseAssignmentManagement() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const role = user?.role || 'admin';
  const prefix = role === 'doctor' ? '/doctor' : '/admin';

  // 1. Fetch patient profile
  const { data: patients } = useQuery({
    queryKey: ['patients'],
    queryFn: async () => {
      const response = await api.get('/users/patients');
      return response.data;
    }
  });

  const selectedPatient = useMemo(() => {
    if (!patients) return null;
    return patients.find(p => p.id === patientId || p.patient_id === patientId);
  }, [patients, patientId]);

  // 2. Fetch care plans for patient
  const { data: carePlans, isLoading: isPlansLoading } = useQuery({
    queryKey: ['patientCarePlans', patientId],
    queryFn: async () => {
      const response = await api.get(`/care-plans/patient/${patientId}`);
      return response.data;
    }
  });

  // 3. Fetch exercise catalog
  const { data: exercises, isLoading: isExercisesLoading } = useQuery({
    queryKey: ['exercisesCatalog'],
    queryFn: async () => {
      const response = await api.get('/exercises');
      return response.data;
    }
  });

  // 4. Fetch existing assignments for patient
  const { data: assignments, isLoading: isAssignmentsLoading, error: assignmentsError, refetch: refetchAssignments } = useQuery({
    queryKey: ['patientExerciseAssignments', patientId],
    queryFn: async () => {
      const response = await api.get(`/exercise-assignments?patient_id=${patientId}`);
      return response.data;
    }
  });

  // Local Form State
  const [selectedPlanId, setSelectedPlanId] = useState('');
  const [selectedStageId, setSelectedStageId] = useState('');
  const [selectedExerciseId, setSelectedExerciseId] = useState('');
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(10);
  const [durationMinutes, setDurationMinutes] = useState(5);
  const [frequency, setFrequency] = useState('daily');

  // Edit Assignment Form State
  const [editingAssignmentId, setEditingAssignmentId] = useState(null);
  const [editSets, setEditSets] = useState(3);
  const [editReps, setEditReps] = useState(10);
  const [editDurationMinutes, setEditDurationMinutes] = useState(5);
  const [editFrequency, setEditFrequency] = useState('daily');
  const [editStatus, setEditStatus] = useState('assigned');

  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Extract available stages of the selected plan
  const selectedPlanStages = useMemo(() => {
    if (!carePlans || !selectedPlanId) return [];
    const plan = carePlans.find(cp => cp.id === selectedPlanId);
    return plan ? plan.stages : [];
  }, [carePlans, selectedPlanId]);

  // Mutations
  const assignExerciseMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post('/exercise-assignments', payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patientExerciseAssignments', patientId] });
      setSuccessMessage('Exercise prescribed successfully.');
      setSelectedExerciseId('');
      setErrorMessage('');
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to prescribe exercise.');
    }
  });

  const updateAssignmentMutation = useMutation({
    mutationFn: async ({ id, payload }) => {
      const response = await api.patch(`/exercise-assignments/${id}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patientExerciseAssignments', patientId] });
      setSuccessMessage('Prescription updated successfully.');
      setEditingAssignmentId(null);
      setErrorMessage('');
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to update prescription.');
    }
  });

  const handleCreateAssignment = (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    if (!selectedPlanId || !selectedStageId || !selectedExerciseId) {
      setErrorMessage('Please select a Care Plan, Stage, and Exercise.');
      return;
    }

    const payload = {
      patient_id: patientId,
      care_plan_id: selectedPlanId,
      stage_id: selectedStageId,
      exercise_id: selectedExerciseId,
      sets: parseInt(sets) || 3,
      reps: parseInt(reps) || 10,
      duration_seconds: (parseInt(durationMinutes) || 5) * 60,
      frequency: frequency
    };

    assignExerciseMutation.mutate(payload);
  };

  const handleStartEdit = (assign) => {
    setEditingAssignmentId(assign.id);
    setEditSets(assign.sets);
    setEditReps(assign.reps);
    setEditDurationMinutes(Math.round(assign.duration_seconds / 60));
    setEditFrequency(assign.frequency);
    setEditStatus(assign.status);
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleSaveEdit = (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    const payload = {
      sets: parseInt(editSets) || 3,
      reps: parseInt(editReps) || 10,
      duration_seconds: (parseInt(editDurationMinutes) || 5) * 60,
      frequency: editFrequency,
      status: editStatus
    };

    updateAssignmentMutation.mutate({ id: editingAssignmentId, payload });
  };

  if (assignmentsError) {
    return <ErrorState message="Could not load assignments details." onRetry={() => refetchAssignments()} />;
  }

  const isLoading = isPlansLoading || isExercisesLoading || isAssignmentsLoading;

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. HEADER CONTAINER */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 border-b border-[#E5E0D6]/65 pb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Prescription Panel</span>
          <h1 className="text-3xl font-extrabold text-[#183B4A] mt-1">
            Exercise Desk: {selectedPatient?.full_name || 'Patient'}
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-[#60716E]">
            {selectedPatient?.email} {selectedPatient?.date_of_birth && `| DOB: ${selectedPatient.date_of_birth}`}
          </p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => navigate(`${prefix}/patients`)}
          className="text-xs font-bold py-2.5 px-4 rounded-xl border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex items-center gap-1.5 shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Patients
        </Button>
      </div>

      {/* ALERT MESSAGES */}
      {successMessage && (
        <div className="p-4 bg-[#EEF5F1] border border-[#0F6B63]/20 rounded-2xl text-[#0F6B63] font-bold text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200/50 rounded-2xl text-red-700 font-bold text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {errorMessage}
        </div>
      )}

      {isLoading ? (
        <AssignmentListSkeleton />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* LEFT: ASSIGN NEW EXERCISE FORM */}
          <div className="lg:col-span-1 space-y-6">
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 shadow-sm space-y-5">
              <div className="pb-3 border-b border-[#E5E0D6]/40 flex items-center gap-2">
                <HeartPulse className="w-5 h-5 text-[#0F6B63]" />
                <h3 className="text-base font-extrabold text-[#183B4A]">
                  Prescribe Exercise
                </h3>
              </div>

              <form onSubmit={handleCreateAssignment} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#183B4A]">Select Care Plan</label>
                  <select
                    className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none"
                    value={selectedPlanId}
                    onChange={e => {
                      setSelectedPlanId(e.target.value);
                      setSelectedStageId('');
                    }}
                  >
                    <option value="">-- Choose Plan --</option>
                    {carePlans?.map(plan => (
                      <option key={plan.id} value={plan.id}>{plan.title} ({plan.status})</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#183B4A]">Select Milestone Stage</label>
                  <select
                    disabled={!selectedPlanId}
                    className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                    value={selectedStageId}
                    onChange={e => setSelectedStageId(e.target.value)}
                  >
                    <option value="">-- Choose Stage --</option>
                    {selectedPlanStages.map(stage => (
                      <option key={stage.stage_id} value={stage.stage_id}>{stage.title} ({stage.status})</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#183B4A]">Select Exercise Movement</label>
                  <select
                    className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none"
                    value={selectedExerciseId}
                    onChange={e => setSelectedExerciseId(e.target.value)}
                  >
                    <option value="">-- Choose Exercise --</option>
                    {exercises?.filter(ex => ex.active).map(ex => (
                      <option key={ex.id} value={ex.id}>{ex.title} ({ex.category})</option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4 pt-2 border-t border-[#E5E0D6]/35">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#183B4A]">Target Sets</label>
                    <input
                      type="number"
                      min="1"
                      className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] text-center focus:ring-4 focus:ring-[#0F6B63]/10 outline-none"
                      value={sets}
                      onChange={e => setSets(parseInt(e.target.value) || 3)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#183B4A]">Target Reps</label>
                    <input
                      type="number"
                      min="1"
                      className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] text-center focus:ring-4 focus:ring-[#0F6B63]/10 outline-none"
                      value={reps}
                      onChange={e => setReps(parseInt(e.target.value) || 10)}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#183B4A]">Duration (Min)</label>
                    <input
                      type="number"
                      min="1"
                      className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] text-center focus:ring-4 focus:ring-[#0F6B63]/10 outline-none"
                      value={durationMinutes}
                      onChange={e => setDurationMinutes(parseInt(e.target.value) || 5)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#183B4A]">Frequency</label>
                    <select
                      className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 outline-none"
                      value={frequency}
                      onChange={e => setFrequency(e.target.value)}
                    >
                      <option value="daily">Daily</option>
                      <option value="twice a day">Twice a day</option>
                      <option value="three times a day">Three times a day</option>
                      <option value="weekly">Weekly</option>
                    </select>
                  </div>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  className="w-full text-xs py-2.5 mt-4 rounded-xl font-bold cursor-pointer border border-transparent"
                  disabled={assignExerciseMutation.isPending}
                >
                  <Plus className="w-4 h-4" />
                  Assign to Patient
                </Button>
              </form>
            </section>
          </div>

          {/* RIGHT: EXISTING ASSIGNMENTS LIST */}
          <div className="lg:col-span-2 space-y-6">
            <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 shadow-sm space-y-5">
              <div className="pb-3 border-b border-[#E5E0D6]/40 flex items-center gap-2">
                <Dumbbell className="w-5 h-5 text-[#0F6B63]" />
                <h3 className="text-base font-extrabold text-[#183B4A]">
                  Active & Prescribed Routines
                </h3>
              </div>

              {!assignments || assignments.length === 0 ? (
                <div className="text-center py-16 bg-[#F7F4ED]/15 border border-dashed border-[#E5E0D6] rounded-2xl max-w-md mx-auto space-y-4">
                  <ClipboardList className="w-8 h-8 text-[#60716E]/40 mx-auto" />
                  <div className="space-y-1">
                    <h4 className="text-sm font-extrabold text-[#183B4A]">No prescribed routines</h4>
                    <p className="text-xs text-[#60716E] leading-relaxed px-4">
                      No exercises are assigned to this patient's care stages. Complete the form to prescribe dynamic routines.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {assignments.map(assign => {
                    const exObj = exercises?.find(ex => ex.id === assign.exercise_id);
                    const cpObj = carePlans?.find(cp => cp.id === assign.care_plan_id);
                    const stageObj = cpObj?.stages?.find(s => s.stage_id === assign.stage_id);

                    const isEditingThis = editingAssignmentId === assign.id;

                    return (
                      <div key={assign.id} className="p-4 border border-[#E5E0D6] bg-[#F7F4ED]/10 rounded-2xl space-y-3">
                        <div className="flex justify-between items-start gap-4">
                          <div>
                            <h4 className="font-extrabold text-sm text-[#183B4A]">{exObj?.title || 'Movement'}</h4>
                            <p className="text-[10px] text-[#60716E] mt-1 font-semibold">
                              Plan: {cpObj?.title || 'Plan'} | Stage: {stageObj?.title || assign.stage_id}
                            </p>
                          </div>
                          <span className={`px-2.5 py-0.5 rounded text-[8px] font-bold uppercase border shrink-0 ${
                            assign.status === 'completed' 
                              ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                              : assign.status === 'in_progress'
                                ? 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20'
                                : assign.status === 'cancelled'
                                  ? 'bg-red-50 text-red-700 border-red-200/50'
                                  : 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10'
                          }`}>
                            {assign.status}
                          </span>
                        </div>

                        {isEditingThis ? (
                          <form onSubmit={handleSaveEdit} className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-[#E5E0D6]/35">
                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-[#60716E] uppercase">Sets</label>
                              <input
                                type="number"
                                min="1"
                                className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2 text-xs text-center text-[#183B4A] focus:ring-2 focus:ring-[#0F6B63]/10 outline-none"
                                value={editSets}
                                onChange={e => setEditSets(parseInt(e.target.value) || 3)}
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-[#60716E] uppercase">Reps</label>
                              <input
                                type="number"
                                min="1"
                                className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2 text-xs text-center text-[#183B4A] focus:ring-2 focus:ring-[#0F6B63]/10 outline-none"
                                value={editReps}
                                onChange={e => setEditReps(parseInt(e.target.value) || 10)}
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-[#60716E] uppercase">Duration (Min)</label>
                              <input
                                type="number"
                                min="1"
                                className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2 text-xs text-center text-[#183B4A] focus:ring-2 focus:ring-[#0F6B63]/10 outline-none"
                                value={editDurationMinutes}
                                onChange={e => setEditDurationMinutes(parseInt(e.target.value) || 5)}
                              />
                            </div>
                            <div className="space-y-1">
                              <label className="text-[10px] font-bold text-[#60716E] uppercase">Status</label>
                              <select
                                className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2 text-xs text-[#183B4A] outline-none"
                                value={editStatus}
                                onChange={e => setEditStatus(e.target.value)}
                              >
                                <option value="assigned">Assigned</option>
                                <option value="in_progress">In Progress</option>
                                <option value="completed">Completed</option>
                                <option value="cancelled">Cancelled</option>
                              </select>
                            </div>
                            <div className="col-span-2 sm:col-span-4 flex justify-end gap-2 pt-3 border-t border-[#E5E0D6]/35 mt-2">
                              <button
                                type="button"
                                className="text-xs px-3.5 py-1.5 border border-[#E5E0D6] rounded-xl font-bold text-[#60716E] hover:text-[#0F6B63]"
                                onClick={() => setEditingAssignmentId(null)}
                              >
                                Cancel
                              </button>
                              <Button
                                type="submit"
                                variant="primary"
                                className="text-[10px] py-1.5 px-4 rounded-xl font-bold cursor-pointer border border-transparent"
                                disabled={updateAssignmentMutation.isPending}
                              >
                                <Save className="w-3.5 h-3.5" />
                                Save
                              </Button>
                            </div>
                          </form>
                        ) : (
                          <div className="flex justify-between items-center pt-2 border-t border-[#E5E0D6]/35 mt-2">
                            <div className="text-[10px] text-[#60716E] space-x-3">
                              <span><strong>Prescription:</strong> {assign.sets} sets · {assign.reps} reps · {Math.round(assign.duration_seconds / 60)} min</span>
                              <span><strong>Frequency:</strong> {assign.frequency}</span>
                            </div>
                            <button
                              type="button"
                              className="text-[#0F6B63] text-[10px] font-extrabold hover:underline flex items-center gap-1 cursor-pointer"
                              onClick={() => handleStartEdit(assign)}
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              Adjust Prescription
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>

        </div>
      )}

    </div>
  );
}
// Stub component import mapping fallback inside workspace
function Edit3({ className }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" className={className}>
      <path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>
    </svg>
  );
}
