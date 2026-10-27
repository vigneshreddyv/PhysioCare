import React, { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { DayPicker } from 'react-day-picker';
import { format, parseISO } from 'date-fns';
import api from '../../services/api';
import DoctorCard from '../../components/features/DoctorCard';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';
import { isOutsideBookingWindow } from '../../utils/clinicDate';

export default function BookAppointment() {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  // Multi-step states
  const [step, setStep] = useState(1); // 1: Specialist, 2: Date, 3: Time, 4: Reason
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState('');
  const [reason, setReason] = useState('');
  const [doctorQuery, setDoctorQuery] = useState('');
  const [handoffNotice, setHandoffNotice] = useState('');
  const [slotNotice, setSlotNotice] = useState('');
  const [confirmedAppointment, setConfirmedAppointment] = useState(null);
  
  // Confirmation modal state
  const [modalOpen, setModalOpen] = useState(false);

  // Fetch doctors
  const { 
    data: doctors, 
    isLoading: loadingDoctors, 
    error: doctorsError,
    refetch: refetchDoctors,
  } = useQuery({
    queryKey: ['bookingDoctors'],
    queryFn: async () => {
      const response = await api.get('/users/public/doctors');
      return response.data;
    }
  });
  const normalizedDoctorQuery = doctorQuery.trim().toLowerCase();
  const visibleDoctors = useMemo(() => (doctors || []).filter((doctor) => (
    [doctor.full_name, doctor.specialization, doctor.qualifications, ...(doctor.specialties || [])]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(normalizedDoctorQuery))
  )), [doctors, normalizedDoctorQuery]);

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
    data: bookingWindow,
    isLoading: loadingBookingWindow,
    isError: bookingWindowError,
    refetch: refetchBookingWindow,
  } = useQuery({
    queryKey: ['bookingWindow'],
    queryFn: async () => (await api.get('/appointments/booking-window')).data,
  });

  // Mutation to book appointment
  const bookMutation = useMutation({
    mutationFn: async (appointmentData) => {
      const response = await api.post('/appointments', appointmentData);
      return response.data;
    },
    onSuccess: (appointment) => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['patientAppointments'] });
      queryClient.invalidateQueries({ queryKey: ['patientHistory'] });
      queryClient.invalidateQueries({ queryKey: ['appointmentAvailability', selectedDoctor?.id, selectedDateKey] });
      setConfirmedAppointment(appointment);
      setModalOpen(true);
    },
    onError: () => {
      refetchAvailability();
    },
  });

  const handleDoctorSelect = (doc) => {
    if (selectedDoctor?.id !== doc.id) {
      setSelectedDate(null);
      setSelectedTime('');
      setReason('');
      setSlotNotice('');
      bookMutation.reset();
    }
    setSelectedDoctor(doc);
    setStep(2);
  };

  const requestedDoctorId = location.state?.bookingPreference?.doctorId;

  useEffect(() => {
    if (!requestedDoctorId || !doctors) return;

    const requestedDoctor = doctors.find((doctor) => doctor.id === requestedDoctorId);
    if (requestedDoctor) {
      setSelectedDoctor(requestedDoctor);
      setStep(2);
      setHandoffNotice(`${requestedDoctor.full_name} is selected from the public clinician profile. Choose a date to continue.`);
    } else {
      setHandoffNotice('The physiotherapist you viewed is not currently listed for booking. Choose another specialist below.');
    }

    // The preference is public directory context, not a persistent booking draft.
    navigate(location.pathname, { replace: true, state: null });
  }, [doctors, location.pathname, navigate, requestedDoctorId]);

  useEffect(() => {
    if (!selectedTime || !availability?.slots) return;

    const currentSlot = availability.slots.find((slot) => slot.time_slot === selectedTime);
    if (!currentSlot?.available) {
      setSelectedTime('');
      setReason('');
      setStep(3);
      setSlotNotice('That time is no longer available. Your specialist and date are still selected—please choose another listed time.');
    }
  }, [availability, selectedTime]);

  const handleDateSelect = (date) => {
    if (date) {
      if (!selectedDate || date.toDateString() !== selectedDate.toDateString()) {
        setSelectedTime('');
        setReason('');
        setSlotNotice('');
        bookMutation.reset();
      }
      setSelectedDate(date);
      setStep(3);
    }
  };

  const handleTimeSelect = (time) => {
    if (time !== selectedTime) bookMutation.reset();
    setSlotNotice('');
    setSelectedTime(time);
    setStep(4);
  };

  const handleStartOver = () => {
    setSelectedDoctor(null);
    setSelectedDate(null);
    setSelectedTime('');
    setReason('');
    setDoctorQuery('');
    setHandoffNotice('');
    setSlotNotice('');
    setConfirmedAppointment(null);
    setStep(1);
    bookMutation.reset();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!selectedDoctor || !selectedDate || !selectedTime || !reason.trim()) return;

    bookMutation.mutate({
      doctor_id: selectedDoctor.id,
      appointment_date: format(selectedDate, 'yyyy-MM-dd'),
      time_slot: selectedTime,
      reason: reason.trim()
    });
  };

  const handleModalClose = () => {
    setModalOpen(false);
    navigate('/patient/dashboard');
  };

  if (doctorsError || bookingWindowError) {
    return (
      <div className="patient-page patient-booking__error">
        <ErrorState message="Could not load appointment booking." onRetry={() => { refetchDoctors(); refetchBookingWindow(); }} />
      </div>
    );
  }

  const bookingErrorDetail = bookMutation.error?.response?.data?.detail;
  const bookingErrorMessage = typeof bookingErrorDetail === 'string'
    ? bookingErrorDetail
    : bookingErrorDetail?.[0]?.msg || 'Your draft is still here. Check your connection and try again.';

  const progressSteps = [
    { number: 1, label: 'Specialist', available: true },
    { number: 2, label: 'Date', available: Boolean(selectedDoctor) },
    { number: 3, label: 'Time', available: Boolean(selectedDate) },
    { number: 4, label: 'Details', available: Boolean(selectedTime) },
  ];
  const appointmentSlots = availability?.slots || [];
  const availableSlotCount = appointmentSlots.filter((slot) => slot.available).length;
  const hasUnavailableSlots = appointmentSlots.some((slot) => !slot.available);

  const disabledDays = (date) => isOutsideBookingWindow(date, bookingWindow);

  return (
    <div className="patient-page patient-booking patient-booking--focused flex flex-col gap-stack-lg max-w-5xl mx-auto animate-fade-in pb-16">
      
      {/* Stepper Progress bar */}
      <ol className="patient-booking__stepper" aria-label="Booking progress" data-patient-reveal>
        {progressSteps.map((progressStep) => (
          <li key={progressStep.number} className={step >= progressStep.number ? 'is-complete' : ''}>
            <button
              type="button"
              disabled={!progressStep.available || bookMutation.isPending}
              aria-current={step === progressStep.number ? 'step' : undefined}
              onClick={() => setStep(progressStep.number)}
            >
              <span>{progressStep.number}</span>
              {progressStep.label}
            </button>
          </li>
        ))}
      </ol>

      <div className="patient-page__header patient-booking__header" data-patient-reveal>
        <div className="patient-page__header-copy">
          <p className="patient-page__eyebrow">Clinic appointment</p>
          <h1 className="patient-page__title">Book an appointment</h1>
          <p className="patient-page__description">Choose your specialist, date, and an available IST time. Review everything before you confirm.</p>
          <ul className="patient-booking__assurances" aria-label="Booking information">
            <li><span className="material-symbols-outlined" aria-hidden="true">schedule</span>India Standard Time</li>
            <li><span className="material-symbols-outlined" aria-hidden="true">payments</span>No payment taken</li>
            <li><span className="material-symbols-outlined" aria-hidden="true">edit_note</span>Edit before confirming</li>
          </ul>
        </div>
      </div>

      {handoffNotice && (
        <div className="patient-booking__handoff" role="status" aria-live="polite">
          <span className="material-symbols-outlined" aria-hidden="true">person_check</span>
          <span>{handoffNotice}</span>
        </div>
      )}

      <div className={`patient-booking__toolbar${step === 1 ? ' is-initial' : ''}`} aria-label="Booking draft actions">
        <button type="button" onClick={() => setStep(Math.max(1, step - 1))} disabled={step === 1 || bookMutation.isPending}>
          <span className="material-symbols-outlined" aria-hidden="true">arrow_back</span>
          Back
        </button>
        <button type="button" onClick={handleStartOver} disabled={step === 1 || bookMutation.isPending}>
          Clear draft
        </button>
      </div>

      <div className="patient-booking__workspace">
        <div className="patient-booking__flow">

      {/* STEP 1: Select Specialist */}
      {step === 1 && (
      <section className="flex flex-col gap-stack-md" data-patient-reveal>
        <div className="patient-booking__section-heading">
          <div>
            <p>Step 1 of 4</p>
            <h2 className="patient-booking__section-title">Select a specialist</h2>
          </div>
          <span>Choose who you would like to see.</span>
        </div>
        {loadingDoctors ? (
          <div className="space-y-4">
            <Skeleton variant="row" count={2} />
          </div>
        ) : doctors?.length ? (
          <>
          <div className="patient-booking__clinician-finder">
            <label htmlFor="booking-clinician-search">
              <span className="material-symbols-outlined" aria-hidden="true">search</span>
              <span className="sr-only">Search booking clinicians</span>
              <input
                id="booking-clinician-search"
                type="search"
                value={doctorQuery}
                onChange={(event) => setDoctorQuery(event.target.value)}
                placeholder="Search by name, specialty, or focus area"
                aria-controls="booking-clinician-results"
              />
            </label>
            <span role="status" aria-live="polite">{visibleDoctors.length} shown</span>
          </div>
          {visibleDoctors.length > 0 ? (
          <div id="booking-clinician-results" className="grid grid-cols-1 gap-gutter">
            {visibleDoctors.map((doc) => (
              <DoctorCard
                key={doc.id}
                doctor={doc}
                selected={selectedDoctor?.id === doc.id}
                interactive
                onClick={() => handleDoctorSelect(doc)}
              />
            ))}
          </div>
          ) : (
            <div id="booking-clinician-results" className="patient-booking__empty-doctors" role="status">
              <span className="material-symbols-outlined" aria-hidden="true">search_off</span>
              <div>
                <strong>No specialists match “{doctorQuery.trim()}”.</strong>
                <span>Try another name, specialty, or focus area.</span>
                <button type="button" onClick={() => setDoctorQuery('')}>Clear search</button>
              </div>
            </div>
          )}
          </>
        ) : (
          <div className="patient-booking__empty-doctors" role="status">
            <span className="material-symbols-outlined" aria-hidden="true">event_busy</span>
            <div>
              <strong>No specialists are available to book right now.</strong>
              <span>Please check again later. No appointment request has been sent.</span>
            </div>
          </div>
        )}
      </section>
      )}

      {/* STEP 2: Choose Date */}
      {step === 2 && selectedDoctor && (
        <section className="flex flex-col gap-stack-md" data-patient-reveal>
          <div className="patient-booking__section-heading">
            <div>
              <p>Step 2 of 4</p>
              <h2 className="patient-booking__section-title">Choose a date</h2>
            </div>
            <span>Book from today up to {bookingWindow?.horizon_days || 30} days ahead.</span>
          </div>
          <div className="patient-booking__calendar bg-surface-container-lowest rounded-xl p-6 shadow-[0px_4px_20px_rgba(0,123,167,0.05)] border border-surface-container flex flex-col items-center">
            {loadingBookingWindow ? <Skeleton variant="row" count={2} /> : <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={handleDateSelect}
              startMonth={parseISO(bookingWindow.earliest_date)}
              endMonth={parseISO(bookingWindow.latest_date)}
              disabled={disabledDays}
            />}
            {selectedDate && (
              <div className="patient-booking__selected-date" role="status" aria-live="polite">
                <span className="material-symbols-outlined" aria-hidden="true">event_available</span>
                <span><small>Selected date</small><strong>{format(selectedDate, 'PPPP')}</strong></span>
              </div>
            )}
          </div>
        </section>
      )}

      {/* STEP 3: Select Time Slots */}
      {step === 3 && selectedDate && (
        <section className="flex flex-col gap-stack-md" data-patient-reveal>
          <div className="patient-booking__section-heading">
            <div>
              <p>Step 3 of 4</p>
              <h2 className="patient-booking__section-title">Select a time</h2>
            </div>
            {!loadingAvailability && !availabilityError && <span>{availableSlotCount} available</span>}
          </div>
          <div className="patient-booking__schedule-note" role="note">
            <span className="material-symbols-outlined" aria-hidden="true">schedule</span>
            <span><strong>{availability?.demo_configuration ? 'Demo schedule' : 'Published clinician schedule'}</strong>{availability?.configuration_label || 'Availability has not loaded yet.'} All listed times use India Standard Time in 30-minute appointments.</span>
          </div>
          {slotNotice && (
            <div className="patient-booking__slot-notice" role="status" aria-live="assertive">
              <span className="material-symbols-outlined" aria-hidden="true">update</span>
              {slotNotice}
            </div>
          )}
          {loadingAvailability ? (
            <Skeleton variant="row" count={3} />
          ) : availabilityError ? (
            <div className="patient-booking__submit-error" role="alert">
              <span>Availability could not be loaded.</span>
              <button type="button" onClick={() => refetchAvailability()} className="font-semibold underline">Try again</button>
            </div>
          ) : appointmentSlots.length > 0 ? (
          <>
          <div className="patient-booking__time-slots grid grid-cols-3 gap-3">
            {appointmentSlots.map((slot) => {
              const isSelected = selectedTime === slot.time_slot;
              const slotState = slot.availability_state === 'past' ? 'Passed' : !slot.available ? 'Occupied' : 'Available';
              return (
                <button
                  key={slot.time_slot}
                  type="button"
                  onClick={() => handleTimeSelect(slot.time_slot)}
                  aria-pressed={isSelected}
                  aria-describedby={!slot.available ? 'booking-unavailable-help' : undefined}
                  disabled={!slot.available || bookMutation.isPending}
                  className={`patient-booking__time-slot py-3 px-4 rounded-full border text-center font-label-md text-label-md transition-all duration-200 ${
                    isSelected 
                      ? 'border-2 border-primary bg-primary-fixed text-on-primary-container font-semibold shadow-sm'
                      : slot.available
                        ? 'border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary hover:text-primary'
                        : 'border-outline-variant bg-surface-container text-on-surface-variant opacity-50 cursor-not-allowed'
                  }`}
                >
                  <strong>{slot.time_slot}</strong>
                  <span>{isSelected ? 'Selected' : slotState}</span>
                </button>
              );
            })}
          </div>
          {hasUnavailableSlots && (
            <p id="booking-unavailable-help" className="patient-booking__availability-help">
              <span className="material-symbols-outlined" aria-hidden="true">info</span>
              Unavailable times are already booked or have passed.
            </p>
          )}
          </>
          ) : (
            <div className="patient-booking__empty-slots" role="status">
              <span className="material-symbols-outlined" aria-hidden="true">event_busy</span>
              <div><strong>No times are available for this date.</strong><span>Go back and choose another date. Your specialist selection is saved.</span></div>
            </div>
          )}
        </section>
      )}

      {/* STEP 4: Reason for Visit */}
      {step === 4 && selectedTime && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-stack-md" data-patient-reveal aria-busy={bookMutation.isPending}>
          <div className="patient-booking__section-heading">
            <div>
              <p>Step 4 of 4</p>
              <h2 className="patient-booking__section-title">Add visit details</h2>
            </div>
            <span>Review your selection, then confirm.</span>
          </div>
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
              maxLength={500}
              aria-describedby="reason-help"
              className="patient-booking__reason w-full rounded-xl border border-outline-variant bg-surface-container-lowest p-4 font-body-md text-body-md focus:border-primary focus:ring-1 focus:ring-primary transition-colors placeholder-on-surface-variant/50"
              required
            />
          </div>

          <div id="reason-help" className="patient-booking__reason-help">
            <span>Share only what the specialist needs to prepare for this visit.</span>
            <span>{reason.length}/500</span>
          </div>

          {bookMutation.isError && (
            <div className="patient-booking__submit-error" role="alert">
              <span className="material-symbols-outlined" aria-hidden="true">error</span>
              <div>
                <strong>Booking was not confirmed.</strong>
                <span>{bookingErrorMessage}</span>
              </div>
            </div>
          )}

          <Button
            variant="patientPrimary"
            type="submit"
            className="w-full mt-4 py-4"
            disabled={bookMutation.isPending}
          >
            {bookMutation.isPending ? 'Confirming booking…' : 'Confirm booking'}
          </Button>
        </form>
      )}
        </div>

        <aside className={`patient-booking__summary${step === 1 ? ' is-empty' : ''}${step === 4 ? ' is-review' : ''}`} aria-labelledby="booking-summary-heading">
          <p className="patient-page__eyebrow">Your selection</p>
          <h2 id="booking-summary-heading">Appointment summary</h2>
          {selectedDoctor && (
            <div className="patient-booking__summary-clinician">
              {selectedDoctor.profile_image ? (
                <img src={selectedDoctor.profile_image} alt="" referrerPolicy="no-referrer" />
              ) : (
                <span aria-hidden="true">{selectedDoctor.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</span>
              )}
              <div><small>Selected clinician</small><strong>{selectedDoctor.full_name}</strong><span>{selectedDoctor.specialization}</span></div>
            </div>
          )}
          <dl>
            <div>
              <dt>Specialist</dt>
              <dd>{selectedDoctor ? selectedDoctor.full_name : 'Not selected'}</dd>
            </div>
            <div>
              <dt>Date</dt>
              <dd>{selectedDate ? format(selectedDate, 'EEE, MMM d, yyyy') : 'Not selected'}</dd>
            </div>
            <div>
              <dt>Time</dt>
              <dd>{selectedTime ? `${selectedTime} IST` : 'Not selected'}</dd>
            </div>
          </dl>
          <p className="patient-booking__summary-note">
            <span className="material-symbols-outlined" aria-hidden="true">lock</span>
            Times use India Standard Time. Nothing is sent until you select “Confirm booking.”
          </p>
        </aside>
      </div>

      {/* Booking confirmation Success Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={handleModalClose}
        title="Booking Confirmed!"
        panelClassName="patient-booking-confirmation"
      >
        <div className="text-center space-y-4">
          <div className="patient-booking-success__icon w-16 h-16 rounded-full bg-primary-container/20 text-primary flex items-center justify-center mx-auto" aria-hidden="true">
            <span className="material-symbols-outlined" style={{ fontSize: '32px', fontVariationSettings: "'FILL' 1" }}>check_circle</span>
          </div>
          <div>
            <h4 className="patient-booking-confirmation__message font-bold text-lg text-on-surface">Your clinic appointment is scheduled.</h4>
            <p className="patient-booking-confirmation__description text-sm text-on-surface-variant mt-1">It now appears in your upcoming appointments. No payment was taken in this app.</p>
          </div>
          
          <div className="patient-booking-confirmation__details bg-surface-container-low rounded-xl p-4 text-left text-sm space-y-2 border border-surface-container">
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Specialist:</span>
              <span className="font-bold text-on-surface">{confirmedAppointment?.doctor_name || selectedDoctor?.full_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Date:</span>
              <span className="font-bold text-on-surface">{confirmedAppointment?.appointment_date ? format(parseISO(confirmedAppointment.appointment_date), 'MMMM dd, yyyy') : selectedDate && format(selectedDate, 'MMMM dd, yyyy')}</span>
            </div>
            <div className="flex justify-between">
              <span className="font-semibold text-on-surface-variant">Time:</span>
              <span className="font-bold text-on-surface">{confirmedAppointment?.time_slot || selectedTime} IST</span>
            </div>
          </div>

          <Button variant="patientPrimary" onClick={handleModalClose} className="patient-booking-confirmation__done w-full">
            View upcoming appointment
          </Button>
        </div>
      </Modal>

    </div>
  );
}
