import React from 'react';
import { Link } from 'react-router-dom';

const services = [
  { title: 'Clinic consultation', description: 'Choose a published clinician, date, and listed IST slot.', icon: 'stethoscope', to: '/patient/book', tone: 'teal', status: 'Available now', cta: 'Book clinic care' },
  { title: 'Home visit', description: 'Choose a physiotherapist, date, and available time for a home visit in Nellore.', icon: 'home_health', to: '/patient/home-visits', tone: 'mint', status: 'Slot booking', cta: 'Book home care' },
  { title: 'Laboratory tests', description: 'Build a demo test request for clinic review—without checkout or payment.', icon: 'biotech', to: '/patient/laboratory', tone: 'coral', status: 'Clinic review', cta: 'Build a request' },
  { title: 'Physiotherapy treatment', description: 'Start with the existing clinician-led clinic booking flow.', icon: 'physical_therapy', to: '/patient/book', tone: 'navy', status: 'Available now', cta: 'Choose a clinician' },
  { title: 'Online consultation', description: 'Review the current Phase 1 status and requirements still needed.', icon: 'video_camera_front', to: '/patient/services/online-consultation', tone: 'blue', status: 'Requirements needed', cta: 'View current status' },
  { title: 'Personalized care plans', description: 'See what must be clinically specified before this service can launch.', icon: 'assignment', to: '/patient/services/care-plans', tone: 'gold', status: 'Requirements needed', cta: 'View current status' },
  { title: 'Exercise & recovery plans', description: 'A future clinical module; no exercises are prescribed in this demo.', icon: 'exercise', to: '/patient/services/recovery-plans', tone: 'sage', status: 'Future clinical module', cta: 'View current status' },
];

export default function PatientServices() {
  return <div className="patient-services patient-page animate-fade-in pb-20">
    <header className="patient-services__hero patient-product-header">
      <div><div className="patient-product-header__meta"><span className="material-symbols-outlined" aria-hidden="true">location_on</span>Nellore care access</div><p className="patient-page__eyebrow">Patient services</p><h1>What can we help you with?</h1><p>Choose a care path and see exactly what happens next.</p></div>
      <div className="patient-product-header__mark" aria-hidden="true"><span className="material-symbols-outlined">health_and_safety</span></div>
    </header>
    <div className="patient-services__truth" role="note"><span className="material-symbols-outlined" aria-hidden="true">verified_user</span><span><strong>Choose the care option that suits you.</strong> Home visits are currently available in Nellore.</span></div>
    <section className="patient-services__grid" aria-label="Available and planned services">
      {services.map((service) => <Link key={service.title} to={service.to} className={`patient-services__card patient-services__card--${service.tone}`}>
        <div className="patient-services__card-top"><span className="patient-services__icon material-symbols-outlined" aria-hidden="true">{service.icon}</span><span className="patient-services__status">{service.status}</span></div>
        <div><h2>{service.title}</h2><p>{service.description}</p></div>
        <div className="patient-services__cta"><span>{service.cta}</span><span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></div>
      </Link>)}
    </section>
  </div>;
}
