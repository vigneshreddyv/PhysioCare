# Physiocare UI Modernization - Laboratory Phase 2 Plan

## HomeVisitLab.jsx Redesign Plan

### Changes to Make:
1. **Container Styling**
   - Change outer container: `min-h-screen bg-slate-50 px-6 py-10` → `min-h-screen bg-[F7F4ED] px-4 py-12`
   - Change inner container: `mx-auto max-w-6xl` → `mx-auto max-w-4xl`

2. **Header Styling**
   - Contextual label: 
     - Text: `HOME VISIT LAB TEST` → `LABORATORY CARE`
     - Classes: `text-sm font-semibold text-emerald-700` → `text-sm font-semibold uppercase tracking-wider text-[60716E]`
   - Heading:
     - Classes: `mt-2 text-3xl font-bold text-slate-900 sm:text-4xl` → `mt-4 text-3xl font-bold tracking-tight text-[183B4A] sm:text-4xl`
   - Description:
     - Classes: `mt-3 max-w-2xl text-base text-slate-600` → `mt-6 max-w-xl text-base text-[60716E] mx-auto`

3. **Location Section**
   - Container: 
     - Classes: `mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm` → `mb-6 rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6`
   - Heading: `text-lg font-bold text-slate-900` → `text-lg font-bold text-[183B4A]`
   - Description: `mt-1 text-sm text-slate-500` → `mt-1 text-sm text-[60716E]`
   - Button:
     - Classes: `mt-5 rounded-xl bg-cyan-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-cyan-700` → 
       `mt-5 w-full rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6 text-sm font-semibold text-[0F6B63] hover:bg-[F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2`
     - Add ArrowRight icon after text
   - Success Message:
     - Container: `mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4` → `mt-4 rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-4`
     - Text: `font-semibold text-emerald-700` → `font-semibold text-[183B4A]`
     - Text: `mt-1 text-sm text-emerald-600` → `mt-1 text-sm text-[60716E]`
   - Error Message:
     - Classes: `mt-3 text-sm text-red-600` → `mt-3 text-sm text-[60716E]`

4. **Saved Address Section**
   - Container: 
     - Classes: `mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-6` → `mb-6 rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6`
   - Checkmark Icon: 
     - `text-2xl` → `flex h-10 w-10 items-center justify-center rounded-xl bg-[DDEFEA]` with inner `span className="w-6 h-6 text-[0F6B63]"`
   - Heading: `font-bold text-emerald-800` → `font-bold text-[183B4A]`
   - Description: `mt-2 text-sm leading-6 text-emerald-700` → `mt-2 text-sm leading-6 text-[60716E]`
   - Checkbox Label: 
     - Classes: `mt-4 flex cursor-pointer items-center gap-2 text-sm font-semibold text-slate-700` → `mt-4 flex cursor-pointer items-center gap-2 text-sm font-semibold text-[60716E]`
     - Keep input functionality identical

5. **New Address Section**
   - Container: 
     - Classes: `rounded-2xl border border-slate-200 bg-white p-6 shadow-sm` → `rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6`
   - Heading: `text-xl font-bold text-slate-900` → `text-xl font-bold text-[183B4A]`
   - Description: `mt-1 text-sm text-slate-500` → `mt-1 text-sm text-[60716E]`
   - Input Labels: 
     - Classes: `mb-2 block text-sm font-semibold text-slate-700` → `mb-2 block text-sm font-semibold text-[60716E]`
   - Inputs:
     - Classes: `w-full rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-cyan-500` → 
       `w-full rounded-xl border border-[E5E0D6]/50 bg-white px-4 py-3 outline-none focus:border-[0F6B63]/70 focus:ring-[0F6B63]/20`
   - Checkbox Label:
     - Classes: `mt-5 flex items-center gap-2 text-sm text-slate-600` → `mt-5 flex items-center gap-2 text-sm text-[60716E]`
     - Keep input functionality identical (checked, readOnly)

6. **Continue Button**
   - Classes: 
     - `rounded-xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-700` → 
       `mt-6 w-full rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6 text-sm font-semibold text-[0F6B63] hover:bg-[F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2`
   - Add ArrowRight icon after text
   - Keep onClick handler identical:
     ```javascript
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
     ```

### Protected Functionality:
- All state variables and setters preserved
- `useEffect` for fetching saved address unchanged
- `handleLocation`, `handleAddressChange`, `formatSavedAddress` unchanged
- `setState` calls for address storage unchanged
- Navigation destination unchanged (`/patient/laboratory/tests`)
- visitType setting unchanged ('home')

## ClinicLaboratoryVisit.jsx Redesign Plan

### Changes to Make:
1. **Container Styling**
   - Change outer container: `min-h-screen bg-slate-50 px-6 py-10` → `min-h-screen bg-[F7F4ED] px-4 py-12`
   - Change inner container: `mx-auto max-w-6xl` → `mx-auto max-w-4xl`

2. **Header Styling**
   - Contextual label: 
     - Text: `CLINIC VISIT LAB TEST` → `LABORATORY CARE`
     - Classes: `text-sm font-semibold text-cyan-700` → `text-sm font-semibold uppercase tracking-wider text-[60716E]`
   - Heading:
     - Classes: `mt-2 text-4xl font-bold text-slate-900` → `mt-4 text-3xl font-bold tracking-tight text-[183B4A] sm:text-4xl`
   - Description:
     - Classes: `mt-3 max-w-2xl text-base leading-7 text-slate-600` → `mt-6 max-w-xl text-base text-[60716E] mx-auto`

3. **Main Card**
   - Container:
     - Classes: `mt-10 rounded-3xl border border-slate-200 bg-white p-8 shadow-sm` → 
       `mt-6 rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6`
   - Heading: `text-2xl font-bold text-slate-900` → (removed, replaced with section below)
   - Description: `mt-3 max-w-2xl text-slate-600` → (removed, replaced with section below)

4. **"What happens next?" Section**
   - Container: 
     - Classes: `mt-8 rounded-2xl border border-cyan-100 bg-cyan-50 p-6` → 
       `mt-4 rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-4`
   - Heading: `font-bold text-slate-900` → `font-bold text-[183B4A]`
   - List Items:
     - Classes: `mt-3 space-y-2 text-sm text-slate-600` → `mt-3 space-y-2 text-sm text-[60716E]`
     - Keep checkmark symbols (✓) unchanged

5. **Continue Button**
   - Classes: 
     - `rounded-xl bg-cyan-600 px-6 py-3 text-sm font-bold text-white transition hover:bg-cyan-700` → 
       `mt-6 w-full rounded-2xl border border-[E5E0D6]/50 bg-[F7F4ED]/50 p-6 text-sm font-semibold text-[0F6B63] hover:bg-[F7F4ED]/70 transition-colors duration-200 flex items-center justify-center gap-2`
   - Add ArrowRight icon after text
   - Keep onClick handler identical:
     ```javascript
     onClick={() => {
       // Store visit type in our storage system
       setState({ visitType: 'clinic' });
       navigate('/patient/laboratory/tests');
     }}
     ```

### Protected Functionality:
- `setState` call for visitType unchanged ('clinic')
- Navigation destination unchanged (`/patient/laboratory/tests`)
- No state variables or effects to preserve (simple component)

## Verification Steps:
1. Run `npm run build` to ensure no build errors
2. Run `npm run lint` to ensure no new lint warnings
3. Verify git diff shows only className and text changes in the two target files
4. Confirm no changes to:
   - laboratoryStorageUtils.jsx
   - LaboratoryReview.jsx
   - LaboratoryPayment.jsx
   - LaboratorySuccess.jsx
   - App.jsx routes
   - Any other files

## Design System Compliance:
- Colors: 
  - Deep Teal #0F6B63 → text-[0F6B63]
  - Deep Navy #183B4A → text-[183B4A]
  - Warm Cream #F7F4ED → bg-[F7F4ED] and bg-[F7F4ED]/50
  - Soft Sage #EEF5F1 → text-[60716E] (muted text)
  - Soft Teal #DDEFEA → bg-[DDEFEA]
  - Warm Border #E5E0D6 → border-[E5E0D6]/50
- Typography hierarchy matches PatientDashboard and LaboratoryTests
- Button styling consistent with LaboratoryTests.jsx
- Card styling consistent with PatientDashboard service cards
- Responsive behavior: container max-width and padding appropriate for mobile/desktop
- Accessibility: semantic button elements, preserved labels, focus indicators via outline-none and ring