import React, { useEffect, useState } from 'react';
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
} from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useTheme } from '../../context/useTheme';
import api from '../../services/api';
import Card from '../../components/common/Card';
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
    landmark:
      saved.landmark === 'Not specified'
        ? ''
        : saved.landmark || '',
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
    setAddressError(
      'Location detection is not supported by this browser.'
    );
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
        /*
         * Reverse geocoding using OpenStreetMap.
         * This converts latitude/longitude into area,
         * city, state and PIN code.
         */

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

          area:
            location.suburb ||
            location.neighbourhood ||
            location.residential ||
            location.road ||
            '',

          city:
            location.city ||
            location.town ||
            location.village ||
            location.municipality ||
            '',

          state:
            location.state ||
            '',

          pincode:
            location.postcode ||
            '',
        }));

        setAddressSuccess(
          'Your current location has been detected. Please complete your house details.'
        );
      } catch (error) {
        console.error('Reverse geocoding failed:', error);

        setAddressError(
          'Location detected, but address details could not be loaded. Please enter them manually.'
        );
      } finally {
        setDetectingLocation(false);
      }
    },

    (error) => {
      console.error('Location error:', error);

      let message = 'Unable to detect your location.';

      if (error.code === error.PERMISSION_DENIED) {
        message =
          'Location permission was denied. Please allow location access in your browser.';
      } else if (error.code === error.POSITION_UNAVAILABLE) {
        message =
          'Your location is currently unavailable.';
      } else if (error.code === error.TIMEOUT) {
        message =
          'Location detection timed out. Please try again.';
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

  if (addressError) {
    setAddressError('');
  }

  if (addressSuccess) {
    setAddressSuccess('');
  }
};

const handleAddressFocus = () => {
  if (addressError) {
    setAddressError('');
  }

  if (addressSuccess) {
    setAddressSuccess('');
  }
};


  // ============================
  // SAVE ADDRESS
  // ============================

  
  const handleSaveAddress = async () => {
  const {
    apartment,
    flat,
    area,
    city,
    state,
    pincode,
    landmark,
  } = addressFields;

  // Clear old messages
  setAddressError('');
  setAddressSuccess('');

  // Validation
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

  // Backend SavedAddressUpdate expects these fields
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

  console.log('ADDRESS PAYLOAD:', payload);

  try {
    setSavingAddress(true);

    const response = await api.put(
      '/users/me/address',
      payload
    );

    console.log('ADDRESS SAVE RESPONSE:', response.data);

    // Build address for display
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

    // Return to laboratory review if required
    const returnTo = new URLSearchParams(
      location.search
    ).get('returnTo');

    if (returnTo === 'laboratory-review') {
      navigate('/patient/laboratory/review');
    }

  } catch (error) {
    console.error(
      'ADDRESS SAVE ERROR:',
      error.response?.data || error.message
    );

    console.error(
      'STATUS:',
      error.response?.status
    );

    console.error(
      'REQUEST DATA:',
      error.config?.data
    );

    const detail = error.response?.data?.detail;

    let message = 'Failed to save address. Please try again.';

    if (Array.isArray(detail)) {
      message = detail
        .map((item) => {
          if (typeof item === 'string') {
            return item;
          }

          return item?.msg || 'Invalid address field';
        })
        .join(', ');
    } else if (typeof detail === 'string') {
      message = detail;
    } else if (
      detail &&
      typeof detail === 'object'
    ) {
      message =
        detail.msg ||
        'Invalid address details.';
    } else if (
      typeof error.response?.data?.message === 'string'
    ) {
      message = error.response.data.message;
    }

    setAddressError(message);

  } finally {
    setSavingAddress(false);
  }
};

  // ============================
  // CANCEL EDIT
  // ============================

  const handleCancelEdit = () => {
    setEditingAddress(false);
    setAddressError('');
    setAddressSuccess('');
  };

  return (
    <div className="mx-auto max-w-5xl">
      {/* PAGE HEADER */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-slate-900">
          Profile & Preferences
        </h1>

        <p className="mt-2 text-base text-slate-600">
          Manage your health profile, address and accessibility preferences.
        </p>
      </div>

      <Card className="space-y-8">

        {/* ============================
            MEDICAL HEALTH CARD
        ============================ */}

        <div>
          <h3 className="mb-4 border-b border-surface-container pb-3 text-2xl font-semibold text-on-surface">
            Medical Health Card
          </h3>

          <div className="grid grid-cols-1 gap-5 text-sm sm:grid-cols-2">

            <div>
              <p className="font-bold text-on-surface-variant">
                Full Name
              </p>

              <p className="mt-1 text-base text-on-surface">
                {user?.full_name || 'Not registered'}
              </p>
            </div>

            <div>
              <p className="font-bold text-on-surface-variant">
                Registered Email
              </p>

              <p className="mt-1 text-base text-on-surface">
                {user?.email || 'Not registered'}
              </p>
            </div>

            <div>
              <p className="font-bold text-on-surface-variant">
                Contact Phone
              </p>

              <p className="mt-1 text-base text-on-surface">
                {user?.profile?.phone || 'Not registered'}
              </p>
            </div>

            <div>
              <p className="font-bold text-on-surface-variant">
                Date of Birth
              </p>

              <p className="mt-1 text-base text-on-surface">
                {user?.profile?.date_of_birth || 'Not registered'}
              </p>
            </div>

            <div>
              <p className="font-bold text-on-surface-variant">
                Care Subscription Status
              </p>

              <span className="mt-1 inline-block rounded-full bg-primary-container/20 px-3 py-1 text-xs font-bold capitalize text-primary">
                {user?.profile?.subscription_status || 'Active'}
              </span>
            </div>

          </div>
        </div>


        {/* ============================
    SAVED ADDRESS
============================ */}

<div className="border-t border-surface-container pt-8">

  <div className="flex flex-col gap-2">
    <div className="flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-50 text-cyan-700">
        <MapPin size={22} />
      </div>

      <div>
        <h3 className="text-2xl font-semibold text-on-surface">
          Home Address
        </h3>

        <p className="mt-1 text-sm text-on-surface-variant">
          Used for home visits and laboratory sample collection.
        </p>
      </div>
    </div>
  </div>


  {/* ============================
      SAVED ADDRESS DISPLAY
  ============================ */}

  {!editingAddress && (

    <div className="mt-6">

      {loadingAddress ? (

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
          <div className="h-5 w-40 animate-pulse rounded bg-slate-200" />
          <div className="mt-3 h-4 w-3/4 animate-pulse rounded bg-slate-200" />
          <div className="mt-2 h-4 w-1/2 animate-pulse rounded bg-slate-200" />
        </div>

      ) : address ? (

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-6">

          <div className="flex items-start justify-between gap-4">

            <div className="flex gap-4">

              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-emerald-600 shadow-sm">
                <Home size={20} />
              </div>

              <div>

                <p className="text-xs font-bold uppercase tracking-wide text-emerald-700">
                  Saved Home Address
                </p>

                <p className="mt-2 max-w-2xl text-base leading-7 text-slate-700">
                  {address}
                </p>

              </div>

            </div>

            <button
              type="button"
              onClick={() => {
                setEditingAddress(true);
                setAddressSuccess('');
                setAddressError('');
              }}
              className="shrink-0 rounded-xl border border-cyan-300 bg-white px-4 py-2 text-sm font-bold text-cyan-700 transition hover:bg-cyan-50"
            >
              ✎ Edit
            </button>

          </div>

        </div>

      ) : (

        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6">

          <div className="flex items-start gap-4">

            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white text-cyan-600 shadow-sm">
              <Home size={22} />
            </div>

            <div>
              <p className="font-semibold text-slate-800">
                No home address added
              </p>

              <p className="mt-1 text-sm leading-6 text-slate-500">
                Add your home address to enable home visits and sample collection.
              </p>

              <Button
                className="mt-4"
                onClick={() => {
                  setEditingAddress(true);
                  setAddressSuccess('');
                  setAddressError('');
                }}
              >
                + Add Home Address
              </Button>
            </div>

          </div>

        </div>

      )}

    </div>

  )}


  {/* ============================
      ADDRESS EDITOR
  ============================ */}

  {editingAddress && (

    <div className="mt-6 rounded-3xl border border-cyan-200 bg-gradient-to-br from-cyan-50/70 to-white p-6">

      {/* HEADER */}

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

        <div>

          <p className="text-xs font-bold uppercase tracking-wider text-cyan-700">
            Delivery / Visit Location
          </p>

          <h4 className="mt-1 text-xl font-bold text-slate-900">
            Add your home address
          </h4>

          <p className="mt-1 text-sm text-slate-500">
            Use your current location or enter your address manually.
          </p>

        </div>


        {/* DETECT LOCATION */}

        <button
          type="button"
          onClick={detectCurrentLocation}
          disabled={detectingLocation}
          className="flex items-center justify-center gap-2 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-60"
        >

          {detectingLocation ? (
            <>
              <Loader2
                size={18}
                className="animate-spin"
              />

              Detecting location...
            </>
          ) : (
            <>
              <Navigation size={18} />

              Use Current Location
            </>
          )}

        </button>

      </div>


      {/* LOCATION DETECTED */}

      {coordinates.latitude && coordinates.longitude && (

        <div className="mt-5 flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">

          <CheckCircle2
            size={20}
            className="text-emerald-600"
          />

          <div>
            <p className="text-sm font-bold text-emerald-700">
              Location detected
            </p>

            <p className="text-xs text-emerald-600">
              Address details were filled using your current location.
            </p>
          </div>

        </div>

      )}


      {/* ERROR */}

      {addressError && (

        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
          {addressError}
        </div>

      )}


      {/* SUCCESS */}

      {addressSuccess && (

        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
          {addressSuccess}
        </div>

      )}


      {/* ============================
          ADDRESS FIELDS
      ============================ */}

      <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2">


        {/* APARTMENT */}

        <div className="sm:col-span-2">

          <label className="mb-2 block text-sm font-bold text-slate-700">
            Apartment / Building Name
          </label>

          <div className="relative">

            <Building2
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={addressFields.apartment}
              onChange={(e) =>
                handleAddressChange(
                  'apartment',
                  e.target.value
                )
              }
              placeholder="e.g. lotusin appartments"
              className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pl-11 pr-4 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
            />

          </div>

        </div>


        {/* FLAT NUMBER */}

        <div>

          <label className="mb-2 block text-sm font-bold text-slate-700">
            Flat / House No. *
          </label>

          <div className="relative">

            <Home
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={addressFields.flat}
              onChange={(e) =>
                handleAddressChange(
                  'flat',
                  e.target.value
                )
              }
              placeholder="e.g. Flat 302"
              className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pl-11 pr-4 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
            />

          </div>

        </div>


        {/* AREA */}

        <div>

          <label className="mb-2 block text-sm font-bold text-slate-700">
            Area / Street *
          </label>

          <div className="relative">

            <Map
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={addressFields.area}
              onChange={(e) =>
                handleAddressChange(
                  'area',
                  e.target.value
                )
              }
              placeholder="e.g. Magunta Layout"
              className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pl-11 pr-4 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
            />

          </div>

        </div>


        {/* CITY */}

        <div>

          <label className="mb-2 block text-sm font-bold text-slate-700">
            City *
          </label>

          <input
            type="text"
            value={addressFields.city}
            onChange={(e) =>
              handleAddressChange(
                'city',
                e.target.value
              )
            }
            placeholder="e.g. Nellore"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
          />

        </div>


        {/* STATE */}

        <div>

          <label className="mb-2 block text-sm font-bold text-slate-700">
            State
          </label>

          <input
            type="text"
            value={addressFields.state}
            onChange={(e) =>
              handleAddressChange(
                'state',
                e.target.value
              )
            }
            placeholder="e.g. Andhra Pradesh"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
          />

        </div>


        {/* PINCODE */}

        <div>

          <label className="mb-2 block text-sm font-bold text-slate-700">
            PIN Code *
          </label>

          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={addressFields.pincode}
            onChange={(e) =>
              handleAddressChange(
                'pincode',
                e.target.value.replace(/\D/g, '')
              )
            }
            placeholder="6-digit PIN code"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
          />

        </div>


        {/* LANDMARK */}

        <div className="sm:col-span-2">

          <label className="mb-2 block text-sm font-bold text-slate-700">
            Landmark
            <span className="ml-1 font-normal text-slate-400">
              (Optional)
            </span>
          </label>

          <div className="relative">

            <Landmark
              size={19}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
            />

            <input
              type="text"
              value={addressFields.landmark}
              onChange={(e) =>
                handleAddressChange(
                  'landmark',
                  e.target.value
                )
              }
              placeholder="e.g. Near Nellore Railway Station"
              className="w-full rounded-xl border border-slate-300 bg-white py-3.5 pl-11 pr-4 text-sm outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-100"
            />

          </div>

        </div>

      </div>


      {/* ACTIONS */}

      <div className="mt-7 flex flex-col gap-3 border-t border-cyan-100 pt-6 sm:flex-row">

        <Button
          onClick={handleSaveAddress}
          disabled={savingAddress}
          className="min-w-[160px]"
        >
          {savingAddress
            ? 'Saving...'
            : 'Save Address'}
        </Button>

        <Button
          variant="outline"
          onClick={handleCancelEdit}
          disabled={savingAddress}
        >
          Cancel
        </Button>

      </div>

    </div>

  )}

</div>


        {/* ============================
            ACCESSIBILITY SETTINGS
        ============================ */}

        <div className="border-t border-surface-container pt-6">

          <h3 className="mb-4 text-2xl font-semibold text-on-surface">
            Accessibility Settings
          </h3>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">

            <div>
              <p className="font-semibold text-on-surface">
                Color Theme
              </p>

              <p className="text-xs text-on-surface-variant">
                Toggle dark/light background display
              </p>
            </div>

            <Button
              variant="outline"
              onClick={toggleTheme}
              className="flex items-center gap-2"
            >
              <span className="material-symbols-outlined">
                {theme === 'light'
                  ? 'dark_mode'
                  : 'light_mode'}
              </span>

              {theme === 'light'
                ? 'Dark Mode'
                : 'Light Mode'}
            </Button>

          </div>

        </div>

      </Card>
    </div>
  );
}
