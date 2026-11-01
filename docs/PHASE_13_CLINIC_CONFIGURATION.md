# Phase 13 Clinic Configuration Readiness

Assessment date: 2026-10-31

Status: **Template ready; clinic facts and protected-environment state missing**

No schedule, price, service area, test availability, or clinical policy in this
document is asserted as a real clinic value. Bracketed entries require the
clinic owner.

## Capability audit

### Clinic and clinician schedules

| Need | Current capability | Gap / restriction |
|---|---|---|
| Clinic operating hours / working days | Global validated demo window; per-clinician published weekly blocks | No independent clinic-wide calendar; demo window is not verified clinic policy |
| Holidays | Per-clinician date exceptions can contain no blocks | No named clinic-wide holiday calendar or bulk closure policy |
| Breaks | Representable as gaps between non-overlapping blocks | No explicit break entity/label |
| Appointment duration | Global demo slot length; clinician schedule stores `slot_minutes` (currently 30) | Input enforces 30-minute boundaries; no service/doctor-specific duration or variable-length booking |
| Individual availability | Admin draft, preview, revision-checked publish, date exceptions, audit trail | Owner must populate/publish every clinician schedule |
| Unavailable periods / leave | Date exceptions and gaps | No leave-request/approval workflow; no reason field |
| Available slots | Derived from published blocks, booking horizon, current time, and active appointment claims | Requires connected DB/index validation and legacy preflight |
| Booking restrictions | Global 1–365 day horizon, future-slot rule, published schedule and collision rules | No lead-time, cutoff, per-service age/referral, or capacity policy |

Draft-first publication is a useful safety control: patients consume published
blocks while admins can preview uncommitted changes. Schedule blocks for clinic
and home visit cannot overlap for the same clinician; publication uses expected
revision to reject stale admin writes.

### Home visits and travel

| Need | Current capability | Gap / restriction |
|---|---|---|
| Home-visit availability | Separate home-visit schedule blocks and explicit confirmed booking path | Must be enabled/configured and entitlement/coordination policy approved |
| Travel buffers | None | Requires implementation before schedules can model travel time safely |
| Appointment spacing | Fixed common slot grid; blocks can leave manual gaps | No explicit pre/post buffer or travel-time calculation |
| Geography | One normalized configured city plus address confirmation | No radius, postcode, zone, distance, route, or boundary-map validation |
| Capacity sharing | Clinic/home bookings share atomic clinician `slot_claim` | Connected Mongo race/index validation still required |
| Provisional requests | Legacy request records remain separate and state they do not confirm time/payment | The legacy create route is retired (410); current UI uses controlled demo request/booking behavior |

Do not enable home visits for clinic use until geographic coverage, clinician
travel policy, buffers, cancellation handling, emergency limitations, and
address-verification procedure are approved.

### Laboratory

Two representations coexist:

- the active `/patient/laboratory` experience uses a fixed 12-item **demo**
  request catalogue with no price, checkout, or confirmed collection promise;
- legacy `/api/laboratory` models use database-backed tests/prices/bookings, but
  that catalogue and normal database were not inspected and legacy checkout is
  disabled in the active product flow.

| Need | Current capability | Gap / restriction |
|---|---|---|
| Catalogue and descriptions | Fixed demo IDs/names/categories/descriptions; database-backed legacy test model | No owner-approved authoritative catalogue/versioning/import process |
| Prices | Legacy model supports a price and booking snapshot | No verified prices; demo request flow intentionally has none |
| Booking requirements | Demo request validates 1–12 unique allowed tests and location/contact fields | Request is coordination only, not a confirmed booking |
| Availability | Admin can review/assign; laboratorian can prepare report | No per-test capacity, preparation, turnaround, specimen, or collection calendar |
| Cancellation | Patient may withdraw eligible request states; admin manages lifecycle | Clinic-specific cutoff/fee/refund rules not modeled |
| Report release | Laboratorian uploads/finalizes; admin publishes; patient/assigned doctor access released result | Storage/retention/malware controls require production design |

## Clinic owner configuration template

### A. Organization and environment

| Field | Owner entry |
|---|---|
| Clinic legal/display name | `[required]` |
| Deployment environment and public origins | `[required; HTTPS URLs only]` |
| Clinic IANA timezone | `[required]` |
| Booking horizon (days) | `[required: 1–365]` |
| Minimum booking lead/cancellation cutoff | `[required; implementation may be needed]` |
| Patient support/escalation contact | `[required; store outside this document if sensitive]` |

### B. Clinic calendar

| Day / exception | Open blocks | Closed/break blocks | Effective dates | Approved by |
|---|---|---|---|---|
| Monday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Tuesday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Wednesday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Thursday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Friday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Saturday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Sunday | `[HH:MM–HH:MM]` | `[HH:MM–HH:MM]` | `[date/range]` | `[owner]` |
| Holidays/closures | `[date + name]` | `Closed` | `[date]` | `[owner]` |

### C. Clinician schedule (repeat per clinician)

| Field | Owner entry |
|---|---|
| Clinician internal ID and display name | `[required]` |
| Clinic weekly blocks | `[day, start, end]` |
| Home-visit weekly blocks | `[day, start, end or disabled]` |
| Date exceptions / leave | `[date, replacement blocks or closed]` |
| Slot duration | `[currently must be 30 minutes]` |
| Services/scope | `[required; informational unless implemented]` |
| Effective date / reviewer | `[required]` |
| Draft preview accepted | `[yes/no + date]` |
| Published revision | `[system-recorded]` |

### D. Home-visit policy

| Field | Owner entry / implementation flag |
|---|---|
| Enabled | `[yes/no]` |
| Covered city | `[required if enabled; current single-city support]` |
| Covered zones/postcodes/radius | `[requires implementation beyond single city]` |
| Pre/post travel buffer | `[requires implementation]` |
| Maximum travel appointments per block/day | `[requires implementation]` |
| Address verification owner | `[required]` |
| Cancellation/no-access/late-arrival policy | `[required]` |
| Clinical eligibility and emergency disclaimer | `[required]` |

### E. Laboratory catalogue (repeat per test)

| Field | Owner entry |
|---|---|
| Stable test code | `[required]` |
| Patient-facing name/description | `[required]` |
| Category | `[required]` |
| Active/available | `[required]` |
| Price and currency | `[required only after approved billing design; do not invent]` |
| Specimen/preparation requirements | `[required]` |
| Collection location/modes | `[required]` |
| Available days/capacity | `[requires implementation]` |
| Expected turnaround | `[required]` |
| Cancellation/refund rule | `[requires approved policy/payment design]` |
| Result reviewer/release authority | `[required]` |

### F. Records, storage, and operations

| Field | Owner entry |
|---|---|
| Clinical/lab report retention | `[required]` |
| Storage, encryption, backup, restore owner | `[required]` |
| Malware scanning/content-disarm policy | `[required; implementation needed]` |
| Audit-log retention and reviewers | `[required]` |
| Appointment/payment reconciliation owner | `[required]` |
| Downtime/manual booking procedure | `[required]` |
| Privacy incident and access-review procedure | `[required]` |

## Readiness conclusion

The application can model and publish basic per-clinician weekly schedules and
date exceptions and can derive collision-safe slots. It does not yet represent
travel buffers, a clinic-wide calendar, flexible durations, or operational lab
capacity. Clinic configuration is therefore **Requires owner decision**, with
targeted implementation required for travel and production laboratory policies.
