import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  MapPin,
  Navigation,
  Building2,
  Home,
  Map,
  Landmark,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sun,
  Moon,
  User,
  Mail,
  Phone,
  Calendar,
  ShieldCheck,
  CreditCard,
} from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import api from '../../services/api';
import Button from '../../components/common/Button';

export default function PatientProfile() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const navigate = useNavigate();
  const location = useLocation();

  const [address, setAddress] = useState('');
  const [loadingAddress, setLoadingAddress] = useState(true);
  const [savingAddress, setSavingAddress] = useState(false);
  const [addressError, setAddressError] = useState('');
  const [addressSuccess, setAddressSuccess] = useState('');
  const [editingAddress, setEditingAddress] = useState(false);
  const [detectingLocation, setDetectingLocation] = useState(false);

  const [addressFields, setAddressFields] = useState({
    apartment: '',
    flat: '',
    area: '',
    city: '',
    state: '',
    pincode: '',
    landmark: '',
  });

  const [coordinates, setCoordinates] = useState({
    latitude: null,
    longitude: null,
  });

  // ============================
  // LOAD SAVED ADDRESS
  // ============================
  useEffect(() => {
    const loadAddress = async () => {
      try {
        setLoadingAddress(true);
        setAddressError('');

        const response = await api.get('/users/me/address');
        const saved = response.data?.saved_address;

        if (saved) {
          const formattedAddress = [
            saved.building_name,
            saved.door_number,
            saved.area,
            saved.street,
            saved.landmark,
            saved.pincode,
          ]
            .filter(Boolean)
            .join(', ');

          setAddress(formattedAddress);

          setAddressFields({
            apartment: saved.building_name || '',
            flat: saved.door_number || '',
            area: saved.area || '',
            city: saved.street?.split(',')[0]?.trim() || '',
            state: saved.street?.split(',')[1]?.trim() || '',
            pincode: saved.pincode || '',
            landmark: saved.landmark === 'Not specified' ? '' : saved.landmark || '',
          });

          setCoordinates({
            latitude: saved.latitude ?? null,
            longitude: saved.longitude ?? null,
          });
        } else {
          setAddress('');
        }
      } catch (error) {
        console.error('Failed to load address:', error);
        if (error.response?.status !== 404) {
          setAddressError('Unable to load your saved address.');
        }
      } finally {
        setLoadingAddress(false);
      }
    };

    loadAddress();
  }, []);

  const detectCurrentLocation = () => {
    if (!navigator.geolocation) {
      setAddressError('Location detection is not supported by this browser.');
      return;
    }

    setDetectingLocation(true);
    setAddressError('');
    setAddressSuccess('');

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;

        setCoordinates({
          latitude,
          longitude,
        });

        try {
          const response = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`,
            {
              headers: {
                Accept: 'application/json',
              },
            }
          );

          if (!response.ok) {
            throw new Error('Unable to detect address.');
          }

          const data = await response.json();
          const location = data.address || {};

          setAddressFields((prev) => ({
            ...prev,
            area: location.suburb || location.neighbourhood || location.residential || location.road || '',
            city: location.city || location.town || location.village || location.municipality || '',
            state: location.state || '',
            pincode: location.postcode || '',
          }));

          setAddressSuccess('Your current location has been detected. Please complete your house details.');
        } catch (error) {
          console.error('Reverse geocoding failed:', error);
          setAddressError('Location detected, but address details could not be loaded. Please enter them manually.');
        } finally {
          setDetectingLocation(false);
        }
      },
      (error) => {
        console.error('Location error:', error);
        let message = 'Unable to detect your location.';
        if (error.code === error.PERMISSION_DENIED) {
          message = 'Location permission was denied. Please allow location access in your browser.';
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          message = 'Your location is currently unavailable.';
        } else if (error.code === error.TIMEOUT) {
          message = 'Location detection timed out. Please try again.';
        }
        setAddressError(message);
        setDetectingLocation(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 0,
      }
    );
  };

  const handleAddressChange = (field, value) => {
    setAddressFields((prev) => ({
      ...prev,
      [field]: value,
    }));
    if (addressError) setAddressError('');
    if (addressSuccess) setAddressSuccess('');
  };

  // ============================
  // SAVE ADDRESS
  // ============================
  const handleSaveAddress = async () => {
    const { apartment, flat, area, city, state, pincode, landmark } = addressFields;

    setAddressError('');
    setAddressSuccess('');

    if (!flat.trim()) {
      setAddressError('Please enter your flat / house number.');
      return;
    }
    if (!area.trim()) {
      setAddressError('Please enter your area / street.');
      return;
    }
    if (!city.trim()) {
      setAddressError('Please enter your city.');
      return;
    }
    if (!pincode.trim()) {
      setAddressError('Please enter your PIN code.');
      return;
    }
    if (!/^\d{6}$/.test(pincode.trim())) {
      setAddressError('Please enter a valid 6-digit PIN code.');
      return;
    }

    const payload = {
      building_name: apartment.trim() || 'Not specified',
      door_number: flat.trim(),
      area: area.trim(),
      street: `${city.trim()}, ${state.trim()}`,
      landmark: landmark.trim() || 'Not specified',
      pincode: pincode.trim(),
      latitude: coordinates.latitude,
      longitude: coordinates.longitude,
    };

    try {
      setSavingAddress(true);
      await api.put('/users/me/address', payload);

      const completeAddress = [
        apartment.trim(),
        flat.trim(),
        area.trim(),
        landmark.trim(),
        city.trim(),
        state.trim(),
        pincode.trim(),
      ]
        .filter(Boolean)
        .join(', ');

      setAddress(completeAddress);
      setAddressSuccess('Address saved successfully.');
      setEditingAddress(false);

      const returnTo = new URLSearchParams(location.search).get('returnTo');
      if (returnTo === 'laboratory-review') {
        navigate('/patient/laboratory/review');
      }
    } catch (error) {
      console.error('ADDRESS SAVE ERROR:', error.response?.data || error.message);
      const detail = error.response?.data?.detail;
      let message = 'Failed to save address. Please try again.';

      if (Array.isArray(detail)) {
        message = detail.map((item) => (typeof item === 'string' ? item : item?.msg || 'Invalid address field')).join(', ');
      } else if (typeof detail === 'string') {
        message = detail;
      } else if (detail && typeof detail === 'object') {
        message = detail.msg || 'Invalid address details.';
      } else if (typeof error.response?.data?.message === 'string') {
        message = error.response.data.message;
      }
      setAddressError(message);
    } finally {
      setSavingAddress(false);
    }
  };

  const handleCancelEdit = () => {
    setEditingAddress(false);
    setAddressError('');
    setAddressSuccess('');
  };

  // Get Avatar Initials
  const initials = useMemo(() => {
    if (!user?.full_name) return 'PT';
    return user.full_name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  }, [user]);

  return (
    <div className="max-w-[1500px] mx-auto space-y-8 animate-fade-in p-4 sm:p-6 lg:p-8">
      
      {/* 1. PROFILE HERO */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E5E0D6] bg-gradient-to-br from-[#EEF5F1] via-[#F7F4ED] to-[#EEF5F1]/20 p-6 sm:p-10 lg:p-12 shadow-sm">
        <div className="relative z-10 flex flex-col sm:flex-row items-center gap-6 sm:gap-8">
          <div className="w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-white border border-[#E5E0D6] flex items-center justify-center text-[#1F4B45] text-2xl sm:text-3xl font-black shadow-xs shrink-0 select-none">
            {initials}
          </div>
          <div className="space-y-2 text-center sm:text-left">
            <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Official Medical Card</span>
            <h1 className="text-3xl font-black tracking-tight text-[#1E2A2B]">{user?.full_name || 'Patient Profile'}</h1>
            <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2.5 pt-1">
              <span className="inline-flex px-3 py-0.5 rounded bg-white text-xs font-bold uppercase tracking-wider text-[#1F4B45] border border-[#1F4B45]/15 shadow-xs">
                {user?.role || 'Patient'}
              </span>
              <span className="inline-flex px-3 py-0.5 rounded bg-[#EEF5F1] text-xs font-bold uppercase tracking-wider text-[#1F4B45] border border-[#1F4B45]/10">
                {user?.profile?.subscription_status || 'Active'} Member
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. TWO-COLUMN DETAILS GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT COLUMN: IDENTITY & ACCOUNT DETAILS */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* PERSONAL INFORMATION */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center gap-3 pb-4 border-b border-[#E5E0D6]/40">
              <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] flex items-center justify-center border border-[#1F4B45]/10">
                <User className="w-5 h-5 text-[#1F4B45]" />
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-[#1E2A2B]">Personal Information</h2>
                <p className="text-xs text-[#60716E]">Your verified personal contact details.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-[#60716E] flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-[#1F4B45]/60" /> Full Name
                </span>
                <p className="text-sm font-extrabold text-[#1E2A2B]">{user?.full_name || 'Not provided'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-[#60716E] flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5 text-[#1F4B45]/60" /> Registered Email
                </span>
                <p className="text-sm font-extrabold text-[#1E2A2B] break-all">{user?.email || 'Not provided'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-[#60716E] flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-[#1F4B45]/60" /> Contact Phone
                </span>
                <p className="text-sm font-extrabold text-[#1E2A2B]">{user?.profile?.phone || 'Not provided'}</p>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-[#60716E] flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-[#1F4B45]/60" /> Date of Birth
                </span>
                <p className="text-sm font-extrabold text-[#1E2A2B]">{user?.profile?.date_of_birth || 'Not provided'}</p>
              </div>
            </div>
          </section>

          {/* HOME VISIT LOCATION CARD */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-6 shadow-sm">
            <div className="flex items-center justify-between pb-4 border-b border-[#E5E0D6]/40 gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] flex items-center justify-center border border-[#1F4B45]/15">
                  <MapPin className="w-5 h-5 text-[#1F4B45]" />
                </div>
                <div>
                  <h2 className="text-lg font-extrabold text-[#1E2A2B]">Home Visit Location</h2>
                  <p className="text-xs text-[#60716E]">Used for physical home therapy sessions and lab test collections.</p>
                </div>
              </div>

              {!editingAddress && address && !loadingAddress && (
                <button
                  type="button"
                  onClick={() => {
                    setEditingAddress(true);
                    setAddressSuccess('');
                    setAddressError('');
                  }}
                  className="px-3.5 py-1.5 text-xs font-bold text-[#1F4B45] hover:text-[#1F4B45]/90 bg-[#EEF5F1] hover:bg-[#EEF5F1]/80 rounded-xl border border-[#E5E0D6] transition"
                >
                  ✎ Edit Address
                </button>
              )}
            </div>

            {/* DISPLAY ADDRESS */}
            {!editingAddress && (
              <div className="space-y-4">
                {loadingAddress ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-2">
                    <Loader2 className="w-6 h-6 animate-spin text-[#1F4B45]" />
                    <p className="text-xs text-[#60716E]">Loading address details...</p>
                  </div>
                ) : address ? (
                  <div className="rounded-2xl border border-[#E5E0D6] bg-[#F7F4ED]/40 p-5 flex items-start gap-4">
                    <div className="w-9 h-9 rounded-lg bg-white border border-[#E5E0D6] flex items-center justify-center shrink-0">
                      <Home className="w-4.5 h-4.5 text-[#1F4B45]" />
                    </div>
                    <div>
                      <span className="text-xs font-bold uppercase tracking-wider text-[#60716E] block">Saved Home Address</span>
                      <p className="text-sm font-bold text-[#1E2A2B] mt-1.5 leading-relaxed">{address}</p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-[#E5E0D6] bg-[#F7F4ED]/20 p-8 text-center space-y-4">
                    <div className="w-12 h-12 rounded-full bg-[#EEF5F1] flex items-center justify-center mx-auto border border-[#E5E0D6]/40">
                      <MapPin className="w-5.5 h-5.5 text-[#60716E]" />
                    </div>
                    <div className="space-y-1">
                      <h3 className="text-base font-extrabold text-[#1E2A2B]">No Saved Address</h3>
                      <p className="text-xs text-[#60716E] max-w-sm mx-auto leading-relaxed">
                        Add your physical home address to configure clinical therapist visits or home test bookings.
                      </p>
                    </div>
                    <Button
                      onClick={() => {
                        setEditingAddress(true);
                        setAddressSuccess('');
                        setAddressError('');
                      }}
                      className="text-xs py-2 px-5 min-h-[44px] shadow-xs font-bold"
                    >
                      + Add Home Address
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* ADDRESS EDITOR FORM */}
            {editingAddress && (
              <div className="space-y-6">
                
                {/* Location detection capture */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-[#F7F4ED]/35 p-4 rounded-xl border border-[#E5E0D6]/50">
                  <div className="space-y-0.5">
                    <h4 className="text-sm font-bold text-[#1E2A2B]">GPS Geolocation Detection</h4>
                    <p className="text-xs text-[#60716E]">Autofill fields using your mobile device coordinates.</p>
                  </div>

                  <button
                    type="button"
                    onClick={detectCurrentLocation}
                    disabled={detectingLocation}
                    className="flex items-center justify-center gap-2 px-4.5 py-2.5 rounded-xl border border-[#E5E0D6] bg-white text-xs font-bold text-[#1F4B45] hover:bg-[#EEF5F1] transition disabled:opacity-50"
                  >
                    {detectingLocation ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Detecting...
                      </>
                    ) : (
                      <>
                        <Navigation className="w-4 h-4" />
                        Capture GPS Coordinates
                      </>
                    )}
                  </button>
                </div>

                {coordinates.latitude && coordinates.longitude && (
                  <div className="flex items-center gap-2 p-3.5 bg-[#EEF5F1] text-[#1F4B45] border border-[#1F4B45]/10 rounded-xl text-xs font-medium">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>Coordinates successfully saved ({coordinates.latitude.toFixed(4)}, {coordinates.longitude.toFixed(4)})</span>
                  </div>
                )}

                {addressError && (
                  <div className="flex items-start gap-2 p-3.5 bg-red-50 text-red-700 border border-red-200/50 rounded-xl text-xs font-semibold">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{addressError}</span>
                  </div>
                )}

                {addressSuccess && (
                  <div className="flex items-center gap-2 p-3.5 bg-[#EEF5F1] text-[#1F4B45] border border-[#1F4B45]/10 rounded-xl text-xs font-semibold">
                    <CheckCircle2 className="w-4 h-4 shrink-0" />
                    <span>{addressSuccess}</span>
                  </div>
                )}

                {/* Form fields */}
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  
                  <div className="sm:col-span-2 space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">Apartment / Building Name</label>
                    <div className="relative">
                      <Building2 className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#60716E]" />
                      <input
                        type="text"
                        value={addressFields.apartment}
                        onChange={(e) => handleAddressChange('apartment', e.target.value)}
                        placeholder="e.g. Lavender Heights"
                        className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 pl-10 pr-3 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">Flat / House No. *</label>
                    <div className="relative">
                      <Home className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#60716E]" />
                      <input
                        type="text"
                        value={addressFields.flat}
                        onChange={(e) => handleAddressChange('flat', e.target.value)}
                        placeholder="e.g. Apartment 4B"
                        className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 pl-10 pr-3 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">Area / Street *</label>
                    <div className="relative">
                      <Map className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#60716E]" />
                      <input
                        type="text"
                        value={addressFields.area}
                        onChange={(e) => handleAddressChange('area', e.target.value)}
                        placeholder="e.g. Park Circus Avenue"
                        className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 pl-10 pr-3 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">City *</label>
                    <input
                      type="text"
                      value={addressFields.city}
                      onChange={(e) => handleAddressChange('city', e.target.value)}
                      placeholder="e.g. Nellore"
                      className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 px-3.5 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">State</label>
                    <input
                      type="text"
                      value={addressFields.state}
                      onChange={(e) => handleAddressChange('state', e.target.value)}
                      placeholder="e.g. Andhra Pradesh"
                      className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 px-3.5 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-[#60716E]">PIN Code *</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={addressFields.pincode}
                      onChange={(e) => handleAddressChange('pincode', e.target.value.replace(/\D/g, ''))}
                      placeholder="6-digit PIN code"
                      className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 px-3.5 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                    />
                  </div>

                  <div className="space-y-1.5 sm:col-span-2">
                    <label className="text-xs font-bold text-[#60716E]">Landmark <span className="font-normal">(Optional)</span></label>
                    <div className="relative">
                      <Landmark className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#60716E]" />
                      <input
                        type="text"
                        value={addressFields.landmark}
                        onChange={(e) => handleAddressChange('landmark', e.target.value)}
                        placeholder="e.g. Behind Central Mall"
                        className="w-full rounded-xl border border-[#E5E0D6] bg-white py-2.5 pl-10 pr-3 text-xs text-[#1E2A2B] outline-none focus:border-[#1F4B45] focus:ring-4 focus:ring-[#1F4B45]/10 transition font-medium"
                      />
                    </div>
                  </div>

                </div>

                {/* Actions */}
                <div className="flex flex-col sm:flex-row gap-3 pt-4 border-t border-[#E5E0D6]/40">
                  <Button
                    onClick={handleSaveAddress}
                    disabled={savingAddress}
                    className="text-xs py-2.5 font-bold"
                  >
                    {savingAddress ? 'Saving Address...' : 'Save Location Address'}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleCancelEdit}
                    disabled={savingAddress}
                    className="text-xs py-2.5 border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#1F4B45] font-bold"
                  >
                    Cancel Edit
                  </Button>
                </div>

              </div>
            )}
          </section>

        </div>

        {/* RIGHT COLUMN: SECURITY, ACCOUNT DETAILS, ACCESSIBILITY */}
        <div className="space-y-8">
          
          {/* MEDICAL ACCOUNT INFORMATION */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center gap-3 pb-3 border-b border-[#E5E0D6]/40">
              <div className="w-9 h-9 rounded-xl bg-[#EEF5F1] flex items-center justify-center border border-[#E5E0D6]/40 shrink-0">
                <ShieldCheck className="w-5 h-5 text-[#1F4B45]" />
              </div>
              <div>
                <h3 className="font-extrabold text-sm text-[#1E2A2B]">Clinical System Identity</h3>
                <p className="text-xs text-[#60716E]">Authorized credentials details</p>
              </div>
            </div>

            <div className="space-y-4 text-xs">
              <div className="space-y-1">
                <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider block">Authorized Role</span>
                <span className="font-bold text-[#1E2A2B] block">{user?.role ? user.role.toUpperCase() : 'PATIENT'}</span>
              </div>
              <div className="space-y-1">
                <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider block">Patient Reference ID</span>
                <code className="text-xs font-bold text-[#1F4B45] block font-mono bg-gray-50 border border-gray-200/50 p-2 rounded-xl">
                  {user?.id || 'N/A'}
                </code>
              </div>
              <div className="space-y-1">
                <span className="text-xs font-bold text-[#60716E] uppercase tracking-wider block">Session Security Status</span>
                <span className="font-bold text-emerald-700 bg-emerald-50 border border-emerald-250/20 px-2 py-0.5 rounded text-xs w-fit block">
                  Active Cryptographic Key
                </span>
              </div>
            </div>
          </section>

          {/* MEMBERSHIP DESCRIPTION CARD */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="w-10 h-10 rounded-xl bg-[#F7F4ED] border border-[#C9A86A]/20 flex items-center justify-center">
              <CreditCard className="w-5 h-5 text-[#C9A86A]" />
            </div>
            <div>
              <h4 className="font-extrabold text-sm text-[#1E2A2B]">PhysioCare Membership</h4>
              <p className="text-xs text-[#60716E] mt-1.5 leading-relaxed">
                As an active recovery subscriber, you get access to personalized physical care pathways, daily therapeutic exercises, clinical milestone trackers, and scheduled therapist reviews.
              </p>
            </div>
          </section>

          {/* ACCESSIBILITY DISPLAY SETTINGS */}
          <section className="bg-white border border-[#E5E0D6] rounded-3xl p-6 sm:p-8 space-y-5 shadow-sm">
            <div>
              <h3 className="font-extrabold text-sm text-[#1E2A2B]">Accessibility Settings</h3>
              <p className="text-xs text-[#60716E]">Configure theme preferences</p>
            </div>

            <div className="flex items-center justify-between pt-1">
              <div>
                <p className="text-xs font-bold text-[#1E2A2B]">Visual Theme</p>
                <p className="text-xs text-[#60716E]">Toggle Dark/Light state</p>
              </div>

              <Button
                variant="outline"
                onClick={toggleTheme}
                className="flex items-center gap-2 text-xs py-2 min-h-[44px] border-[#E5E0D6] bg-white text-[#60716E] hover:text-[#1F4B45] font-bold shrink-0"
              >
                {theme === 'light' ? (
                  <>
                    <Moon className="w-4 h-4 text-[#1F4B45]" />
                    <span>Dark Mode</span>
                  </>
                ) : (
                  <>
                    <Sun className="w-4 h-4 text-[#C9A86A]" />
                    <span>Light Mode</span>
                  </>
                )}
              </Button>
            </div>
          </section>

        </div>

      </div>

    </div>
  );
}