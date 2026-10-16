import React from 'react';
import { format, parseISO } from 'date-fns';
import {
  Calendar,
  Clock,
  Stethoscope,
  FileText,
  CheckCircle2,
  XCircle,
  AlertCircle,
  PlayCircle,
} from 'lucide-react';

export default function AppointmentCard({ appointment, displayRole = 'admin', userRole, onStatusChange, onCancelClick, onRescheduleClick }) {
  const {
    id,
    patient_name,
    doctor_name,
    appointment_date,
    time_slot,
    reason,
    status,
    specialization
  } = appointment;

  // Format date (date-only) and use time_slot for time
  const dateObj = parseISO(appointment_date);
  const formattedDate = format(dateObj, 'EEEE, MMMM do, yyyy');

  // Support both prop formats to correctly identify patient perspective (fixing the patient action buttons visibility bug)
  const isPatientView = displayRole === 'patient' || userRole === 'patient';

  // Status colors, labels and Lucide icons
  const statusConfig = {
    pending_payment: {
      color: 'text-[#C9A86A]',
      label: 'Payment Pending',
      icon: AlertCircle,
      bgClass: 'bg-[#C9A86A]/10 border-[#C9A86A]/20'
    },
    confirmed: {
      color: 'text-[#1F4B45]',
      label: 'Confirmed',
      icon: CheckCircle2,
      bgClass: 'bg-[#EEF5F1] border-[#1F4B45]/20'
    },
    scheduled: {
      color: 'text-[#1F4B45]',
      label: 'Scheduled',
      icon: CheckCircle2,
      bgClass: 'bg-[#EEF5F1] border-[#1F4B45]/20'
    },
    in_progress: {
      color: 'text-[#1F4B45] font-bold',
      label: 'In Progress',
      icon: PlayCircle,
      bgClass: 'bg-[#EEF5F1] border-[#1F4B45]/30'
    },
    completed: {
      color: 'text-[#60716E]',
      label: 'Completed',
      icon: CheckCircle2,
      bgClass: 'bg-[#EEF5F1] border-[#E5E0D6]/50'
    },
    cancelled: {
      color: 'text-red-700',
      label: 'Cancelled',
      icon: XCircle,
      bgClass: 'bg-red-50 border-red-200/50'
    },
    no_show: {
      color: 'text-red-700',
      label: 'No Show',
      icon: XCircle,
      bgClass: 'bg-red-50 border-red-200/50'
    }
  };

  const statusInfo = statusConfig[status] || statusConfig.scheduled;
  const StatusIcon = statusInfo.icon;

  // Specialty mapping with colors
  const specialties = {
    'Physical Therapy': { color: '#1F4B45', bgClass: 'bg-[#1F4B45]' },
    'Sports Massage': { color: '#1F4B45', bgClass: 'bg-[#1F4B45]' },
    'Chiropractic': { color: '#C9A86A', bgClass: 'bg-[#C9A86A]' },
    'Acupuncture': { color: '#1E2A2B', bgClass: 'bg-[#1E2A2B]' },
    'Massage Therapy': { color: '#1F4B45', bgClass: 'bg-[#1F4B45]' }
  };

  const specialtyInfo = specialties[specialization] || {
    color: '#60716E',
    bgClass: 'bg-[#60716E]'
  };

  return (
    <div className="bg-white rounded-xl border border-[#E5E0D6] p-5 shadow-xs hover:shadow-md transition-all duration-300">
      
      {/* Header with info and status badge */}
      <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D6]/50">
        <div className="flex items-center gap-3.5">
          {/* Avatar with initials */}
          <div className="w-10 h-10 bg-[#EEF5F1]/45 rounded-full flex items-center justify-center shrink-0">
            <span className="text-[#1F4B45] font-bold text-sm">
              {isPatientView 
                ? (doctor_name?.split(' ').pop()?.[0] || 'D')
                : (patient_name?.split(' ').pop()?.[0] || 'P')}
            </span>
          </div>
          <div>
            {isPatientView ? (
              <>
                <p className="font-extrabold text-sm text-[#1E2A2B]">{doctor_name}</p>
                {specialization && (
                  <p className="text-xs text-[#60716E] mt-0.5">
                    {specialization}
                  </p>
                )}
              </>
            ) : (
              <p className="font-extrabold text-sm text-[#1E2A2B]">{patient_name}</p>
            )}
          </div>
        </div>

        {/* Status Badge */}
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold ${statusInfo.bgClass} ${statusInfo.color}`}>
          <StatusIcon className="w-3.5 h-3.5" />
          {statusInfo.label}
        </div>
      </div>

      {/* Appointment details */}
      <div className="py-4 space-y-3.5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-[#60716E]">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[#1F4B45] shrink-0" />
            <span>{formattedDate}</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#1F4B45] shrink-0" />
            <span>{time_slot}</span>
          </div>
          <div className="flex items-center gap-2">
            <Stethoscope className="w-4 h-4 text-[#1F4B45] shrink-0" />
            <span>{doctor_name}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${specialtyInfo.bgClass}`} />
            <span>{specialization || 'General Treatment'}</span>
          </div>
        </div>

        {/* Reason for visit */}
        {reason && (
          <div className="border-t border-[#E5E0D6]/30 pt-3">
            <p className="flex items-start gap-2 text-xs text-[#60716E] leading-relaxed">
              <FileText className="w-4 h-4 text-[#1F4B45] shrink-0 mt-0.5" />
              <span>{reason}</span>
            </p>
          </div>
        )}
      </div>

      {/* Action buttons (only for admin/doctor views) */}
      {!isPatientView && (
        <div className="border-t border-[#E5E0D6]/50 pt-4 space-y-2">
          {status === 'scheduled' && (
            <div className="space-y-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onStatusChange(id, 'in_progress');
                }}
                className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#1F4B45] hover:bg-[#1F4B45]/90 text-white rounded-xl text-xs font-bold transition duration-150 shadow-sm"
              >
                <Clock className="w-4 h-4" />
                Start Visit
              </button>
              <div className="flex gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(id, 'completed');
                  }}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#EEF5F1] hover:bg-[#EEF5F1]/80 border border-[#E5E0D6] text-[#1F4B45] rounded-xl text-xs font-bold transition duration-150"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Complete
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onStatusChange(id, 'cancelled');
                  }}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-red-50 hover:bg-red-100/50 border border-red-200 text-red-700 rounded-xl text-xs font-bold transition duration-150"
                >
                  <XCircle className="w-4 h-4" />
                  Cancel
                </button>
              </div>
            </div>
          )}
          {status !== 'scheduled' && status !== 'confirmed' && (
            <div className="text-center py-1 text-xs">
              {status === 'completed' && (
                <span className="text-[#1F4B45] font-bold flex items-center justify-center gap-1.5">
                  <CheckCircle2 className="w-4.5 h-4.5" />
                  Visit Completed
                </span>
              )}
              {status === 'cancelled' && (
                <span className="text-red-700 font-bold flex items-center justify-center gap-1.5">
                  <XCircle className="w-4.5 h-4.5" />
                  Appointment Cancelled
                </span>
              )}
            </div>
          )}
        </div>
      )}
      {isPatientView && (status === 'scheduled' || status === 'confirmed' || status === 'pending_payment' || status === 'in_progress') && (
        <div className="border-t border-[#E5E0D6]/50 pt-4 flex flex-col sm:flex-row gap-2">
          {status !== 'in_progress' && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onRescheduleClick?.(appointment);
              }}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-[#EEF5F1] hover:bg-[#EEF5F1]/80 border border-[#1F4B45]/20 text-[#1F4B45] rounded-xl text-xs font-bold transition duration-150 cursor-pointer"
              style={{ minHeight: '48px' }}
            >
              <Calendar className="w-4 h-4" />
              Reschedule Appointment
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onCancelClick?.(appointment);
            }}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-red-50 hover:bg-red-100/50 border border-red-200 text-red-700 rounded-xl text-xs font-bold transition duration-150 cursor-pointer"
            style={{ minHeight: '48px' }}
          >
            <XCircle className="w-4 h-4" />
            Cancel Appointment
          </button>
        </div>
      )}
    </div>
  );
}