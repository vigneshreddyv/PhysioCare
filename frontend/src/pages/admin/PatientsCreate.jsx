import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';

export default function PatientsCreate() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    subscription_status: 'active'
  });
  const [modalOpen, setModalOpen] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const createPatient = useMutation({
    mutationFn: async (patientData) => {
      const response = await api.post('/users/patients', patientData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] });
      setModalOpen(true);
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    createPatient.mutate(formData);
  };

  const handleModalClose = () => {
    setModalOpen(false);
    navigate('/admin/patients');
  };

  return (
    <div className="space-y-stack-lg animate-fade-in pb-16">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg font-semibold text-on-surface tracking-tight">Register New Patient</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-1">Enter the patient's details to create a new record.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="full_name">
            Full Name
          </label>
          <input
            id="full_name"
            name="full_name"
            value={formData.full_name}
            onChange={handleChange}
            placeholder="Enter full name"
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
            required
          />
        </div>

        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="email">
            Email Address
          </label>
          <input
            id="email"
            name="email"
            type="email"
            value={formData.email}
            onChange={handleChange}
            placeholder="Enter email address"
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
            required
          />
        </div>

        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="phone">
            Phone Number
          </label>
          <input
            id="phone"
            name="phone"
            value={formData.phone}
            onChange={handleChange}
            placeholder="Enter phone number"
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
          />
        </div>

        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="date_of_birth">
            Date of Birth
          </label>
          <input
            id="date_of_birth"
            name="date_of_birth"
            type="date"
            value={formData.date_of_birth}
            onChange={handleChange}
            placeholder="Enter date of birth"
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
          />
        </div>

        <div>
          <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="subscription_status">
            Subscription Status
          </label>
          <select
            id="subscription_status"
            name="subscription_status"
            value={formData.subscription_status}
            onChange={handleChange}
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="pending">Pending</option>
          </select>
        </div>

        <Button
          type="submit"
          className="w-full mt-4 py-4"
          disabled={createPatient.isPending}
        >
          {createPatient.isPending ? 'Registering Patient...' : 'Register Patient'}
        </Button>
      </form>

      {/* Success Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        title="Patient Registered Successfully!"
      >
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-primary-container/20 text-primary flex items-center justify-center mx-auto">
            <span className="material-symbols-outlined" style={{ fontSize: '32px', fontVariationSettings: "'FILL' 1" }}>person_add</span>
          </div>
          <div>
            <h4 className="font-bold text-lg text-on-surface">New patient added!</h4>
            <p className="text-sm text-on-surface-variant mt-1">The patient has been successfully registered in the system.</p>
          </div>

          <Button variant="primary" onClick={handleModalClose} className="w-full">
            Done
          </Button>
        </div>
      </Modal>
    </div>
  );
}