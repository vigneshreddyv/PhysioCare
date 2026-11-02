export const LOGOUT_PENDING_KEY = 'physiocare:logout-unconfirmed';

export function readLogoutMarker(getStorage = () => globalThis.sessionStorage) {
  try {
    const storage = getStorage();
    if (!storage || typeof storage.getItem !== 'function'
      || typeof storage.setItem !== 'function' || typeof storage.removeItem !== 'function') {
      throw new Error('Session storage unavailable');
    }
    return { storage, pending: Boolean(storage.getItem(LOGOUT_PENDING_KEY)) };
  } catch {
    // Without a readable marker, keep private content hidden until sign-out is confirmed.
    return { storage: null, pending: true };
  }
}

export async function revokeSessionWithPrivacy({
  postLogout,
  refreshCsrf,
  checkNoSession,
  clearCsrf,
  clearPrivateState,
  setStatus,
  storage,
  retry = false,
}) {
  clearPrivateState();
  setStatus('pending');

  try {
    storage?.setItem(LOGOUT_PENDING_KEY, '1');
    try {
      await postLogout();
    } catch (error) {
      if (!retry || error.response?.status !== 403) throw error;
      let noSessionConfirmed = false;
      try {
        await refreshCsrf();
      } catch (refreshError) {
        if (!storage && refreshError.response?.status === 401 && checkNoSession) {
          try {
            await checkNoSession();
          } catch (sessionError) {
            noSessionConfirmed = sessionError.response?.status === 401;
          }
        }
        if (!noSessionConfirmed) throw refreshError;
      }
      if (!noSessionConfirmed) await postLogout();
    }

    clearCsrf();
    storage?.removeItem(LOGOUT_PENDING_KEY);
    setStatus(null);
    return true;
  } catch {
    setStatus('failed');
    return false;
  }
}
