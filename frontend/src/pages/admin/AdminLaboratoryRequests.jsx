import React from 'react';
import AdminLabRequestsPanel from './AdminLabRequestsPanel';

export default function AdminLaboratoryRequests() {
  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow">
          <span className="material-symbols-outlined" aria-hidden="true">biotech</span>
          Laboratory workflow
        </span>
        <h1>Laboratory Requests</h1>
        <p>Review patient requests, assign laboratorians, and review or publish finalized reports.</p>
      </header>
      <AdminLabRequestsPanel />
    </div>
  );
}
