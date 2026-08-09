import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Building2,
  Home,
  Laptop,
  Activity,
  FlaskConical,
  ClipboardList,
  PersonStanding,
  ArrowRight,
  ShieldCheck,
  CalendarCheck,
  Stethoscope,
  Clock,
  Bone,
  Users,
} from 'lucide-react';
import api from '../../services/api';
import heroImage from '../../assets/hero.png';

// Each service carries its own tint + accent so the grid reads as a set of
// distinct "doors" into care rather than one repeated card. Swap the copy
// for whatever services PhysioCare actually offers.
const services = [
  {
    service: 'clinic',
    title: 'Clinic Consultation',
    description: 'Meet a specialist at our clinic for a full assessment.',
    icon: Building2,
    tint: 'from-[#eaf7fd] to-[#f6fcff]',
    accent: '#0b84a5',
    iconBg: '#dff3fb',
  },
  {
    service: 'home',
    title: 'Home Visit',
    description: 'Professional physiotherapy care in your own home.',
    icon: Home,
    tint: 'from-[#e9faf3] to-[#f5fffb]',
    accent: '#16a382',
    iconBg: '#dff6ec',
  },
  {
    service: 'online',
    title: 'Online Consultation',
    description: 'Talk to a physiotherapist by secure video, anywhere.',
    icon: Laptop,
    tint: 'from-[#efeeff] to-[#f8f8ff]',
    accent: '#6c63d6',
    iconBg: '#e7e5fc',
  },
  {
    service: 'physiotherapy',
    title: 'Physiotherapy Treatment',
    description: 'Sessions built around pain relief and mobility.',
    icon: Bone,
    tint: 'from-[#fff6e7] to-[#fffdf5]',
    accent: '#d99022',
    iconBg: '#fbedcf',
  },
  {
    service: 'laboratory',
    title: 'Laboratory Tests',
    description: 'Book and track the tests your care plan needs.',
    icon: FlaskConical,
    tint: 'from-[#fff0f5] to-[#fff9fb]',
    accent: '#d75d88',
    iconBg: '#fbe1ea',
  },
  {
    service: 'care-plan',
    title: 'Personalized Care Plans',
    description: 'A plan shaped around your goals and progress.',
    icon: ClipboardList,
    tint: 'from-[#edf7ff] to-[#f8fbff]',
    accent: '#3a87c9',
    iconBg: '#dcedfb',
  },
  {
    service: 'exercise',
    title: 'Exercise & Recovery',
    description: 'Guided movement plans that track with you.',
    icon: PersonStanding,
    tint: 'from-[#f3f0ff] to-[#faf9ff]',
    accent: '#7a62cf',
    iconBg: '#e9e4fc',
  },
];

const features = [
  { icon: ShieldCheck, title: 'Secure & Private', text: 'Encrypted and fully confidential.' },
  { icon: CalendarCheck, title: 'Easy Booking', text: 'A few taps to your next slot.' },
  { icon: Stethoscope, title: 'Expert Therapists', text: 'Vetted, experienced specialists.' },
  { icon: Clock, title: 'Flexible Schedule', text: 'Times that fit around your day.' },
];

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function PatientDashboard() {
  const navigate = useNavigate();

  const { data: appointments = [] } = useQuery({
    queryKey: ['patient-appointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    },
  });

  const upcoming = appointments.filter(
    (appointment) =>
      appointment.status === 'scheduled' || appointment.status === 'in_progress'
  );

  const userName = localStorage.getItem('user_name') || 'there';

  const handleService = (service) => {
    navigate(`/patient/book?service=${service}`);
  };

  return (
    <div className="max-w-[1500px] mx-auto">
      {/* HERO */}
      <section className="relative overflow-hidden rounded-[28px] min-h-[300px] bg-gradient-to-br from-[#e9f8ff] via-[#f2fbff] to-[#e6f9f1] border border-white shadow-[0_18px_50px_rgba(20,80,120,0.07)]">
        <div className="absolute -top-24 -right-16 w-[340px] h-[340px] rounded-full bg-cyan-200/25 blur-3xl" />
        <div className="absolute bottom-[-120px] left-[38%] w-[280px] h-[280px] rounded-full bg-emerald-200/20 blur-3xl" />

        {/* recovery-path motif */}
        <svg
          className="absolute left-8 sm:left-12 lg:left-16 bottom-8 w-64 h-16 text-cyan-500/25 hidden sm:block"
          viewBox="0 0 260 60"
          fill="none"
        >
          <path
            d="M0 30 H60 L75 8 L95 52 L112 30 H150 L162 42 L175 18 L190 30 H260"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        <div className="relative grid lg:grid-cols-[1.05fr_.95fr] min-h-[300px]">
          {/* TEXT */}
          <div className="flex flex-col justify-center px-7 sm:px-10 lg:px-12 xl:px-16 py-10">
            <div className="inline-flex items-center gap-2 w-fit px-3 py-1.5 rounded-full bg-white/75 border border-white text-[#0786ad] text-xs font-bold tracking-wide">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              YOUR HEALTHCARE JOURNEY
            </div>

            <h1 className="text-4xl sm:text-5xl xl:text-[50px] leading-[1.08] font-extrabold tracking-tight text-[#0a2540] mt-5">
              {getGreeting()}, <span className="text-[#0b84a5]">{userName}</span>{' '}
              <span aria-hidden>👋</span>
            </h1>

            <p className="mt-4 text-base sm:text-lg text-slate-600 max-w-xl leading-7">
              Your care, appointments and recovery — all in one place.
              Choose a service below to get started.
            </p>

            <div className="flex flex-wrap gap-3 mt-7">
              <button
                onClick={() => navigate('/patient/book')}
                className="group px-6 py-3.5 rounded-xl bg-[#0b84a5] text-white font-bold shadow-[0_10px_25px_rgba(11,132,165,0.25)] hover:bg-[#08708c] hover:-translate-y-0.5 transition inline-flex items-center gap-2"
              >
                Book an appointment
                <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition" />
              </button>

              <button
                onClick={() => navigate('/patient/history')}
                className="px-6 py-3.5 rounded-xl bg-white/85 border border-white text-[#0b84a5] font-bold hover:bg-white transition"
              >
                View appointments
              </button>
            </div>
          </div>

          {/* IMAGE */}
          <div className="hidden lg:block relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-r from-[#eaf8ff] via-transparent to-transparent z-10" />
            <img
              src={heroImage}
              alt="Physiotherapist assisting a patient"
              className="absolute inset-0 w-full h-full object-cover object-center"
            />

            <div className="absolute left-8 top-10 z-20 w-11 h-11 rounded-full bg-white shadow-lg flex items-center justify-center">
              <Bone className="w-5 h-5 text-[#0b84a5]" />
            </div>
            <div className="absolute left-2 top-28 z-20 w-11 h-11 rounded-full bg-white shadow-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-[#0b84a5]" />
            </div>
          </div>
        </div>
      </section>

      {/* SERVICES */}
      <section className="mt-10">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between mb-6">
          <div>
            <p className="text-[#0b84a5] text-xs font-bold uppercase tracking-[0.18em]">
              Explore care
            </p>
            <h2 className="text-3xl font-extrabold text-[#0a2540] mt-1">
              Choose the care you need
            </h2>
          </div>

          <button
            onClick={() => navigate('/patient/book')}
            className="mt-4 md:mt-0 text-sm font-bold text-[#0b84a5] hover:underline"
          >
            View all services →
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
          {services.map((service) => {
            const Icon = service.icon;
            return (
              <button
                key={service.service}
                onClick={() => handleService(service.service)}
                className={`group relative overflow-hidden text-left min-h-[220px] rounded-[22px] border border-white bg-gradient-to-br ${service.tint} p-6 shadow-[0_8px_28px_rgba(30,80,120,0.05)] hover:-translate-y-1.5 hover:shadow-[0_20px_40px_rgba(30,80,120,0.11)] transition-all duration-300`}
              >
                <div className="absolute -right-10 -bottom-10 w-32 h-32 rounded-full bg-white/40 group-hover:scale-125 transition-transform duration-500" />

                <div className="relative">
                  <div
                    className="w-12 h-12 rounded-2xl bg-white shadow-sm flex items-center justify-center"
                    style={{ backgroundColor: service.iconBg }}
                  >
                    <Icon className="w-5 h-5" style={{ color: service.accent }} strokeWidth={2.2} />
                  </div>

                  <h3 className="text-lg font-extrabold text-[#0a2540] mt-5">
                    {service.title}
                  </h3>

                  <p className="text-sm text-slate-600 leading-6 mt-2">
                    {service.description}
                  </p>

                  <div
                    className="mt-4 inline-flex items-center gap-1.5 text-sm font-extrabold group-hover:gap-2.5 transition-all"
                    style={{ color: service.accent }}
                  >
                    Explore service
                    <ArrowRight className="w-3.5 h-3.5" />
                  </div>
                </div>
              </button>
            );
          })}

          {/* CTA card completes the grid */}
          <div className="relative overflow-hidden rounded-[22px] min-h-[220px] bg-gradient-to-br from-[#0a3a52] via-[#0b84a5] to-[#12a5be] text-white p-6 flex flex-col justify-between">
            <div className="absolute -right-10 -top-10 w-40 h-40 rounded-full border-[24px] border-white/5" />
            <div className="relative">
              <p className="text-xs font-bold tracking-wide text-cyan-100">
                YOUR HEALTH IS OUR PRIORITY
              </p>
              <p className="text-xl font-extrabold mt-2 leading-snug">
                Care that follows your journey.
              </p>
            </div>
            <button
              onClick={() => navigate('/patient/profile')}
              className="relative w-fit mt-4 px-4 py-2.5 rounded-xl bg-white text-[#0b84a5] text-sm font-bold hover:bg-cyan-50 transition"
            >
              View care profile →
            </button>
          </div>
        </div>
      </section>

      {/* FEATURE STRIP */}
      <section className="mt-8 bg-white rounded-[22px] border border-[#e7edf5] shadow-[0_8px_28px_rgba(30,80,120,0.05)] p-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <div key={feature.title} className="flex items-start gap-3">
              <div className="w-11 h-11 shrink-0 rounded-xl bg-[#eaf7fd] flex items-center justify-center">
                <Icon className="w-5 h-5 text-[#0b84a5]" />
              </div>
              <div>
                <p className="font-bold text-[#0a2540] text-sm">{feature.title}</p>
                <p className="text-xs text-slate-500 mt-0.5">{feature.text}</p>
              </div>
            </div>
          );
        })}
      </section>

      {/* UPCOMING APPOINTMENTS */}
      <section className="mt-8 bg-white rounded-[22px] border border-[#e7edf5] shadow-[0_8px_28px_rgba(30,80,120,0.05)] p-6 lg:p-7">
        <div className="flex items-center justify-between mb-6">
          <div>
            <p className="text-[#0b84a5] text-xs font-bold uppercase tracking-[0.18em]">
              Your schedule
            </p>
            <h2 className="text-2xl font-extrabold text-[#0a2540] mt-1">
              Upcoming consultations
            </h2>
          </div>

          <button
            onClick={() => navigate('/patient/history')}
            className="text-sm font-bold text-[#0b84a5] hover:underline"
          >
            View all →
          </button>
        </div>

        {upcoming.length === 0 ? (
          <div className="rounded-[20px] bg-gradient-to-br from-[#f5faff] to-[#f0f9ff] border border-[#e5f0f7] p-10 text-center">
            <div className="w-14 h-14 rounded-2xl bg-white shadow-sm mx-auto flex items-center justify-center">
              <CalendarCheck className="w-6 h-6 text-[#0b84a5]" />
            </div>
            <h3 className="text-xl font-extrabold text-[#0a2540] mt-5">
              No sessions scheduled
            </h3>
            <p className="text-slate-500 mt-2">
              You don't have any therapy visits booked yet.
            </p>
            <button
              onClick={() => navigate('/patient/book')}
              className="mt-5 px-6 py-3 rounded-xl bg-[#0b84a5] text-white font-bold hover:bg-[#08708c] transition"
            >
              Schedule a session →
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {upcoming.map((appointment) => (
              <div
                key={appointment.id}
                className="border border-[#e8edf3] rounded-[18px] p-5 hover:border-cyan-200 hover:shadow-md transition"
              >
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5">
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-100 to-blue-100 flex items-center justify-center font-extrabold text-[#0b84a5]">
                        {appointment.doctor_name?.charAt(0) || 'D'}
                      </div>
                      <div>
                        <h3 className="font-extrabold text-lg text-[#0a2540]">
                          {appointment.doctor_name || 'Physiotherapist'}
                        </h3>
                        <p className="text-sm text-slate-500">
                          Physiotherapy consultation
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-5 mt-4 text-sm text-slate-500">
                      <span className="inline-flex items-center gap-1.5">
                        <CalendarCheck className="w-4 h-4" />
                        {appointment.appointment_date}
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <Clock className="w-4 h-4" />
                        {appointment.reason || 'Consultation'}
                      </span>
                    </div>
                  </div>

                  <span className="self-start md:self-center px-4 py-2 rounded-full bg-emerald-50 text-emerald-700 text-xs font-extrabold capitalize">
                    {appointment.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="h-8" />
    </div>
  );
}