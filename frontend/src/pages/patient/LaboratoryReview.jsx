import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../services/api';

export default function LaboratoryReview() {
  const navigate = useNavigate();

  const [savedAddress, setSavedAddress] = useState('');
  const [addressLoading, setAddressLoading] = useState(true);

useEffect(() => {
  const loadAddress = async () => {
    try {
      const response = await api.get('/users/me/address');

      console.log('ADDRESS API STATUS:', response.status);
      console.log('ADDRESS API RESPONSE:', response.data);

      const data = response.data;

const address = data
  ? [
      data.building_name,
      data.door_number,
      data.area,
      data.street,
      data.landmark,
      data.pincode,
    ]
      .filter(Boolean)
      .join(', ')
  : '';

setSavedAddress(address);

    } catch (error) {
      console.error('Failed to load saved address:', error);
      setSavedAddress('');
    } finally {
      setAddressLoading(false);
    }
  };

  loadAddress();
}, []);

  const selectedTests = useMemo(() => {
    try {
      return JSON.parse(
        sessionStorage.getItem('selected_lab_tests') || '[]'
      );
    } catch {
      return [];
    }
  }, []);

  const total = Number(
    sessionStorage.getItem('selected_lab_tests_total') || 0
  );

  const visitType =
    sessionStorage.getItem('laboratory_visit_type') || 'home';

  const selectedDate =
    sessionStorage.getItem('laboratory_selected_date') || '';

  const selectedTime =
    sessionStorage.getItem('laboratory_selected_time') || '';

  const formattedDate = selectedDate
    ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString(
        'en-IN',
        {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        }
      )
    : 'Not selected';

  const handleContinue = () => {
    sessionStorage.setItem(
      'laboratory_booking_ready',
      'true'
    );

    navigate('/patient/laboratory/payment');
  };

  return (
  <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

    {/* Header */}
    <div className="mb-8">
      <p className="text-sm font-bold uppercase tracking-wide text-cyan-700">
        Laboratory Services
      </p>

      <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
        Review Your Booking
      </h1>

      <p className="mt-3 max-w-2xl text-base text-slate-600">
        Check your laboratory tests, collection method, date and
        time before proceeding to payment.
      </p>
    </div>

        {/* Progress */}
        <div className="mb-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <p className="hidden text-sm font-semibold text-slate-600 sm:block">
                Tests
              </p>
            </div>

            <div className="mx-3 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                ✓
              </div>

              <p className="hidden text-sm font-semibold text-slate-600 sm:block">
                Date & Time
              </p>
            </div>

            <div className="mx-3 h-px flex-1 bg-cyan-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-cyan-600 text-sm font-bold text-white">
                3
              </div>

              <p className="text-sm font-bold text-cyan-700">
                Review
              </p>
            </div>

            <div className="mx-3 h-px flex-1 bg-slate-200" />

            <div className="hidden items-center gap-3 sm:flex">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-400">
                4
              </div>

              <p className="text-sm font-semibold text-slate-400">
                Payment
              </p>
            </div>

          </div>
        </div>

        <div className="grid w-full grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">

  {/* ================= LEFT SIDE ================= */}
  <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">

    {/* Collection Details */}
    <div className="p-6 sm:p-8">

      <div className="mb-6 flex items-start justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
            Collection Details
          </p>

          <h2 className="mt-2 text-2xl font-bold text-slate-900">
            Laboratory Appointment
          </h2>
        </div>

        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-cyan-50 text-3xl">
          {visitType === 'clinic' ? '🏥' : '🏠'}
        </div>
      </div>

      {/* Appointment information */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">

        {/* Collection Method */}
        <div className="rounded-2xl bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Collection Method
          </p>

          <p className="mt-3 text-lg font-bold text-slate-900">
            {visitType === 'clinic'
              ? 'Clinic Visit'
              : 'Home Sample Collection'}
          </p>

          <p className="mt-1 text-sm text-slate-500">
            {visitType === 'clinic'
              ? 'Complete your tests at the clinic'
              : 'Lab assistant visits your home'}
          </p>
        </div>

        {/* Date */}
        <div className="rounded-2xl bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Appointment Date
          </p>

          <p className="mt-3 text-lg font-bold text-slate-900">
            {selectedDate
  ? new Date(`${selectedDate}T00:00:00`).toLocaleDateString(
      'en-IN',
      {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
      }
    )
  : 'Not selected'}
          </p>
        </div>

        {/* Time */}
        <div className="rounded-2xl bg-slate-50 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Appointment Time
          </p>

          <p className="mt-3 text-lg font-bold text-slate-900">
            {selectedTime || 'Not selected'}
          </p>
        </div>

        {/* Location */}
        <div className="rounded-2xl bg-slate-50 p-5">

          <div className="flex items-start justify-between gap-3">

            <div className="min-w-0">

              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Location
              </p>

              <p className="mt-3 text-lg font-bold text-slate-900">
                {visitType === 'clinic'
                  ? 'PhysioCare Clinic'
                  : 'Home Address'}
              </p>

              {visitType === 'clinic' ? (
                <p className="mt-1 text-sm text-slate-500">
                  Laboratory testing facility
                </p>
              ) : (
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {savedAddress || 'No saved address found.'}
                </p>
              )}

            </div>

            {/* Edit Address */}
            {visitType !== 'clinic' && (
              <button
                type="button"
                onClick={() =>
                    navigate('/patient/profile?returnTo=laboratory-review')
                }
                className="shrink-0 rounded-lg border border-cyan-300 bg-white px-3 py-2 text-xs font-bold text-cyan-700 transition hover:bg-cyan-50"
              >
                ✎ Edit Address
              </button>
            )}

          </div>

          {visitType !== 'clinic' && !savedAddress && (
            <button
              type="button"
              onClick={() =>
                navigate('/patient/profile?returnTo=laboratory-review')
            }
              className="mt-3 rounded-lg bg-cyan-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-cyan-700"
            >
              Add Address
            </button>
          )}

        </div>

      </div>
    </div>


    {/* ================= SELECTED TESTS ================= */}

    <div className="border-t border-slate-200 p-6 sm:p-8">

      <div className="mb-5 flex items-center justify-between">

        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
            Selected Tests
          </p>

          <h2 className="mt-2 text-2xl font-bold text-slate-900">
            Your Laboratory Tests
          </h2>
        </div>

        <span className="rounded-full bg-cyan-50 px-4 py-2 text-xs font-bold text-cyan-700">
          {selectedTests.length} test
          {selectedTests.length !== 1 ? 's' : ''}
        </span>

      </div>


      {/* Wide test list */}
      <div className="space-y-3">

        {selectedTests.map((test, index) => (

          <div
            key={test.id}
            className="flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:border-cyan-200 hover:bg-cyan-50/30"
          >

            {/* Icon */}
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-white text-2xl shadow-sm">
              🧪
            </div>

            {/* Test information */}
            <div className="min-w-0 flex-1">

              <p className="text-base font-bold text-slate-900">
                {index + 1}. {test.name}
              </p>

              <p className="mt-1 text-sm text-slate-500">
                {test.sample}
              </p>

            </div>

            {/* Price */}
            <p className="shrink-0 text-lg font-bold text-cyan-700">
              ₹{test.price}
            </p>

          </div>

        ))}

      </div>


      {/* Change selected tests */}
      <button
        type="button"
        onClick={() =>
          navigate('/patient/laboratory/tests')
        }
        className="mt-5 text-sm font-bold text-cyan-700 transition hover:text-cyan-800"
      >
        ← Change selected tests
      </button>

    </div>

  </div>


  {/* ================= RIGHT SIDE ================= */}

  <div className="h-fit rounded-3xl border border-slate-200 bg-white p-7 shadow-sm lg:sticky lg:top-6">

    <p className="text-xs font-bold uppercase tracking-wide text-cyan-700">
      Payment Summary
    </p>

    <h2 className="mt-2 text-2xl font-bold text-slate-900">
      Booking Total
    </h2>


    {/* Test prices */}
    <div className="mt-6 space-y-4">

      {selectedTests.map((test) => (

        <div
          key={test.id}
          className="flex items-start justify-between gap-4"
        >

          <p className="text-sm leading-6 text-slate-600">
            {test.name}
          </p>

          <p className="shrink-0 text-sm font-bold text-slate-900">
            ₹{test.price}
          </p>

        </div>

      ))}

    </div>


    {/* Divider */}
    <div className="my-6 border-t border-slate-200" />


    {/* Total */}
    <div className="flex items-center justify-between">

      <p className="text-lg font-bold text-slate-700">
        Total
      </p>

      <p className="text-3xl font-bold text-cyan-700">
        ₹{total}
      </p>

    </div>


    {/* Secure booking */}
    <div className="mt-6 rounded-2xl bg-emerald-50 p-5">

      <div className="flex gap-3">

        <div className="text-xl">
          🔒
        </div>

        <div>
          <p className="text-sm font-bold text-emerald-700">
            Secure booking
          </p>

          <p className="mt-1 text-xs leading-5 text-emerald-700">
            Your booking information is securely processed
            and shared only with the relevant healthcare team.
          </p>
        </div>

      </div>

    </div>


    {/* Payment button */}
    <button
      type="button"
      onClick={handleContinue}
      disabled={
        selectedTests.length === 0 ||
        !selectedDate ||
        !selectedTime ||
        (visitType !== 'clinic' && !savedAddress)
      }
      className="mt-6 w-full rounded-xl bg-cyan-600 px-5 py-4 text-sm font-bold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-300"
    >
      Proceed to Payment →
    </button>


    {/* Change Date & Time */}
    <button
      type="button"
      onClick={() =>
        navigate('/patient/laboratory/date-time')
      }
      className="mt-3 w-full rounded-xl border border-slate-200 px-5 py-3.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
    >
      ← Change Date & Time
    </button>

  </div>
</div>
</div>
  );
}