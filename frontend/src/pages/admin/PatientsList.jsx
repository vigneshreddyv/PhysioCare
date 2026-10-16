import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { useAuth } from '../../context/useAuth';
import { format } from 'date-fns';
import {
  Search,
  Users,
  ShieldCheck,
  ClipboardList,
  Dumbbell,
  Edit2,
  History,
  Mail,
  Phone,
  Plus,
  Activity,
  ChevronRight,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react';

// Lightweight skeleton matching clinical registry layout
const PatientListSkeleton = () => (
  <div className="max-w-6xl mx-auto space-y-6 animate-pulse p-4 sm:p-6 lg:p-8">
    <div className="h-28 bg-zinc-200 dark:bg-zinc-800 rounded-3xl" />
    <div className="h-14 bg-zinc-200 dark:bg-zinc-800 rounded-2xl" />
    <div className="space-y-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-20 bg-zinc-200 dark:bg-zinc-800 rounded-2xl" />
      ))}
    </div>
  </div>
);

export default function PatientsList() {
  const { user } = useAuth();
  const role = user?.role || 'admin';
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  // 1. Fetch registered patients (backend enforces caseload for doctor vs all for admin)
  const {
    data: patients = [],
    isLoading: isPatientsLoading,
    error: patientsError,
    refetch: refetchPatients
  } = useQuery({
    queryKey: ['patients'],
    queryFn: async () => {
      const response = await api.get('/users/patients');
      return response.data;
    },
    retry: 1
  });

  // 2. For clinicians, fetch monitoring data to enrich with real adherence, activity date, and recovery status
  const {
    data: monitoringData = [],
    isLoading: isMonitoringLoading,
    error: monitoringError,
    refetch: refetchMonitoring
  } = useQuery({
    queryKey: ['clinicianPatientMonitoring'],
    queryFn: async () => {
      const response = await api.get('/users/patients/monitoring');
      return response.data;
    },
    enabled: role === 'doctor',
    retry: 1
  });

  const handleRefresh = async () => {
    await Promise.all([
      refetchPatients(),
      role === 'doctor' ? refetchMonitoring() : Promise.resolve()
    ]);
  };

  // Merge patients with monitoring metrics for doctors
  const enrichedPatients = useMemo(() => {
    if (role !== 'doctor' || !monitoringData || monitoringData.length === 0) {
      return patients.map(p => ({
        ...p,
        care_status: p.subscription_status === 'active' ? 'Active' : 'Inactive',
        adherence_percentage: undefined,
        last_activity: undefined,
        active_program: undefined,
      }));
    }

    const monitoringMap = new Map(monitoringData.map(m => [m.id, m]));
    return patients.map(p => {
      const m = monitoringMap.get(p.id);
      return {
        ...p,
        care_status: m?.status || (p.subscription_status === 'active' ? 'Active' : 'Inactive'),
        adherence_percentage: m?.adherence_percentage,
        last_activity: m?.last_activity,
        active_program: m?.active_program,
        current_stage: m?.current_stage,
      };
    });
  }, [patients, monitoringData, role]);

  const isLoading = isPatientsLoading || (role === 'doctor' && isMonitoringLoading);
  const isError = patientsError || (role === 'doctor' && monitoringError);

  // Client-side search logic
  const filteredPatients = useMemo(() => {
    return enrichedPatients.filter(p =>
      p.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.email?.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [enrichedPatients, searchQuery]);

  if (isLoading) {
    return <PatientListSkeleton />;
  }

  if (isError) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 px-4 space-y-6">
        <div className="w-16 h-16 bg-red-50 dark:bg-red-950/20 rounded-full flex items-center justify-center mx-auto border border-red-100 dark:border-red-900/30">
          <AlertTriangle className="w-8 h-8 text-red-600 dark:text-red-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-black text-[#183B4A] dark:text-zinc-100">
            Something went wrong loading your patients.
          </h2>
          <p className="text-sm text-[#60716E] dark:text-zinc-400 max-w-md mx-auto">
            We could not retrieve patient directory data at this time.
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs font-bold shadow-xs transition cursor-pointer min-h-[48px]"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Try Again</span>
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 sm:space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8 text-[#183B4A] dark:text-zinc-100">
      
      {/* 1. PAGE HEADER */}
      <section className="relative overflow-hidden rounded-3xl bg-[#EEF5F1] dark:bg-zinc-900 border border-[#0F6B63]/10 p-6 sm:p-8 lg:p-10 shadow-xs flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
        <div className="space-y-3.5 max-w-2xl">
          <span className="text-[11px] font-extrabold uppercase tracking-widest text-[#0F6B63] dark:text-[#EEF5F1] bg-[#0F6B63]/10 dark:bg-zinc-800 px-3 py-1 rounded-full border border-[#0F6B63]/10 inline-block">
            {role === 'doctor' ? 'Clinical Caseload' : 'Records Directory'}
          </span>
          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black tracking-tight text-[#183B4A] dark:text-zinc-50 leading-tight">
              {role === 'doctor' ? 'MY PATIENTS' : 'PATIENT MANAGEMENT'}
            </h1>
            <p className="text-xs sm:text-sm font-extrabold text-[#60716E] dark:text-zinc-400 uppercase tracking-wider">
              {role === 'doctor' ? 'Your Clinical Caseload' : 'Registered Patient Directory'}
            </p>
          </div>
          <p className="text-xs text-[#60716E] dark:text-zinc-400 font-medium max-w-lg">
            {role === 'doctor' 
              ? 'Patients currently assigned to your clinical caseload.' 
              : 'Manage registered patients, track subscription statuses, and launch clinical configurations.'}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 shrink-0">
          <div className="flex items-center gap-2 bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 px-3.5 py-2 rounded-xl text-xs font-semibold text-[#60716E] dark:text-zinc-300 shadow-2xs">
            <ShieldCheck className="w-4 h-4 text-[#0F6B63] shrink-0" />
            <span>{role === 'doctor' ? 'Caseload Verified' : 'Database Active'}</span>
          </div>

          <div className="bg-[#0F6B63] text-white text-xs font-bold px-4 py-2 rounded-xl shadow-xs shrink-0">
            {filteredPatients.length} {filteredPatients.length === 1 ? 'Patient' : 'Patients'}
          </div>
        </div>
      </section>

      {/* 2. SEARCH & CONTROLS */}
      <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-between items-center">
        <div className="relative w-full sm:max-w-md">
          <Search className="w-4 h-4 absolute left-4 top-1/2 -translate-y-1/2 text-[#60716E] dark:text-zinc-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-11 pr-4 py-3 bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-2xl text-xs sm:text-sm text-[#183B4A] dark:text-zinc-100 placeholder-[#60716E]/70 dark:placeholder-zinc-500 focus:ring-4 focus:ring-[#0F6B63]/10 focus:border-[#0F6B63] transition outline-none min-h-[48px] shadow-2xs"
            placeholder={role === 'doctor' ? 'Search your patients...' : 'Search patients by name or email...'}
          />
        </div>

        {role === 'admin' && (
          <button
            onClick={() => navigate('/admin/patients/create')}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 px-5 py-3 rounded-2xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs sm:text-sm font-bold shadow-xs transition cursor-pointer min-h-[48px]"
          >
            <Plus className="w-4 h-4" />
            <span>New Patient</span>
          </button>
        )}
      </div>

      {/* 3. PATIENT REGISTRY (DESKTOP & MOBILE VIEWS) */}
      {filteredPatients.length === 0 ? (
        <div className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-8 sm:p-12 text-center space-y-4 shadow-xs">
          <div className="w-14 h-14 bg-[#F7F4ED] dark:bg-zinc-800 rounded-full flex items-center justify-center mx-auto border border-[#E5E0D6] dark:border-zinc-700">
            <Users className="w-7 h-7 text-[#0F6B63]" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base sm:text-lg font-black text-[#183B4A] dark:text-zinc-100">
              {searchQuery ? 'No search matches' : (role === 'doctor' ? 'No patients assigned yet.' : 'No patients registered.')}
            </h2>
            <p className="text-xs sm:text-sm text-[#60716E] dark:text-zinc-400 max-w-sm mx-auto">
              {searchQuery 
                ? 'Try refining your search keyword or email.' 
                : (role === 'doctor' 
                    ? 'Patients assigned to your clinical caseload will appear here.' 
                    : 'Patient records will appear here once registered.')}
            </p>
          </div>
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="text-xs font-bold text-[#0F6B63] hover:underline cursor-pointer min-h-[36px]"
            >
              Clear Search Query
            </button>
          )}
        </div>
      ) : (
        <>
          {/* DESKTOP CLINICAL REGISTRY TABLE (hidden on mobile, visible on desktop/tablet) */}
          <div className="hidden md:block bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#F7F4ED]/50 dark:bg-zinc-850/50 border-b border-[#E5E0D6] dark:border-zinc-800 text-[#60716E] dark:text-zinc-400 text-[10px] font-extrabold uppercase tracking-wider">
                    <th className="py-4 px-5 pl-6">Patient</th>
                    <th className="py-4 px-4">Contact</th>
                    <th className="py-4 px-4">Care Status</th>
                    <th className="py-4 px-4 text-center">Adherence</th>
                    <th className="py-4 px-4">Last Activity</th>
                    <th className="py-4 px-5 text-right pr-6">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E5E0D6]/40 dark:divide-zinc-800 text-[#183B4A] dark:text-zinc-200">
                  {filteredPatients.map((patient) => {
                    const initials = patient.full_name
                      ?.split(' ')
                      ?.map(w => w[0])
                      ?.join('')
                      ?.slice(0, 2)
                      ?.toUpperCase() || 'PT';

                    const prefix = role === 'doctor' ? '/doctor' : '/admin';

                    const isCareActive = patient.care_status === 'Active';
                    const isAttention = patient.care_status === 'No recent activity' || patient.care_status === 'Low recent activity';

                    return (
                      <tr 
                        key={patient.id} 
                        className="hover:bg-[#F7F4ED]/20 dark:hover:bg-zinc-800/40 transition duration-150"
                      >
                        {/* PATIENT IDENTITY */}
                        <td className="py-4 px-5 pl-6">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-[#EEF5F1] dark:bg-zinc-800 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center font-black text-xs border border-[#0F6B63]/10 shrink-0">
                              {initials}
                            </div>
                            <div className="min-w-0">
                              <span className="font-extrabold text-sm text-[#183B4A] dark:text-zinc-100 block truncate">
                                {patient.full_name}
                              </span>
                              <span className="font-mono text-[10px] text-[#60716E] dark:text-zinc-400 uppercase block">
                                ID: {patient.id?.slice(-8) || patient.id}
                              </span>
                            </div>
                          </div>
                        </td>

                        {/* CONTACT */}
                        <td className="py-4 px-4 text-[#60716E] dark:text-zinc-400 font-medium">
                          <div className="space-y-0.5">
                            <span className="block truncate">{patient.email}</span>
                            {patient.phone && (
                              <span className="block text-[10px] text-[#60716E]/80 dark:text-zinc-500 font-mono">
                                {patient.phone}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* CARE STATUS */}
                        <td className="py-4 px-4">
                          <span className={`inline-flex px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider border shrink-0 ${
                            isCareActive
                              ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10 dark:bg-zinc-800 dark:text-[#EEF5F1]'
                              : isAttention
                              ? 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20 dark:bg-zinc-800'
                              : 'bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-800 dark:border-zinc-700'
                          }`}>
                            {patient.care_status}
                          </span>
                        </td>

                        {/* ADHERENCE */}
                        <td className="py-4 px-4 text-center">
                          {patient.adherence_percentage !== undefined ? (
                            <div className="inline-flex flex-col items-center space-y-1">
                              <span className="font-black text-xs text-[#183B4A] dark:text-zinc-100">
                                {patient.adherence_percentage}%
                              </span>
                              <div className="w-16 bg-[#E5E0D6]/50 dark:bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full ${
                                    patient.adherence_percentage < 50 ? 'bg-[#C9A86A]' : 'bg-[#0F6B63]'
                                  }`}
                                  style={{ width: `${patient.adherence_percentage}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-[11px] text-[#60716E] dark:text-zinc-400 font-medium">
                              {patient.subscription_status === 'active' ? 'Active Sub' : '—'}
                            </span>
                          )}
                        </td>

                        {/* LAST ACTIVITY */}
                        <td className="py-4 px-4 text-[#60716E] dark:text-zinc-400 font-medium">
                          {patient.last_activity ? (
                            <span className="text-[11px]">
                              {format(new Date(patient.last_activity), 'MMM d, yyyy')}
                            </span>
                          ) : (
                            <span className="italic text-[10px] text-[#60716E]/70 dark:text-zinc-500">
                              No activity logged
                            </span>
                          )}
                        </td>

                        {/* ACTIONS */}
                        <td className="py-4 px-5 text-right pr-6">
                          <div className="flex items-center justify-end gap-1.5">
                            {role === 'doctor' && (
                              <button
                                onClick={() => navigate(`/doctor/snapshot/${patient.id}`)}
                                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-[#0F6B63]/20 bg-[#EEF5F1] dark:bg-zinc-800 text-xs font-bold text-[#0F6B63] dark:text-[#EEF5F1] hover:bg-[#0F6B63] hover:text-white transition cursor-pointer min-h-[36px]"
                              >
                                <Activity className="w-3.5 h-3.5" />
                                <span>Snapshot</span>
                                <ChevronRight className="w-3 h-3" />
                              </button>
                            )}

                            <button
                              onClick={() => navigate(`${prefix}/care-plans/${patient.id}`)}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[11px] font-bold text-[#60716E] dark:text-zinc-300 hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 transition cursor-pointer min-h-[36px]"
                            >
                              <ClipboardList className="w-3.5 h-3.5 text-[#0F6B63]" />
                              <span>Plan</span>
                            </button>

                            <button
                              onClick={() => navigate(`${prefix}/exercises/${patient.id}`)}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[11px] font-bold text-[#60716E] dark:text-zinc-300 hover:text-[#0F6B63] hover:bg-[#EEF5F1]/30 transition cursor-pointer min-h-[36px]"
                            >
                              <Dumbbell className="w-3.5 h-3.5 text-[#0F6B63]" />
                              <span>Exercises</span>
                            </button>

                            {role === 'admin' && (
                              <>
                                <button
                                  onClick={() => navigate(`/admin/patients-edit/${patient.id}`)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[11px] font-bold text-[#60716E] hover:text-[#0F6B63] transition min-h-[36px]"
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                  <span>Edit</span>
                                </button>
                                <button
                                  onClick={() => navigate(`/admin/patients-history/${patient.id}`)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-white dark:bg-zinc-800 text-[11px] font-bold text-[#60716E] hover:text-[#0F6B63] transition min-h-[36px]"
                                >
                                  <History className="w-3.5 h-3.5" />
                                  <span>History</span>
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* MOBILE PATIENT CARDS (hidden on desktop, visible on mobile) */}
          <div className="md:hidden space-y-4">
            {filteredPatients.map((patient) => {
              const initials = patient.full_name
                ?.split(' ')
                ?.map(w => w[0])
                ?.join('')
                ?.slice(0, 2)
                ?.toUpperCase() || 'PT';

              const prefix = role === 'doctor' ? '/doctor' : '/admin';
              const isCareActive = patient.care_status === 'Active';
              const isAttention = patient.care_status === 'No recent activity' || patient.care_status === 'Low recent activity';

              return (
                <div 
                  key={patient.id} 
                  className="bg-white dark:bg-zinc-900 border border-[#E5E0D6] dark:border-zinc-800 rounded-3xl p-5 space-y-4 shadow-xs"
                >
                  {/* Identification & Care Status */}
                  <div className="flex items-start justify-between gap-3 pb-3 border-b border-[#E5E0D6]/60 dark:border-zinc-800">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] dark:bg-zinc-800 text-[#0F6B63] dark:text-[#EEF5F1] flex items-center justify-center font-black text-xs border border-[#0F6B63]/10 shrink-0">
                        {initials}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-extrabold text-sm text-[#183B4A] dark:text-zinc-100 truncate">
                          {patient.full_name}
                        </h3>
                        <p className="font-mono text-[10px] text-[#60716E] dark:text-zinc-400 uppercase mt-0.5">
                          ID: {patient.id?.slice(-8) || patient.id}
                        </p>
                      </div>
                    </div>

                    <span className={`inline-flex px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-wider border shrink-0 ${
                      isCareActive
                        ? 'bg-[#EEF5F1] text-[#0F6B63] border-[#0F6B63]/10 dark:bg-zinc-800 dark:text-[#EEF5F1]'
                        : isAttention
                        ? 'bg-[#F7F4ED] text-[#C9A86A] border-[#C9A86A]/20 dark:bg-zinc-800'
                        : 'bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-800 dark:border-zinc-700'
                    }`}>
                      {patient.care_status}
                    </span>
                  </div>

                  {/* Adherence & Last Activity */}
                  <div className="grid grid-cols-2 gap-3 p-3 bg-[#F7F4ED]/40 dark:bg-zinc-850/40 rounded-2xl border border-[#E5E0D6]/60 dark:border-zinc-800 text-xs">
                    <div className="space-y-0.5">
                      <span className="text-[9px] uppercase tracking-wider font-extrabold text-[#60716E] dark:text-zinc-400 block">
                        Adherence
                      </span>
                      <span className="font-black text-[#183B4A] dark:text-zinc-100 text-sm block">
                        {patient.adherence_percentage !== undefined ? `${patient.adherence_percentage}%` : '—'}
                      </span>
                    </div>

                    <div className="space-y-0.5">
                      <span className="text-[9px] uppercase tracking-wider font-extrabold text-[#60716E] dark:text-zinc-400 block">
                        Last Active
                      </span>
                      <span className="font-bold text-[#183B4A] dark:text-zinc-200 text-[11px] block">
                        {patient.last_activity ? format(new Date(patient.last_activity), 'MMM d, yyyy') : 'No logs'}
                      </span>
                    </div>
                  </div>

                  {/* Contact info */}
                  <div className="space-y-1.5 text-xs text-[#60716E] dark:text-zinc-400 px-1">
                    <div className="flex items-center gap-2">
                      <Mail className="w-3.5 h-3.5 text-[#0F6B63] shrink-0" />
                      <span className="truncate">{patient.email}</span>
                    </div>
                    {patient.phone && (
                      <div className="flex items-center gap-2">
                        <Phone className="w-3.5 h-3.5 text-[#0F6B63] shrink-0" />
                        <span>{patient.phone}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions Grid */}
                  <div className="space-y-2 pt-2 border-t border-[#E5E0D6]/60 dark:border-zinc-800">
                    {role === 'doctor' && (
                      <button
                        onClick={() => navigate(`/doctor/snapshot/${patient.id}`)}
                        className="w-full flex items-center justify-center gap-2 p-3 rounded-2xl bg-[#0F6B63] hover:bg-[#0C5851] text-white text-xs font-bold transition min-h-[48px] cursor-pointer shadow-xs"
                      >
                        <Activity className="w-4 h-4" />
                        <span>View Snapshot</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    )}

                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => navigate(`${prefix}/care-plans/${patient.id}`)}
                        className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-[#F7F4ED]/40 dark:bg-zinc-800 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] transition min-h-[48px] cursor-pointer"
                      >
                        <ClipboardList className="w-4 h-4 text-[#0F6B63]" />
                        <span>Care Plan</span>
                      </button>

                      <button
                        onClick={() => navigate(`${prefix}/exercises/${patient.id}`)}
                        className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl border border-[#E5E0D6] dark:border-zinc-700 bg-[#F7F4ED]/40 dark:bg-zinc-800 text-xs font-bold text-[#183B4A] dark:text-zinc-200 hover:text-[#0F6B63] transition min-h-[48px] cursor-pointer"
                      >
                        <Dumbbell className="w-4 h-4 text-[#0F6B63]" />
                        <span>Exercises</span>
                      </button>
                    </div>

                    {role === 'admin' && (
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => navigate(`/admin/patients-edit/${patient.id}`)}
                          className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl border border-[#E5E0D6] bg-white text-xs font-bold text-[#60716E] hover:text-[#0F6B63] transition min-h-[48px]"
                        >
                          <Edit2 className="w-4 h-4 text-[#0F6B63]" />
                          <span>Edit</span>
                        </button>
                        <button
                          onClick={() => navigate(`/admin/patients-history/${patient.id}`)}
                          className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl border border-[#E5E0D6] bg-white text-xs font-bold text-[#60716E] hover:text-[#0F6B63] transition min-h-[48px]"
                        >
                          <History className="w-4 h-4 text-[#0F6B63]" />
                          <span>History</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

    </div>
  );
}