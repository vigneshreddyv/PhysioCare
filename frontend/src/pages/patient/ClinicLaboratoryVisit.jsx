import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function ClinicLaboratoryVisit() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-6xl">

        <p className="text-sm font-semibold text-cyan-700">
          CLINIC VISIT LAB TEST
        </p>

        <h1 className="mt-2 text-4xl font-bold text-slate-900">
          Clinic Sample Collection
        </h1>

        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
          Visit our clinic to complete your selected laboratory tests.
        </p>

        <div className="mt-10 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">

          <h2 className="text-2xl font-bold text-slate-900">
            Clinic Visit
          </h2>

          <p className="mt-3 max-w-2xl text-slate-600">
            Choose this option if you prefer to visit the clinic and provide
            your samples at the available laboratory facility.
          </p>

          <div className="mt-8 rounded-2xl border border-cyan-100 bg-cyan-50 p-6">
            <h3 className="font-bold text-slate-900">
              What happens next?
            </h3>

            <ul className="mt-3 space-y-2 text-sm text-slate-600">
              <li>✓ Select the laboratory tests you need</li>
              <li>✓ Choose your preferred date and time</li>
              <li>✓ Review your booking</li>
              <li>✓ Visit the clinic for sample collection</li>
            </ul>
          </div>

          <div className="mt-8 flex justify-end">
            <button
              type="button"
              onClick={() => navigate('/patient/laboratory/tests')}
              className="rounded-xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-700"
            >
              Continue to Laboratory Tests →
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}