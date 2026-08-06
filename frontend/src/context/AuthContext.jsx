import React, { createContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchUserProfile = async () => {
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
    } catch (error) {
      // Token is invalid, clear session
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('access_token');

    if (token) {
      fetchUserProfile();
    } else {
      setLoading(false);
    }

    const handleGlobalLogout = () => {
      setUser(null);
    };

    window.addEventListener('auth_logout', handleGlobalLogout);

    return () => {
      window.removeEventListener('auth_logout', handleGlobalLogout);
    };
  }, []);

  const login = async (email, password) => {
    setLoading(true);

    try {
      const response = await api.post('/auth/login', {
        email,
        password,
      });

      const { access_token, refresh_token } = response.data;

      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);

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

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthContext };