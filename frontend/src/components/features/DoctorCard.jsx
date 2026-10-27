import React from 'react';

export default function DoctorCard({ doctor, selected = false, onClick, interactive = false }) {
  const CardElement = interactive ? 'button' : 'div';
  const selectedClass = selected 
    ? 'border-primary shadow-[0px_6px_24px_rgba(0,123,167,0.1)]' 
    : 'border-transparent shadow-[0px_4px_20px_rgba(0,123,167,0.05)] hover:shadow-[0px_6px_24px_rgba(0,123,167,0.08)]';

  const initials = doctor.full_name
    ?.split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((name) => name[0])
    .join('')
    .toUpperCase() || 'PT';

  return (
    <CardElement
      type={interactive ? 'button' : undefined}
      aria-pressed={interactive ? selected : undefined}
      onClick={onClick}
      className={`bg-surface-container-lowest rounded-xl p-4 flex items-center gap-4 border-2 transition-all duration-300 ${selectedClass} ${interactive ? 'patient-booking__doctor w-full text-left cursor-pointer' : ''}`}
    >
      {doctor.profile_image ? (
        <img
          className="patient-doctor__avatar w-16 h-16 rounded-full object-cover shadow-sm shrink-0"
          alt=""
          src={doctor.profile_image}
        />
      ) : (
        <span className="patient-doctor__avatar patient-doctor__avatar--initials" aria-hidden="true">{initials}</span>
      )}
      <div className="flex-1 min-w-0">
        <h3 className="font-label-md text-label-md font-semibold text-on-surface truncate">{doctor.full_name}</h3>
        <p className="font-body-md text-body-md text-on-surface-variant text-sm truncate">{doctor.specialization}</p>
        {doctor.bio && (
          <p className="text-xs text-outline truncate mt-1">{doctor.bio}</p>
        )}
      </div>
      {selected && (
        <span className="material-symbols-outlined text-primary shrink-0 animate-scale" aria-hidden="true" style={{ fontVariationSettings: "'FILL' 1" }}>
          check_circle
        </span>
      )}
    </CardElement>
  );
}
