import React from 'react';
import { useAuth } from '../../../context/useAuth';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';
import { format } from 'date-fns';

export default function DashboardHeader() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const currentDate = new Date();
  const formattedDate = format(currentDate, 'PPPP'); // Format like "August 4, 2026"

  // Get greeting based on time of day
  const hours = currentDate.getHours();
  let greeting = 'Good morning';
  if (hours >= 12 && hours < 17) {
    greeting = 'Good afternoon';
  } else if (hours >= 17) {
    greeting = 'Good evening';
  }

  return (
    <header className="portal-hero flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
      <div>
        <span className="portal-hero__eyebrow"><span className="material-symbols-outlined" aria-hidden="true">monitoring</span>Clinic operations</span>
        <h1>
          {greeting}, {user?.full_name && typeof user.full_name === 'string' ? user.full_name.split(' ')[0] : 'team'}.
        </h1>
        <p>
          Review the clinic's current workload and operational indicators for {formattedDate}.
        </p>
      </div>
      <div className="portal-hero__actions lg:justify-end lg:mt-0">
        <Button variant="outline" size="sm" className="bg-white/10 !text-white !border-white/30 hover:!bg-white/20" onClick={() => navigate('/admin/appointment-booking')}>
          Schedule Appointment
        </Button>
        <Button variant="patientPrimary" size="sm" onClick={() => navigate('/admin/patients-create')}>
          New Patient
        </Button>
      </div>
    </header>
  );
}
