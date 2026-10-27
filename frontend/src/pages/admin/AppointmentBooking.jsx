import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { DayPicker } from 'react-day-picker';
import { format, isAfter, isBefore, parseISO, startOfToday } from 'date-fns';
import api from '../../services/api';
import DoctorCard from '../../components/features/DoctorCard';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import { useAuth } from '../../context/useAuth';

export default function AdminAppointmentBooking() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isReceptionist = user?.role === 'receptionist';

  // Multi-step states
  const [selectedPatient, setSelectedPatient] = useState(null);
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
      const response = await api.get(isReceptionist ? '/users/reception/doctors' : '/users/doctors');
      return response.data;
    }
  });
  const { data: bookingWindow } = useQuery({
    queryKey: ['bookingWindow'],
    queryFn: async () => (await api.get('/appointments/booking-window')).data,
  });

  const selectedDateKey = selectedDate ? format(selectedDate, 'yyyy-MM-dd') : null;
  const {
    data: availability,
    isLoading: loadingAvailability,
    isError: availabilityError,
    refetch: refetchAvailability,
  } = useQuery({
    queryKey: ['appointmentAvailability', selectedDoctor?.id, selectedDateKey],
    enabled: Boolean(selectedDoctor && selectedDateKey),
    queryFn: async () => {
      const response = await api.get('/appointments/availability', {
        params: { doctor_id: selectedDoctor.id, appointment_date: selectedDateKey },
      });
      return response.data;
    },
  });

  const {
    data: patients,
    isLoading: loadingPatients,
    error: patientsError
  } = useQuery({
    queryKey: ['patients', user?.role],
    queryFn: async () => {
      const response = await api.get(isReceptionist ? '/users/reception/patients' : '/users/patients');
      return response.data;
    }
  });

  // Mutation to book appointment
  const bookMutation = useMutation({
    mutationFn: async (appointmentData) => {
      const response = await api.post(
        isReceptionist ? '/appointments/reception' : '/appointments/admin',
        appointmentData,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['receptionSchedule'] });
      queryClient.invalidateQueries({ queryKey: ['adminStats'] });
      queryClient.invalidateQueries({ queryKey: ['appointmentAvailability', selectedDoctor?.id, selectedDateKey] });
      setModalOpen(true);
    },
    onError: () => refetchAvailability(),
  });
  const bookingErrorDetail = bookMutation.error?.response?.data?.detail;
  const bookingErrorMessage = typeof bookingErrorDetail === 'string'
    ? bookingErrorDetail
    : bookingErrorDetail?.[0]?.msg || 'This appointment could not be created. Please review the details and try again.';

  const handleDoctorSelect = (doc) => {
    setSelectedTime('');
    setReason('');
    bookMutation.reset();
    setSelectedDoctor(doc);
    setStep(2);
  };

  const handleDateSelect = (date) => {
    if (date) {
      setSelectedTime('');
      setReason('');
      bookMutation.reset();
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
    if (!selectedPatient || !selectedDoctor || !selectedDate || !selectedTime || (!isReceptionist && !reason.trim())) return;

    const appointmentData = {
      patient_id: selectedPatient.id,
      doctor_id: selectedDoctor.id,
      appointment_date: format(selectedDate, 'yyyy-MM-dd'),
      time_slot: selectedTime,
    };
    if (!isReceptionist) appointmentData.reason = reason.trim();
    bookMutation.mutate(appointmentData);
  };

  const handleModalClose = () => {
    setModalOpen(false);
    navigate(isReceptionist ? '/reception/dashboard' : '/admin/dashboard');
  };

  if (doctorsError || patientsError) {
    return <ErrorState message="Could not load the patient and physiotherapist directories." />;
  }

  // Disable dates in the past
  const disabledDays = (date) => (
    isBefore(date, startOfToday())
    || (bookingWindow?.earliest_date && isBefore(date, parseISO(bookingWindow.earliest_date)))
    || (bookingWindow?.latest_date && isAfter(date, parseISO(bookingWindow.latest_date)))
  );

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
        <div className={`flex-1 h-[2px] mx-2 ${step >= 2 ? 'bg-primary' : 'bg-surface-variant'}`}></div>

        <div className="flex flex-col items-center gap-1">
          <div className={`w-8 h-8 rounded-flex flex items-center justify-center font-label-md text-label-md ${
            step >= 2 ? 'bg-primary text-on-primary font-bold' : 'bg-surface-variant text-on-surface-variant'
          }`}>2</div>
          <span className={`font-label-sm text-label-sm ${step >= 2 ? 'text-primary font-bold' : 'text-on-surface-variant'}`}>Date</span>
        </div>
        <div className={`flex-1 h-[2px] mx-2 ${step >= 3 ? 'bg-primary' : 'bg-surface-variant'}`}></div>

        <div className="flex flex-col items-center gap-1">
          <div className={`w-8 h-8 rounded-flex flex items-center justify-center font-label-md text-label-md ${
            step >= 4 ? 'bg-primary text-on-primary font-bold' : 'bg-surface-variant text-on-surface-variant'
          }`}>3</div>
          <span className={`font-label-sm text-label-sm ${step >= 4 ? 'text-primary font-bold' : 'text-on-surface-variant'}${
            step === 4 ? ' font-bold' : ''
          }`}>Details</span>
        </div>
      </div>

      <div className="text-center">
        <h1 className="font-headline-lg-mobile text-headline-lg-mobile md:font-headline-lg md:text-headline-lg mb-2">Book Appointment</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">Select an existing patient, specialist, and requested appointment time.</p>
      </div>

      <section className="flex flex-col gap-stack-md mt-4">
        <h2 className="font-headline-md text-headline-md">Patient</h2>
        <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="patient_id">Book for an existing patient</label>
        {loadingPatients ? (
          <Skeleton variant="row" count={1} />
        ) : (
          <select
            id="patient_id"
            value={selectedPatient?.id || ''}
            onChange={(event) => {
              const patient = patients?.find((item) => item.id === event.target.value) || null;
              setSelectedPatient(patient);
              setSelectedDoctor(null);
              setSelectedTime('');
              setReason('');
              setStep(1);
              bookMutation.reset();
            }}
            className="w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4"
            required
          >
            <option value="">Select patient</option>
            {patients?.map((patient) => (
              <option key={patient.id} value={patient.id}>{patient.full_name} · {patient.email}</option>
            ))}
          </select>
        )}
      </section>

      {/* STEP 1: Select Specialist */}
      {selectedPatient && <section className="flex flex-col gap-stack-md mt-4">
        <h2 className="font-headline-md text-headline-md">1. Select Specialist</h2>
        {loadingDoctors ? (
          <div className="space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-gutter">
            {Array.isArray(doctors) && doctors.map((doc) => (
              <DoctorCard
                key={doc.id}
                doctor={doc}
                selected={selectedDoctor?.id === doc.id}
                interactive
                onClick={() => handleDoctorSelect(doc)}
              />
            ))}
          </div>
        )}
      </section>}

      {/* STEP 2: Choose Date */}
      {step >= 2 && selectedDoctor && (
        <section className="flex flex-col gap-stack-md mt-4">
          <h2 className="font-headline-md text-headline-md">2. Choose Date</h2>
          <div className="bg-surface-container-lowest rounded-xl p-6 shadow-[0px_4px_20px_rgba(0,123,167,0.05)] border border-surface-container flex flex-col items-center">
            <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={handleDateSelect}
              startMonth={bookingWindow?.earliest_date ? parseISO(bookingWindow.earliest_date) : undefined}
              endMonth={bookingWindow?.latest_date ? parseISO(bookingWindow.latest_date) : undefined}
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
          <p className="text-sm text-on-surface-variant" role="note">{availability?.configuration_label || 'Availability has not loaded yet.'} All listed times use IST in 30-minute appointments.</p>
          {loadingAvailability ? (
            <Skeleton variant="row" count={3} />
          ) : availabilityError ? (
            <p className="patient-booking__submit-error" role="alert">
              Availability could not be loaded. <button type="button" onClick={() => refetchAvailability()} className="font-semibold underline">Try again</button>
            </p>
          ) : (
          <div className="grid grid-cols-3 gap-3">
            {availability?.slots?.map((slot) => {
              const isSelected = selectedTime === slot.time_slot;
              return (
                <button
                  key={slot.time_slot}
                  type="button"
                  onClick={() => handleTimeSelect(slot.time_slot)}
                  disabled={!slot.available || bookMutation.isPending}
                  className={`py-3 px-4 rounded-full border text-center font-label-md text-label-md transition-all duration-200 ${
                    isSelected
                      ? 'border-2 border-primary bg-primary-fixed text-on-primary-container font-semibold shadow-sm'
                      : slot.available
                        ? 'border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary hover:text-primary'
                        : 'border-outline-variant bg-surface-container text-on-surface-variant opacity-50 cursor-not-allowed'
                  }`}
                >
                  {slot.time_slot}{slot.availability_state === 'past' ? ' · Passed' : !slot.available ? ' · Occupied' : ''}
                </button>
              );
            })}
          </div>
          )}
        </section>
      )}

      {/* STEP 4: Reason for Visit */}
      {step >= 4 && selectedTime && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-stack-md mt-4">
          <h2 className="font-headline-md text-headline-md">4. {isReceptionist ? 'Confirm booking' : 'Reason for Visit'}</h2>
          {isReceptionist ? (
            <div className="portal-trust-note" role="note">
              <span className="material-symbols-outlined" aria-hidden="true">privacy_tip</span>
              <span>Reception does not collect or display clinical reasons. The patient can discuss clinical details directly with their physiotherapist.</span>
            </div>
          ) : <div className="flex flex-col gap-2">
            <label className="font-label-md text-label-md text-on-surface-variant" htmlFor="reason">
              Briefly describe the patient's symptoms or goal.
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
          </div>}

          {bookMutation.isError && (
            <p className="patient-booking__submit-error" role="alert">
              {bookingErrorMessage}
            </p>
          )}

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
            <h4 className="font-bold text-lg text-on-surface">Appointment scheduled successfully!</h4>
            <p className="text-sm text-on-surface-variant mt-1">The appointment has been added to the calendar.</p>
          </div>

          <div className="bg-surface-container-low rounded-xl p-4 text-left text-sm space-y-2 border border-surface-container">
            <div className="flex justify-between gap-3">
              <span className="font-semibold text-on-surface-variant">Patient:</span>
              <span className="font-bold text-on-surface text-right">{selectedPatient?.full_name}</span>
            </div>
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
