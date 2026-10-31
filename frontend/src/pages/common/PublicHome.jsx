import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { sourceWordingReview, treatmentCatalog } from '../../content/physioTreatments';
import movementHero from '../../assets/physiocare-movement-hero.webp';
import guidedMobility from '../../assets/physiocare-guided-mobility.webp';
import api from '../../services/api';
import Modal from '../../components/common/Modal';

const categoryIcons = {
  musculoskeletal: 'accessibility_new',
  neurological: 'neurology',
  paediatric: 'child_care',
  vestibular: 'balance',
  'chronic-pain': 'vital_signs',
};

export default function PublicHome() {
  const location = useLocation();
  const [activeCategory, setActiveCategory] = useState(treatmentCatalog[0].id);
  const [query, setQuery] = useState('');
  const [doctorQuery, setDoctorQuery] = useState('');
  const [selectedDoctor, setSelectedDoctor] = useState(null);

  const selectedCategory = treatmentCatalog.find((category) => category.id === activeCategory) || treatmentCatalog[0];
  const normalizedQuery = query.trim().toLowerCase();
  const visibleGroups = useMemo(() => selectedCategory.groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.toLowerCase().includes(normalizedQuery)),
    }))
    .filter((group) => group.items.length > 0), [normalizedQuery, selectedCategory]);
  const visibleCount = visibleGroups.reduce((total, group) => total + group.items.length, 0);
  const {
    data: publicDoctors = [],
    isLoading: doctorsLoading,
    isError: doctorsError,
    refetch: refetchDoctors,
  } = useQuery({
    queryKey: ['publicDoctors'],
    queryFn: async () => {
      const response = await api.get('/users/public/doctors');
      return response.data;
    },
  });
  const normalizedDoctorQuery = doctorQuery.trim().toLowerCase();
  const visibleDoctors = useMemo(() => publicDoctors.filter((doctor) => (
    [
      doctor.full_name,
      doctor.specialization,
      doctor.qualifications,
      ...(doctor.specialties || []),
    ]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(normalizedDoctorQuery))
  )), [normalizedDoctorQuery, publicDoctors]);

  useEffect(() => {
    if (!location.hash) return undefined;

    const targetId = decodeURIComponent(location.hash.slice(1));
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: 'start' });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [location.hash]);

  return (
    <div className="public-physio">
      <header className="public-physio__nav">
        <Link to="/" className="public-physio__brand" aria-label="PhysioCare home">
          <span className="material-symbols-outlined" aria-hidden="true">spa</span>
          <span>PhysioCare</span>
        </Link>
        <nav aria-label="Public navigation">
          <a href="#services">How it works</a>
          <a href="#doctors">Doctors</a>
          <a href="#what-we-treat">What we treat</a>
          <a href="#clinic">Clinic</a>
        </nav>
        <div className="public-physio__auth-actions">
          <Link to="/login">Sign in</Link>
          <Link to="/register">Create account</Link>
        </div>
      </header>

      <main>
        <section className="public-physio__hero">
          <div className="public-physio__hero-copy">
            <p className="public-physio__eyebrow">A clearer way into physiotherapy care</p>
            <h1>Find the right clinician. Keep every visit connected.</h1>
            <p>Explore the clinic’s listed physiotherapists, choose an available session, and return to one private place for your appointment record.</p>
            <ul className="public-physio__hero-proofs" aria-label="Portal highlights">
              <li><span className="material-symbols-outlined" aria-hidden="true">verified_user</span><strong>Private portal</strong><small>Your account and visit history stay behind sign-in.</small></li>
              <li><span className="material-symbols-outlined" aria-hidden="true">schedule</span><strong>Clear timing</strong><small>Clinic sessions are shown in India Standard Time.</small></li>
            </ul>
            <div className="public-physio__hero-actions">
              <Link to="/register">Start with a patient account <span aria-hidden="true">→</span></Link>
              <a href="#doctors">Meet the care team</a>
            </div>
            <p className="public-physio__hero-note"><span className="material-symbols-outlined" aria-hidden="true">info</span>Eligible patients can choose a Nellore home-visit slot; demo hours are not verified clinic hours.</p>
          </div>
          <div className="public-physio__hero-visual">
            <span className="public-physio__orbit public-physio__orbit--one" aria-hidden="true" />
            <span className="public-physio__orbit public-physio__orbit--two" aria-hidden="true" />
            <img src={movementHero} alt="" />
            <aside aria-label="Available portal features">
              <span className="material-symbols-outlined" aria-hidden="true">event_available</span>
              <div>
                <small>YOUR NEXT STEP</small>
                <strong>Choose a clinician, then a time</strong>
                <span>Nothing is booked until you review and confirm.</span>
              </div>
            </aside>
          </div>
        </section>

        <section className="public-physio__care-path" aria-label="How the patient portal works">
          <p><span>01</span><strong>Discover</strong><small>Browse care areas and clinician profiles.</small></p>
          <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
          <p><span>02</span><strong>Choose</strong><small>Select a date and currently listed time.</small></p>
          <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
          <p><span>03</span><strong>Stay organised</strong><small>Return for status, history, or an eligible change.</small></p>
        </section>

        <section id="services" className="public-physio__story" aria-labelledby="story-heading">
          <figure className="public-physio__story-visual">
            <img src={guidedMobility} alt="A physiotherapist guiding a patient through a supported mobility movement" />
            <figcaption>Illustrative care scene — not a member of the clinic team.</figcaption>
            <div aria-hidden="true"><span>01</span><strong>Begin with context</strong><small>Choose by published specialty and focus area.</small></div>
          </figure>
          <div className="public-physio__story-copy">
            <p className="public-physio__eyebrow">Care, without the guesswork</p>
            <h2 id="story-heading">A practical route from first search to visit record.</h2>
            <p>PhysioCare separates discovery, booking, and follow-up so each decision is easier to understand. The portal supports the journey without replacing a clinician’s assessment.</p>
            <ol>
              <li><span>01</span><div><strong>Review the published profile</strong><small>See qualifications, experience, specialties, and biography when the clinic has provided them.</small></div></li>
              <li><span>02</span><div><strong>Choose a listed clinic time</strong><small>Availability is shown in IST and checked again when you confirm.</small></div></li>
              <li><span>03</span><div><strong>Return to your private record</strong><small>See scheduled, completed, and cancelled visits after sign-in.</small></div></li>
            </ol>
            <Link to="/register">Create a patient account <span aria-hidden="true">→</span></Link>
          </div>
        </section>

        <section className="public-physio__section public-physio__services" aria-labelledby="services-heading">
          <div className="public-physio__section-heading">
            <p className="public-physio__eyebrow">What you can do today</p>
            <h2 id="services-heading">One portal, four useful moments.</h2>
            <p>Everything shown here is supported in the current Phase 1 experience.</p>
          </div>
          <div className="public-physio__service-grid">
            <article className="public-physio__service-card public-physio__service-card--feature">
              <div><span className="material-symbols-outlined" aria-hidden="true">person_search</span><small>DISCOVER</small></div>
              <h3>Start with the clinician, not an anonymous slot.</h3>
              <p>Compare the care team by published specialty, focus areas, qualifications, experience, and professional background.</p>
              <a href="#doctors">Explore clinician profiles <span aria-hidden="true">→</span></a>
            </article>
            <article className="public-physio__service-card public-physio__service-card--aqua">
              <div><span className="material-symbols-outlined" aria-hidden="true">event_available</span><small>BOOK</small></div>
              <h3>Build a clinic booking step by step.</h3>
              <p>Choose a clinician, date, listed time, and concise visit reason before one clear confirmation.</p>
            </article>
            <article className="public-physio__service-card public-physio__service-card--warm">
              <div><span className="material-symbols-outlined" aria-hidden="true">home_health</span><small>REQUEST</small></div>
              <h3>Choose a home-visit slot clearly.</h3>
              <p>Eligible demo users may choose an available Nellore slot and confirm only after reviewing the booking details.</p>
            </article>
            <article className="public-physio__service-card public-physio__service-card--light">
              <div><span className="material-symbols-outlined" aria-hidden="true">history</span><small>REVIEW</small></div>
              <h3>Keep the visit trail close.</h3>
              <p>Upcoming and recorded visits stay together, including truthful cancellation status.</p>
            </article>
          </div>
        </section>

        <section id="care-options" className="public-physio__care-options" aria-labelledby="care-options-heading">
          <div className="public-physio__section-heading">
            <p className="public-physio__eyebrow">Two care paths, clearly separated</p>
            <h2 id="care-options-heading">Book clinic time. Request home support.</h2>
            <p>The portal keeps the difference visible so a request is never mistaken for a confirmed visit.</p>
          </div>
          <div className="public-physio__care-option-grid">
            <article>
              <span className="material-symbols-outlined" aria-hidden="true">event_available</span>
              <div><p>Clinic appointment</p><h3>Leave with a confirmed time</h3></div>
              <p>Choose a physiotherapist, date, and currently available demo slot. The resulting appointment appears in your portal in India Standard Time.</p>
              <ul><li>Currently listed availability</li><li>24-hour online cancellation window</li><li>No payment collected in the app</li></ul>
              <Link to="/login">Sign in to book <span aria-hidden="true">→</span></Link>
            </article>
            <article>
              <span className="material-symbols-outlined" aria-hidden="true">home_health</span>
              <div><p>Home-visit booking</p><h3>Choose an available slot</h3></div>
              <p>Eligible demo patients choose a clinician, date, time, address and final confirmation. No payment is collected.</p>
              <ul><li>Demo entitlement required</li><li>Pending until clinic coordination</li><li>No payment or capacity promise</li></ul>
              <Link to="/login">Sign in to book <span aria-hidden="true">→</span></Link>
            </article>
          </div>
        </section>

        <section id="doctors" className="public-physio__section public-physio__doctors" aria-labelledby="doctors-heading">
          <div className="public-physio__doctor-intro">
            <div className="public-physio__section-heading">
              <p className="public-physio__eyebrow">Clinician-led discovery</p>
              <h2 id="doctors-heading">Know who you are choosing.</h2>
              <p>Profiles come directly from the clinic staff directory. Only details published by an administrator appear here.</p>
            </div>
            <aside aria-label="Profile information explained">
              <span className="material-symbols-outlined" aria-hidden="true">badge</span>
              <div><strong>Profile details stay evidence-led</strong><small>Missing qualifications, experience, imagery, or links remain visibly unpublished rather than being invented.</small></div>
            </aside>
          </div>

          {doctorsLoading ? (
            <p className="public-physio__directory-state" role="status">Loading clinician profiles…</p>
          ) : doctorsError ? (
            <div className="public-physio__directory-state public-physio__directory-state--error" role="alert">
              <strong>Clinician profiles are temporarily unavailable.</strong>
              <span>No appointment or account data has been affected.</span>
              <button type="button" onClick={() => refetchDoctors()}>Try loading profiles again</button>
            </div>
          ) : publicDoctors.length === 0 ? (
            <p className="public-physio__directory-state" role="status">No public clinician profiles are available yet.</p>
          ) : (
            <>
              <div className="public-physio__clinician-finder">
                <label htmlFor="public-clinician-search">
                  <span className="material-symbols-outlined" aria-hidden="true">search</span>
                  <span className="sr-only">Search clinicians</span>
                  <input
                    id="public-clinician-search"
                    type="search"
                    value={doctorQuery}
                    onChange={(event) => setDoctorQuery(event.target.value)}
                    placeholder="Search by name, specialty, or focus area"
                    aria-controls="public-clinician-results"
                  />
                </label>
                <p role="status" aria-live="polite">{visibleDoctors.length} {visibleDoctors.length === 1 ? 'clinician' : 'clinicians'} shown</p>
              </div>
              {visibleDoctors.length > 0 ? (
                <div id="public-clinician-results" className="public-physio__doctor-grid">
              {visibleDoctors.map((doctor) => {
                const initials = doctor.full_name
                  .split(/\s+/)
                  .filter(Boolean)
                  .slice(0, 2)
                  .map((part) => part[0])
                  .join('')
                  .toUpperCase();
                return (
                  <article key={doctor.id} className="public-physio__doctor-card">
                    {doctor.profile_image ? (
                      <img src={doctor.profile_image} alt={`${doctor.full_name}, ${doctor.specialization}`} loading="lazy" referrerPolicy="no-referrer" />
                    ) : (
                      <span className="public-physio__doctor-avatar" aria-hidden="true">{initials}</span>
                    )}
                    <div>
                      <p>{doctor.specialization}</p>
                      <h3>{doctor.full_name}</h3>
                      {doctor.qualifications && <span className="public-physio__doctor-qualification">{doctor.qualifications}</span>}
                      <div className="public-physio__doctor-meta">
                        {doctor.years_experience != null && <span>{doctor.years_experience} years’ experience</span>}
                        {doctor.specialties?.slice(0, 2).map((specialty) => <span key={specialty}>{specialty}</span>)}
                      </div>
                      <span>{doctor.bio || 'Additional professional details have not been published yet.'}</span>
                      <button type="button" onClick={() => setSelectedDoctor(doctor)}>View profile</button>
                    </div>
                  </article>
                );
              })}
                </div>
              ) : (
                <div id="public-clinician-results" className="public-physio__directory-state" role="status">
                  <strong>No clinician profiles match “{doctorQuery.trim()}”.</strong>
                  <span>Try a name, physiotherapy specialty, or another focus area.</span>
                  <button type="button" onClick={() => setDoctorQuery('')}>Clear search</button>
                </div>
              )}
            </>
          )}
        </section>

        <section id="what-we-treat" className="public-physio__section public-physio__catalog" aria-labelledby="catalog-heading">
          <div className="public-physio__section-heading">
            <p className="public-physio__eyebrow">Client-provided catalog</p>
            <h2 id="catalog-heading">What we treat</h2>
            <p>Browse the supplied physiotherapy categories. This catalog is informational and is not a diagnosis, clinical recommendation, or promise of treatment suitability.</p>
          </div>

          <div className="public-physio__catalog-controls">
            <div className="public-physio__category-tabs" role="tablist" aria-label="Treatment categories">
              {treatmentCatalog.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  role="tab"
                  aria-selected={category.id === activeCategory}
                  onClick={() => {
                    setActiveCategory(category.id);
                    setQuery('');
                  }}
                >
                  <span className="material-symbols-outlined" aria-hidden="true">{categoryIcons[category.id] || 'medical_services'}</span>
                  <span>{category.label}</span>
                </button>
              ))}
            </div>
            <label className="public-physio__search">
              <span className="material-symbols-outlined" aria-hidden="true">search</span>
              <span className="sr-only">Search within {selectedCategory.label}</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={`Search ${selectedCategory.label.toLowerCase()}`}
              />
            </label>
          </div>

          <div className="public-physio__catalog-panel" role="tabpanel">
            <div className="public-physio__catalog-intro">
              <div>
                <h3>{selectedCategory.label}</h3>
                <p>{selectedCategory.description}</p>
              </div>
              <span>{visibleCount} {visibleCount === 1 ? 'entry' : 'entries'}</span>
            </div>

            {visibleGroups.length > 0 ? (
              <div className="public-physio__condition-groups">
                {visibleGroups.map((group) => (
                  <details key={group.label} open={visibleGroups.length === 1}>
                    <summary>
                      <span>{group.label}</span>
                      <span>{group.items.length}</span>
                    </summary>
                    <ul>
                      {group.items.map((item) => (
                        <li key={item}>
                          <span>{item}</span>
                          {sourceWordingReview.has(item) && <em title="The wording is preserved from the source and needs clinical copy review.">Source wording—review</em>}
                        </li>
                      ))}
                    </ul>
                  </details>
                ))}
              </div>
            ) : (
              <p className="public-physio__no-results" role="status">No catalog entries match “{query}” in this category.</p>
            )}

            <p className="public-physio__review-note">
              <span className="material-symbols-outlined" aria-hidden="true">fact_check</span>
              Source spellings are preserved. Labels marked “Source wording—review” require client and clinical copy review before publication.
            </p>
          </div>
        </section>

        <section className="public-physio__section public-physio__faq" aria-labelledby="faq-heading">
          <div className="public-physio__section-heading">
            <p className="public-physio__eyebrow">Before you continue</p>
            <h2 id="faq-heading">Clear answers for the current demo.</h2>
            <p>These answers reflect implemented Phase 1 behavior—not future clinic policy.</p>
          </div>
          <div className="public-physio__faq-list">
            <details><summary>Are the displayed hours final clinic hours?<span aria-hidden="true">+</span></summary><p>Administrator-published clinician schedules are shown when configured. Unconfigured clinicians continue using clearly labelled demonstration availability until the clinic confirms their days, hours, breaks, and leave.</p></details>
            <details><summary>Can I cancel a clinic appointment online?<span aria-hidden="true">+</span></summary><p>Yes, until exactly 24 hours before the appointment. Inside that window, contact the clinic. The demo applies no automatic cancellation fee.</p></details>
            <details><summary>When is a home visit confirmed?<span aria-hidden="true">+</span></summary><p>For an entitled patient, the final booking action confirms the selected available slot. Demo hours still require clinic configuration before launch, and no payment is collected.</p></details>
            <details><summary>Can I pay in PhysioCare?<span aria-hidden="true">+</span></summary><p>Razorpay Test Mode checkout is implemented but is available only when the clinic enables an authorized test merchant configuration. Live payments and production charges are not enabled.</p></details>
          </div>
        </section>

        <section id="clinic" className="public-physio__section public-physio__clinic" aria-labelledby="clinic-heading">
          <div className="public-physio__clinic-mark" aria-hidden="true"><span className="material-symbols-outlined">location_on</span></div>
          <div>
            <p className="public-physio__eyebrow">Clinic information</p>
            <h2 id="clinic-heading">Ready for verified local details.</h2>
            <p>The clinic address, phone number, opening days, service area, and public directions have not been confirmed. They remain intentionally unpublished until the client supplies them.</p>
          </div>
          <div className="public-physio__clinic-actions">
            <Link to="/login">Open the patient portal</Link>
            <Link to="/register">Create an account</Link>
          </div>
        </section>
      </main>

      <footer className="public-physio__footer">
        <div><span>PhysioCare</span><small>Patient access, clinician discovery, and appointment records.</small></div>
        <nav aria-label="Footer navigation"><a href="#services">How it works</a><a href="#doctors">Care team</a><a href="#what-we-treat">What we treat</a></nav>
        <p>Portal content requires client and clinical review before public launch.</p>
      </footer>

      <Modal
        isOpen={Boolean(selectedDoctor)}
        onClose={() => setSelectedDoctor(null)}
        title={selectedDoctor ? `${selectedDoctor.full_name} · profile` : 'Clinician profile'}
        panelClassName="public-physio__profile-modal max-w-2xl"
      >
        {selectedDoctor && (
          <article className="public-physio__profile-detail">
            <div className="public-physio__profile-heading">
              {selectedDoctor.profile_image ? (
                <img src={selectedDoctor.profile_image} alt={`${selectedDoctor.full_name}, ${selectedDoctor.specialization}`} referrerPolicy="no-referrer" />
              ) : (
                <span className="public-physio__doctor-avatar" aria-hidden="true">
                  {selectedDoctor.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}
                </span>
              )}
              <div>
                <p>{selectedDoctor.specialization}</p>
                <h3>{selectedDoctor.full_name}</h3>
                {selectedDoctor.qualifications && <span>{selectedDoctor.qualifications}</span>}
              </div>
            </div>
            <dl>
              {selectedDoctor.years_experience != null && <div><dt>Experience</dt><dd>{selectedDoctor.years_experience} years</dd></div>}
              {selectedDoctor.specialties?.length > 0 && <div><dt>Focus areas</dt><dd>{selectedDoctor.specialties.join(', ')}</dd></div>}
            </dl>
            <p>{selectedDoctor.bio || 'The clinic has not published a full professional biography for this physiotherapist.'}</p>
            {(selectedDoctor.linkedin_url || selectedDoctor.website_url) && (
              <div className="public-physio__profile-links" aria-label="Verified professional links">
                {selectedDoctor.linkedin_url && <a href={selectedDoctor.linkedin_url} target="_blank" rel="noreferrer">LinkedIn profile <span aria-hidden="true">↗</span></a>}
                {selectedDoctor.website_url && <a href={selectedDoctor.website_url} target="_blank" rel="noreferrer">Professional website <span aria-hidden="true">↗</span></a>}
              </div>
            )}
            <p className="public-physio__profile-note">Only details published by the clinic administrator are shown here. Sign in to view current appointment times.</p>
            <div className="public-physio__profile-actions">
              <Link
                to="/login"
                state={{
                  from: {
                    pathname: '/patient/book',
                    state: { bookingPreference: { doctorId: selectedDoctor.id } },
                  },
                }}
              >
                Sign in and choose a time
              </Link>
              <Link
                to="/register"
                state={{
                  from: {
                    pathname: '/patient/book',
                    state: { bookingPreference: { doctorId: selectedDoctor.id } },
                  },
                }}
              >
                Create a patient account
              </Link>
            </div>
          </article>
        )}
      </Modal>
    </div>
  );
}
