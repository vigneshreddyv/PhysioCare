import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import {
  Hospital,
  Home,
  Video,
  Accessibility,
  FlaskConical,
  ClipboardList,
  Dumbbell,
  ArrowRight,
  Headset,
} from 'lucide-react';

const services = [
  {
    id: 'clinic',
    icon: Hospital,
    title: 'Clinic Consultation',
    description: 'Visit our clinic and consult with a physiotherapy specialist.',
    featured: false,
  },
  {
    id: 'home-visit',
    icon: Home,
    title: 'Home Visit',
    description: 'Get professional physiotherapy care at your home.',
    featured: false,
  },
  {
    id: 'online',
    icon: Video,
    title: 'Online Consultation',
    description: 'Talk to a physiotherapist from anywhere through video consultation.',
    featured: false,
  },
  {
    id: 'physiotherapy',
    icon: Accessibility,
    title: 'Physiotherapy Treatment',
    description: 'Personalized treatment sessions for pain, injury and recovery.',
    featured: false,
  },
  {
    id: 'laboratory',
    icon: FlaskConical,
    title: 'Laboratory Tests',
    description: 'Book and manage your required laboratory investigations.',
    featured: true,
  },
  {
    id: 'care-plan',
    icon: ClipboardList,
    title: 'Personalized Care Plans',
    description: 'Get a customized healthcare and physiotherapy care plan.',
    featured: false,
  },
  {
    id: 'exercise',
    icon: Dumbbell,
    title: 'Exercise & Recovery Plans',
    description: 'Follow guided exercises and recovery plans designed for you.',
    featured: false,
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
    <div className="max-w-5xl mx-auto animate-fade-in p-4 sm:p-6 lg:p-8 pb-[84px] lg:pb-12 text-[#1E2A2B] dark:text-zinc-100">

      {/* Greeting */}
      <header className="pt-2 pb-8 sm:pb-10 space-y-2">
        <p className="text-xs font-extrabold uppercase tracking-widest text-[#1F4B45] dark:text-[#5FC2B8]">
          Welcome to PhysioCare
        </p>
        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
          Good to see you, {firstName}
        </h1>
        <p className="mt-2 max-w-2xl text-[15px] sm:text-base text-[#60716E] dark:text-zinc-400 font-medium leading-relaxed">
          How can we help you today? Choose a healthcare service to get started with your care journey.
        </p>
      </header>

      {/* Services heading */}
      <div className="mb-6">
        <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-[#1E2A2B] dark:text-zinc-50">
          Choose a Service
        </h2>
        <p className="mt-1 text-sm text-[#60716E] dark:text-zinc-400 font-medium">
          Select the service that best matches your current healthcare needs.
        </p>
      </div>

      {/* Services */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

        {services.map((service) => {
          const Icon = service.icon;
          return (
            <button
              key={service.id}
              type="button"
              onClick={() => handleServiceSelect(service)}
              className={`group text-left rounded-3xl border p-5 sm:p-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md min-h-[48px] ${
                service.featured
                  ? 'bg-[#1F4B45] border-[#1F4B45] text-white shadow-lg shadow-[#1F4B45]/20'
                  : 'bg-white dark:bg-zinc-900 border-[#E5E0D6] dark:border-zinc-800 text-[#1E2A2B] dark:text-zinc-100 hover:border-[#1F4B45]/30'
              }`}
            >
              <span className={`mb-4 flex h-12 w-12 items-center justify-center rounded-2xl ${
                service.featured
                  ? 'bg-white/10 text-white'
                  : 'bg-[#EEF5F1] text-[#1F4B45] dark:bg-zinc-800 dark:text-[#5FC2B8]'
              }`}>
                <Icon className="w-5 h-5" strokeWidth={2} />
              </span>

              <h3 className="text-lg font-bold tracking-tight">
                {service.title}
              </h3>

              <p className={`mt-1.5 min-h-[48px] text-[13px] leading-5 font-medium ${
                service.featured ? 'text-white/70' : 'text-[#60716E] dark:text-zinc-400'
              }`}>
                {service.description}
              </p>

              <div className={`mt-4 flex items-center gap-1.5 text-sm font-bold ${
                service.featured ? 'text-[#C9A86A]' : 'text-[#C1694A]'
              }`}>
                Get started
                <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
              </div>
            </button>
          );
        })}

      </div>

      {/* Support section */}
      <div className="mt-10 rounded-3xl border border-[#E5E0D6] dark:border-zinc-800 bg-[#F7F4ED] dark:bg-zinc-900 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

          <div className="flex items-start gap-4">
            <div className="w-11 h-11 rounded-2xl bg-white dark:bg-zinc-800 border border-[#E5E0D6] dark:border-zinc-700 flex items-center justify-center shrink-0 text-[#1F4B45] dark:text-[#5FC2B8]">
              <Headset className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#1E2A2B] dark:text-zinc-100">
                Not sure which service you need?
              </h3>
              <p className="mt-1 text-[13px] text-[#60716E] dark:text-zinc-400 font-medium">
                Our healthcare team can help you choose the right treatment.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="shrink-0 rounded-xl border border-[#1F4B45]/20 dark:border-zinc-700 bg-white dark:bg-zinc-800 px-5 py-3 text-sm font-bold text-[#1F4B45] dark:text-[#5FC2B8] transition hover:bg-[#EEF5F1] dark:hover:bg-zinc-700 min-h-[48px]"
          >
            Contact Support
          </button>

        </div>
      </div>

    </div>
  );
}