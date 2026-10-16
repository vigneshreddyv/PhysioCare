/**
 * Razorpay Checkout loader helper (Phase 4, Task 3).
 *
 * Loads the OFFICIAL hosted checkout script exactly once and opens Checkout
 * using ONLY backend-provided order values (key_id, order_id, amount,
 * currency). The frontend never computes an amount and never knows any
 * secret — the Razorpay secret key must never appear in frontend code.
 *
 * Checkout success is NOT treated as backend-confirmed payment: the success
 * handler only captures the Razorpay response (payment id, order id,
 * signature) for the LATER backend verification task.
 */

const CHECKOUT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';

let scriptPromise = null;

/**
 * Load checkout.js exactly once per page lifetime. Subsequent calls reuse
 * the in-flight/loaded script (no duplicate <script> tags).
 *
 * Rejects with a friendly Error when the script cannot be loaded or the
 * window.Razorpay global never appears.
 */
export function loadRazorpayCheckout() {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Checkout is only available in the browser.'));
  }

  // Already available (loaded previously in this session).
  if (window.Razorpay) {
    return Promise.resolve(window.Razorpay);
  }

  // A load attempt is already in flight — reuse it.
  if (scriptPromise) {
    return scriptPromise;
  }

  scriptPromise = new Promise((resolve, reject) => {
    // Guard against the tag existing without our promise tracking it
    // (e.g. HMR or an external injection): reuse the existing tag.
    let script = document.querySelector(`script[src="${CHECKOUT_SRC}"]`);

    if (!script) {
      script = document.createElement('script');
      script.src = CHECKOUT_SRC;
      script.async = true;
      document.head.appendChild(script);
    }

    const finish = () => {
      if (window.Razorpay) {
        resolve(window.Razorpay);
      } else {
        scriptPromise = null;
        reject(new Error('Payment could not be initialized. Please try again.'));
      }
    };

    script.addEventListener('load', finish);
    script.addEventListener('error', () => {
      // Allow a genuine retry on a later attempt.
      scriptPromise = null;
      script.remove();
      reject(new Error('We couldn\'t open secure payment. Please check your connection and try again.'));
    });

    // Safety net: if neither event fires (blocked/cached edge cases), fail
    // after a timeout instead of leaving the user waiting forever.
    setTimeout(() => {
      if (window.Razorpay) {
        resolve(window.Razorpay);
      } else {
        scriptPromise = null;
        reject(new Error('Payment is taking too long to load. Please try again.'));
      }
    }, 15000);
  });

  return scriptPromise;
}

/**
 * Open Razorpay Checkout with backend-authoritative order values.
 *
 * @param {Object} params
 * @param {string} params.keyId        Public key id from the backend order response.
 * @param {string} params.orderId      Razorpay order id from the backend order response.
 * @param {number} params.amount       Integer paise EXACTLY as returned by the backend.
 * @param {string} params.currency     Currency exactly as returned by the backend.
 * @param {string} params.description  Short human-readable description shown in Checkout.
 * @param {Object} [params.prefill]    Safe prefill fields (name/email/contact) only.
 * @param {string} [params.themeColor] Brand color for the Checkout modal.
 * @param {Function} params.onSuccess  Receives the raw Razorpay handler response
 *                                     (razorpay_payment_id, razorpay_order_id,
 *                                     razorpay_signature). NOT proof of payment.
 * @param {Function} params.onDismiss  Called when the user closes Checkout or
 *                                     payment fails inside Checkout.
 * @returns {Promise<void>} resolves once Checkout has been opened.
 */
export async function openRazorpayCheckout({
  keyId,
  orderId,
  amount,
  currency,
  description,
  prefill,
  themeColor = '#1F4B45',
  onSuccess,
  onDismiss,
}) {
  const Razorpay = await loadRazorpayCheckout();

  const options = {
    // All four values come from the backend order endpoint verbatim.
    key: keyId,
    amount,
    currency,
    name: 'PhysioCare',
    description: description || 'PhysioCare payment',
    order_id: orderId,
    prefill: prefill || {},
    theme: { color: themeColor },

    handler: (response) => {
      // Capture only. Verification happens in the NEXT backend task;
      // this callback is NOT treated as proof of payment anywhere.
      if (typeof onSuccess === 'function') {
        onSuccess(response);
      }
    },

    modal: {
      ondismiss: () => {
        if (typeof onDismiss === 'function') {
          onDismiss();
        }
      },
    },
  };

  const checkout = new Razorpay(options);

  // Payment failure inside Checkout (network decline, bank failure, etc.).
  // Never treated as success; the booking remains pending payment.
  checkout.on('payment.failed', (resp) => {
    if (typeof onDismiss === 'function') {
      onDismiss(resp);
    }
  });

  checkout.open();
}
