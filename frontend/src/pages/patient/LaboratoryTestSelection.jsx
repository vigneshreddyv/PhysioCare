import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import { laboratoryTests } from '../../data/laboratoryTests';
import { getState, setState } from './laboratoryStorageUtils';
import { Search, TestTube, Microscope, ArrowRight, ArrowLeft } from 'lucide-react';

export default function LaboratoryTestSelection() {
  const navigate = useNavigate();

  const [selectedTests, setSelectedTests] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [sortOrder, setSortOrder] = useState('az');

  // Load diagnostic tests from backend
  const { data: dbTests = [] } = useQuery({
    queryKey: ['laboratory-tests'],
    queryFn: async () => {
      const response = await api.get('/laboratory/tests');
      return response.data;
    },
    retry: 1
  });

  // Adapt backend models to frontend ID keys with local list fallback
  const activeTests = useMemo(() => {
    if (dbTests && dbTests.length > 0) {
      return dbTests.map((test) => ({
        ...test,
        id: test.test_id || test.id
      }));
    }
    return laboratoryTests;
  }, [dbTests]);

  // Initialize selectedTests from storage on mount
  useEffect(() => {
    const state = getState();
    if (state && Array.isArray(state.selectedTests)) {
      setSelectedTests(state.selectedTests);
    }
  }, []);

  // Persist selectedTests to storage whenever it changes
  useEffect(() => {
    setState({ selectedTests });
  }, [selectedTests]);

  const categories = useMemo(() => {
    const uniqueCategories = [
      ...new Set(activeTests.map((test) => test.category)),
    ];

    return ['All', ...uniqueCategories.sort()];
  }, [activeTests]);

  const filteredTests = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();

    let results = activeTests.filter((test) => {
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
  }, [activeTests, searchTerm, selectedCategory, sortOrder]);

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

    navigate('/patient/laboratory/date-time');
  };

  const clearSelection = () => {
    setSelectedTests([]);
  };

  return (
    <div className="min-h-screen bg-[#F7F4ED] px-4 py-12">
      <div className="mx-auto max-w-4xl">

        {/* Header */}
        <div className="mb-8">
          <button
            type="button"
            onClick={() => navigate('/patient/dashboard')}
            className="inline-flex items-center gap-2 mb-4 px-3 py-2.5 -ml-3 rounded-xl text-sm font-bold text-[#60716E] hover:text-[#1F4B45] hover:bg-[#EEF5F1]/60 transition-colors min-h-[44px]"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>

          <p className="text-sm font-semibold uppercase tracking-wider text-[#60716E]">
            LABORATORY CARE
          </p>

          <div className="mt-2 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
            <div>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-[#1E2A2B] sm:text-4xl">
                Select Laboratory Tests
              </h1>

              <p className="mt-6 max-w-xl text-base text-[#60716E] mx-auto">
                Choose the laboratory tests you would like to book.
                You can select multiple tests.
              </p>
            </div>

            <div className="rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                Available Tests
              </p>

              <p className="mt-1 text-2xl font-bold text-[#1E2A2B]">
                {laboratoryTests.length}
              </p>
            </div>
          </div>
        </div>

        {/* Progress Tracker */}
        <div className="mb-8 rounded-2xl border border-[#E5E0D6]/50 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center text-xs font-bold text-[#1E2A2B]">
              <span className="flex items-center gap-2">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#1F4B45] text-white text-xs font-black">1</span>
                Step 1 of 4
              </span>
              <span className="text-[#1F4B45]">Select Tests</span>
            </div>
            <div className="w-full bg-[#E5E0D6]/40 h-1.5 rounded-full overflow-hidden flex gap-1">
              {[1, 2, 3, 4].map((s) => (
                <div 
                  key={s} 
                  className={`h-full flex-1 transition-all duration-300 ${
                    s <= 1 ? 'bg-[#1F4B45]' : 'bg-[#E5E0D6]/30'
                  }`} 
                />
              ))}
            </div>
          </div>
        </div>

        {/* Search + Filters */}
        <div className="mb-6 rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6">

          <div className="flex flex-col gap-4 lg:flex-row">

            {/* Search */}
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 flex h-4 w-4 items-center justify-center text-[#60716E]">
                <Search className="w-4 h-4" />
              </span>

              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search tests like CBC, clotting, glucose..."
                className="w-full rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 outline-none text-[#60716E] focus:border-[#1F4B45]/70 focus:ring-[#1F4B45]/20"
              />

              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-[#60716E] hover:text-[#1F4B45]/80"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Sort */}
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
              className="rounded-xl border border-[#E5E0D6]/50 bg-white px-4 py-3 text-sm font-semibold text-[#60716E] outline-none transition focus:border-[#1F4B45]/70 focus:ring-[#1F4B45]/20"
            >
              <option value="az">A–Z</option>
              <option value="za">Z–A</option>
            </select>
          </div>

          {/* Category buttons */}
          <div className="mt-5">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-[#1E2A2B]">
                Browse by category
              </p>

              <p className="text-xs text-[#60716E]">
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
                        ? 'bg-[#1F4B45] text-white'
                        : 'border border-[#E5E0D6]/50 bg-white text-[#60716E] hover:border-[#1F4B45]/50 hover:bg-[#1F4B45]/10 hover:text-[#1F4B45]'
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
            <span className="text-sm font-semibold text-[#60716E]">
              Showing:
            </span>

            {searchTerm && (
              <span className="rounded-full bg-[#F7F4ED]/50 px-3 py-1 text-xs font-semibold text-[#1E2A2B]">
                Search: "{searchTerm}"
              </span>
            )}

            {selectedCategory !== 'All' && (
              <span className="rounded-full bg-[#F7F4ED]/50 px-3 py-1 text-xs font-semibold text-[#1E2A2B]">
                {selectedCategory}
              </span>
            )}

            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setSelectedCategory('All');
              }}
              className="text-xs font-bold text-[#60716E] underline hover:text-[#1F4B45]/80"
            >
              Reset filters
            </button>
          </div>
        )}

        {/* Tests */}
        {filteredTests.length > 0 ? (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {filteredTests.map((test) => {
              const selected = selectedTests.some(
                (item) => item.id === test.id
              );

              return (
                <button
                  key={test.id}
                  type="button"
                  onClick={() => toggleTest(test)}
                  className={
                    selected
                      ? "group relative overflow-hidden rounded-2xl border border-[#1F4B45] bg-[#EEF5F1]/50 p-6 text-left transition-all duration-200 hover:bg-[#EEF5F1]/70"
                      : "group relative overflow-hidden rounded-2xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 p-6 text-left transition-all duration-200 hover:bg-[#F7F4ED]/70"
                  }
                >

                  {/* Selected indicator */}
                  <div className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-xl border-2 transition border-[#1F4B45] bg-[#1F4B45] text-[#F7F4ED]">
                    ✓
                  </div>

                  {/* Icon */}
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEF5F1]">
                    <TestTube className="w-5 h-5 text-[#1F4B45]" />
                  </div>

                  {/* Category */}
                  <div className="mt-4">
                    <span className="rounded-full bg-[#F7F4ED]/50 px-3 py-1 text-xs font-semibold text-[#60716E]">
                      {test.category}
                    </span>
                  </div>

                  {/* Name */}
                  <h2 className="mt-3 text-xl font-bold text-[#1E2A2B]">
                    {test.name}
                  </h2>

                  {/* Description */}
                  <p className="mt-2 text-base text-[#60716E]">
                    {test.description}
                  </p>

                  {/* Bottom */}
                  <div className="mt-4 flex items-end justify-between gap-4 border-t border-[#E5E0D6]/50 pt-4">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                        Sample
                      </p>

                      <p className="mt-1 text-base font-semibold text-[#1E2A2B]">
                        {test.sample}
                      </p>
                    </div>

                    <div className="text-right">
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                        Test price
                      </p>

                      <p className="mt-1 text-2xl font-bold text-[#1F4B45]">
                        ₹{test.price}
                      </p>
                    </div>
                  </div>

                  {/* Selected label */}
                  {selected && (
                    <div className="mt-3 rounded-xl bg-[#1F4B45]/20 px-3 py-2 text-center text-xs font-semibold text-[#1F4B45]">
                      ✓ Added to your tests
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        ) : (
          <div className="rounded-2xl border border-[#E5E0D6]/50 dashed bg-[#F7F4ED]/50 px-6 py-12 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#EEF5F1]">
              <Microscope className="w-6 h-6 text-[#60716E]" />
            </div>

            <h2 className="mt-4 text-2xl font-bold text-[#1E2A2B]">
              No laboratory tests found
            </h2>

            <p className="mt-2 text-base text-[#60716E]">
              Try another test name or choose a different category.
            </p>

            <button
              type="button"
              onClick={() => {
                setSearchTerm('');
                setSelectedCategory('All');
              }}
              className="mt-5 w-full rounded-xl border border-[#E5E0D6]/50 bg-[#F7F4ED]/50 px-5 py-3 text-sm font-semibold text-[#60716E] hover:bg-[#F7F4ED]/70"
            >
              Clear Search
            </button>
          </div>
        )}

        {/* Bottom Selection Bar */}
        <div className="sticky bottom-[80px] lg:bottom-4 z-20 mt-6 rounded-2xl border border-[#E5E0D6] bg-white shadow-lg p-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

            <div className="flex items-center gap-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#EEF5F1]">
                <TestTube className="w-4 h-4 text-[#1F4B45]" />
              </div>

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  Selected Tests
                </p>

                <p className="text-lg font-bold text-[#1E2A2B]">
                  {selectedTests.length} test
                  {selectedTests.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>

            <div className="flex flex-1 flex-col gap-4 sm:flex-row sm:items-center sm:justify-end">

              <div className="text-left sm:text-right">
                <p className="text-xs font-semibold uppercase tracking-wide text-[#60716E]">
                  Estimated Total
                </p>

                <p className="text-2xl font-bold text-[#1F4B45]">
                  ₹{total}
                </p>
              </div>

              {selectedTests.length > 0 && (
                <button
                  type="button"
                  onClick={clearSelection}
                  className="rounded-xl border border-[#E5E0D6]/50 px-4 py-3 text-sm font-semibold text-[#60716E] transition hover:bg-[#F7F4ED]/70"
                >
                  Clear
                </button>
              )}

              <button
                type="button"
                disabled={selectedTests.length === 0}
                onClick={handleContinue}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#1F4B45] px-6 py-3.5 text-sm font-extrabold text-white shadow-sm transition hover:bg-[#17352F] disabled:cursor-not-allowed disabled:opacity-50 min-h-[48px]"
              >
                Continue to Date & Time
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}