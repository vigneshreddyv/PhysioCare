import React, { createContext, useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import api, {
  clearCsrfToken,
  initializeCsrfToken,
  setCsrfToken,
} from '../services/api';
import { readLogoutMarker, revokeSessionWithPrivacy } from './logoutSession';
import { establishLogin, isValidAuthProfile, retryLoginProfile } from './loginSession';
import { cancelClinicalPageRequests } from '../services/clinicalPagination';
import { cancelPdfViewers } from '../utils/openPdfBlob';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingLogin, setPendingLogin] = useState(null);
  const [logoutMarker] = useState(readLogoutMarker);
  const [logoutStatus, setLogoutStatus] = useState(() =>
    logoutMarker.pending ? 'failed' : null,
  );
  const queryClient = useQueryClient();
  const logoutPendingRef = useRef(logoutStatus !== null);
  const authEpoch = useRef(0);
  const logoutInFlight = useRef(null);
  const loginInFlight = useRef(null);
  const pendingLoginRef = useRef(null);

  const updatePendingLogin = (status) => {
    pendingLoginRef.current = status;
    setPendingLogin(status);
  };

  const fetchUserProfile = async ({
    initializeCsrf = false,
    preserveCsrfOnFailure = false,
    throwOnFailure = false,
  } = {}) => {
    const requestEpoch = authEpoch.current;
    try {
      if (initializeCsrf) await initializeCsrfToken();
      const response = await api.get('/auth/me');
      if (logoutPendingRef.current || requestEpoch !== authEpoch.current) return false;
      if (!isValidAuthProfile(response.data)) throw new Error('Account profile is incomplete');
      setUser(response.data);
      return true;
    } catch (error) {
      if (!logoutPendingRef.current && requestEpoch === authEpoch.current) {
        if (!preserveCsrfOnFailure) clearCsrfToken();
        setUser(null);
      }
      if (throwOnFailure) throw error;
      return false;
    } finally {
      if (requestEpoch === authEpoch.current) setLoading(false);
    }
  };

  useEffect(() => {
    // Cookie sessions intentionally replace and invalidate legacy browser tokens.
    try {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    } catch {
      // Legacy bearer tokens are ignored by the cookie-session API.
    }
    if (logoutPendingRef.current) setLoading(false);
    else fetchUserProfile({ initializeCsrf: true });

    const handleGlobalLogout = () => {
      cancelClinicalPageRequests();
      cancelPdfViewers();
      clearCsrfToken();
      queryClient.clear();
      setUser(null);
    };

    window.addEventListener('auth_logout', handleGlobalLogout);

    return () => {
      window.removeEventListener('auth_logout', handleGlobalLogout);
    };
  }, [queryClient]);

  const loadLoginProfile = async () => {
    const confirmed = await fetchUserProfile({ preserveCsrfOnFailure: true, throwOnFailure: true });
    if (!confirmed) throw new Error('Profile request was interrupted');
  };

  const login = (email, password) => {
    if (loginInFlight.current) return loginInFlight.current;
    if (pendingLoginRef.current) return Promise.reject('Check the pending session before signing in again.');

    const request = (async () => {
      authEpoch.current += 1;
      cancelClinicalPageRequests();
      cancelPdfViewers();
      queryClient.clear();
      setUser(null);
      setLoading(true);
      try {
        const result = await establishLogin({
          postLogin: () => api.post('/auth/login', { email, password }),
          fetchProfile: loadLoginProfile,
          setCsrf: setCsrfToken,
          setPending: updatePendingLogin,
        });
        if (result.status === 'ready') return true;
        if (result.status === 'profile_failed') {
          throw 'Your credentials were accepted, but your account could not be loaded. Retry the session check.';
        }
        if (result.ambiguous) {
          throw 'We could not confirm whether sign-in completed. Check your connection, then retry the session check.';
        }
        const error = result.error;
        if (error.response?.status === 401) throw 'Incorrect email or password';
        if (error.response?.status === 429) throw 'Too many sign-in attempts. Please try again later.';
        if (error.response) throw 'Sign-in is temporarily unavailable. Please try again.';
        throw error.message || 'An unexpected error occurred.';
      } finally {
        setLoading(false);
      }
    })().finally(() => {
      loginInFlight.current = null;
    });
    loginInFlight.current = request;
    return request;
  };

  const retryPendingLogin = () => {
    if (loginInFlight.current) return loginInFlight.current;
    const request = (async () => {
      setLoading(true);
      try {
        const result = await retryLoginProfile({
          pending: pendingLoginRef.current,
          recoverCsrf: initializeCsrfToken,
          fetchProfile: loadLoginProfile,
          setPending: updatePendingLogin,
        });
        if (result.status === 'ready') return true;
        if (result.status === 'no_session') {
          throw 'No active session could be confirmed. Please sign in again.';
        }
        throw 'Your account could not be loaded. Check your connection and retry the session check.';
      } finally {
        setLoading(false);
      }
    })().finally(() => {
      loginInFlight.current = null;
    });
    loginInFlight.current = request;
    return request;
  };

  const executeLogout = (retry) => {
    if (logoutInFlight.current) return logoutInFlight.current;
    if (!retry) authEpoch.current += 1;
    cancelClinicalPageRequests();
    cancelPdfViewers();
    updatePendingLogin(null);
    logoutPendingRef.current = true;
    const request = revokeSessionWithPrivacy({
      postLogout: () => api.post('/auth/logout'),
      refreshCsrf: initializeCsrfToken,
      checkNoSession: () => api.get('/auth/me', { skipAuthRefresh: true }),
      clearCsrf: clearCsrfToken,
      clearPrivateState: () => {
        cancelClinicalPageRequests();
        cancelPdfViewers();
        queryClient.clear();
        setUser(null);
      },
      setStatus: setLogoutStatus,
      storage: logoutMarker.storage,
      retry,
    }).then((confirmed) => {
      if (confirmed) logoutPendingRef.current = false;
      return confirmed;
    }).finally(() => {
      logoutInFlight.current = null;
    });
    logoutInFlight.current = request;
    return request;
  };
  const logout = () => executeLogout(false);

  const value = {
    user,
    loading,
    login,
    retryPendingLogin,
    pendingLogin,
    logout,
    refreshUserProfile: fetchUserProfile,
    isAuthenticated: !!user,
  };

  if (logoutStatus) {
    return (
      <main className="auth-flow" aria-labelledby="logout-status-heading">
        <section className="auth-flow__card" role={logoutStatus === 'failed' ? 'alert' : 'status'}>
          <div className="auth-flow__content">
            <h1 id="logout-status-heading">
              {logoutStatus === 'pending' ? 'Signing out…' : 'Sign-out could not be confirmed'}
            </h1>
            <p>Your private information is hidden in this tab.</p>
            {logoutStatus === 'failed' && (
              <>
                <p>The server may still have an active session. Retry sign-out before leaving this device.</p>
                <button type="button" className="auth-flow__primary" onClick={() => executeLogout(true)}>
                  Retry sign-out
                </button>
              </>
            )}
          </div>
        </section>
      </main>
    );
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthContext };
