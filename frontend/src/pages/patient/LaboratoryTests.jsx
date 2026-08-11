import React from 'react';
import { useNavigate } from 'react-router-dom';

export default function LaboratoryTests() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-5xl">

        <div className="mb-10">
          <p className="text-sm font-semibold text-cyan-700">
            LABORATORY SERVICES
          </p>

          <h1 className="mt-2 text-3xl font-bold text-slate-900 sm:text-4xl">
            Laboratory Tests 🧪
          </h1>

          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Choose how you would like to complete your laboratory tests.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">

          {/* Home Visit */}
          <button
            type="button"
            onClick={() => {
                sessionStorage.setItem('laboratory_visit_type', 'home');
                navigate('/patient/laboratory/home-visit');
            }}
            className="group rounded-3xl border border-slate-200 bg-gradient-to-br from-emerald-50 to-teal-50 p-7 text-left shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-emerald-300 hover:shadow-lg"
          >
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-3xl shadow-sm">
              🏠
            </div>

            <h2 className="text-2xl font-bold text-slate-900">
              Home Visit Lab Test
            </h2>

            <p className="mt-3 text-sm leading-6 text-slate-600">
              A qualified lab assistant can visit your home to collect
              samples for your selected laboratory tests.
            </p>

            <div className="mt-6 flex items-center text-sm font-bold text-emerald-700">
              Continue
              <span className="ml-2 transition-transform group-hover:translate-x-1">
                →
              </span>
            </div>
          </button>

          {/* Clinic Visit */}
          <button
            type="button"
            onClick={() => {
                sessionStorage.setItem('laboratory_visit_type', 'clinic');
                navigate('/patient/laboratory/clinic');
            }}
            className="group rounded-3xl border border-slate-200 bg-gradient-to-br from-cyan-50 to-blue-50 p-7 text-left shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-cyan-300 hover:shadow-lg"
          >
            <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-3xl shadow-sm">
              🏥
            </div>

            <h2 className="text-2xl font-bold text-slate-900">
              Clinic Visit Lab Test
            </h2>

            <p className="mt-3 text-sm leading-6 text-slate-600">
              Visit the clinic and complete your selected laboratory tests
              at the available facility.
            </p>

            <div className="mt-6 flex items-center text-sm font-bold text-cyan-700">
              Continue
              <span className="ml-2 transition-transform group-hover:translate-x-1">
                →
              </span>
            </div>
          </button>

        </div>

      </div>
    </div>
  );
}