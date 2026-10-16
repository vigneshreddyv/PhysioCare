import React from 'react';
import { useAuth } from '../../../context/useAuth';
import { useNavigate } from 'react-router-dom';
import Button from '../../../components/common/Button';
import { format } from 'date-fns';
import { ShieldCheck, Plus, Calendar } from 'lucide-react';

export default function DashboardHeader() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const currentDate = new Date();
  const formattedDate = format(currentDate, 'PPPP');

  // Get greeting based on time of day
  const hours = currentDate.getHours();
  let greeting = 'Good morning';
  if (hours >= 12 && hours < 17) {
    greeting = 'Good afternoon';
  } else if (hours >= 17) {
    greeting = 'Good evening';
  }

  const name = user?.full_name && typeof user.full_name === 'string' 
    ? user.full_name.split(' ')[0] 
    : 'Admin';

  return (
    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 border-b border-[#E5E0D6]/65 pb-6 mb-8">
      <div>
        <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Platform Overview</span>
        <h1 className="text-3xl font-extrabold text-[#183B4A] mt-1">
          {greeting}, {name}
        </h1>
        <p className="mt-2 text-sm sm:text-base text-[#60716E] max-w-2xl leading-relaxed">
          Overview of PhysioCare platform statistics and today's scheduling operations • {formattedDate}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-[#60716E] bg-white border border-[#E5E0D6] p-2.5 rounded-xl shadow-xs shrink-0 mr-1.5">
          <ShieldCheck className="w-5 h-5 text-[#0F6B63] shrink-0" />
          <span>Admin Workspace Active</span>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={() => navigate('/admin/appointment-booking')}
          className="text-xs font-bold py-2.5 px-4 rounded-xl border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63] flex items-center gap-1.5"
        >
          <Calendar className="w-4 h-4" />
          Schedule Appointment
        </Button>
        <Button 
          variant="primary" 
          size="sm" 
          onClick={() => navigate('/admin/patients/create')}
          className="text-xs font-bold py-2.5 px-4 rounded-xl flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          New Patient
        </Button>
      </div>
    </div>
  );
}