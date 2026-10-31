import React, { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import Button from '../../components/common/Button';
import ErrorState from '../../components/common/ErrorState';
import {
  ClipboardList,
  Trash2,
  Save,
  Plus,
  Play,
  CheckCircle2,
  Pause,
  AlertTriangle,
  ArrowLeft,
  XCircle,
} from '../../components/common/LucideCompat';

// Custom lightweight skeleton for loading states
const CarePlanListSkeleton = () => (
  <div className="space-y-4 animate-pulse">
    <div className="h-14 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-32 bg-gray-100 rounded-2xl border border-gray-200" />
    <div className="h-32 bg-gray-100 rounded-2xl border border-gray-200" />
  </div>
);

export default function CarePlanManagement() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const role = user?.role || 'admin';
  const prefix = role === 'doctor' ? '/doctor' : '/admin';

  // 1. Fetch patient profile to identify them in header
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

  // 2. Fetch care plans for this patient
  const {
    data: carePlans,
    isLoading: isPlansLoading,
    error: plansError,
    refetch: refetchPlans
  } = useQuery({
    queryKey: ['patientCarePlans', patientId],
    queryFn: async () => {
      const response = await api.get(`/care-plans/patient/${patientId}`);
      return response.data;
    }
  });

  // State for active selected plan to edit (null means "Create New Plan" mode)
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [isEditMode, setIsEditMode] = useState(false);

  // Form State
  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formStartDate, setFormStartDate] = useState('');
  const [formTargetDate, setFormTargetDate] = useState('');
  const [formStatus, setFormStatus] = useState('active');
  const [formCurrentStage, setFormCurrentStage] = useState(1);

  const [stages, setStages] = useState([]);
  const [goals, setGoals] = useState([]);
  const [recommendations, setRecommendations] = useState([]);

  // Local state for goals progress inputs
  const [goalsProgressInput, setGoalsProgressInput] = useState({});

  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Find currently selected care plan object from data list
  const selectedCarePlan = useMemo(() => {
    if (!carePlans || !selectedPlanId) return null;
    return carePlans.find(cp => cp.id === selectedPlanId);
  }, [carePlans, selectedPlanId]);

  // Mode Toggles
  const handleStartCreate = () => {
    setSelectedPlanId(null);
    setIsEditMode(true);
    setFormTitle('');
    setFormDescription('');
    setFormStartDate(new Date().toISOString().split('T')[0]);
    setFormTargetDate(new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]);
    setFormStatus('active');
    setFormCurrentStage(1);
    setStages([
      { stage_id: 'stage_1', title: 'Acute Pain Relief', description: 'Focus on reducing swelling and passive motion.', status: 'active', progress: 0, start_date: new Date().toISOString().split('T')[0], target_date: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], focus_areas: ['Mobility'] }
    ]);
    setGoals([
      { goal_id: 'goal_1', title: 'Reduce pain level', description: 'Pain scale target', target_value: 2.0, unit: '/ 10', status: 'active', progress_value: 0.0 }
    ]);
    setRecommendations([
      { recommendation_id: 'rec_1', title: 'Home Ice', description: 'Apply ice wrap for 15 minutes twice daily.', priority: 'medium' }
    ]);
    setGoalsProgressInput({ goal_1: 0 });
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleStartEdit = (plan) => {
    setSelectedPlanId(plan.id);
    setIsEditMode(true);
    setFormTitle(plan.title);
    setFormDescription(plan.description);
    setFormStartDate(plan.start_date ? plan.start_date.split('T')[0] : '');
    setFormTargetDate(plan.target_date ? plan.target_date.split('T')[0] : '');
    setFormStatus(plan.status || 'active');
    setFormCurrentStage(plan.current_stage || 1);

    // Map stages
    setStages(plan.stages.map(s => ({
      ...s,
      start_date: s.start_date ? s.start_date.split('T')[0] : '',
      target_date: s.target_date ? s.target_date.split('T')[0] : '',
      focus_areas: Array.isArray(s.focus_areas) ? s.focus_areas : [s.focus_areas]
    })));

    setGoals(plan.goals || []);
    setRecommendations(plan.recommendations || []);

    // Set initial values for goals progress input fields
    const progressMap = {};
    if (plan.goals) {
      plan.goals.forEach(g => {
        progressMap[g.goal_id] = g.progress_value || 0;
      });
    }
    setGoalsProgressInput(progressMap);

    setErrorMessage('');
    setSuccessMessage('');
  };

  // Add/Remove Nested items helpers
  const handleAddStage = () => {
    setStages(prev => [
      ...prev,
      {
        stage_id: 'stage_' + Date.now(),
        title: '',
        description: '',
        status: 'upcoming',
        progress: 0,
        start_date: '',
        target_date: '',
        focus_areas: []
      }
    ]);
  };

  const handleRemoveStage = (index) => {
    setStages(prev => prev.filter((_, i) => i !== index));
  };

  const handleStageChange = (index, field, value) => {
    setStages(prev => prev.map((s, i) => {
      if (i !== index) return s;
      if (field === 'focus_areas') {
        const val = value.split(',').map(item => item.trim()).filter(Boolean);
        return { ...s, [field]: val };
      }
      return { ...s, [field]: value };
    }));
  };

  const handleAddGoal = () => {
    const goalId = 'goal_' + Date.now();
    setGoals(prev => [
      ...prev,
      {
        goal_id: goalId,
        title: '',
        description: '',
        target_value: 0,
        unit: '',
        status: 'active',
        progress_value: 0.0
      }
    ]);
    setGoalsProgressInput(prev => ({ ...prev, [goalId]: 0 }));
  };

  const handleRemoveGoal = (index) => {
    setGoals(prev => prev.filter((_, i) => i !== index));
  };

  const handleGoalChange = (index, field, value) => {
    setGoals(prev => prev.map((g, i) => {
      if (i !== index) return g;
      return { ...g, [field]: field === 'target_value' ? parseFloat(value) || 0 : value };
    }));
  };

  const handleAddRec = () => {
    setRecommendations(prev => [
      ...prev,
      {
        recommendation_id: 'rec_' + Date.now(),
        title: '',
        description: '',
        priority: 'medium'
      }
    ]);
  };

  const handleRemoveRec = (index) => {
    setRecommendations(prev => prev.filter((_, i) => i !== index));
  };

  const handleRecChange = (index, field, value) => {
    setRecommendations(prev => prev.map((r, i) => {
      if (i !== index) return r;
      return { ...r, [field]: value };
    }));
  };

  // React Query Mutations for Clinical Workflow
  const mutateStageStatus = useMutation({
    mutationFn: async ({ stageId, status }) => {
      const response = await api.patch(`/care-plans/${selectedPlanId}/stages/${stageId}`, { status });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['patientCarePlans', patientId] });
      setSuccessMessage('Stage status updated successfully.');
      handleStartEdit(data);
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to update stage status.');
    }
  });

  const mutateGoalProgress = useMutation({
    mutationFn: async ({ goalId, progressValue, status }) => {
      const response = await api.patch(`/care-plans/${selectedPlanId}/goals/${goalId}`, {
        progress_value: parseFloat(progressValue) || 0,
        status
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['patientCarePlans', patientId] });
      setSuccessMessage('Goal progress updated successfully.');
      handleStartEdit(data);
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to update goal progress.');
    }
  });

  const mutatePlanStatus = useMutation({
    mutationFn: async (newStatus) => {
      const response = await api.patch(`/care-plans/${selectedPlanId}`, { status: newStatus });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['patientCarePlans', patientId] });
      setSuccessMessage(`Care Plan status changed to ${newStatus}.`);
      handleStartEdit(data);
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to change Care Plan status.');
    }
  });

  const createPlanMutation = useMutation({
    mutationFn: async (planData) => {
      const response = await api.post('/care-plans', planData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patientCarePlans', patientId] });
      setSuccessMessage('Care Plan created successfully.');
      setIsEditMode(false);
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to create Care Plan.');
    }
  });

  const updatePlanMutation = useMutation({
    mutationFn: async ({ id, planData }) => {
      const response = await api.patch(`/care-plans/${id}`, planData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patientCarePlans', patientId] });
      setSuccessMessage('Care Plan updated successfully.');
      setIsEditMode(false);
    },
    onError: (err) => {
      setErrorMessage(err.response?.data?.detail || 'Failed to update Care Plan.');
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    setErrorMessage('');
    setSuccessMessage('');

    // Prepare JSON payload
    const payload = {
      patient_id: patientId,
      title: formTitle,
      description: formDescription,
      start_date: formStartDate ? new Date(formStartDate).toISOString() : new Date().toISOString(),
      target_date: formTargetDate ? new Date(formTargetDate).toISOString() : new Date().toISOString(),
      status: formStatus,
      current_stage: parseInt(formCurrentStage) || 1,
      stages: stages.map(s => ({
        ...s,
        progress: parseFloat(s.progress) || 0,
        start_date: s.start_date ? new Date(s.start_date).toISOString() : null,
        target_date: s.target_date ? new Date(s.target_date).toISOString() : null
      })),
      goals: goals.map(g => ({
        ...g,
        target_value: parseFloat(g.target_value) || 0,
        progress_value: parseFloat(goalsProgressInput[g.goal_id]) || 0
      })),
      recommendations: recommendations
    };

    if (selectedPlanId) {
      updatePlanMutation.mutate({ id: selectedPlanId, planData: payload });
    } else {
      createPlanMutation.mutate(payload);
    }
  };

  const handleCancelForm = () => {
    setIsEditMode(false);
    setErrorMessage('');
  };

  if (plansError) {
    return <ErrorState message="Could not load Care Plans." onRetry={() => refetchPlans()} />;
  }

  // Check if current plan status allows modifications
  const isPlanImmutable = selectedCarePlan?.status === 'completed' || selectedCarePlan?.status === 'cancelled';

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. CLINICIAN DESK HEADER */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 border-b border-[#E5E0D6]/65 pb-6">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Clinician Desk</span>
          <h1 className="text-3xl font-extrabold text-[#183B4A] mt-1">
            Care Plan: {selectedPatient?.full_name || 'Patient Records'}
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

      {/* 2. MODE ROUTER CONTAINER */}
      {!isEditMode ? (
        <div className="space-y-6">
          
          {/* Create Plan Toggle Bar */}
          <div className="flex justify-between items-center bg-white border border-[#E5E0D6] p-4 rounded-2xl shadow-xs">
            <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider pl-2">Rehabilitation Pathways</span>
            <Button 
              variant="primary" 
              onClick={handleStartCreate}
              className="text-xs font-bold py-2 px-4 rounded-xl flex items-center gap-1 cursor-pointer border border-transparent"
            >
              <Plus className="w-4 h-4" />
              Create New Care Plan
            </Button>
          </div>

          {isPlansLoading ? (
            <CarePlanListSkeleton />
          ) : !carePlans || carePlans.length === 0 ? (
            <div className="text-center py-16 bg-white border border-[#E5E0D6] rounded-3xl max-w-md mx-auto space-y-4">
              <ClipboardList className="w-8 h-8 text-[#60716E]/40 mx-auto" />
              <div className="space-y-1">
                <h4 className="text-base font-extrabold text-[#183B4A]">No care plans configured</h4>
                <p className="text-xs text-[#60716E] leading-relaxed px-4">
                  No active or historical care plans found for this patient. Start by creating a rehabilitation pathway.
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {carePlans.map((plan) => (
                <div key={plan.id} className="bg-white border border-[#E5E0D6] rounded-3xl p-6 space-y-4 hover:shadow-md transition duration-150 flex flex-col justify-between shadow-sm">
                  <div className="space-y-3">
                    <div className="flex justify-between items-start gap-3 pb-3 border-b border-[#E5E0D6]/40">
                      <div>
                        <h4 className="font-extrabold text-[#183B4A] text-base leading-snug">{plan.title}</h4>
                        <span className="font-mono text-[9px] text-[#60716E] block mt-1 uppercase">Ref: {plan.id?.slice(-8) || plan.id}</span>
                      </div>
                      <span className={`px-2.5 py-0.5 rounded text-[8px] font-bold uppercase border shrink-0 ${
                        plan.status === 'active' 
                          ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                          : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20'
                      }`}>
                        {plan.status}
                      </span>
                    </div>

                    <p className="text-xs text-[#60716E] leading-relaxed line-clamp-2">{plan.description}</p>

                    <div className="grid grid-cols-2 gap-4 text-xs pt-2">
                      <div>
                        <span className="font-bold text-[#60716E] uppercase text-[9px]">Timeline Range</span>
                        <p className="text-[#183B4A] mt-0.5 font-semibold">
                          {new Date(plan.start_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })} - {new Date(plan.target_date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                        </p>
                      </div>
                      <div>
                        <span className="font-bold text-[#60716E] uppercase text-[9px]">Pathway Stages</span>
                        <p className="text-[#183B4A] mt-0.5 font-semibold">{plan.stages?.length || 0} stages defined</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end pt-4 border-t border-[#E5E0D6]/40 mt-4">
                    <Button 
                      variant="outline" 
                      className="text-xs font-bold py-1.5 px-3.5 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl" 
                      onClick={() => handleStartEdit(plan)}
                    >
                      Configure & Progress Plan
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-8">
          
          {/* CLINICAL DECISION ACTION PANEL */}
          {selectedPlanId && (
            <div className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
              <div className="pb-3 border-b border-[#E5E0D6]/40">
                <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">Clinical Progression</span>
                <h4 className="text-base font-extrabold text-[#183B4A] mt-0.5">Timeline Status Controller</h4>
                <p className="text-xs text-[#60716E] mt-1 leading-relaxed">
                  Directly transition recovery targets and milestone stages without rebuilding the care document.
                </p>
              </div>

              {isPlanImmutable && (
                <div className="p-4 bg-red-50 border border-red-200/50 rounded-2xl text-red-700 font-bold text-xs flex items-center gap-2">
                  <XCircle className="w-4 h-4 shrink-0" />
                  This rehabilitation plan is {selectedCarePlan?.status.toUpperCase()} and cannot be clinically modified.
                </div>
              )}

              {/* 1. GENERAL PLAN STATUS STATE MACHINE ACTIONS */}
              <div className="flex flex-wrap gap-2.5 pb-4">
                {selectedCarePlan?.status === 'active' && (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs font-bold py-2 px-4 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl flex items-center gap-1"
                      onClick={() => mutatePlanStatus.mutate('paused')}
                      disabled={mutatePlanStatus.isPending}
                    >
                      <Pause className="w-4 h-4 text-[#C9A86A]" />
                      Pause Plan
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs font-bold py-2 px-4 border-green-200 text-green-700 bg-green-50 hover:bg-green-100/50 rounded-xl flex items-center gap-1"
                      onClick={() => mutatePlanStatus.mutate('completed')}
                      disabled={mutatePlanStatus.isPending}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Complete Plan
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs font-bold py-2 px-4 border-red-200 text-red-700 bg-red-50 hover:bg-red-100/50 rounded-xl flex items-center gap-1"
                      onClick={() => mutatePlanStatus.mutate('cancelled')}
                      disabled={mutatePlanStatus.isPending}
                    >
                      <XCircle className="w-4 h-4" />
                      Cancel Plan
                    </Button>
                  </>
                )}

                {selectedCarePlan?.status === 'paused' && (
                  <>
                    <Button
                      type="button"
                      variant="primary"
                      className="text-xs font-bold py-2 px-4 rounded-xl flex items-center gap-1"
                      onClick={() => mutatePlanStatus.mutate('active')}
                      disabled={mutatePlanStatus.isPending}
                    >
                      <Play className="w-4 h-4" />
                      Resume Plan
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="text-xs font-bold py-2 px-4 border-red-200 text-red-700 bg-red-50 hover:bg-red-100/50 rounded-xl flex items-center gap-1"
                      onClick={() => mutatePlanStatus.mutate('cancelled')}
                      disabled={mutatePlanStatus.isPending}
                    >
                      <XCircle className="w-4 h-4" />
                      Cancel Plan
                    </Button>
                  </>
                )}
              </div>

              {/* 2. CLINICAL STAGE STATUS ACTIONS */}
              {!isPlanImmutable && selectedCarePlan?.stages && (
                <div className="space-y-4 border-t border-[#E5E0D6]/40 pt-4">
                  <h5 className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Milestone Stage Timelines</h5>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {selectedCarePlan.stages.map((stage) => (
                      <div key={stage.stage_id} className="p-4 bg-[#F7F4ED]/20 border border-[#E5E0D6] rounded-2xl flex justify-between items-center gap-4">
                        <div>
                          <p className="text-xs font-bold text-[#183B4A]">{stage.title}</p>
                          <span className={`inline-block px-2 py-0.5 mt-1.5 rounded text-[8px] font-bold uppercase border ${
                            stage.status === 'active' 
                              ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                              : 'bg-white text-[#60716E] border-[#E5E0D6]'
                          }`}>
                            {stage.status}
                          </span>
                        </div>
                        <div className="flex gap-1.5 shrink-0">
                          {stage.status === 'upcoming' && (
                            <Button
                              type="button"
                              variant="primary"
                              className="text-[10px] py-1.5 px-3 rounded-lg flex items-center gap-1 border border-transparent font-bold cursor-pointer"
                              onClick={() => mutateStageStatus.mutate({ stageId: stage.stage_id, status: 'active' })}
                              disabled={mutateStageStatus.isPending}
                            >
                              <Play className="w-3 h-3" />
                              Activate
                            </Button>
                          )}
                          {stage.status === 'active' && (
                            <Button
                              type="button"
                              variant="outline"
                              className="text-[10px] py-1.5 px-3 rounded-lg border-green-200 text-green-700 bg-green-50 hover:bg-green-100/50 font-bold"
                              onClick={() => mutateStageStatus.mutate({ stageId: stage.stage_id, status: 'completed' })}
                              disabled={mutateStageStatus.isPending}
                            >
                              <CheckCircle2 className="w-3 h-3" />
                              Complete
                            </Button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 3. GOAL PROGRESS PROGRESSION ACTIONS */}
              {!isPlanImmutable && selectedCarePlan?.goals && (
                <div className="space-y-4 border-t border-[#E5E0D6]/40 pt-4">
                  <h5 className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Goal Target Metric Progress Logs</h5>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {selectedCarePlan.goals.map((goal) => {
                      const currentProgressInput = goalsProgressInput[goal.goal_id] || 0;
                      return (
                        <div key={goal.goal_id} className="p-4 bg-[#F7F4ED]/20 border border-[#E5E0D6] rounded-2xl space-y-4">
                          <div className="flex justify-between items-start gap-3">
                            <div>
                              <p className="text-xs font-bold text-[#183B4A]">{goal.title}</p>
                              <p className="text-[10px] text-[#60716E] mt-1">
                                Target: <span className="font-extrabold text-[#183B4A]">{goal.target_value} {goal.unit}</span> | Logged: <span className="font-extrabold text-[#0F6B63]">{goal.progress_value || 0} {goal.unit}</span>
                              </p>
                            </div>
                            <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase border shrink-0 ${
                              goal.status === 'achieved' 
                                ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10' 
                                : 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20'
                            }`}>
                              {goal.status}
                            </span>
                          </div>

                          {goal.status !== 'achieved' && (
                            <div className="flex items-center gap-2 pt-2 border-t border-[#E5E0D6]/35">
                              <input
                                type="number"
                                step="any"
                                className="w-16 bg-white border border-[#E5E0D6] rounded-lg p-1.5 text-xs text-center focus:ring-2 focus:ring-[#0F6B63]/10 outline-none"
                                value={currentProgressInput}
                                onChange={(e) => setGoalsProgressInput(prev => ({
                                  ...prev,
                                  [goal.goal_id]: parseFloat(e.target.value) || 0
                                }))}
                              />
                              <Button
                                type="button"
                                variant="outline"
                                className="text-[10px] py-1.5 px-3 rounded-lg border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex-1 font-bold"
                                onClick={() => mutateGoalProgress.mutate({
                                  goalId: goal.goal_id,
                                  progressValue: currentProgressInput,
                                  status: 'active'
                                })}
                                disabled={mutateGoalProgress.isPending}
                              >
                                Log progress
                              </Button>
                              <Button
                                type="button"
                                variant="primary"
                                className="text-[10px] py-1.5 px-3 rounded-lg flex items-center gap-1 font-bold cursor-pointer border border-transparent"
                                onClick={() => mutateGoalProgress.mutate({
                                  goalId: goal.goal_id,
                                  progressValue: goal.target_value,
                                  status: 'achieved'
                                })}
                                disabled={mutateGoalProgress.isPending}
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Achieve
                              </Button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* MAIN CARE PLAN CONFIGURATION FORM */}
          <form onSubmit={handleSubmit} className="space-y-8 bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 shadow-sm">
            <div className="pb-3 border-b border-[#E5E0D6]/40">
              <span className="text-[10px] font-bold text-[#60716E] uppercase tracking-wider">Plan Details</span>
              <h3 className="text-lg font-extrabold text-[#183B4A] mt-0.5">
                {selectedPlanId ? 'Rehabilitation Plan Configuration' : 'Create Rehabilitation Pathway'}
              </h3>
            </div>

            {/* BASIC METADATA */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold text-[#183B4A]">Care Plan Title</label>
                <input
                  type="text"
                  required
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                  placeholder="e.g. Rotator Cuff Post-Op Recovery"
                  value={formTitle}
                  onChange={e => setFormTitle(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-[#183B4A]">Plan Status</label>
                <select
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                  value={formStatus}
                  onChange={e => setFormStatus(e.target.value)}
                >
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                  <option value="paused">Paused</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <label className="text-xs font-bold text-[#183B4A]">Clinical Overview Description</label>
                <textarea
                  required
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none min-h-[90px] disabled:opacity-50 leading-relaxed"
                  placeholder="Provide deep clinical pathway goals and recovery guidelines."
                  value={formDescription}
                  onChange={e => setFormDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-[#183B4A]">Start Date</label>
                <input
                  type="date"
                  required
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                  value={formStartDate}
                  onChange={e => setFormStartDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-[#183B4A]">Target Date</label>
                <input
                  type="date"
                  required
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                  value={formTargetDate}
                  onChange={e => setFormTargetDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-bold text-[#183B4A]">Current Stage Index</label>
                <input
                  type="number"
                  min="1"
                  required
                  disabled={isPlanImmutable}
                  className="w-full bg-white border border-[#E5E0D6] rounded-xl p-3 text-xs text-[#183B4A] focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] outline-none disabled:opacity-50"
                  value={formCurrentStage}
                  onChange={e => setFormCurrentStage(parseInt(e.target.value) || 1)}
                />
              </div>
            </div>

            {/* STAGES SETTINGS */}
            <div className="space-y-4 border-t border-[#E5E0D6]/40 pt-6">
              <div className="flex justify-between items-center">
                <h4 className="font-extrabold text-[#183B4A] text-base">Timeline Treatment Stages</h4>
                {!isPlanImmutable && (
                  <Button 
                    type="button" 
                    variant="outline" 
                    className="text-xs font-bold py-1.5 px-3 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl flex items-center gap-1" 
                    onClick={handleAddStage}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Stage
                  </Button>
                )}
              </div>

              {stages.map((stage, idx) => (
                <div key={idx} className="bg-[#F7F4ED]/20 p-5 border border-[#E5E0D6] rounded-2xl space-y-4">
                  <div className="flex justify-between items-center border-b border-[#E5E0D6]/35 pb-2.5">
                    <span className="text-[10px] font-bold text-[#0F6B63] uppercase tracking-wider">Stage Details #{idx + 1}</span>
                    {!isPlanImmutable && (
                      <button 
                        type="button" 
                        className="text-red-700 hover:text-red-900 text-xs font-bold flex items-center gap-1 cursor-pointer" 
                        onClick={() => handleRemoveStage(idx)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Remove Stage
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Stage ID / Slug</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. stage_1"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.stage_id}
                        onChange={e => handleStageChange(idx, 'stage_id', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Stage Title</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. Passive Joint Activation"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.title}
                        onChange={e => handleStageChange(idx, 'title', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Stage Status</label>
                      <select
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.status}
                        onChange={e => handleStageChange(idx, 'status', e.target.value)}
                      >
                        <option value="upcoming">Upcoming</option>
                        <option value="active">Active</option>
                        <option value="completed">Completed</option>
                      </select>
                    </div>
                    <div className="space-y-1 md:col-span-3">
                      <label className="text-xs text-[#60716E] font-bold">Stage Description</label>
                      <textarea
                        required
                        disabled={isPlanImmutable}
                        placeholder="Clinical outline of movements and guidelines allowed during this rehab timeline phase."
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none min-h-[60px] disabled:opacity-50 leading-relaxed"
                        value={stage.description}
                        onChange={e => handleStageChange(idx, 'description', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Start Date</label>
                      <input
                        type="date"
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.start_date}
                        onChange={e => handleStageChange(idx, 'start_date', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Target Date</label>
                      <input
                        type="date"
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.target_date}
                        onChange={e => handleStageChange(idx, 'target_date', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Progress Percentage (0-100)</label>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.progress}
                        onChange={e => handleStageChange(idx, 'progress', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1 md:col-span-3">
                      <label className="text-xs text-[#60716E] font-bold">Focus Areas (Comma-separated)</label>
                      <input
                        type="text"
                        disabled={isPlanImmutable}
                        placeholder="e.g. Joint mobility, pain relief"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={stage.focus_areas ? stage.focus_areas.join(', ') : ''}
                        onChange={e => handleStageChange(idx, 'focus_areas', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* GOALS */}
            <div className="space-y-4 border-t border-[#E5E0D6]/40 pt-6">
              <div className="flex justify-between items-center">
                <h4 className="font-extrabold text-[#183B4A] text-base">Key Focus Area Targets</h4>
                {!isPlanImmutable && (
                  <Button 
                    type="button" 
                    variant="outline" 
                    className="text-xs font-bold py-1.5 px-3 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl flex items-center gap-1" 
                    onClick={handleAddGoal}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Goal
                  </Button>
                )}
              </div>

              {goals.map((goal, idx) => (
                <div key={idx} className="bg-[#F7F4ED]/20 p-5 border border-[#E5E0D6] rounded-2xl space-y-4">
                  <div className="flex justify-between items-center border-b border-[#E5E0D6]/35 pb-2.5">
                    <span className="text-[10px] font-bold text-[#0F6B63] uppercase tracking-wider">Goal Target #{idx + 1}</span>
                    {!isPlanImmutable && (
                      <button 
                        type="button" 
                        className="text-red-700 hover:text-red-900 text-xs font-bold flex items-center gap-1 cursor-pointer" 
                        onClick={() => handleRemoveGoal(idx)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Remove Goal
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Goal ID</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. goal_1"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.goal_id}
                        onChange={e => handleGoalChange(idx, 'goal_id', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Goal Title</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. Flexion angle"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.title}
                        onChange={e => handleGoalChange(idx, 'title', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Unit Metric</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. degrees, reps"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.unit}
                        onChange={e => handleGoalChange(idx, 'unit', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Target Value</label>
                      <input
                        type="number"
                        required
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.target_value}
                        onChange={e => handleGoalChange(idx, 'target_value', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Status</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.status}
                        onChange={e => handleGoalChange(idx, 'status', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1 md:col-span-3">
                      <label className="text-xs text-[#60716E] font-bold">Goal Description</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="Details on what to evaluate."
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={goal.description}
                        onChange={e => handleGoalChange(idx, 'description', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* THERAPIST RECOMMENDATIONS */}
            <div className="space-y-4 border-t border-[#E5E0D6]/40 pt-6">
              <div className="flex justify-between items-center">
                <h4 className="font-extrabold text-[#183B4A] text-base">Clinician Recommendations</h4>
                {!isPlanImmutable && (
                  <Button 
                    type="button" 
                    variant="outline" 
                    className="text-xs font-bold py-1.5 px-3 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl flex items-center gap-1" 
                    onClick={handleAddRec}
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Recommendation
                  </Button>
                )}
              </div>

              {recommendations.map((rec, idx) => (
                <div key={idx} className="bg-[#F7F4ED]/20 p-5 border border-[#E5E0D6] rounded-2xl space-y-4">
                  <div className="flex justify-between items-center border-b border-[#E5E0D6]/35 pb-2.5">
                    <span className="text-[10px] font-bold text-[#0F6B63] uppercase tracking-wider">Recommendation #{idx + 1}</span>
                    {!isPlanImmutable && (
                      <button 
                        type="button" 
                        className="text-red-700 hover:text-red-900 text-xs font-bold flex items-center gap-1 cursor-pointer" 
                        onClick={() => handleRemoveRec(idx)}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        Remove Recommendation
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Recommendation ID</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. rec_1"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={rec.recommendation_id}
                        onChange={e => handleRecChange(idx, 'recommendation_id', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Instruction Title</label>
                      <input
                        type="text"
                        required
                        disabled={isPlanImmutable}
                        placeholder="e.g. Apply Ice Pack"
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={rec.title}
                        onChange={e => handleRecChange(idx, 'title', e.target.value)}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs text-[#60716E] font-bold">Priority Level</label>
                      <select
                        disabled={isPlanImmutable}
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none disabled:opacity-50"
                        value={rec.priority}
                        onChange={e => handleRecChange(idx, 'priority', e.target.value)}
                      >
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                      </select>
                    </div>
                    <div className="space-y-1 md:col-span-3">
                      <label className="text-xs text-[#60716E] font-bold">Instruction Details</label>
                      <textarea
                        required
                        disabled={isPlanImmutable}
                        placeholder="Provide details on ice wraps, stretching, frequencies..."
                        className="w-full bg-white border border-[#E5E0D6] rounded-xl p-2.5 text-xs text-[#183B4A] outline-none min-h-[60px] disabled:opacity-50 leading-relaxed"
                        value={rec.description}
                        onChange={e => handleRecChange(idx, 'description', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* SUBMIT ACTIONS */}
            <div className="flex gap-3 pt-6 border-t border-[#E5E0D6]/40 justify-end">
              <Button 
                type="button" 
                variant="outline" 
                onClick={handleCancelForm}
                className="text-xs font-bold py-2.5 px-4.5 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 rounded-xl"
              >
                Cancel
              </Button>
              {!isPlanImmutable && (
                <Button
                  type="submit"
                  variant="primary"
                  className="text-xs font-bold py-2.5 px-4.5 rounded-xl flex items-center gap-1.5 cursor-pointer border border-transparent"
                  disabled={createPlanMutation.isPending || updatePlanMutation.isPending}
                >
                  <Save className="w-4 h-4" />
                  {selectedPlanId ? 'Save Changes' : 'Create Care Plan'}
                </Button>
              )}
            </div>
          </form>
        </div>
      )}

    </div>
  );
}
