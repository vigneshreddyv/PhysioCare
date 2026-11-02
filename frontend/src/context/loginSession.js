const AUTH_ROLES = new Set(['patient', 'doctor', 'admin', 'receptionist', 'laboratorian']);

export function isValidAuthProfile(profile) {
  if (!profile || typeof profile.id !== 'string' || !profile.id
    || typeof profile.email !== 'string' || !profile.email
    || typeof profile.full_name !== 'string' || !profile.full_name
    || !AUTH_ROLES.has(profile.role)) return false;
  return !['patient', 'doctor'].includes(profile.role)
    || (Boolean(profile.profile) && typeof profile.profile === 'object');
}

export async function establishLogin({ postLogin, fetchProfile, setCsrf, setPending }) {
  let response;
  try {
    response = await postLogin();
  } catch (error) {
    const ambiguous = !error.response && Boolean(error.request);
    if (ambiguous) setPending('unknown');
    return { status: 'login_failed', error, ambiguous };
  }

  const csrfToken = response.data?.csrf_token;
  if (typeof csrfToken !== 'string' || !csrfToken) {
    setPending('unknown');
    return { status: 'profile_failed' };
  }
  setCsrf(csrfToken);
  setPending('profile');
  try {
    await fetchProfile();
    setPending(null);
    return { status: 'ready' };
  } catch {
    return { status: 'profile_failed' };
  }
}

export async function retryLoginProfile({ pending, recoverCsrf, fetchProfile, setPending }) {
  if (!pending) return { status: 'no_pending_session' };

  if (pending === 'unknown') {
    try {
      await recoverCsrf();
    } catch (error) {
      if (error.response?.status === 401) {
        setPending(null);
        return { status: 'no_session' };
      }
      return { status: 'profile_failed' };
    }
  }

  try {
    await fetchProfile();
    setPending(null);
    return { status: 'ready' };
  } catch (error) {
    if (error.response?.status === 401) {
      setPending(null);
      return { status: 'no_session' };
    }
    return { status: 'profile_failed' };
  }
}
