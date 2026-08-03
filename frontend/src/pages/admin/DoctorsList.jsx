import React from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function DoctorsList() {
  const { 
    data: doctors, 
    isLoading, 
    error, 
    refetch 
  } = useQuery({
    queryKey: ['doctors'],
    queryFn: async () => {
      const response = await api.get('/users/doctors');
      return response.data;
    }
  });

  if (error) {
    return <ErrorState message="Could not load medical staff records." onRetry={() => refetch()} />;
  }

  const defaultAvatar = "https://lh3.googleusercontent.com/aida-public/AB6AXuDFn5Hei2SRFOwq8VfxOjEJ1rwnbl99DQdqSoIyafjmP98BmyxyVwwHz9lpRd2ndIJKltdXwOPRQ94BNRWN1aVR2P2H6iSxNak7fSL-3uAv9_at3PU8wH6uofYyuw_IlF00M1kbDdCvVEAqj_IUOOK0bCWyvS31V1rESgSBE6QboywWshpbbSg4ys1gtY-0bQsOa6xic8By3d1gRId_Abxh5agY429_-O8JNDjiSfDd67m10ZDpujiX";

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Doctors</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Configure and manage clinical practitioner listings.</p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
          <h3 className="font-headline-md text-headline-md text-on-surface">Physiotherapy Staff</h3>
          <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
            {doctors ? doctors.length : 0} Doctors Active
          </span>
        </div>

        {isLoading ? (
          <div className="p-6 space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : !doctors || doctors.length === 0 ? (
          <div className="p-6">
            <EmptyState 
              title="No doctors added" 
              message="No medical specialists have been created in the database yet."
              icon="stethoscope"
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                  <th className="p-4">Physiotherapist</th>
                  <th className="p-4">Specialization</th>
                  <th className="p-4">Bio / Profile Details</th>
                  <th className="p-4">Status Today</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container">
                {doctors.map((doc) => (
                  <tr key={doc.id} className="hover:bg-surface-container-low transition-colors duration-150">
                    <td className="p-4 flex items-center gap-3">
                      <img
                        className="w-10 h-10 rounded-full object-cover shadow-sm shrink-0"
                        alt={doc.full_name}
                        src={doc.profile_image || defaultAvatar}
                      />
                      <div>
                        <span className="font-semibold text-on-surface block">{doc.full_name}</span>
                        <span className="text-xs text-outline block">{doc.email}</span>
                      </div>
                    </td>
                    <td className="p-4 text-on-surface-variant text-sm font-semibold">{doc.specialization}</td>
                    <td className="p-4 text-on-surface-variant text-sm max-w-xs truncate">{doc.bio || '—'}</td>
                    <td className="p-4">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                        doc.is_active_today 
                          ? 'bg-primary-container/20 text-primary' 
                          : 'bg-surface-variant text-on-surface-variant'
                      }`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {doc.is_active_today ? 'Available' : 'Off-duty'}
                      </span>
                    </td>
                    <td className="p-4 text-right">
                      <button className="text-primary hover:text-secondary text-sm font-semibold hover:underline mr-3">Schedule</button>
                      <button className="text-on-surface-variant hover:text-on-surface text-sm font-semibold hover:underline">Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
