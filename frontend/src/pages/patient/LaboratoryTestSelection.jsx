import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { laboratoryTests } from '../../data/laboratoryTests';

export default function LaboratoryTestSelection() {
  const navigate = useNavigate();

  const [selectedTests, setSelectedTests] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [sortOrder, setSortOrder] = useState('az');

  const categories = useMemo(() => {
    const uniqueCategories = [
      ...new Set(laboratoryTests.map((test) => test.category)),
    ];

    return ['All', ...uniqueCategories.sort()];
  }, []);

  const filteredTests = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();

    let results = laboratoryTests.filter((test) => {
      const matchesSearch =
        !search ||
        test.name.toLowerCase().includes(search) ||
        test.description.toLowerCase().includes(search) ||
        test.category.toLowerCase().includes(search);

      const matchesCategory =
        selectedCategory === 'All' ||
        test.category === selectedCategory;

      return matchesSearch && matchesCategory;
    });

    results = [...results].sort((a, b) => {
      if (sortOrder === 'az') {
        return a.name.localeCompare(b.name);
      }

      return b.name.localeCompare(a.name);
    });

    return results;
  }, [searchTerm, selectedCategory, sortOrder]);

  const toggleTest = (test) => {
    setSelectedTests((current) => {
      const exists = current.some((item) => item.id === test.id);

      if (exists) {
        return current.filter((item) => item.id !== test.id);
      }

      return [...current, test];
    });
  };

  const total = useMemo(() => {
    return selectedTests.reduce((sum, test) => sum + Number(test.price || 0), 0);
  }, [selectedTests]);

  const handleContinue = () => {
    if (selectedTests.length === 0) {
      return;
    }

    sessionStorage.setItem(
      'selected_lab_tests',
      JSON.stringify(selectedTests)
    );

    sessionStorage.setItem(
      'selected_lab_tests_total',
      String(total)
    );

    navigate('/patient/laboratory/date-time');
  };

  const clearSelection = () => {
    setSelectedTests([]);
  };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">

        {/* Header */}
        <div className="mb-8">
          <p className="text-sm font-bold uppercase tracking-wide text-cyan-700">
            Laboratory Services
          </p>

          <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                Select Laboratory Tests
                <span className="ml-2">🧪</span>
              </h1>

              <p className="mt-3 max-w-2xl text-base text-slate-600">
                Choose the laboratory tests you would like to book.
                You can select multiple tests.
              </p>
            </div>

            <div className="rounded-2xl border border-cyan-100 bg-cyan-50 px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">
                Available Tests
              </p>

              <p className="mt-1 text-2xl font-bold text-slate-900">
                {laboratoryTests.length}
              </p>
            </div>
          </div>
        </div>

        {/* Search + Filters */}
        <div className="mb-8 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">

          <div className="flex flex-col gap-4 lg:flex-row">

            {/* Search */}
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-xl text-slate-400">
                🔎
              </span>

              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search tests like CBC, clotting, glucose..."
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 py-4 pl-12 pr-4 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-100"
              />

              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm('')}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-400 hover:text-slate-700"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Sort */}
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm font-semibold text-slate-700 outline-none transition focus:border-cyan-500 focus:ring-4 focus:ring-cyan-100"
            >
              <option value="az">A–Z</option>
              <option value="za">Z–A</option>
            </select>
          </div>

          {/* Category buttons */}
          <div className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-bold text-slate-800">
                Browse by category
              </p>

              <p className="text-xs text-slate-500">
                {filteredTests.length} result
                {filteredTests.length !== 1 ? 's' : ''}
              </p>
            </div>

            <div className="flex gap-2 overflow-x-auto pb-1">
              {categories.map((category) => {
                const active = selectedCategory === category;

                return (
                  <button
                    key={category}
                    type="button"
                    onClick={() => setSelectedCategory(category)}
                    className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
                      active
                        ? 'bg-cyan-600 text-white shadow-sm'
                        : 'border border-slate-200 bg-white text-slate-600 hover:border-cyan-300 hover:bg-cyan-50 hover:text-cyan-700'
                    }`}
                  >
                    {category}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Active filters */}
        {(searchTerm || selectedCategory !== 'All') && (
          <div className="mb-5 flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-slate-600">
              Showing:
            </span>

            {searchTerm && (
              <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700">
                Search: "{searchTerm}"
              </span>
            )}

            {selectedCategory !== 'All' && (
              <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700">
                {selectedCategory}
              </span>
            )}

            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setSelectedCategory('All');
              }}
              className="text-xs font-bold text-slate-500 underline hover:text-cyan-700"
            >
              Reset filters
            </button>
          </div>
        )}

        {/* Tests */}
        {filteredTests.length > 0 ? (
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            {filteredTests.map((test) => {
              const selected = selectedTests.some(
                (item) => item.id === test.id
              );

              return (
                <button
                  key={test.id}
                  type="button"
                  onClick={() => toggleTest(test)}
                  className={`group relative overflow-hidden rounded-3xl border p-6 text-left transition-all duration-200 ${
                    selected
                      ? 'border-cyan-500 bg-cyan-50 shadow-lg shadow-cyan-100'
                      : 'border-slate-200 bg-white shadow-sm hover:-translate-y-1 hover:border-cyan-300 hover:shadow-lg'
                  }`}
                >

                  {/* Selected indicator */}
                  <div
                    className={`absolute right-5 top-5 flex h-7 w-7 items-center justify-center rounded-lg border-2 transition ${
                      selected
                        ? 'border-cyan-600 bg-cyan-600 text-white'
                        : 'border-slate-300 bg-white text-transparent'
                    }`}
                  >
                    ✓
                  </div>

                  {/* Icon */}
                  <div
                    className={`flex h-14 w-14 items-center justify-center rounded-2xl text-2xl ${
                      selected
                        ? 'bg-white'
                        : 'bg-cyan-50'
                    }`}
                  >
                    🧪
                  </div>

                  {/* Category */}
                  <div className="mt-5">
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                      {test.category}
                    </span>
                  </div>

                  {/* Name */}
                  <h2 className="mt-4 pr-8 text-lg font-bold leading-7 text-slate-900">
                    {test.name}
                  </h2>

                  {/* Description */}
                  <p className="mt-2 min-h-[48px] text-sm leading-6 text-slate-600">
                    {test.description}
                  </p>

                  {/* Bottom */}
                  <div className="mt-5 flex items-end justify-between gap-4 border-t border-slate-100 pt-4">
                    <div>
                      <p className="text-xs font-medium text-slate-400">
                        Sample
                      </p>

                      <p className="mt-1 text-sm font-semibold text-slate-600">
                        {test.sample}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-xs font-medium text-slate-400">
                        Test price
                      </p>

                      <p className="mt-1 text-xl font-bold text-cyan-700">
                        ₹{test.price}
                      </p>
                    </div>
                  </div>

                  {/* Selected label */}
                  {selected && (
                    <div className="mt-4 rounded-xl bg-cyan-600 px-3 py-2 text-center text-xs font-bold text-white">
                      ✓ Added to your tests
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
            <div className="text-5xl">🔬</div>

            <h2 className="mt-4 text-xl font-bold text-slate-900">
              No laboratory tests found
            </h2>

            <p className="mt-2 text-sm text-slate-500">
              Try another test name or choose a different category.
            </p>

            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setSelectedCategory('All');
              }}
              className="mt-5 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-bold text-white hover:bg-cyan-700"
            >
              Clear Search
            </button>
          </div>
        )}

        {/* Bottom Selection Bar */}
        <div className="sticky bottom-4 z-20 mt-8 rounded-3xl border border-slate-200 bg-white/95 p-4 shadow-xl backdrop-blur sm:p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-50 text-xl">
                🧪
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Selected Tests
                </p>

                <p className="text-lg font-bold text-slate-900">
                  {selectedTests.length} test
                  {selectedTests.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>

            <div className="flex flex-1 flex-col gap-4 sm:flex-row sm:items-center sm:justify-end">

              <div className="text-left sm:text-right">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Estimated Total
                </p>

                <p className="text-2xl font-bold text-cyan-700">
                  ₹{total}
                </p>
              </div>

              {selectedTests.length > 0 && (
                <button
                  type="button"
                  onClick={clearSelection}
                  className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
                >
                  Clear
                </button>
              )}

              <button
                type="button"
                disabled={selectedTests.length === 0}
                onClick={handleContinue}
                className="rounded-xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Continue to Date & Time →
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}