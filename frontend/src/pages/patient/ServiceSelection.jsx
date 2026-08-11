import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';

const services = [
  {
    id: 'clinic',
    icon: '🏥',
    title: 'Clinic Consultation',
    description: 'Visit our clinic and consult with a physiotherapy specialist.',
    color: 'from-cyan-50 to-blue-50',
  },
  {
    id: 'home-visit',
    icon: '🏠',
    title: 'Home Visit',
    description: 'Get professional physiotherapy care at your home.',
    color: 'from-emerald-50 to-teal-50',
  },
  {
    id: 'online',
    icon: '💻',
    title: 'Online Consultation',
    description: 'Talk to a physiotherapist from anywhere through video consultation.',
    color: 'from-violet-50 to-indigo-50',
  },
  {
    id: 'physiotherapy',
    icon: '🦴',
    title: 'Physiotherapy Treatment',
    description: 'Personalized treatment sessions for pain, injury and recovery.',
    color: 'from-orange-50 to-amber-50',
  },
  {
    id: 'laboratory',
    icon: '🧪',
    title: 'Laboratory Tests',
    description: 'Book and manage your required laboratory investigations.',
    color: 'from-rose-50 to-pink-50',
  },
  {
    id: 'care-plan',
    icon: '📋',
    title: 'Personalized Care Plans',
    description: 'Get a customized healthcare and physiotherapy care plan.',
    color: 'from-blue-50 to-sky-50',
  },
  {
    id: 'exercise',
    icon: '🏃',
    title: 'Exercise & Recovery Plans',
    description: 'Follow guided exercises and recovery plans designed for you.',
    color: 'from-lime-50 to-green-50',
  },
];

export default function ServiceSelection() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const firstName = user?.full_name?.split(' ')[0] || 'there';

  const handleServiceSelect = (service) => {
    if (service.id === 'laboratory') {
      navigate('/patient/laboratory');
        return;
        }

        navigate(`/patient/book?service=${service.id}`);
        };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">

        {/* Greeting */}
        <div className="mb-10">
          <p className="mb-2 text-sm font-medium text-cyan-700">
            Welcome to PhysioCare
          </p>

          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Good to see you, {firstName} 👋
          </h1>

          <p className="mt-3 max-w-2xl text-base text-slate-600 sm:text-lg">
            How can we help you today?
            Choose a healthcare service to get started with your care journey.
          </p>
        </div>

        {/* Service heading */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-900">
            Choose a Service
          </h2>

          <p className="mt-1 text-sm text-slate-500">
            Select the service that best matches your current healthcare needs.
          </p>
        </div>

        {/* Services */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">

          {services.map((service) => (
            <button
              key={service.id}
              type="button"
              onClick={() => handleServiceSelect(service)}
              className="group text-left"
            >
              <div
                className={`h-full rounded-2xl border border-slate-200 bg-gradient-to-br ${service.color} p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-cyan-300 hover:shadow-lg`}
              >

                {/* Icon */}
                <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-3xl shadow-sm">
                  {service.icon}
                </div>

                {/* Title */}
                <h3 className="text-xl font-bold text-slate-900">
                  {service.title}
                </h3>

                {/* Description */}
                <p className="mt-2 min-h-[60px] text-sm leading-6 text-slate-600">
                  {service.description}
                </p>

                {/* Action */}
                <div className="mt-5 flex items-center text-sm font-semibold text-cyan-700">
                  Get started
                  <span className="ml-2 transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </div>

              </div>
            </button>
          ))}

        </div>

        {/* Support section */}
        <div className="mt-10 rounded-2xl border border-cyan-100 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Not sure which service you need?
              </h3>

              <p className="mt-1 text-sm text-slate-600">
                Our healthcare team can help you choose the right treatment.
              </p>
            </div>

            <button
              type="button"
              className="rounded-xl border border-cyan-700 px-5 py-3 text-sm font-semibold text-cyan-700 transition hover:bg-cyan-50"
            >
              Contact Support
            </button>

          </div>
        </div>

      </div>
    </div>
  );
}