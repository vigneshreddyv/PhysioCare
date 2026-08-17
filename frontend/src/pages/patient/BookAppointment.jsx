import { physioProblems } from '../../data/physioProblems';
import { physioSymptoms } from '../../data/physioSymptoms';
import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { DayPicker } from 'react-day-picker';
import { format, isBefore, startOfToday } from 'date-fns';
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  Check,
  Clock3,
  Home,
  Laptop,
  MapPin,
  Microscope,
  Stethoscope,
  ClipboardList,
  Activity,
  Dumbbell,
  CreditCard,
  Banknote,
  ShieldCheck,
  HeartPulse,
} from 'lucide-react';

import api from '../../services/api';
import DoctorCard from '../../components/features/DoctorCard';
import Button from '../../components/common/Button';
import Modal from '../../components/common/Modal';
import Skeleton from '../../components/common/Skeleton';
import ErrorState from '../../components/common/ErrorState';

const services = [
  {
    id: 'clinic',
    title: 'Clinic Consultation',
    description: 'Visit our clinic and receive professional physiotherapy care.',
    icon: Stethoscope,
  },
  {
    id: 'home_visit',
    title: 'Home Visit',
    description: 'Get personalized physiotherapy treatment at your home.',
    icon: Home,
  },
  {
    id: 'online',
    title: 'Online Consultation',
    description: 'Consult with a physiotherapist from anywhere.',
    icon: Laptop,
  },
  {
    id: 'physiotherapy',
    title: 'Physiotherapy Treatment',
    description: 'Personalized treatment for pain, mobility and recovery.',
    icon: HeartPulse,
  },
  {
    id: 'laboratory',
    title: 'Laboratory Tests',
    description: 'Book and manage your recommended laboratory tests.',
    icon: Microscope,
  },
  {
    id: 'care_plan',
    title: 'Personalized Care Plans',
    description: 'Structured care plans designed around your recovery.',
    icon: ClipboardList,
  },
  {
    id: 'exercise_plan',
    title: 'Exercise & Recovery Plans',
    description: 'Guided exercises and recovery plans for better mobility.',
    icon: Dumbbell,
  },
];

const timeSlots = [
  '09:00 AM',
  '10:30 AM',
  '11:00 AM',
  '01:00 PM',
  '02:30 PM',
  '04:00 PM',
];

const painLevels = [
  {
    value: 'low',
    label: 'Low',
    description: 'Mild discomfort',
  },
  {
    value: 'medium',
    label: 'Medium',
    description: 'Noticeable pain',
  },
  {
    value: 'high',
    label: 'High',
    description: 'Severe pain',
  },
];

export default function BookAppointment() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [step, setStep] = useState(1);

  const [selectedService, setSelectedService] = useState(null);
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [selectedBodyArea, setSelectedBodyArea] = useState('');
  const [selectedProblem, setSelectedProblem] = useState('');
  const [customProblem, setCustomProblem] = useState('');
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedTime, setSelectedTime] = useState('');

  const [reason, setReason] = useState('');
  const [selectedSymptoms, setSelectedSymptoms] = useState([]);
  const [customSymptoms, setCustomSymptoms] = useState('');
  const [durationDays, setDurationDays] = useState('');
  const [painLevel, setPainLevel] = useState('');
  const [visitAddress, setVisitAddress] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('offline');
  const [locationStatus, setLocationStatus] = useState('idle');
  const [locationError, setLocationError] = useState('');
  const [coordinates, setCoordinates] = useState(null);

  const [addressDetails, setAddressDetails] = useState({
    buildingName: '',
    doorNumber: '',
    area: '',
    street: '',
    landmark: '',
    pincode: '',
  });
  useEffect(() => {
  const loadSavedAddress = async () => {
    try {
      const response = await api.get('/users/me/address');

      const savedAddress = response.data;

      if (!savedAddress) {
        return;
      }

      setAddressDetails({
        buildingName: savedAddress.building_name || '',
        doorNumber: savedAddress.door_number || '',
        area: savedAddress.area || '',
        street: savedAddress.street || '',
        landmark: savedAddress.landmark || '',
        pincode: savedAddress.pincode || '',
      });

      if (savedAddress.latitude && savedAddress.longitude) {
        setCoordinates({
          latitude: savedAddress.latitude,
          longitude: savedAddress.longitude,
        });
      }

      setVisitAddress(
        [
          savedAddress.building_name,
          savedAddress.door_number,
          savedAddress.area,
          savedAddress.street,
          savedAddress.landmark,
          savedAddress.pincode,
        ]
          .filter(Boolean)
          .join(', ')
      );
    } catch (error) {
      if (error.response?.status !== 404) {
        console.error('Failed to load saved address:', error);
      }
    }
  };

  loadSavedAddress();
}, []);

  const [saveAddress, setSaveAddress] = useState(false);
  

  const NELLORE_CENTER = {
    latitude: 14.4426,
    longitude: 79.9865,
  };

  const HOME_VISIT_RADIUS_KM = 50;

  const calculateDistanceKm = (lat1, lon1, lat2, lon2) => {
  const earthRadius = 6371;

  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return earthRadius * c;
};

const handleUseCurrentLocation = () => {
  if (!navigator.geolocation) {
    setLocationStatus('error');
    setLocationError(
      'Location services are not supported by your browser.'
    );
    return;
  }

  setLocationStatus('loading');
  setLocationError('');

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const latitude = position.coords.latitude;
      const longitude = position.coords.longitude;

      const distance = calculateDistanceKm(
        latitude,
        longitude,
        NELLORE_CENTER.latitude,
        NELLORE_CENTER.longitude
      );

      setCoordinates({
        latitude,
        longitude,
        distanceKm: Number(distance.toFixed(2)),
      });

      if (distance <= HOME_VISIT_RADIUS_KM) {
        setLocationStatus('available');
      } else {
        setLocationStatus('outside');
      }
    },
    (error) => {
      setLocationStatus('error');

      if (error.code === error.PERMISSION_DENIED) {
        setLocationError(
          'Location permission was denied. Please allow location access to check home-visit availability.'
        );
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        setLocationError(
          'Your current location could not be detected. Please try again.'
        );
      } else {
        setLocationError(
          'Unable to detect your location. Please try again.'
        );
      }
    },
    {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    }
  );
};

const handleAddressChange = (field, value) => {
  setAddressDetails((current) => ({
    ...current,
    [field]: value,
  }));
};

  const [modalOpen, setModalOpen] = useState(false);

  const {
    data: doctors,
    isLoading: loadingDoctors,
    error: doctorsError,
  } = useQuery({
    queryKey: ['bookingDoctors'],
    queryFn: async () => {
      const response = await api.get('/users/doctors');
      return response.data;
    },
  });

  const bookMutation = useMutation({
    mutationFn: async (appointmentData) => {
      const response = await api.post('/appointments', appointmentData);
      return response.data;
    },

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['appointments'],
      });

      setModalOpen(true);
    },

    onError: (err) => {
      console.error(
        'Failed to book appointment:',
        err.response?.data || err.message
      );
    },
  });

  const handleServiceSelect = (service) => {
    if (service.id === 'laboratory') {
      navigate('/patient/laboratory');
        return;
        }

        setSelectedService(service);
        setStep(2);
      };

  const toggleSymptom = (symptom) => {
    if (symptom === 'Other symptoms') {
      setSelectedSymptoms((current) =>
        current.includes(symptom)
          ? current.filter((item) => item !== symptom)
          : [...current, symptom]
        );

        return;
      }

      setSelectedSymptoms((current) =>
        current.includes(symptom)
          ? current.filter((item) => item !== symptom)
          : [...current, symptom]
        );
      };

const handleHealthContinue = (event) => {
  event.preventDefault();

  if (!selectedBodyArea) {
    return;
  }

  if (!selectedProblem) {
    return;
  }

  if (
    selectedProblem.toLowerCase().includes('other') &&
    !customProblem.trim()
  ) {
    return;
  }

  if (selectedService?.id === 'home_visit') {
    if (locationStatus !== 'available') {
      return;
    }

    if (
      !addressDetails.buildingName.trim() ||
      !addressDetails.doorNumber.trim() ||
      !addressDetails.area.trim() ||
      !addressDetails.street.trim() ||
      !addressDetails.pincode.trim()
    ) {
      return;
    }
  }

  setStep(3);
};

  const handleDoctorSelect = (doctor) => {
    setSelectedDoctor(doctor);
    setStep(4);
  };

  const handleDateSelect = (date) => {
    if (date) {
      setSelectedDate(date);
      setSelectedTime('');
    }
  };

  const handleTimeSelect = (time) => {
    setSelectedTime(time);
    setStep(5);
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    if (
  !selectedService ||
  !selectedDoctor ||
  !selectedDate ||
  !selectedTime ||
  !selectedProblem
) {
  return;
}

if (
  selectedProblem.toLowerCase().includes('other') &&
  !customProblem.trim()
) {
  return;
}

    if (selectedService.id === 'home_visit' && !visitAddress.trim()) {
      return;
    }

    const appointmentDate = new Date(
      selectedDate.getFullYear(),
      selectedDate.getMonth(),
      selectedDate.getDate(),
      12,
      0,
      0
    );

    bookMutation.mutate({
      doctor_id: selectedDoctor.id,

      service_type: selectedService.id,

      appointment_date: appointmentDate.toISOString(),
      time_slot: selectedTime,

      reason:
        selectedProblem?.toLowerCase().includes('other')
          ? customProblem.trim()
          : selectedProblem,

symptoms:
  [
    ...selectedSymptoms.filter(
      (symptom) => symptom !== 'Other symptoms'
    ),
    ...(selectedSymptoms.includes('Other symptoms') &&
    customSymptoms.trim()
      ? [customSymptoms.trim()]
      : []),
  ].join(', ') || null,

      duration_days: durationDays
        ? Number(durationDays)
        : null,

      pain_level: painLevel || null,

      visit_address:
        selectedService.id === 'home_visit'
          ? visitAddress.trim()
          : null,

      payment_method: paymentMethod,
    });
  };

  const handleModalClose = () => {
    setModalOpen(false);
    navigate('/patient/dashboard');
  };

  const goBack = () => {
    if (step === 1) {
      navigate('/patient/dashboard');
      return;
    }

    setStep((current) => current - 1);
  };

  if (doctorsError) {
    return (
      <ErrorState message="Could not load physiotherapist staff." />
    );
  }

  const disabledDays = (date) =>
    isBefore(date, startOfToday());

  return (
    <div className="min-h-screen bg-[#f6fbfd] px-4 py-6 md:px-8 md:py-10">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <button
            type="button"
            onClick={goBack}
            className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-[#0b84a5] transition-colors mb-5"
          >
            <ArrowLeft className="w-4 h-4" />
            {step === 1 ? 'Back to Dashboard' : 'Back'}
          </button>

          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#e7f7fb] text-[#0b84a5] text-xs font-extrabold mb-3">
                <HeartPulse className="w-4 h-4" />
                PHYSIOCARE APPOINTMENTS
              </div>

              <h1 className="text-3xl md:text-4xl font-black text-[#0a2540]">
                Book your care
              </h1>

              <p className="mt-2 text-slate-500 max-w-2xl">
                Choose the service that suits your needs and schedule
                professional physiotherapy care at your convenience.
              </p>
            </div>

            <div className="hidden md:flex items-center gap-2 text-sm text-slate-400">
              <ShieldCheck className="w-5 h-5 text-emerald-500" />
              Secure booking
            </div>
          </div>
        </div>

        {/* Progress */}
        <div className="bg-white border border-[#e4edf2] rounded-2xl p-4 md:p-5 mb-8 shadow-[0_8px_30px_rgba(30,80,120,0.05)]">
          <div className="flex items-center justify-between max-w-4xl mx-auto">

            {[
              { number: 1, label: 'Service' },
              { number: 2, label: 'Health Details' },
              { number: 3, label: 'Specialist' },
              { number: 4, label: 'Date & Time' },
              { number: 5, label: 'Review' },
            ].map((item, index) => (
              <React.Fragment key={item.number}>
                <div className="flex flex-col items-center min-w-[55px]">
                  <div
                    className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-black transition-all ${
                      step >= item.number
                        ? 'bg-[#0b84a5] text-white shadow-md'
                        : 'bg-[#edf3f6] text-slate-400'
                    }`}
                  >
                    {step > item.number ? (
                      <Check className="w-4 h-4" />
                    ) : (
                      item.number
                    )}
                  </div>

                  <span
                    className={`mt-2 text-[10px] md:text-xs font-bold text-center ${
                      step >= item.number
                        ? 'text-[#0b84a5]'
                        : 'text-slate-400'
                    }`}
                  >
                    {item.label}
                  </span>
                </div>

                {index < 4 && (
                  <div
                    className={`h-[2px] flex-1 mx-1 md:mx-3 ${
                      step > item.number
                        ? 'bg-[#0b84a5]'
                        : 'bg-[#e6eef2]'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* STEP 1 — SERVICE */}
        {step === 1 && (
          <section>
            <div className="mb-6">
              <p className="text-sm font-bold text-[#0b84a5]">
                STEP 01
              </p>

              <h2 className="text-2xl font-black text-[#0a2540] mt-1">
                What care do you need?
              </h2>

              <p className="text-slate-500 mt-1">
                Select a service and we'll guide you through the rest.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {services.map((service) => {
                const Icon = service.icon;
                const selected =
                  selectedService?.id === service.id;

                return (
                  <button
                    key={service.id}
                    type="button"
                    onClick={() => handleServiceSelect(service)}
                    className={`group text-left bg-white rounded-2xl p-6 border-2 transition-all duration-300 ${
                      selected
                        ? 'border-[#0b84a5] shadow-[0_16px_40px_rgba(11,132,165,0.14)] bg-[#f5fcff]'
                        : 'border-[#e5edf2] shadow-[0_8px_25px_rgba(30,80,120,0.05)] hover:border-[#9bd8e8] hover:-translate-y-1 hover:shadow-[0_18px_40px_rgba(30,80,120,0.10)]'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div
                        className={`w-14 h-14 rounded-2xl flex items-center justify-center transition-colors ${
                          selected
                            ? 'bg-[#0b84a5] text-white'
                            : 'bg-[#eaf7fb] text-[#0b84a5] group-hover:bg-[#0b84a5] group-hover:text-white'
                        }`}
                      >
                        <Icon className="w-7 h-7" />
                      </div>

                      <ArrowRight
                        className={`w-5 h-5 transition-all ${
                          selected
                            ? 'text-[#0b84a5]'
                            : 'text-slate-300 group-hover:text-[#0b84a5] group-hover:translate-x-1'
                        }`}
                      />
                    </div>

                    <h3 className="text-lg font-extrabold text-[#0a2540] mt-5">
                      {service.title}
                    </h3>

                    <p className="text-sm text-slate-500 leading-6 mt-2">
                      {service.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {/* STEP 2 — HEALTH DETAILS */}
        {step === 2 && selectedService && (
          <section className="max-w-3xl mx-auto">
            <div className="mb-6">
              <p className="text-sm font-bold text-[#0b84a5]">
                STEP 02
              </p>

              <h2 className="text-2xl font-black text-[#0a2540] mt-1">
                Tell us about your condition
              </h2>

              <p className="text-slate-500 mt-1">
                This helps your physiotherapist understand your needs
                before the appointment.
              </p>
            </div>

            <form
              onSubmit={handleHealthContinue}
              className="bg-white rounded-3xl border border-[#e4edf2] shadow-[0_12px_35px_rgba(30,80,120,0.06)] p-6 md:p-8"
            >
              {/* Selected service */}
              <div className="flex items-center gap-4 p-4 rounded-2xl bg-[#eef9fc] border border-[#d5eef5] mb-7">
                <div className="w-12 h-12 rounded-xl bg-[#0b84a5] text-white flex items-center justify-center">
                  {(() => {
                    const Icon = selectedService.icon;
                    return <Icon className="w-6 h-6" />;
                  })()}
                </div>

                <div>
                  <p className="text-xs font-bold text-[#0b84a5] uppercase tracking-wide">
                    Selected Service
                  </p>

                  <p className="font-extrabold text-[#0a2540]">
                    {selectedService.title}
                  </p>
                </div>
              </div>

              {/* Physiotherapy Problem Selection */}

              <div className="mb-8">
                <label className="block text-sm font-extrabold text-[#0a2540] mb-2">
                  Where are you having a problem?
                </label>

                <p className="text-sm text-slate-500 mb-4">
                  Select the area where you are experiencing pain or difficulty.
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                  {Object.keys(physioProblems).map((area) => {
                    const selected = selectedBodyArea === area;

                    return (
                      <button
                        key={area}
                        type="button"
                        onClick={() => {
                          setSelectedBodyArea(area);
                          setSelectedProblem('');
                          setCustomProblem('');
                        }}
                        className={`rounded-2xl border-2 px-4 py-3 text-sm font-extrabold transition-all ${
                          selected
                            ? 'border-[#0b84a5] bg-[#eef9fc] text-[#0b84a5] shadow-sm'
                            : 'border-[#e1ebef] bg-white text-[#334e68] hover:border-[#9bd8e8] hover:text-[#0b84a5]'
                        }`}
                      >
                        {area}
                      </button>
                    );
                  })}
                </div>
              </div>

              {selectedBodyArea && (
                <div className="mb-8">
                  <label className="block text-sm font-extrabold text-[#0a2540] mb-2">
                    Which best describes your problem?
                  </label>

                  <p className="text-sm text-slate-500 mb-4">
                    Choose the option that best matches what you are experiencing.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {physioProblems[selectedBodyArea].map((problem) => {
                      const selected = selectedProblem === problem;

                      return (
                        <button
                          key={problem}
                          type="button"
                          onClick={() => {
                            setSelectedProblem(problem);

                            if (problem !== 'Other problem' &&
                                !problem.toLowerCase().includes('other')) {
                              setCustomProblem('');
                            }
                          }}
                          className={`text-left rounded-2xl border-2 px-4 py-4 transition-all ${
                            selected
                              ? 'border-[#0b84a5] bg-[#eef9fc] shadow-sm'
                              : 'border-[#e1ebef] bg-white hover:border-[#9bd8e8]'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 ${
                                selected
                                  ? 'border-[#0b84a5] bg-[#0b84a5]'
                                  : 'border-slate-300'
                              }`}
                            >
                              {selected && (
                                <Check className="w-3 h-3 text-white" />
                              )}
                            </div>

                            <span
                              className={`text-sm font-bold ${
                                selected
                                  ? 'text-[#0b84a5]'
                                  : 'text-[#334e68]'
                              }`}
                            >
                              {problem}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {selectedProblem &&
                selectedProblem.toLowerCase().includes('other') && (
                  <div className="mb-7">
                    <label
                      htmlFor="customProblem"
                      className="block text-sm font-extrabold text-[#0a2540] mb-2"
                    >
                      Can't find your problem?
                    </label>

                    <p className="text-sm text-slate-500 mb-3">
                      Tell us in your own words what you are experiencing.
                    </p>

                    <textarea
                      id="customProblem"
                      value={customProblem}
                      onChange={(event) =>
                        setCustomProblem(event.target.value)
                      }
                      rows={3}
                      placeholder="Example: Pain near my lower back after sitting for a long time..."
                      className="w-full rounded-2xl border border-[#dce7ed] bg-[#fbfdfe] px-4 py-3.5 text-sm text-slate-700 outline-none transition focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
                      required
                    />
                  </div>
                )}

{/* Symptoms */}

<div className="mb-8">
  <label className="block text-sm font-extrabold text-[#0a2540] mb-2">
    Describe your symptoms
  </label>

  <p className="text-sm text-slate-500 mb-4">
    Select all the symptoms you are currently experiencing.
  </p>

  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
    {physioSymptoms.map((symptom) => {
      const selected = selectedSymptoms.includes(symptom);

      return (
        <button
          key={symptom}
          type="button"
          onClick={() => toggleSymptom(symptom)}
          className={`text-left rounded-2xl border-2 px-4 py-3.5 transition-all ${
            selected
              ? 'border-[#0b84a5] bg-[#eef9fc] text-[#0b84a5]'
              : 'border-[#e1ebef] bg-white text-[#334e68] hover:border-[#9bd8e8]'
          }`}
        >
          <div className="flex items-center gap-3">
            <div
              className={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 ${
                selected
                  ? 'border-[#0b84a5] bg-[#0b84a5]'
                  : 'border-slate-300'
              }`}
            >
              {selected && (
                <Check className="w-3.5 h-3.5 text-white" />
              )}
            </div>

            <span className="text-sm font-bold">
              {symptom}
            </span>
          </div>
        </button>
      );
    })}
  </div>
</div>

{selectedSymptoms.includes('Other symptoms') && (
  <div className="mb-7">
    <label
      htmlFor="customSymptoms"
      className="block text-sm font-extrabold text-[#0a2540] mb-2"
    >
      Tell us about your other symptoms
    </label>

    <textarea
      id="customSymptoms"
      value={customSymptoms}
      onChange={(event) =>
        setCustomSymptoms(event.target.value)
      }
      rows={3}
      placeholder="Describe any other symptoms you're experiencing..."
      className="w-full rounded-2xl border border-[#dce7ed] bg-[#fbfdfe] px-4 py-3.5 text-sm text-slate-700 outline-none transition focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
      required
    />
  </div>
)}

              {/* Duration */}
              <div className="mb-6">
                <label
                  htmlFor="duration"
                  className="block text-sm font-extrabold text-[#0a2540] mb-2"
                >
                  How long have you had this problem?
                </label>

                <div className="relative">
                  <input
                    id="duration"
                    type="number"
                    min="0"
                    value={durationDays}
                    onChange={(event) =>
                      setDurationDays(event.target.value)
                    }
                    placeholder="Number of days"
                    className="w-full rounded-2xl border border-[#dce7ed] bg-[#fbfdfe] px-4 py-3.5 text-sm text-slate-700 outline-none transition focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
                  />

                  <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-slate-400 font-semibold">
                    days
                  </span>
                </div>
              </div>

              {/* Pain level */}
              <div className="mb-6">
                <p className="text-sm font-extrabold text-[#0a2540] mb-3">
                  How would you describe your pain?
                </p>

                <div className="grid grid-cols-3 gap-3">
                  {painLevels.map((pain) => {
                    const selected = painLevel === pain.value;

                    return (
                      <button
                        key={pain.value}
                        type="button"
                        onClick={() =>
                          setPainLevel(pain.value)
                        }
                        className={`rounded-2xl border-2 p-4 text-center transition-all ${
                          selected
                            ? 'border-[#0b84a5] bg-[#eef9fc] text-[#0b84a5]'
                            : 'border-[#e3ebef] bg-white hover:border-[#a8dbe8]'
                        }`}
                      >
                        <div className="font-extrabold">
                          {pain.label}
                        </div>

                        <div className="text-xs text-slate-400 mt-1">
                          {pain.description}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

{/* Home Visit Location */}

{selectedService?.id === 'home_visit' && (
  <div className="mb-8">
    <label className="block text-sm font-extrabold text-[#0a2540] mb-2">
      Where should the physiotherapist visit?
    </label>

    <p className="text-sm text-slate-500 mb-4">
      We currently provide home visits within approximately
      50 km of Nellore.
    </p>

    <div className="rounded-2xl border border-[#dce7ed] bg-white p-5">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-xl bg-[#eef9fc] text-[#0b84a5] flex items-center justify-center shrink-0">
          <span className="text-xl">📍</span>
        </div>

        <div className="flex-1">
          <h3 className="text-sm font-extrabold text-[#0a2540]">
            Check home-visit availability
          </h3>

          <p className="text-sm text-slate-500 mt-1">
            Allow location access so we can check whether
            home physiotherapy is available in your area.
          </p>

          <button
            type="button"
            onClick={handleUseCurrentLocation}
            disabled={locationStatus === 'loading'}
            className="mt-4 rounded-xl bg-[#0b84a5] px-5 py-3 text-sm font-extrabold text-white transition hover:bg-[#08748f] disabled:opacity-60"
          >
            {locationStatus === 'loading'
              ? 'Detecting location...'
              : 'Use My Current Location'}
          </button>
        </div>
      </div>

      {locationStatus === 'available' && (
        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="flex items-start gap-3">
            <span className="text-lg">✅</span>

            <div>
              <p className="text-sm font-extrabold text-emerald-700">
                Home visit is available
              </p>

              <p className="text-sm text-emerald-600 mt-1">
                Your location is within our current Nellore
                service area.
              </p>

              {coordinates && (
                <p className="text-xs text-emerald-600 mt-2">
                  Approx. {coordinates.distanceKm} km from Nellore
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {locationStatus === 'outside' && (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-3">
            <span className="text-lg">⚠️</span>

            <div>
              <p className="text-sm font-extrabold text-red-700">
                Home visit is currently unavailable
              </p>

              <p className="text-sm text-red-600 mt-1">
                Your location is outside our current Nellore
                home-visit service area.
              </p>

              <p className="text-sm text-red-600 mt-1">
                Please choose a clinic consultation instead.
              </p>
            </div>
          </div>
        </div>
      )}

      {locationStatus === 'error' && (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-bold text-amber-700">
            {locationError}
          </p>
        </div>
      )}
    </div>

    {locationStatus === 'available' && (
      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Building / House Name
          </label>

          <input
            type="text"
            value={addressDetails.buildingName}
            onChange={(event) =>
              handleAddressChange(
                'buildingName',
                event.target.value
              )
            }
            placeholder="Enter building or house name"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Door / Flat Number
          </label>

          <input
            type="text"
            value={addressDetails.doorNumber}
            onChange={(event) =>
              handleAddressChange(
                'doorNumber',
                event.target.value
              )
            }
            placeholder="Example: 2-45"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Area / Locality
          </label>

          <input
            type="text"
            value={addressDetails.area}
            onChange={(event) =>
              handleAddressChange(
                'area',
                event.target.value
              )
            }
            placeholder="Enter your area"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Street
          </label>

          <input
            type="text"
            value={addressDetails.street}
            onChange={(event) =>
              handleAddressChange(
                'street',
                event.target.value
              )
            }
            placeholder="Enter street name"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Landmark
          </label>

          <input
            type="text"
            value={addressDetails.landmark}
            onChange={(event) =>
              handleAddressChange(
                'landmark',
                event.target.value
              )
            }
            placeholder="Nearby landmark"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-[#0a2540] mb-2">
            Pincode
          </label>

          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={addressDetails.pincode}
            onChange={(event) =>
              handleAddressChange(
                'pincode',
                event.target.value.replace(/\D/g, '')
              )
            }
            placeholder="Enter pincode"
            className="w-full rounded-xl border border-[#dce7ed] bg-white px-4 py-3 text-sm outline-none focus:border-[#0b84a5] focus:ring-4 focus:ring-[#0b84a5]/10"
          />
        </div>
      </div>
    )}
  </div>
)}

<div className="mt-6 rounded-xl border border-[#dce7ed] bg-[#f8fbfc] p-4">
  <label className="flex items-center gap-3 cursor-pointer">
    <input
      type="checkbox"
      checked={saveAddress}
      onChange={(event) => setSaveAddress(event.target.checked)}
      className="h-5 w-5 accent-[#0b84a5]"
    />

    <div>
      <p className="text-sm font-bold text-[#0a2540]">
        Save this address for future home visits
      </p>

      <p className="text-xs text-slate-500 mt-1">
        You can use this address for your future bookings without typing it again.
      </p>
    </div>
  </label>
</div>

<div className="mt-8 flex justify-end">
  <button
    type="submit"
    className="rounded-xl bg-[#0b84a5] px-6 py-3 font-bold text-white transition hover:bg-[#096f8a]"
  >
    Continue to Specialists →
  </button>
</div>
  </form>
</section>
)}

        {/* STEP 3 — DOCTOR */}
        {step === 3 && (
          <section>
            <div className="mb-6">
              <p className="text-sm font-bold text-[#0b84a5]">
                STEP 03
              </p>

              <h2 className="text-2xl font-black text-[#0a2540] mt-1">
                Choose your specialist
              </h2>

              <p className="text-slate-500 mt-1">
                Select a physiotherapist based on their expertise and
                availability.
              </p>
            </div>

            {loadingDoctors ? (
              <div className="space-y-4">
                <Skeleton variant="row" count={3} />
              </div>
            ) : doctors?.length ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {doctors.map((doctor) => (
                  <DoctorCard
                    key={doctor.id}
                    doctor={doctor}
                    selected={selectedDoctor?.id === doctor.id}
                    onClick={() => handleDoctorSelect(doctor)}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-[#e5edf2] p-10 text-center">
                <Stethoscope className="w-10 h-10 text-slate-300 mx-auto" />

                <h3 className="font-extrabold text-[#0a2540] mt-4">
                  No specialists available
                </h3>

                <p className="text-sm text-slate-500 mt-1">
                  Please try again later.
                </p>
              </div>
            )}
          </section>
        )}

        {/* STEP 4 — DATE & TIME */}
        {step === 4 && selectedDoctor && (
          <section>
            <div className="mb-6">
              <p className="text-sm font-bold text-[#0b84a5]">
                STEP 04
              </p>

              <h2 className="text-2xl font-black text-[#0a2540] mt-1">
                Choose date & time
              </h2>

              <p className="text-slate-500 mt-1">
                Select a convenient appointment date and available slot.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Calendar */}
              <div className="bg-white rounded-3xl border border-[#e4edf2] shadow-[0_10px_30px_rgba(30,80,120,0.05)] p-6">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-11 h-11 rounded-xl bg-[#eaf7fb] text-[#0b84a5] flex items-center justify-center">
                    <CalendarDays className="w-5 h-5" />
                  </div>

                  <div>
                    <h3 className="font-extrabold text-[#0a2540]">
                      Select a date
                    </h3>

                    <p className="text-xs text-slate-400">
                      Past dates are unavailable
                    </p>
                  </div>
                </div>

                <div className="flex justify-center">
                  <DayPicker
                    mode="single"
                    selected={selectedDate}
                    onSelect={handleDateSelect}
                    disabled={disabledDays}
                  />
                </div>

                {selectedDate && (
                  <div className="mt-5 p-4 rounded-2xl bg-[#eef9fc] border border-[#d5eef5]">
                    <p className="text-xs font-bold text-[#0b84a5] uppercase">
                      Selected Date
                    </p>

                    <p className="font-extrabold text-[#0a2540] mt-1">
                      {format(selectedDate, 'EEEE, MMMM dd, yyyy')}
                    </p>
                  </div>
                )}
              </div>

              {/* Slots */}
              <div className="bg-white rounded-3xl border border-[#e4edf2] shadow-[0_10px_30px_rgba(30,80,120,0.05)] p-6">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-11 h-11 rounded-xl bg-[#eaf7fb] text-[#0b84a5] flex items-center justify-center">
                    <Clock3 className="w-5 h-5" />
                  </div>

                  <div>
                    <h3 className="font-extrabold text-[#0a2540]">
                      Available time slots
                    </h3>

                    <p className="text-xs text-slate-400">
                      {selectedDate
                        ? format(selectedDate, 'MMM dd')
                        : 'Select a date first'}
                    </p>
                  </div>
                </div>

                {!selectedDate ? (
                  <div className="h-48 flex items-center justify-center text-center text-slate-400">
                    <div>
                      <CalendarDays className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm font-semibold">
                        Select a date to view slots
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {timeSlots.map((time) => {
                      const selected = selectedTime === time;

                      return (
                        <button
                          key={time}
                          type="button"
                          onClick={() =>
                            handleTimeSelect(time)
                          }
                          className={`flex items-center justify-center gap-2 rounded-xl border-2 py-3.5 text-sm font-extrabold transition-all ${
                            selected
                              ? 'border-[#0b84a5] bg-[#0b84a5] text-white shadow-md'
                              : 'border-[#e1ebef] bg-white text-[#334e68] hover:border-[#0b84a5] hover:text-[#0b84a5]'
                          }`}
                        >
                          <Clock3 className="w-4 h-4" />
                          {time}
                        </button>
                      );
                    })}
                  </div>
                )}

                {selectedTime && (
                  <div className="mt-5 flex items-center gap-2 text-sm font-bold text-emerald-600">
                    <Check className="w-4 h-4" />
                    {selectedTime} selected
                  </div>
                )}
              </div>
            </div>
          </section>
        )}

        {/* STEP 5 — REVIEW & PAYMENT */}
        {step === 5 &&
          selectedDoctor &&
          selectedDate &&
          selectedTime && (
            <section className="max-w-4xl mx-auto">
              <div className="mb-6">
                <p className="text-sm font-bold text-[#0b84a5]">
                  STEP 05
                </p>

                <h2 className="text-2xl font-black text-[#0a2540] mt-1">
                  Review your booking
                </h2>

                <p className="text-slate-500 mt-1">
                  Check your appointment details and choose your payment
                  method.
                </p>
              </div>

              <form
                onSubmit={handleSubmit}
                className="grid grid-cols-1 lg:grid-cols-5 gap-6"
              >
                {/* Summary */}
                <div className="lg:col-span-3 bg-white rounded-3xl border border-[#e4edf2] shadow-[0_12px_35px_rgba(30,80,120,0.06)] p-6 md:p-8">

                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-11 h-11 rounded-xl bg-[#eaf7fb] text-[#0b84a5] flex items-center justify-center">
                      <ClipboardList className="w-5 h-5" />
                    </div>

                    <div>
                      <h3 className="font-extrabold text-[#0a2540]">
                        Appointment summary
                      </h3>

                      <p className="text-xs text-slate-400">
                        Your selected care details
                      </p>
                    </div>
                  </div>

                  <div className="space-y-5">

                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                        Service
                      </p>

                      <p className="font-extrabold text-[#0a2540] mt-1">
                        {selectedService?.title}
                      </p>
                    </div>

                    <div className="h-px bg-[#edf2f5]" />

                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                        Specialist
                      </p>

                      <p className="font-extrabold text-[#0a2540] mt-1">
                        {selectedDoctor.full_name}
                      </p>

                      <p className="text-sm text-[#0b84a5] font-semibold mt-1">
                        {selectedDoctor.specialization}
                      </p>
                    </div>

                    <div className="h-px bg-[#edf2f5]" />

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                          Date
                        </p>

                        <p className="font-bold text-[#0a2540] mt-1">
                          {format(
                            selectedDate,
                            'MMM dd, yyyy'
                          )}
                        </p>
                      </div>

                      <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                          Time
                        </p>

                        <p className="font-bold text-[#0a2540] mt-1">
                          {selectedTime}
                        </p>
                      </div>
                    </div>

                    <div className="h-px bg-[#edf2f5]" />

                    <div>
                      <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                        Problem
                      </p>

                      <p className="text-sm text-slate-600 mt-1 leading-6">
                        {reason}
                      </p>
                    </div>

                    {painLevel && (
                      <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                          Pain level
                        </p>

                        <span className="inline-flex mt-2 px-3 py-1.5 rounded-full bg-[#fff5e8] text-[#b66b00] text-xs font-extrabold capitalize">
                          {painLevel}
                        </span>
                      </div>
                    )}

                    {selectedService?.id === 'home_visit' &&
                      visitAddress && (
                        <div>
                          <p className="text-xs font-bold text-slate-400 uppercase tracking-wide">
                            Home visit address
                          </p>

                          <p className="text-sm text-slate-600 mt-1">
                            {visitAddress}
                          </p>
                        </div>
                      )}
                  </div>
                </div>

                {/* Payment */}
                <div className="lg:col-span-2 bg-white rounded-3xl border border-[#e4edf2] shadow-[0_12px_35px_rgba(30,80,120,0.06)] p-6 md:p-8 h-fit">

                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-11 h-11 rounded-xl bg-[#eaf7fb] text-[#0b84a5] flex items-center justify-center">
                      <CreditCard className="w-5 h-5" />
                    </div>

                    <div>
                      <h3 className="font-extrabold text-[#0a2540]">
                        Payment method
                      </h3>

                      <p className="text-xs text-slate-400">
                        Choose how you'd like to pay
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3">

                    <button
                      type="button"
                      onClick={() =>
                        setPaymentMethod('offline')
                      }
                      className={`w-full text-left rounded-2xl border-2 p-4 transition-all ${
                        paymentMethod === 'offline'
                          ? 'border-[#0b84a5] bg-[#eef9fc]'
                          : 'border-[#e2ebef] hover:border-[#a8dbe8]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-[#0b84a5]">
                          <Banknote className="w-5 h-5" />
                        </div>

                        <div className="flex-1">
                          <p className="font-extrabold text-[#0a2540]">
                            Pay Offline
                          </p>

                          <p className="text-xs text-slate-500 mt-0.5">
                            Pay at the clinic or during your visit
                          </p>
                        </div>

                        {paymentMethod === 'offline' && (
                          <Check className="w-5 h-5 text-[#0b84a5]" />
                        )}
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setPaymentMethod('online')
                      }
                      className={`w-full text-left rounded-2xl border-2 p-4 transition-all ${
                        paymentMethod === 'online'
                          ? 'border-[#0b84a5] bg-[#eef9fc]'
                          : 'border-[#e2ebef] hover:border-[#a8dbe8]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-white flex items-center justify-center text-[#0b84a5]">
                          <CreditCard className="w-5 h-5" />
                        </div>

                        <div className="flex-1">
                          <p className="font-extrabold text-[#0a2540]">
                            Pay Online
                          </p>

                          <p className="text-xs text-slate-500 mt-0.5">
                            Secure payment via Razorpay
                          </p>
                        </div>

                        {paymentMethod === 'online' && (
                          <Check className="w-5 h-5 text-[#0b84a5]" />
                        )}
                      </div>
                    </button>
                  </div>

                  <div className="border-t border-[#edf2f5] my-6" />

                  <div className="flex items-center justify-between mb-5">
                    <span className="text-sm text-slate-500">
                      Consultation
                    </span>

                    <span className="font-extrabold text-[#0a2540]">
                      ₹
                      {selectedDoctor.consultation_fee || 120}
                    </span>
                  </div>

                  <div className="flex items-center justify-between mb-6">
                    <span className="font-extrabold text-[#0a2540]">
                      Total
                    </span>

                    <span className="text-2xl font-black text-[#0b84a5]">
                      ₹
                      {selectedDoctor.consultation_fee || 120}
                    </span>
                  </div>

                  {bookMutation.isError && (
                    <div className="mb-4 rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-sm text-red-600">
                      {bookMutation.error?.response?.data?.detail ||
                        'Unable to confirm this appointment. Please try another slot.'}
                    </div>
                  )}

                  <Button
                    type="submit"
                    className="w-full py-4"
                    disabled={bookMutation.isPending}
                  >
                    {bookMutation.isPending
                      ? 'Confirming...'
                      : paymentMethod === 'online'
                        ? 'Continue to Payment'
                        : 'Confirm Appointment'}
                  </Button>

                  <div className="flex items-center justify-center gap-2 mt-4 text-xs text-slate-400">
                    <ShieldCheck className="w-4 h-4 text-emerald-500" />
                    Your booking information is secure
                  </div>
                </div>
              </form>
            </section>
          )}

        {/* Confirmation */}
        <Modal
          isOpen={modalOpen}
          onClose={handleModalClose}
          title="Booking Confirmed!"
        >
          <div className="text-center space-y-5">

            <div className="w-16 h-16 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center mx-auto">
              <Check className="w-8 h-8" strokeWidth={3} />
            </div>

            <div>
              <h4 className="font-black text-xl text-[#0a2540]">
                Your appointment is confirmed
              </h4>

              <p className="text-sm text-slate-500 mt-2">
                Your physiotherapy booking has been successfully
                created.
              </p>
            </div>

            <div className="bg-[#f7fbfc] rounded-2xl p-5 text-left space-y-3 border border-[#e5eef2]">

              <div className="flex justify-between gap-4">
                <span className="text-sm text-slate-500">
                  Service
                </span>

                <span className="text-sm font-bold text-[#0a2540] text-right">
                  {selectedService?.title}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="text-sm text-slate-500">
                  Specialist
                </span>

                <span className="text-sm font-bold text-[#0a2540] text-right">
                  {selectedDoctor?.full_name}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="text-sm text-slate-500">
                  Date
                </span>

                <span className="text-sm font-bold text-[#0a2540]">
                  {selectedDate &&
                    format(selectedDate, 'MMM dd, yyyy')}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="text-sm text-slate-500">
                  Time
                </span>

                <span className="text-sm font-bold text-[#0a2540]">
                  {selectedTime}
                </span>
              </div>

              <div className="flex justify-between gap-4">
                <span className="text-sm text-slate-500">
                  Payment
                </span>

                <span className="text-sm font-bold text-[#0a2540] capitalize">
                  {paymentMethod}
                </span>
              </div>
            </div>

            <Button
              variant="primary"
              onClick={handleModalClose}
              className="w-full"
            >
              Go to Dashboard
            </Button>
          </div>
        </Modal>
      </div>
    </div>
  );
}