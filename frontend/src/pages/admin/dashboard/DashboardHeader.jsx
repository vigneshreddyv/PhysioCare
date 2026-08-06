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
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between mb-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          {greeting}, {user?.full_name && typeof user.full_name === 'string' ? user.full_name.split(' ')[0] : 'Dr.'}!
        </h1>
        <p className="text-gray-600">
          Overview of your clinic's performance today • {formattedDate}
        </p>
      </div>
      <div className="flex space-x-3 mt-4 lg:mt-0">
        <Button variant="outline" size="sm" onClick={() => navigate('/admin/appointment-booking')}>
          Schedule Appointment
        </Button>
        <Button variant="primary" size="sm" onClick={() => navigate('/admin/patients-create')}>
          New Patient
        </Button>
      </div>
    </div>
  );
}