import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';
import { UserPlus, Calendar, TrendingUp, CreditCard } from 'lucide-react';

export default function QuickActions() {
  const navigate = useNavigate();

  return (
    <div className="space-y-2">
      <Button 
        variant="primary" 
        className="w-full justify-start text-xs font-bold py-2.5 px-4 rounded-xl flex items-center gap-2" 
        onClick={() => navigate('/admin/patients-create')}
      >
        <UserPlus className="w-4 h-4 shrink-0" />
        Register New Patient
      </Button>
      <Button 
        variant="outline" 
        className="w-full justify-start text-xs font-bold py-2.5 px-4 rounded-xl border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex items-center gap-2" 
        onClick={() => navigate('/admin/appointment-booking')}
      >
        <Calendar className="w-4 h-4 shrink-0" />
        Schedule Appointment
      </Button>
      <Button 
        variant="outline" 
        className="w-full justify-start text-xs font-bold py-2.5 px-4 rounded-xl border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex items-center gap-2" 
        onClick={() => navigate('/admin/analytics')}
      >
        <TrendingUp className="w-4 h-4 shrink-0" />
        View Analytics
      </Button>
      <Button 
        variant="outline" 
        className="w-full justify-start text-xs font-bold py-2.5 px-4 rounded-xl border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex items-center gap-2" 
        onClick={() => navigate('/admin/billing')}
      >
        <CreditCard className="w-4 h-4 shrink-0" />
        Process Payments
      </Button>
    </div>
  );
}