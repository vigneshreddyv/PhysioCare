import React from 'react';
import { Link, useParams } from 'react-router-dom';

const details = {
  'online-consultation': { icon: 'video_camera_front', title: 'Online consultation', summary: 'This service is requested, but a secure consultation workflow is not configured yet.', needs: ['Approved video provider and consent flow', 'Clinician availability and escalation policy', 'Clinical record and privacy requirements'] },
  'care-plans': { icon: 'assignment', title: 'Personalized care plans', summary: 'Care plans require clinician-authored goals and review rules before they can be offered safely.', needs: ['Who authors and approves a plan', 'Patient acknowledgement and revision history', 'Plan visibility across clinic roles'] },
  'recovery-plans': { icon: 'exercise', title: 'Exercise & recovery plans', summary: 'No exercise, dosage, or recovery instruction is generated in this Phase 1 demo.', needs: ['Clinician-approved exercise library', 'Contraindication and safety review', 'Progress tracking and stop/escalation guidance'] },
};

export default function ServiceDetails() {
  const { serviceKey } = useParams();
  const service = details[serviceKey];
  if (!service) return <div className="portal-section-card p-6"><h1>Service not found</h1><Link to="/patient/services">Return to services</Link></div>;
  return <div className="patient-service-detail patient-page animate-fade-in pb-20">
    <Link to="/patient/services" className="patient-service-detail__back"><span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>All services</Link>
    <header><span className="material-symbols-outlined" aria-hidden="true">{service.icon}</span><p className="patient-page__eyebrow">Requirements preview</p><h1>{service.title}</h1><p>{service.summary}</p></header>
    <section><h2>What is still needed</h2><ul>{service.needs.map((item) => <li key={item}><span className="material-symbols-outlined" aria-hidden="true">check_circle</span>{item}</li>)}</ul></section>
    <div className="patient-services__truth" role="note"><span className="material-symbols-outlined" aria-hidden="true">info</span><span>This page does not create a booking, clinical plan, video session, or treatment instruction.</span></div>
  </div>;
}
