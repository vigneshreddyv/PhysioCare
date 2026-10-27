import React, { createContext, useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import api, {
  clearCsrfToken,
  initializeCsrfToken,
  setCsrfToken,
} from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  const fetchUserProfile = async ({ initializeCsrf = false } = {}) => {
    try {
      if (initializeCsrf) await initializeCsrfToken();
      const response = await api.get('/auth/me');
      setUser(response.data);
      return true;
    } catch {
      clearCsrfToken();
      setUser(null);
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Cookie sessions intentionally replace and invalidate legacy browser tokens.
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    fetchUserProfile({ initializeCsrf: true });

    const handleGlobalLogout = () => {
      clearCsrfToken();
      queryClient.clear();
      setUser(null);
    };

    window.addEventListener('auth_logout', handleGlobalLogout);

    return () => {
      window.removeEventListener('auth_logout', handleGlobalLogout);
    };
  }, [queryClient]);

  const login = async (email, password) => {
    setLoading(true);

    try {
      const response = await api.post('/auth/login', {
        email,
        password,
      });

      setCsrfToken(response.data.csrf_token);

      await fetchUserProfile();

      return true;
    } catch (error) {
      setLoading(false);

      if (error.response) {
        let errorMessage = 'Authentication failed';

        if (error.response.data) {
          errorMessage =
            error.response.data.detail ||
            error.response.data.message ||
            error.response.data.error ||
            error.response.data?.errors?.[0]?.message ||
            'Authentication failed';
        }

        throw errorMessage;
      }

      if (error.request) {
        throw 'Network error - please check if the backend server is running.';
      }

      throw error.message || 'An unexpected error occurred.';
    }
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } finally {
      clearCsrfToken();
      queryClient.clear();
      setUser(null);
    }
  };

  const value = {
    user,
    loading,
    login,
    logout,
    refreshUserProfile: fetchUserProfile,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthContext };
