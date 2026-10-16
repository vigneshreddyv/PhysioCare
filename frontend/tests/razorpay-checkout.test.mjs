/**
 * Phase 4 Task 3 tests — Razorpay Checkout integration.
 *
 * Run with:  node --test tests/
 *
 * Two layers:
 * 1. RUNTIME tests of src/services/razorpayCheckout.js with a minimal DOM
 *    shim (script injection, once-only loading, pass-through of backend
 *    order values, success/dismiss/failure wiring).
 * 2. STRUCTURAL tests of the page sources (fake simulation removed, order
 *    endpoints called before checkout, no secrets, no fake payment ids).
 *
 * No real Razorpay script is ever fetched: the runtime layer shims
 * document/window and never performs network I/O.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(__dirname, '..', 'src');

// ---------------------------------------------------------------------------
// Minimal DOM shim (enough for razorpayCheckout.js)
// ---------------------------------------------------------------------------

function installDomShim() {
  const scripts = [];
  const realSetTimeout = globalThis.setTimeout;
  const timers = [];

  // Capture timers so the loader's safety-net timeout never fires after a
  // test ends (which would touch a torn-down shim).
  globalThis.setTimeout = (fn, ms) => {
    timers.push({ fn, ms });
    return timers.length;
  };

  global.document = {
    querySelector: () => null, // no pre-existing script tag
    createElement: () => ({
      src: '',
      async: false,
      removed: false,
      _listeners: {},
      addEventListener(evt, fn) {
        this._listeners[evt] = fn;
      },
      remove() {
        this.removed = true;
      },
      _fire(evt) {
        this._listeners[evt]?.();
      },
    }),
    head: { appendChild: (el) => scripts.push(el) },
  };

  global.window = {
    Razorpay: undefined,
  };

  return {
    scripts,
    timers,
    fireScriptLoad() {
      scripts[0]?._fire('load');
    },
    fireScriptError() {
      scripts[0]?._fire('error');
    },
    setRazorpay(Ctor) {
      global.window.Razorpay = Ctor;
    },
    cleanup() {
      globalThis.setTimeout = realSetTimeout;
      delete global.document;
      delete global.window;
    },
  };
}

async function freshLoader() {
  // Bust the module cache by importing with a unique query each time.
  return import(`../src/services/razorpayCheckout.js?case=${Date.now()}-${Math.random()}`);
}

// ---------------------------------------------------------------------------
// RUNTIME TESTS
// ---------------------------------------------------------------------------

test('checkout script loads once — repeated calls inject a single script tag', async () => {
  const shim = installDomShim();
  try {
    const loader = await freshLoader();

    const p1 = loader.loadRazorpayCheckout();
    const p2 = loader.loadRazorpayCheckout();

    assert.equal(shim.scripts.length, 1, 'exactly one script tag injected');
    assert.equal(shim.scripts[0].src, 'https://checkout.razorpay.com/v1/checkout.js');

    shim.setRazorpay(function FakeRazorpay() {});
    shim.fireScriptLoad();

    await Promise.all([p1, p2]);
    // A third call after load resolves without injecting another tag.
    await loader.loadRazorpayCheckout();
    assert.equal(shim.scripts.length, 1, 'still exactly one script tag');
  } finally {
    shim.cleanup();
  }
});

test('script load failure is handled with a friendly error', async () => {
  const shim = installDomShim();
  try {
    const loader = await freshLoader();
    const promise = loader.loadRazorpayCheckout();

    shim.fireScriptError();

    await assert.rejects(promise, /couldn't open secure payment/i);
    assert.equal(shim.scripts[0].removed, true, 'failed script tag removed');
  } finally {
    shim.cleanup();
  }
});

test('script that loads without a Razorpay global rejects instead of hanging', async () => {
  const shim = installDomShim();
  try {
    const loader = await freshLoader();
    const promise = loader.loadRazorpayCheckout();

    shim.fireScriptLoad(); // loaded but window.Razorpay missing

    await assert.rejects(promise, /could not be initialized/i);
  } finally {
    shim.cleanup();
  }
});

test('Checkout receives backend order values unchanged (key/order/amount/currency)', async () => {
  const shim = installDomShim();
  try {
    const loader = await freshLoader();

    let capturedOptions = null;
    let openCalled = false;

    shim.setRazorpay(class RazorpayStub {
      constructor(options) {
        capturedOptions = options;
      }
      open() {
        openCalled = true;
      }
      on() {}
    });
    shim.fireScriptLoad();

    const backend = { keyId: 'rzp_test_backendkey', orderId: 'order_backend123', amount: 50000, currency: 'INR' };
    const success = () => {};
    const dismiss = () => {};

    await loader.openRazorpayCheckout({
      ...backend,
      description: 'Laboratory tests payment',
      prefill: { name: 'A', email: 'a@b.c' },
      onSuccess: success,
      onDismiss: dismiss,
    });

    assert.equal(openCalled, true);
    assert.equal(capturedOptions.key, backend.keyId, 'backend key_id passed through');
    assert.equal(capturedOptions.order_id, backend.orderId, 'backend order_id passed through');
    assert.equal(capturedOptions.amount, backend.amount, 'backend amount passed through unchanged');
    assert.equal(capturedOptions.currency, backend.currency, 'backend currency passed through');
    assert.deepEqual(capturedOptions.prefill, { name: 'A', email: 'a@b.c' });
  } finally {
    shim.cleanup();
  }
});

test('success handler only captures the response; dismiss and payment.failed route to onDismiss', async () => {
  const shim = installDomShim();
  try {
    const loader = await freshLoader();

    let instance = null;
    shim.setRazorpay(class RazorpayStub {
      constructor(options) {
        instance = this;
        this.options = options;
      }
      open() {}
      on(evt, fn) {
        this[`_${evt}`] = fn;
      }
    });
    shim.fireScriptLoad();

    let succeededWith = null;
    let dismissedCount = 0;
    await loader.openRazorpayCheckout({
      keyId: 'k', orderId: 'o', amount: 100, currency: 'INR',
      onSuccess: (r) => { succeededWith = r; },
      onDismiss: () => { dismissedCount += 1; },
    });

    // Success path: capture only, no state claims.
    const handler = instance.options.handler;
    assert.equal(typeof handler, 'function', 'success handler is wired');
    handler({ razorpay_payment_id: 'pay_X', razorpay_order_id: 'o', razorpay_signature: 'sig' });
    assert.deepEqual(succeededWith, {
      razorpay_payment_id: 'pay_X', razorpay_order_id: 'o', razorpay_signature: 'sig',
    });

    // modal.ondismiss routes to onDismiss.
    assert.equal(typeof instance.options.modal.ondismiss, 'function');
    instance.options.modal.ondismiss();
    assert.equal(dismissedCount, 1, 'modal dismiss routes to onDismiss');

    // payment.failed path routes to onDismiss.
    // NOTE: the event name contains a dot, so it is stored under a single
    // literal key rather than a nested object.
    instance['_payment.failed']?.({ error: { description: 'declined' } });
    assert.equal(dismissedCount, 2, 'payment.failed routes to onDismiss');
  } finally {
    shim.cleanup();
  }
});

// ---------------------------------------------------------------------------
// STRUCTURAL TESTS — page sources
// ---------------------------------------------------------------------------

function readSrc(rel) {
  return fs.readFileSync(path.join(SRC, rel), 'utf8');
}

test('laboratory fake simulation is fully removed (1.5s timer, fake ids, PATCH)', () => {
  const src = readSrc('pages/patient/LaboratoryPayment.jsx');
  assert.ok(!src.includes('setTimeout(resolve, 1500)'), '1.5s simulation removed');
  assert.ok(!/pay_\$\{Math\.random\(\)/.test(src), 'fake pay_ ids removed');
  assert.ok(!/ord_\$\{Math\.random\(\)/.test(src), 'fake ord_ ids removed');
  assert.ok(!src.includes("/payment`"), 'payment PATCH path removed');
  assert.ok(!src.includes('payment_status: \'success\''), 'simulated success mutation removed');
});

test('laboratory page calls order endpoint before opening checkout', () => {
  const src = readSrc('pages/patient/LaboratoryPayment.jsx');
  const bookingIdx = src.indexOf("api.post('/laboratory/bookings'");
  const orderIdx = src.indexOf('/laboratory/bookings/${bookingId}/payment/order');
  const openIdx = src.indexOf('openRazorpayCheckout(');
  assert.ok(bookingIdx > -1 && orderIdx > bookingIdx, 'booking created before order');
  assert.ok(openIdx > orderIdx, 'checkout opened only after the order endpoint');
  // Backend values are destructured and passed; no local amount computation.
  assert.ok(src.includes('{ key_id, order_id, amount, currency }'), 'backend order shape consumed');
  assert.ok(src.includes('amount,'), 'backend amount passed to checkout');
});

test('appointment page calls order endpoint before opening checkout', () => {
  const src = readSrc('pages/patient/BookAppointment.jsx');
  const orderIdx = src.indexOf('/appointments/${appointment.id}/payment/order');
  const openIdx = src.indexOf('openRazorpayCheckout(');
  assert.ok(orderIdx > -1, 'order endpoint called');
  assert.ok(openIdx > orderIdx, 'checkout opened only after the order endpoint');
});

test('appointment retry does not create a duplicate booking', () => {
  const src = readSrc('pages/patient/BookAppointment.jsx');
  assert.ok(src.includes("checkoutState === 'idle' &&\r\n      !razorpayPaymentResponse") ||
            (/createdAppointment &&[^]*?checkoutState === 'idle'/.test(src)),
    'retry resumes checkout with the existing appointment');
});

test('checkout success captures response only — no payment PATCH / no paid marking', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  assert.ok(!/billing_status\s*[:=]/.test(lab), 'lab page never writes billing_status');
  assert.ok(lab.includes('paymentStatus'), 'lab page tracks neutral payment status');

  const appt = readSrc('pages/patient/BookAppointment.jsx');
  assert.ok(appt.includes("setCheckoutState('verifying')"), 'neutral verifying state used');
  assert.ok(!appt.includes("status: 'confirmed'"), 'appointment never confirmed from frontend');

  // Neither page calls the fake-success PATCH.
  assert.ok(!lab.includes('api.patch('), 'lab page performs no PATCH');
  assert.ok(!appt.includes("/payment`, {"), 'appointment page performs no payment PATCH');
});

test('no Razorpay secret anywhere in the frontend', () => {
  const forbidden = /RAZORPAY_KEY_SECRET|key_secret|razorpay_secret|payment secret/i;
  const offenders = [];

  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (/\.(js|jsx|mjs)$/.test(entry.name)) {
        const text = fs.readFileSync(full, 'utf8');
        if (forbidden.test(text)) offenders.push(path.relative(SRC, full));
      }
    }
  };
  walk(SRC);

  assert.deepEqual(offenders, [], 'no secret material in frontend sources');
});

test('clinical warmth: error/dismiss messages use approved wording, min 44px targets kept', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  const appt = readSrc('pages/patient/BookAppointment.jsx');

  for (const src of [lab, appt]) {
    assert.ok(src.includes('Payment window closed'), 'dismiss message present');
    assert.ok(src.includes('open secure payment'), 'load-failure message present');
  }
  // Existing 44px+ interactive targets preserved in the lab payment page.
  assert.ok(lab.includes('min-h-[44px]'), '44px minimum target retained');
});

// ---------------------------------------------------------------------------
// TASK 4 — BACKEND VERIFICATION INTEGRATION
// ---------------------------------------------------------------------------

test('T4-1: checkout success invokes the backend verification endpoints', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');

  // Appointment: success handler calls verification with the captured values.
  const apptSuccess = appt.indexOf('onSuccess: (paymentResponse) =>');
  const apptVerifyCall = appt.indexOf('verifyAppointmentPayment(appointment, captured)');
  const apptVerifyPost = appt.indexOf('/appointments/${appointment.id}/payment/verify`');
  assert.ok(apptSuccess > -1 && apptVerifyCall > apptSuccess, 'appointment success handler triggers verification');
  assert.ok(apptVerifyPost > -1, 'appointment verify endpoint called');
  assert.ok(appt.includes('razorpay_payment_id: captured.razorpay_payment_id'), 'payment id sent to backend');
  assert.ok(appt.includes('razorpay_order_id: captured.razorpay_order_id'), 'order id sent to backend');
  assert.ok(appt.includes('razorpay_signature: captured.razorpay_signature'), 'signature sent to backend');

  // Laboratory: same wiring.
  const labVerifyPost = lab.indexOf('/laboratory/bookings/${bookingId}/payment/verify`');
  const labVerifyCall = lab.indexOf('verifyLaboratoryPayment(bookingId, captured);');
  assert.ok(labVerifyPost > -1, 'laboratory verify endpoint called');
  assert.ok(labVerifyCall > -1, 'laboratory success handler triggers verification');
});

test('T4-2: UI stays verifying until the backend verification response arrives', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  // 'verifying' is set BEFORE the verify call; the confirmation modal opens
  // only inside the success branch (after await).
  const setStateIdx = appt.indexOf("setCheckoutState('verifying')");
  const verifyCallIdx = appt.indexOf('verifyAppointmentPayment(appointment, captured)');
  const verifiedGate = appt.indexOf("response.data?.status === 'verified'");
  // Search for the modal INSIDE the verify function (after the gate), since
  // setModalOpen(true) legitimately also exists in the offline path earlier
  // in the file.
  const modalIdx = appt.indexOf('setModalOpen(true)', verifiedGate);
  assert.ok(setStateIdx > -1 && verifyCallIdx > setStateIdx, 'verifying set before verification');
  assert.ok(verifiedGate > -1 && modalIdx > verifiedGate, 'modal opens only after backend-verified response');
  // The lab page navigates to success only inside the verified branch.
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  const labGate = lab.indexOf("response.data?.status === 'verified'");
  const labNav = lab.indexOf("navigate('/patient/laboratory/success'");
  assert.ok(labGate > -1 && labNav > labGate, 'lab success navigation gated on backend response');
});

test('T4-3: verified backend response produces the confirmation UI with backend states', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  assert.ok(appt.includes("setCheckoutState('verified')"), 'appointment enters verified state');
  assert.ok(appt.includes("queryClient.invalidateQueries({ queryKey: ['appointments'] })"), 'appointment data refreshed after verification');

  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  assert.ok(lab.includes("paymentStatus: 'paid'"), 'lab success page receives backend-confirmed payment state');
  assert.ok(lab.includes("bookingStatus: 'confirmed'"), 'lab success page receives backend-confirmed booking state');
});

test('T4-4: verification failure never shows payment success', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  // Both catch paths show the neutral retryable message and never claim success.
  for (const [src, name] of [[appt, 'appointment'], [lab, 'lab']]) {
    assert.ok(src.includes('Payment is being verified. Please try again shortly.'), `${name} neutral failure message present`);
  }
  // Lab: catch path does NOT navigate to the success page.
  const labCatch = lab.indexOf("console.error('Laboratory payment verification error:'");
  const labNav = lab.indexOf("navigate('/patient/laboratory/success'");
  const catchBlock = lab.slice(labCatch, labCatch + 1200);
  assert.ok(!catchBlock.includes('navigate('), 'lab catch path never navigates to success');
  assert.ok(labNav > -1, 'lab navigation exists only in the verified branch');
  // Appointment: catch path does not open the modal.
  const apptCatch = appt.indexOf("console.error('Appointment payment verification error:'");
  const apptCatchBlock = appt.slice(apptCatch, apptCatch + 1200);
  assert.ok(!apptCatchBlock.includes('setModalOpen(true)'), 'appointment catch path never opens confirmation modal');
});

test('T4-5: verification retry reuses the SAME payment/order/signature', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  // Retry branch: captured response present -> re-verify, not re-checkout.
  const retryBranchIdx = appt.indexOf('if (razorpayPaymentResponse) {');
  const reverifyIdx = appt.indexOf('verifyAppointmentPayment(createdAppointment, razorpayPaymentResponse)');
  assert.ok(retryBranchIdx > -1 && reverifyIdx > retryBranchIdx,
    'appointment retry re-verifies with the captured response');
  // Within the retry branch, verification takes precedence over checkout resume.
  const branchBody = appt.slice(retryBranchIdx, retryBranchIdx + 600);
  const resumeInBranch = branchBody.indexOf('startAppointmentCheckout(createdAppointment)');
  const reverifyInBranch = branchBody.indexOf('verifyAppointmentPayment(createdAppointment, razorpayPaymentResponse)');
  assert.ok(reverifyInBranch > -1 && reverifyInBranch < resumeInBranch,
    'verification retry takes precedence over checkout resume');

  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  assert.ok(lab.includes('state.razorpay_payment_response'), 'lab reads the stored capture for retry');
  const labRetryIdx = lab.indexOf('await verifyLaboratoryPayment(');
  assert.ok(labRetryIdx > lab.indexOf('VERIFICATION RETRY'),
    'lab retry re-verifies the SAME captured values');
});

test('T4-6: no direct client-side paid mutation exists', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  for (const [src, name] of [[appt, 'appointment'], [lab, 'lab']]) {
    assert.ok(!src.includes('api.patch('), `${name} performs no PATCH`);
    assert.ok(!src.includes('api.put('), `${name} performs no PUT`);
    assert.ok(!/billing_status\s*[:=]/.test(src), `${name} never writes billing_status`);
    assert.ok(!src.includes("status: 'confirmed'"), `${name} never writes a confirmed status locally`);
  }
  // The verified state shown to the user comes from the backend response.
  assert.ok(appt.includes("response.data?.status === 'verified'"), 'appointment trusts only the backend verify response');
  assert.ok(lab.includes("response.data?.status === 'verified'"), 'lab trusts only the backend verify response');
});

test('T4-7: existing lab retry behavior intact — same booking reused, no duplicate bookings', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  assert.ok(lab.includes('bookingIdRef'), 'booking reuse ref preserved');
  assert.ok(lab.includes('if (!bookingId)'), 'booking created only when none exists');
  assert.ok(lab.includes("api.post('/laboratory/bookings'"), 'booking creation unchanged');
  // The verification retry path returns BEFORE booking creation.
  const retryIdx = lab.indexOf('VERIFICATION RETRY');
  const bookingIdx = lab.indexOf("api.post('/laboratory/bookings'");
  assert.ok(retryIdx > -1 && retryIdx < bookingIdx, 'verification retry never re-enters booking creation');
});

test('T4-8: existing appointment retry behavior intact', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  assert.ok(appt.includes('createdAppointment'), 'created appointment reference preserved');
  assert.ok(/paymentMethod === 'online' &&\s*createdAppointment/.test(appt), 'online retry branch preserved');
  assert.ok(appt.includes('startAppointmentCheckout(createdAppointment)'), 'checkout resume with SAME appointment preserved');
  // Offline path untouched.
  assert.ok(appt.includes("setModalOpen(true)"), 'offline confirmation modal preserved');
});

// ---------------------------------------------------------------------------
// TASK 5 — PAYMENT LIFECYCLE HARDENING
// ---------------------------------------------------------------------------

test('T5-1: checkout dismissal never marks paid/failed and never calls state APIs', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  const appt = readSrc('pages/patient/BookAppointment.jsx');

  // The dismiss handlers keep the safe pending-payment wording — explicit
  // invariant: Checkout dismissed is NOT treated as payment failure.
  for (const [src, name] of [[lab, 'lab'], [appt, 'appointment']]) {
    const dismissIdx = src.indexOf('onDismiss:');
    const block = src.slice(dismissIdx, dismissIdx + 700);
    assert.ok(block.includes('Payment window closed'), `${name} dismiss message present`);
    assert.ok(block.includes('pending payment'), `${name} dismiss keeps pending-payment semantics`);
    assert.ok(!block.includes('api.patch'), `${name} dismiss makes no PATCH`);
    assert.ok(!block.includes('api.post'), `${name} dismiss makes no POST`);
    assert.ok(!/paymentStatus:\s*'failed'/.test(block), `${name} dismiss never marks failed`);
  }
  // Neither page contains any local failed-state write for payments.
  for (const [src, name] of [[lab, 'lab'], [appt, 'appointment']]) {
    assert.ok(!/paymentStatus:\s*'failed'/.test(src), `${name} page never writes paymentStatus failed`);
  }
});

test('T5-2: payment.failed routes to the dismiss path — no trusted failure marking', () => {
  const loader = readSrc('services/razorpayCheckout.js');
  // The loader wires payment.failed to onDismiss; pages derive NO backend
  // authority from it (structural: the failure event handler exists and
  // routes onward without extra claims).
  assert.ok(loader.includes('payment.failed'), 'failure event handled');
  const failIdx = loader.indexOf('payment.failed');
  const handlerBlock = loader.slice(failIdx, failIdx + 300);
  assert.ok(handlerBlock.includes('onDismiss'), 'payment.failed routes to onDismiss');
  assert.ok(!handlerBlock.includes('fetch(') && !handlerBlock.includes('api.'), 'failure path performs no API call');
});

test('T5-3: verification retry after transient failure reuses the SAME capture (lab)', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  // Transient (5xx) failures keep the captured response for retry; definitive
  // (4xx) rejections clear it so the same order can restart checkout.
  assert.ok(lab.includes('if (status && status < 500)'), 'lab distinguishes transient vs definitive verification failures');
  const keepIdx = lab.indexOf('if (status && status < 500)');
  const block = lab.slice(keepIdx, keepIdx + 300);
  assert.ok(block.includes('razorpay_payment_response: null'), 'definitive rejection clears the stale capture');
  // Retry path re-verifies with the stored capture before any booking creation.
  const retryIdx = lab.indexOf('VERIFICATION RETRY');
  const bookingIdx = lab.indexOf("api.post('/laboratory/bookings'");
  assert.ok(retryIdx > -1 && retryIdx < bookingIdx, 'verification retry never creates a duplicate booking');
  assert.ok(lab.includes('await verifyLaboratoryPayment(captured.booking_id, captured)'), 'retry reuses the SAME payment/order/signature');
});

test('T5-4: verification retry after failure re-verifies with the SAME capture (appointment)', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  // Retry branch re-verifies the captured response instead of resuming checkout.
  const branchIdx = appt.indexOf('if (razorpayPaymentResponse) {');
  assert.ok(branchIdx > -1, 'appointment retry branch exists');
  const branch = appt.slice(branchIdx, branchIdx + 400);
  assert.ok(branch.includes('verifyAppointmentPayment(createdAppointment, razorpayPaymentResponse)'), 'retry re-verifies the captured response');
  assert.ok(branch.indexOf('verifyAppointmentPayment') < branch.indexOf('startAppointmentCheckout'), 'verification retry takes precedence over new checkout');
});

test('T5-5: verified confirmation only from backend response; failure never claims success', () => {
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  for (const [src, name] of [[appt, 'appointment'], [lab, 'lab']]) {
    assert.ok(src.includes("response.data?.status === 'verified'"), `${name} gates on the backend-verified response`);
    assert.ok(!/Payment Successful|Payment successful/.test(src.split('response.data?.status')[1] || ''), `${name} shows success only after verification`);
  }
  // Lab success page receives backend-confirmed states (never self-computed).
  assert.ok(lab.includes("bookingStatus: 'confirmed'"), 'lab confirmation states come from the verified branch');
  assert.ok(lab.includes("paymentStatus: 'paid'"), 'lab paid state only after backend verification');
});

test('T5-6: no frontend direct paid mutation / no fabricated payment ids', () => {
  const lab = readSrc('pages/patient/LaboratoryPayment.jsx');
  const appt = readSrc('pages/patient/BookAppointment.jsx');
  for (const [src, name] of [[lab, 'lab'], [appt, 'appointment']]) {
    assert.ok(!src.includes('api.patch('), `${name} no PATCH`);
    assert.ok(!src.includes('api.put('), `${name} no PUT`);
    assert.ok(!/\bpay_\$\{|\bord_\$\{/.test(src), `${name} no fabricated ids`);
    assert.ok(!src.includes("Math.random()"), `${name} no random payment data`);
  }
});
