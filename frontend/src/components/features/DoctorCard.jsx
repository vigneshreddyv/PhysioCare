import React from 'react';
import {
  CheckCircle2,
  Star,
  Clock3,
  Home,
  Video,
  BadgeCheck,
  Stethoscope,
  ArrowRight,
} from 'lucide-react';

export default function DoctorCard({
  doctor,
  selected = false,
  onClick,
}) {
  const avatarUrl =
    'https://lh3.googleusercontent.com/aida-public/AB6AXuDFn5Hei2SRFOwq8VfxOjEJ1rwnbl99DQdqSoIyafjmP98BmyxyVwwHz9lpRd2ndIJKltdXwOPRQ94BNRWN1aVR2P2H6iSxNak7fSL-3uAv9_at3PU8wH6uofYyuw_IlF00M1kbDdCvVEAqj_IUOOK0bCWyvS31V1rESgSBE6QboywWshpbbSg4ys1gtY-0bQsOa6xic8By3d1gRId_Abxh5agY429_-O8JNDjiSfDd67m10ZDpujiX';

  const experience =
    doctor.experience_years !== undefined
      ? `${doctor.experience_years}+ years`
      : null;

  const rating =
    doctor.rating !== undefined && doctor.rating !== null
      ? Number(doctor.rating).toFixed(1)
      : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className={`group w-full text-left rounded-[22px] border-2 p-5 transition-all duration-300 bg-white ${
        selected
          ? 'border-[#0b84a5] shadow-[0_16px_40px_rgba(11,132,165,0.15)] bg-[#f5fcff]'
          : 'border-[#e7edf3] shadow-[0_8px_28px_rgba(30,80,120,0.06)] hover:border-[#9bd8e8] hover:-translate-y-1 hover:shadow-[0_18px_40px_rgba(30,80,120,0.10)]'
      }`}
    >
      {/* Top section */}
      <div className="flex items-start gap-4">
        {/* Doctor avatar */}
        <div className="relative shrink-0">
          <img
            src={doctor.profile_image || avatarUrl}
            alt={doctor.full_name}
            className="w-[76px] h-[76px] rounded-[20px] object-cover border border-[#e2edf3] shadow-sm"
          />

          {doctor.is_active_today && (
            <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 border-[3px] border-white" />
          )}
        </div>

        {/* Doctor information */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-lg font-extrabold text-[#0a2540] truncate">
                  {doctor.full_name}
                </h3>

                <BadgeCheck
                  className="w-4 h-4 text-[#0b84a5] shrink-0"
                  fill="#e7f7fb"
                />
              </div>

              <p className="text-sm font-semibold text-[#0b84a5] mt-1">
                {doctor.specialization || 'Physiotherapy Specialist'}
              </p>
            </div>

            {selected && (
              <CheckCircle2
                className="w-6 h-6 text-[#0b84a5] shrink-0"
                fill="#e6f7fb"
              />
            )}
          </div>

          {/* Rating + experience */}
          <div className="flex flex-wrap items-center gap-3 mt-3">
            {rating && (
              <span className="inline-flex items-center gap-1 text-sm font-bold text-[#334e68]">
                <Star
                  className="w-4 h-4 text-amber-400"
                  fill="currentColor"
                />
                {rating}

                {doctor.total_reviews !== undefined && (
                  <span className="font-medium text-slate-400">
                    ({doctor.total_reviews})
                  </span>
                )}
              </span>
            )}

            {experience && (
              <span className="inline-flex items-center gap-1.5 text-sm text-slate-500">
                <Clock3 className="w-4 h-4" />
                {experience}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Bio */}
      {doctor.bio && (
        <p className="mt-4 text-sm text-slate-600 leading-6 line-clamp-2">
          {doctor.bio}
        </p>
      )}

      {/* Expertise */}
      {doctor.expertise?.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-400 mb-2">
            Expertise
          </p>

          <div className="flex flex-wrap gap-2">
            {doctor.expertise.slice(0, 4).map((item, index) => (
              <span
                key={`${item}-${index}`}
                className="px-2.5 py-1 rounded-full bg-[#eef8fb] text-[#0b7593] text-xs font-semibold"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Availability */}
      <div className="mt-5 pt-4 border-t border-[#edf1f5] flex flex-wrap items-center gap-2">
        {doctor.home_visit_available && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-bold">
            <Home className="w-3.5 h-3.5" />
            Home Visit
          </span>
        )}

        {doctor.online_consultation_available && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-bold">
            <Video className="w-3.5 h-3.5" />
            Online
          </span>
        )}

        {doctor.is_active_today && (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-cyan-50 text-cyan-700 text-xs font-bold">
            <Stethoscope className="w-3.5 h-3.5" />
            Available Today
          </span>
        )}
      </div>

      {/* Bottom action */}
      <div className="mt-5 flex items-center justify-between">
        <div>
          {doctor.consultation_fee !== undefined && (
            <>
              <p className="text-[11px] uppercase tracking-wide text-slate-400 font-bold">
                Consultation
              </p>

              <p className="text-lg font-extrabold text-[#0a2540]">
                ₹{doctor.consultation_fee}
              </p>
            </>
          )}
        </div>

        <span
          className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-extrabold transition-all ${
            selected
              ? 'bg-[#0b84a5] text-white'
              : 'bg-[#eaf7fd] text-[#0b84a5] group-hover:bg-[#0b84a5] group-hover:text-white'
          }`}
        >
          {selected ? 'Selected' : 'Select Doctor'}
          <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
        </span>
      </div>
    </button>
  );
}