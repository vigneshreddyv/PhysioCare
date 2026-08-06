import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import api from '../../services/api';
import StatCard from '../../components/features/StatCard';
import AppointmentCard from '../../components/features/AppointmentCard';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';
import Button from '../../components/common/Button';

export default function PatientDashboard() {
  const navigate = useNavigate();

  const { 
    data: appointments, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['patientAppointments'],
    queryFn: async () => {
      const response = await api.get('/appointments');
      return response.data;
    }
  });

  if (error) {
    return <ErrorState message="Could not load patient dashboard data." onRetry={() => refetch()} />;
  }

  // Filter appointments: upcoming (scheduled or in-progress) vs past (completed or cancelled)
  const upcoming = appointments?.filter(
    (a) => a.status === 'scheduled' || a.status === 'in_progress'
  ) || [];

  const primaryDoc = appointments?.[0]?.doctor_name || 'Assigned Specialist';

  return (
    <div className="space-y-stack-lg animate-fade-in pb-16">
      
      {/* Welcome Heading */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Your Health Portal</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Check upcoming therapy sessions and track your care plan.</p>
        </div>
        <Button 
          variant="primary" 
          onClick={() => navigate('/patient/book')}
          className="hidden sm:flex"
        >
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>add</span>
          Book Consultation
        </Button>
      </div>

      {/* Bento Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-gutter mb-12">
        {isLoading ? (
          <Skeleton variant="card" count={3} />
        ) : (
          <>
            <StatCard
              title="Upcoming Sessions"
              value={upcoming.length}
              icon="calendar_today"
              changeText="Next scheduled visit"
              changeType="flat"
              colorVariant="primary"
            />
            <StatCard
              title="Care Program"
              value="Active"
              icon="card_membership"
              changeText="Monthly subscription active"
              changeType="flat"
              colorVariant="secondary"
            />
            <StatCard
              title="Primary Therapist"
              value={primaryDoc}
              icon="stethoscope"
              changeText="Assigned"
              changeType="flat"
              colorVariant="tertiary"
              wrapText={true}
            />
          </>
        )}
      </div>

      {/* Quick CTA banner for mobile */}
      <div className="sm:hidden mb-6">
        <Button 
          variant="primary" 
          onClick={() => navigate('/patient/book')}
          className="w-full py-4"
        >
          <span className="material-symbols-outlined" style={{ fontVariationSettings: "'FILL' 1" }}>add</span>
          Book Consultation
        </Button>
      </div>

      {/* Upcoming appointments list */}
      <div className="bg-surface-container-lowest rounded-xl shadow-sm border border-surface-container p-6">
        <div className="flex justify-between items-center mb-6 border-b border-surface-container-high pb-4">
          <h3 className="font-headline-md text-headline-md text-on-surface">Upcoming Consultations</h3>
          <Link to="/patient/history" className="text-primary hover:underline text-sm font-semibold">View All History</Link>
        </div>

        {isLoading ? (
          <Skeleton variant="row" count={2} />
        ) : upcoming.length === 0 ? (
          <EmptyState 
            title="No sessions scheduled" 
            message="You don't have any therapy visits booked. Ready to schedule a session?"
            icon="calendar_today"
            actionLabel="Schedule Now"
            onAction={() => navigate('/patient/book')}
          />
        ) : (
          <div className="space-y-4 divide-y divide-surface-container">
            {upcoming.map((appt) => (
              <AppointmentCard
                key={appt.id}
                appointment={appt}
                displayRole="patient"
              />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
