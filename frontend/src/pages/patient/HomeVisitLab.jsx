import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { setState } from './laboratoryStorageUtils';
import { ArrowRight } from 'lucide-react';

export default function HomeVisitLab() {
  const navigate = useNavigate();

  const [savedAddress, setSavedAddress] = useState(null);
  const [loadingAddress, setLoadingAddress] = useState(true);
  const [useSavedAddress, setUseSavedAddress] = useState(false);

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
          // Store the address in our laboratory booking state
          const address = response.data;
          const formattedAddress = [
            address.building_name,
            address.door_number,
            address.area,
            address.street,
            address.landmark,
            address.pincode,
          ]
            .filter(Boolean)
            .join(', ');
          setState({ savedAddress: formattedAddress });
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
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <h1 className="mt-2 text-3xl font-bold text-[#183B4A] sm:text-4xl">
            Home Sample Collection
          </h1>

          <p className="mt-3 max-w-2xl text-base text-[#60716E]">
            Our lab assistant can visit your home to collect samples for your
            selected laboratory tests.
          </p>
        </div>

        {/* Location */}
        <div className="mb-6 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
          <h2 className="text-lg font-bold text-[#183B4A]">
            Check home-visit availability
          </h2>

          <p className="mt-1 text-sm text-[#60716E]">
            Allow location access so we can check whether home sample collection
            is available in your area.
          </p>

          <button
            type="button"
            onClick={handleLocation}
            className="mt-5 w-full rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 text-sm font-semibold text-[#0F6B63] hover:bg-[#F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2"
          >
            {locationStatus === 'loading'
              ? 'Getting Location...'
              : useSavedAddress
                ? 'Change Location'
                : 'Use My Current Location'}
            <ArrowRight className="w-4 h-4" />
          </button>

          {locationStatus === 'success' && (
            <div className="mt-4 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-4">
              <p className="font-semibold text-[#183B4A]">
                ✓ Location captured
              </p>

              <p className="mt-1 text-sm text-[#60716E]">
                Your current location has been detected successfully.
              </p>
            </div>
          )}

          {locationError && (
            <p className="mt-3 text-sm text-[#60716E]">
              {locationError}
            </p>
          )}
        </div>

        {/* Saved Address */}
        {!loadingAddress && savedAddress && (
          <div className="mb-6 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#DDEFEA]">
                <span className="w-6 h-6 text-[#0F6B63]">✓</span>
              </div>

              <div className="flex-1">
                <h2 className="font-bold text-[#183B4A]">
                  Saved Address
                </h2>

                <p className="mt-2 text-sm leading-6 text-[#60716E]">
                  {formatSavedAddress(savedAddress)}
                </p>

                <label className="mt-4 flex cursor-pointer items-center gap-2 text-sm font-semibold text-[#60716E]">
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
          <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">
            <div className="mb-6">
              <h2 className="text-xl font-bold text-[#183B4A]">
                Enter Address
              </h2>

              <p className="mt-1 text-sm text-[#60716E]">
                This address will be saved for your future home lab visits.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Building / House Name
                </label>

                <input
                  name="building_name"
                  value={addressDetails.building_name}
                  onChange={handleAddressChange}
                  placeholder="Sree Ram Building"
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Door / Flat Number
                </label>

                <input
                  name="door_number"
                  value={addressDetails.door_number}
                  onChange={handleAddressChange}
                  placeholder="42"
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Area / Locality
                </label>

                <input
                  name="area"
                  value={addressDetails.area}
                  onChange={handleAddressChange}
                  placeholder="Vijayalakshmi Nagar"
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Street
                </label>

                <input
                  name="street"
                  value={addressDetails.street}
                  onChange={handleAddressChange}
                  placeholder="5th Street"
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Landmark
                </label>

                <input
                  name="landmark"
                  value={addressDetails.landmark}
                  onChange={handleAddressChange}
                  placeholder="Near Vowel 14 School"
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm font-semibold text-[#60716E]">
                  Pincode
                </label>

                <input
                  name="pincode"
                  value={addressDetails.pincode}
                  onChange={handleAddressChange}
                  placeholder="524004"
                  maxLength={6}
                  className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[#0F6B63]/70 focus:ring-[#0F6B63]/20"
                />
              </div>
            </div>

            <label className="mt-5 flex items-center gap-2 text-sm text-[#60716E]">
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
            onClick={() => {
              let addressToStore = '';
              if (useSavedAddress) {
                addressToStore = formatSavedAddress(savedAddress);
              } else {
                addressToStore = formatSavedAddress(addressDetails);
              }
              setState({ visitType: 'home', savedAddress: addressToStore });
              navigate('/patient/laboratory/tests');
            }}
            className="mt-6 w-full rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 text-sm font-semibold text-[#0F6B63] hover:bg-[#F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2"
          >
            Continue to Laboratory Tests →
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}