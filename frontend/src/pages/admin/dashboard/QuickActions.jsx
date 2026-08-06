import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';

export default function QuickActions() {
  const navigate = useNavigate();

  return (
    <div>
      <Button variant="primary" className="w-full justify-start" data-tooltip="Register a new patient to the system" onClick={() => navigate('/admin/patients-create')}>
        <span className="material-symbols-outlined mr-2">person_add</span>
        Register New Patient
      </Button>
      <Button variant="outline" className="w-full justify-start" data-tooltip="Schedule a new appointment for a patient" onClick={() => navigate('/admin/appointment-booking')}>
        <span className="material-symbols-outlined mr-2">calendar_today</span>
        Schedule Appointment
      </Button>
      <Button variant="outline" className="w-full justify-start" data-tooltip="View detailed reports and analytics" onClick={() => navigate('/admin/analytics')}>
        <span className="material-symbols-outlined mr-2">insert_chart</span>
        View Analytics
      </Button>
      <Button variant="outline" className="w-full justify-start" data-tooltip="Process payments and manage billing" onClick={() => navigate('/admin/billing')}>
        <span className="material-symbols-outlined mr-2">receipt_long</span>
        Process Payments
      </Button>
    </div>
  );
}