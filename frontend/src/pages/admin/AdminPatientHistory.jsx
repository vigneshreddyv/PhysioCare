import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/common/Button';

export default function AdminPatientHistory() {
  const navigate = useNavigate();

  const handleGoBack = () => {
    navigate('/admin/patients');
  };

  return (
    <div className="space-y-stack-lg animate-fade-in">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Patient History</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">
          Patient-specific history is not connected in this frontend yet.
        </p>
      </div>

      <div className="bg-surface-container-lowest border border-surface-container rounded-xl shadow-sm">
        <div className="p-6">
          <p className="text-center text-on-surface-variant py-8">
            No patient history data is available on this route. Return without changing the record.
          </p>
          <div className="text-center">
            <Button variant="outline" onClick={handleGoBack}>
              Back to Patient Details
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
