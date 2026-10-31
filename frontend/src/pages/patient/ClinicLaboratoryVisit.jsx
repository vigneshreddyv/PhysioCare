import React from 'react';
import { useNavigate } from 'react-router-dom';
import { setState } from './laboratoryStorageUtils';
import { ArrowRight } from 'lucide-react';

export default function ClinicLaboratoryVisit() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-2 text-3xl font-bold tracking-tight text-[#183B4A] sm:text-4xl">
            Clinic Sample Collection
          </h1>

          <p className="mt-3 max-w-2xl text-base text-[#60716E]">
            Visit our clinic to complete your selected laboratory tests.
          </p>
        </div>

        {/* Main Card */}
        <div className="mt-6 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
          <div className="mt-4 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
            <h3 className="font-bold text-[#183B4A]">
              What happens next?
            </h3>

            <ul className="mt-3 space-y-2 text-sm text-[#60716E]">
              <li>✓ Select the laboratory tests you need</li>
              <li>✓ Choose your preferred date and time</li>
              <li>✓ Review your booking</li>
              <li>✓ Visit the clinic for sample collection</li>
            </ul>
          </div>

          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={() => {
                // Store visit type in our storage system
                setState({ visitType: 'clinic' });
                navigate('/patient/laboratory/tests');
              }}
              className="mt-6 w-full rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 text-sm font-semibold text-[#0F6B63] hover:bg-[#F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2"
            >
              Continue to Laboratory Tests →
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}