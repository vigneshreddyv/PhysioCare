import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

export default function HomeVisitLab() {
  const navigate = useNavigate();

  const [savedAddress, setSavedAddress] = useState(null);
  const [loadingAddress, setLoadingAddress] = useState(true);
  const [useSavedAddress, setUseSavedAddress] = useState(false);
  const [saving, setSaving] = useState(false);

  const [addressDetails, setAddressDetails] = useState({
    building_name: '',
    door_number: '',
    area: '',
    street: '',
    landmark: '',
    pincode: '',
    latitude: null,
    longitude: null,
  });

  const [locationStatus, setLocationStatus] = useState('idle');
  const [locationError, setLocationError] = useState('');

  useEffect(() => {
    const fetchSavedAddress = async () => {
      try {
        const response = await api.get('/users/me/address');

        if (response.data) {
          setSavedAddress(response.data);
          setUseSavedAddress(true);
        }
      } catch (error) {
        if (error.response?.status !== 404) {
          console.error('Failed to load saved address:', error);
        }
      } finally {
        setLoadingAddress(false);
      }
    };

    fetchSavedAddress();
  }, []);

  const handleLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Location access is not supported by your browser.');
      return;
    }

    setLocationStatus('loading');
    setLocationError('');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setAddressDetails((current) => ({
          ...current,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }));

        setLocationStatus('success');
      },
      () => {
        setLocationStatus('error');
        setLocationError(
          'Unable to access your location. Please allow location permission.'
        );
      }
    );
  };

  const handleAddressChange = (event) => {
    const { name, value } = event.target;

    setAddressDetails((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const handleContinue = async () => {
    if (useSavedAddress && savedAddress) {
      navigate('/patient/laboratory/tests', {
        state: {
          address: savedAddress,
          visitType: 'home',
        },
      });

      return;
    }

    if (
      !addressDetails.building_name.trim() ||
      !addressDetails.door_number.trim() ||
      !addressDetails.area.trim() ||
      !addressDetails.street.trim() ||
      !addressDetails.landmark.trim() ||
      !addressDetails.pincode.trim()
    ) {
      alert('Please complete all address fields.');
      return;
    }

    try {
      setSaving(true);

      const response = await api.put('/users/me/address', addressDetails);

      navigate('/patient/laboratory/tests', {
        state: {
          address: response.data.saved_address,
          visitType: 'home',
        },
      });
    } catch (error) {
      console.error('Failed to save address:', error);
      alert('Unable to save your address. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const formatSavedAddress = (address) => {
    if (!address) return '';

    return [
      address.building_name,
      address.door_number,
      address.area,
      address.street,
      address.landmark,
      address.pincode,
    ]
      .filter(Boolean)
      .join(', ');
  };

  return (
    <div className="mx-auto max-w-5xl">
      {/* Header */}
      <div className="mb-8">
        <p className="text-sm font-semibold text-emerald-700">
          HOME VISIT LAB TEST
        </p>

        <h1 className="mt-2 text-3xl font-bold text-slate-900 sm:text-4xl">
          Home Sample Collection
        </h1>

        <p className="mt-3 max-w-2xl text-base text-slate-600">
          Our lab assistant can visit your home to collect samples for your
          selected laboratory tests.
        </p>
      </div>

      {/* Location */}
      <div className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">
          Check home-visit availability
        </h2>

        <p className="mt-1 text-sm text-slate-500">
          Allow location access so we can check whether home sample collection
          is available in your area.
        </p>

        <button
          type="button"
          onClick={handleLocation}
          className="mt-5 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-700"
        >
          {locationStatus === 'loading'
            ? 'Getting Location...'
            : 'Use My Current Location'}
        </button>

        {locationStatus === 'success' && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <p className="font-semibold text-emerald-700">
              ✓ Location captured
            </p>

            <p className="mt-1 text-sm text-emerald-600">
              Your current location has been detected successfully.
            </p>
          </div>
        )}

        {locationError && (
          <p className="mt-3 text-sm text-red-600">
            {locationError}
          </p>
        )}
      </div>

      {/* Saved Address */}
      {!loadingAddress && savedAddress && (
        <div className="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
          <div className="flex items-start gap-3">
            <div className="text-2xl">✓</div>

            <div className="flex-1">
              <h2 className="font-bold text-emerald-800">
                Saved Address
              </h2>

              <p className="mt-2 text-sm leading-6 text-emerald-700">
                {formatSavedAddress(savedAddress)}
              </p>

              <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm font-semibold text-slate-700">
                <input
                  type="checkbox"
                  checked={useSavedAddress}
                  onChange={(event) =>
                    setUseSavedAddress(event.target.checked)
                  }
                  className="h-4 w-4"
                />

                Use this saved address
              </label>
            </div>
          </div>
        </div>
      )}

      {/* New Address */}
      {!useSavedAddress && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-slate-900">
              Enter Address
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              This address will be saved for your future home lab visits.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Building / House Name
              </label>

              <input
                name="building_name"
                value={addressDetails.building_name}
                onChange={handleAddressChange}
                placeholder="Sree Ram Building"
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Door / Flat Number
              </label>

              <input
                name="door_number"
                value={addressDetails.door_number}
                onChange={handleAddressChange}
                placeholder="42"
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Area / Locality
              </label>

              <input
                name="area"
                value={addressDetails.area}
                onChange={handleAddressChange}
                placeholder="Vijayalakshmi Nagar"
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Street
              </label>

              <input
                name="street"
                value={addressDetails.street}
                onChange={handleAddressChange}
                placeholder="5th Street"
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Landmark
              </label>

              <input
                name="landmark"
                value={addressDetails.landmark}
                onChange={handleAddressChange}
                placeholder="Near Vowel 14 School"
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="mb-2 block text-sm font-semibold text-slate-700">
                Pincode
              </label>

              <input
                name="pincode"
                value={addressDetails.pincode}
                onChange={handleAddressChange}
                placeholder="524004"
                maxLength={6}
                className="w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <label className="mt-5 flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked
              readOnly
              className="h-4 w-4"
            />

            Save this address for future home laboratory bookings
          </label>
        </div>
      )}

      {/* Continue */}
      <div className="mt-6 flex justify-end">
        <button
            type="button"
            onClick={() => navigate('/patient/laboratory/tests')}
            className="rounded-xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-700"
        >
            Continue to Laboratory Tests →
        </button>
      </div>
    </div>
  );
}