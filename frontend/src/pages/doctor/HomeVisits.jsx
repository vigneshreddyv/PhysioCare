import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function HomeVisits() {
  const { data: requests, isLoading, error, refetch } = useQuery({
    queryKey: ['doctorHomeVisitRequests'],
    queryFn: async () => (await api.get('/home-visit-requests/doctor')).data,
  });

  if (error) return <ErrorState message="Could not load assigned home-visit requests." onRetry={() => refetch()} />;

  return (
    <div className="portal-page animate-fade-in">
      <header className="portal-hero">
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">home_health</span>Coordination review</span>
        <h1>Assigned home-visit requests</h1>
        <p>Review only requests that named you and were approved by the clinic for coordination.</p>
      </header>
      <div className="portal-trust-note" role="note"><span className="material-symbols-outlined" aria-hidden="true">info</span><span>These are not confirmed or scheduled visits. No time, capacity, coverage, or service-area decision has been made.</span></div>
      <section className="portal-section-card" aria-labelledby="doctor-home-requests-heading">
        <div className="portal-section-card__header"><div><span className="portal-section__eyebrow">Selected clinician only</span><h2 id="doctor-home-requests-heading" className="font-headline-md text-headline-md">Approved for coordination</h2></div><span className="portal-count-pill">{requests?.length || 0} requests</span></div>
        {isLoading ? <Skeleton variant="row" count={2} /> : !requests?.length ? <div className="p-6"><EmptyState title="No assigned requests" message="Only clinic-approved requests that specifically name you appear here." icon="home_health" /></div> : (
          <div className="reception-schedule-grid">
            {requests.map((request) => <article key={request.id} className="portal-mobile-record">
              <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">Approved for coordination</p><h3 className="font-semibold">{request.patient_name}</h3><p className="text-sm text-on-surface-variant">{request.patient_phone || 'No phone provided'}</p></div>
              <div className="portal-mobile-record__row"><span>Address</span><strong>{request.home_address}</strong></div>
              <div className="portal-mobile-record__row"><span>Clinical reason</span><strong>{request.reason}</strong></div>
              <p className="text-sm text-on-surface-variant">{request.confirmation_message}</p>
            </article>)}
          </div>
        )}
      </section>
    </div>
  );
}
