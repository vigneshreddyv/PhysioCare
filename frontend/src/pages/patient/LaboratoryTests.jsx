import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getFlowId, setState } from './laboratoryStorageUtils';
import { Home, Building2, ArrowRight } from 'lucide-react';

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
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-12 text-center">
          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#183B4A] sm:text-4xl">
            Laboratory testing, made simple.
          </h1>
          <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
            Choose how you would like to complete your laboratory tests.
          </p>
        </div>

        {/* Options */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Home Visit */}
          <div className="flex flex-col items-start">
            <button
              onClick={handleHomeVisit}
              className="w-full group flex flex-col items-start rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 hover:bg-[#F7F4ED]/70 transition-colors duration-200"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <Home className="w-6 h-6 text-[#0F6B63]" />
              </div>
              <h2 className="mb-2 text-2xl font-bold text-[#183B4A]">
                Home Visit
              </h2>
              <p className="mb-4 text-base text-[#60716E]">
                A qualified lab assistant can visit your home to collect samples for your selected laboratory tests.
              </p>
              <div className="mt-auto w-fit items-center gap-2 text-sm font-semibold text-[#0F6B63] hover:text-[#0F6B63]/80 transition-colors">
                Continue
                <ArrowRight className="w-4 h-4" />
              </div>
            </button>
          </div>

          {/* Clinic Visit */}
          <div className="flex flex-col items-start">
            <button
              onClick={handleClinicVisit}
              className="w-full group flex flex-col items-start rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 hover:bg-[#F7F4ED]/70 transition-colors duration-200"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <Building2 className="w-6 h-6 text-[#0F6B63]" />
              </div>
              <h2 className="mb-2 text-2xl font-bold text-[#183B4A]">
                Clinic Visit
              </h2>
              <p className="mb-4 text-base text-[#60716E]">
                Visit the clinic and complete your selected laboratory tests at the available facility.
              </p>
              <div className="mt-auto w-fit items-center gap-2 text-sm font-semibold text-[#0F6B63] hover:text-[#0F6B63]/80 transition-colors">
                Continue
                <ArrowRight className="w-4 h-4" />
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}