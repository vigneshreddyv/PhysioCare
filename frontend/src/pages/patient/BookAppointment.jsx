import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { DayPicker } from 'react-day-picker';
import { format, isBefore, startOfToday } from 'date-fns';
import api from '../../services/api';
import DoctorCard from '../../components/features/DoctorCard';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';

export default function BookAppointment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Multi-step states
  const [step, setStep] = useState(1); // 1: Specialist, 2: Date, 3: Time, 4: Reason
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedTime, setSelectedTime] = useState('');
  const [reason, setReason] = useState('');
  
  // Confirmation modal state
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch doctors
  const { 
    data: doctors, 
    isLoading: loadingDoctors, 
    error: doctorsError 
  } = useQuery({
    queryKey: ['bookingDoctors'],
    queryFn: async () => {
      const response = await api.get('/users/doctors');
      return response.data;
    }
  });

  // Mutation to book appointment
  const bookMutation = useMutation({
    mutationFn: async (appointmentData) => {
      const response = await api.post('/appointments/', appointmentData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      setModalOpen(true);
    }
  });

  const handleDoctorSelect = (doc) => {
    setSelectedDoctor(doc);
    setStep(2);
  };

  const handleDateSelect = (date) => {
    if (date) {
      setSelectedDate(date);
      setStep(3);
    }
  };

  const handleTimeSelect = (time) => {
    setSelectedTime(time);
    setStep(4);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!selectedDoctor || !selectedDate || !selectedTime || !reason.trim()) return;

    bookMutation.mutate({
      doctor_id: selectedDoctor.id,
      appointment_date: selectedDate.toISOString(),
      time_slot: selectedTime,
      reason: reason.trim()
    });
  };

  const handleModalClose = () => {
    setModalOpen(false);
    navigate('/patient/dashboard');
  };

  if (doctorsError) {
    return <ErrorState message="Could not load physiotherapist staff." />;
  }

  // Predefined time slots matching Stitch designs
  const timeSlots = [
    '09:00 AM',
    '10:30 AM',
    '11:00 AM',
    '01:00 PM',
    '02:30 PM',
    '04:00 PM'
  ];

  // Disable dates in the past
  const disabledDays = (date) => isBefore(date, startOfToday());

  return (
    <div className="flex flex-col gap-stack-lg max-w-xl mx-auto animate-fade-in pb-16">
      
      {/* Stepper Progress bar */}
      <div className="flex items-center justify-between w-full max-w-sm mx-auto mb-6">
        <div className="flex flex-col items-center gap-1">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-label-md text-label-md ${
            step >= 1 ? 'bg-primary text-on-primary font-bold' : 'bg-surface-variant text-on-surface-variant'
          }`}>1</div>
          <span className={`font-label-sm text-label-sm ${step >= 1 ? 'text-primary font-bold' : 'text-on-surface-variant'}`}>Specialist</span>
        </div>
        <div className={`flex-1 h-[2px] mx-2 ${step >= 2 ? 'bg-primary' : 'bg-primary-fixed'}`}></div>
        
        <div className="flex flex-col items-center gap-1">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-label-md text-label-md ${
            step >= 2 ? 'bg-primary text-on-primary font-bold' : 'bg-surface-variant text-on-surface-variant'
          }`}>2</div>
          <span className={`font-label-sm text-label-sm ${step >= 2 ? 'text-primary font-bold' : 'text-on-surface-variant'}`}>Date</span>
        </div>
        <div className={`flex-1 h-[2px] mx-2 ${step >= 3 ? 'bg-primary' : 'bg-surface-variant'}`}></div>

        <div className="flex flex-col items-center gap-1">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-label-md text-label-md ${
            step >= 4 ? 'bg-primary text-on-primary font-bold' : 'bg-surface-variant text-on-surface-variant'
          }`}>3</div>
          <span className={`font-label-sm text-label-sm ${step >= 4 ? 'text-primary font-bold' : 'text-on-surface-variant'}`}>Details</span>
        </div>
      </div>

      <div className="text-center">
        <h1 className="font-headline-lg-mobile text-headline-lg-mobile md:font-headline-lg md:text-headline-lg mb-2">Book your appointment</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">Select a specialist and time that works for you.</p>
      </div>

      {/* STEP 1: Select Specialist */}
      <section className="flex flex-col gap-stack-md mt-4">
        <h2 className="font-headline-md text-headline-md">1. Select Specialist</h2>
        {loadingDoctors ? (
          <div className="space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-gutter">
            {doctors?.map((doc) => (
              <DoctorCard
                key={doc.id}
                doctor={doc}
                selected={selectedDoctor?.id === doc.id}
                onClick={() => handleDoctorSelect(doc)}
              />
            ))}
          </div>
        )}
      </section>

      {/* STEP 2: Choose Date */}
      {step >= 2 && selectedDoctor && (
        <section className="flex flex-col gap-stack-md mt-4">
          <h2 className="font-headline-md text-headline-md">2. Choose Date</h2>
          <div className="bg-surface-container-lowest rounded-xl p-6 shadow-[0px_4px_20px_rgba(0,123,167,0.05)] border border-surface-container flex flex-col items-center">
            <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={handleDateSelect}
              disabled={disabledDays}
            />
            {selectedDate && (
              <p className="text-sm font-semibold text-primary mt-4">
                Selected Date: {format(selectedDate, 'PPPP')}
              </p>
            )}
          </div>
        </section>
      )}

      {/* STEP 3: Select Time Slots */}
      {step >= 3 && selectedDate && (
        <section className="flex flex-col gap-stack-md mt-4">
          <h2 className="font-headline-md text-headline-md">3. Select Time</h2>
          <div className="grid grid-cols-3 gap-3">
            {timeSlots.map((time) => {
              const isSelected = selectedTime === time;
              return (
                <button
                  key={time}
                  type="button"
                  onClick={() => handleTimeSelect(time)}
                  className={`py-3 px-4 rounded-full border text-center font-label-md text-label-md transition-all duration-200 ${
                    isSelected 
                      ? 'border-2 border-primary bg-primary-fixed text-on-primary-container font-semibold shadow-sm'
                      : 'border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary hover:text-primary'
                  }`}
                >
                  {time}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* STEP 4: Reason for Visit */}
      {step >= 4 && selectedTime && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-stack-md mt-4">
          <h2 className="font-headline-md text-headline-md">4. Reason for Visit</h2>
          <div className="flex flex-col gap-2">
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="reason">
              Briefly describe your symptoms or goal.
            </label>
            <textarea
              id="reason"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="E.g., lower back pain during running..."
              className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full mt-4 py-4"
            disabled={bookMutation.isPending}
          >
            {bookMutation.isPending ? 'Confirming Booking...' : 'Confirm Booking'}
          </Button>
        </form>
      )}

      {/* Booking confirmation Success Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        title="Booking Confirmed!"
      >
        <div className="text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-primary-container/20 text-primary flex items-center justify-center mx-auto">
            <span className="material-symbols-outlined" style={{ fontSize: '32px', fontVariationSettings: "'FILL' 1" }}>check_circle</span>
          </div>
          <div>
            <h4 className="font-bold text-lg text-on-surface">Your visit is scheduled!</h4>
            <p className="text-sm text-on-surface-variant mt-1">We look forward to helping you feel your best.</p>
          </div>
          
          <div className="bg-surface-container-low rounded-xl p-4 text-left text-sm space-y-2 border border-surface-container">
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Specialist:</span>
              <span className="font-bold text-on-surface">{selectedDoctor?.full_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Date:</span>
              <span className="font-bold text-on-surface">{selectedDate && format(selectedDate, 'MMMM dd, yyyy')}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Time:</span>
              <span className="font-bold text-on-surface">{selectedTime}</span>
            </div>
          </div>

          <Button variant="primary" onClick={handleModalClose} className="w-full">
            Done
          </Button>
        </div>
      </Modal>

    </div>
  );
}
