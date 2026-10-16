import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getFlowId, setState } from './laboratoryStorageUtils';
import { Home, Building2, ArrowRight, ArrowLeft, FlaskConical, ShieldCheck } from 'lucide-react';

export default function LaboratoryTests() {
  const navigate = useNavigate();

  // Initialize flow ID when component mounts
  useEffect(() => {
    getFlowId(); // This ensures we have a flow ID in sessionStorage
  }, []);

  const handleHomeVisit = () => {
    sessionStorage.setItem('laboratory_visit_type', 'home');
    setState({ visitType: 'home' });
    navigate('/patient/laboratory/home-visit');
  };

  const handleClinicVisit = () => {
    sessionStorage.setItem('laboratory_visit_type', 'clinic');
    setState({ visitType: 'clinic' });
    navigate('/patient/laboratory/clinic');
  };

  return (
    <div className="min-h-screen bg-[#F6F2EA] dark:bg-zinc-950 px-4 py-8 sm:py-12 text-[#1E2A2B] dark:text-zinc-100">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-10">
          <button
            type="button"
            onClick={() => navigate('/patient/dashboard')}
            className="inline-flex items-center gap-2 mb-6 px-3 py-2.5 -ml-3 rounded-xl text-sm font-bold text-[#60716E] dark:text-zinc-400 hover:text-[#1F4B45] dark:hover:text-[#5FC2B8] hover:bg-[#EEF5F1]/60 dark:hover:bg-zinc-800 transition-colors min-h-[44px]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1F4B45]/10 dark:bg-zinc-800 text-[#1F4B45] dark:text-[#5FC2B8] text-xs font-extrabold uppercase tracking-wide">
            <FlaskConical className="w-4 h-4" />
            Laboratory Care
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50 sm:text-4xl">
            Laboratory testing, made simple.
          </h1>
          <p className="mt-4 max-w-xl text-base text-[#60716E] dark:text-zinc-400">
            Book blood tests, panels and health checkups — at home or at the clinic.
          </p>
        </div>

        {/* Options */}
        <div className="grid gap-5 md:grid-cols-2">
          {/* Home Visit */}
          <button
            onClick={handleHomeVisit}
            className="group w-full flex flex-col items-start text-left rounded-3xl border-2 border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 sm:p-7 transition-all duration-200 hover:border-[#1F4B45]/40 hover:shadow-md"
          >
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800">
              <Home className="w-7 h-7 text-[#1F4B45] dark:text-[#5FC2B8]" />
            </div>
            <h2 className="mb-2 text-xl sm:text-2xl font-bold text-[#1E2A2B] dark:text-zinc-50">
              Home Visit
            </h2>
            <p className="mb-6 text-sm sm:text-base leading-relaxed text-[#60716E] dark:text-zinc-400">
              A qualified lab assistant can visit your home to collect samples for your selected laboratory tests.
            </p>
            <div className="mt-auto inline-flex items-center gap-2 text-sm font-bold text-[#1F4B45] dark:text-[#5FC2B8]">
              Continue
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </div>
          </button>

          {/* Clinic Visit */}
          <button
            onClick={handleClinicVisit}
            className="group w-full flex flex-col items-start text-left rounded-3xl border-2 border-[#E5E0D6] dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 sm:p-7 transition-all duration-200 hover:border-[#1F4B45]/40 hover:shadow-md"
          >
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#EEF5F1] dark:bg-zinc-800">
              <Building2 className="w-7 h-7 text-[#1F4B45] dark:text-[#5FC2B8]" />
            </div>
            <h2 className="mb-2 text-xl sm:text-2xl font-bold text-[#1E2A2B] dark:text-zinc-50">
              Clinic Visit
            </h2>
            <p className="mb-6 text-sm sm:text-base leading-relaxed text-[#60716E] dark:text-zinc-400">
              Visit the clinic and complete your selected laboratory tests at the available facility.
            </p>
            <div className="mt-auto inline-flex items-center gap-2 text-sm font-bold text-[#1F4B45] dark:text-[#5FC2B8]">
              Continue
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </div>
          </button>
        </div>

        {/* Trust note */}
        <div className="mt-8 flex items-start gap-3 rounded-2xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED]/60 dark:bg-zinc-900 p-4">
          <ShieldCheck className="w-5 h-5 text-[#1F4B45] dark:text-[#5FC2B8] shrink-0 mt-0.5" />
          <p className="text-xs sm:text-sm leading-relaxed text-[#60716E] dark:text-zinc-400">
            Samples are collected by certified phlebotomists and processed by our partner laboratories.
          </p>
        </div>
      </div>
    </div>
  );
}