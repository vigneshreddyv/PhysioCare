import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import EmptyState from '../../components/common/EmptyState';

export default function PatientsList() {
  const {
    data: patients,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['patients'],
    queryFn: async () => {
      const response = await api.get('/users/patients');
      return response.data;
    }
  });

  const navigate = useNavigate();

  if (error) {
    return <ErrorState message="Could not load patient records." onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Patients</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Manage and view active patient records.</p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm overflow-hidden">
        <div className="p-6 border-b border-surface-container flex justify-between items-center bg-surface-container-low/40">
          <h3 className="font-headline-md text-headline-md text-on-surface">Registered Records</h3>
          <span className="text-xs bg-primary/10 text-primary font-bold px-3 py-1 rounded-full">
            {patients ? patients.length : 0} Patients Total
          </span>
        </div>

        {() => {
          const isPatientsArray = Array.isArray(patients);
          const isNonEmptyPatientArray = isPatientsArray && patients.length > 0;
          if (isLoading) {
            return <Skeleton variant="row" count={3} />;
          }
          if (!isNonEmptyPatientArray) {
            return (
              <EmptyState
                title="No patients registered"
                message="Patient accounts will appear here once they register on the booking portal."
                icon="groups"
              />
            );
          }
          return (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-surface-container border-b border-surface-container text-on-surface-variant font-label-md text-label-md">
                    <th className="p-4">Name</th>
                    <th className="p-4">Email</th>
                    <th className="p-4">Phone</th>
                    <th className="p-4">Date of Birth</th>
                    <th className="p-4">Subscription</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container">
                  {patients.map((patient) => (
                    <tr key={patient.id} className="hover:bg-surface-container-low transition-colors duration-150">
                      <td className="p-4 flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary-container/20 text-primary flex items-center justify-center font-bold text-xs">
                          {patient.full_name.substring(0, 2).toUpperCase()}
                        </div>
                        <span className="font-semibold text-on-surface">{patient.full_name}</span>
                      </td>
                      <td className="p-4 text-on-surface-variant text-sm">{patient.email}</td>
                      <td className="p-4 text-on-surface-variant text-sm">{patient.phone || '—'}</td>
                      <td className="p-4 text-on-surface-variant text-sm">{patient.date_of_birth || '—'}</td>
                      <td className="p-4">
                        <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          patient.subscription_status === 'active'
                            ? 'bg-primary-container/20 text-primary'
                            : 'bg-error-container/20 text-error'
                        }`}>
                          {patient.subscription_status === 'active' ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-4 text-right">
                        <button
                          className="text-primary hover:text-secondary text-sm font-semibold hover:underline mr-3"
                          onClick={() => navigate(`/admin/patients-edit/${patient.id}`)}
                        >
                          Edit
                        </button>
                        <button
                          className="text-on-surface-variant hover:text-on-surface text-sm font-semibold hover:underline"
                          onClick={() => navigate(`/admin/patients-history/${patient.id}`)}
                        >
                          History
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}()
      </div>
    </div>
  );
}