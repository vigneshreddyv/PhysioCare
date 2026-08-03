import React from 'react';

export default function DoctorCard({ doctor, selected = false, onClick }) {
  const selectedClass = selected 
    ? 'border-primary shadow-[0px_6px_24px_rgba(0,123,167,0.1)]' 
    : 'border-transparent shadow-[0px_4px_20px_rgba(0,123,167,0.05)] hover:shadow-[0px_6px_24px_rgba(0,123,167,0.08)]';

  // Default avatar if no image URL is provided
  const avatarUrl = "https://lh3.googleusercontent.com/aida-public/AB6AXuDFn5Hei2SRFOwq8VfxOjEJ1rwnbl99DQdqSoIyafjmP98BmyxyVwwHz9lpRd2ndIJKltdXwOPRQ94BNRWN1aVR2P2H6iSxNak7fSL-3uAv9_at3PU8wH6uofYyuw_IlF00M1kbDdCvVEAqj_IUOOK0bCWyvS31V1rESgSBE6QboywWshpbbSg4ys1gtY-0bQsOa6xic8By3d1gRId_Abxh5agY429_-O8JNDjiSfDd67m10ZDpujiX";

  return (
    <div
      onClick={onClick}
      className={`bg-surface-container-lowest rounded-xl p-4 flex items-center gap-4 border-2 cursor-pointer transition-all duration-300 transform hover:-translate-y-0.5 ${selectedClass}`}
    >
      <img
        className="w-16 h-16 rounded-full object-cover shadow-sm shrink-0"
        alt={doctor.full_name}
        src={doctor.profile_image || avatarUrl}
      />
      <div className="flex-1 min-w-0">
        <h3 className="font-label-md text-label-md font-semibold text-on-surface truncate">{doctor.full_name}</h3>
        <p className="font-body-md text-body-md text-on-surface-variant text-sm truncate">{doctor.specialization}</p>
        {doctor.bio && (
          <p className="text-xs text-outline truncate mt-1">{doctor.bio}</p>
        )}
      </div>
      {selected && (
        <span className="material-symbols-outlined text-primary shrink-0 animate-scale" style={{ fontVariationSettings: "'FILL' 1" }}>
          check_circle
        </span>
      )}
    </div>
  );
}
