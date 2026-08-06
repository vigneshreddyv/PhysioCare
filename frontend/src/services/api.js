import axios from 'axios';

// Determine if we're in development mode
const isDevelopment = import.meta.env.MODE === 'development';

// In development, use relative URLs so they go through Vite's proxy
// In production, use the full API URL from env vars
const API_URL = isDevelopment
  ? '/api'
  : (import.meta.env.VITE_API_URL || 'http://localhost:8000/api');

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ===================== REQUEST INTERCEPTOR =====================

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');

    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// ===================== TOKEN REFRESH =====================

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

// ===================== RESPONSE INTERCEPTOR =====================

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.set(
            'Authorization',
            `Bearer ${token}`
          );
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');

      if (!refreshToken) {
        isRefreshing = false;
        return Promise.reject(error);
      }

      try {
        const response = await api.post('/auth/refresh', {
          refresh_token: refreshToken,
        });

        const {
          access_token,
          refresh_token: new_refresh_token,
        } = response.data;

        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', new_refresh_token);

        api.defaults.headers.common.Authorization = `Bearer ${access_token}`;

        originalRequest.headers.set(
          'Authorization',
          `Bearer ${access_token}`
        );

        processQueue(null, access_token);

        isRefreshing = false;

        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);

        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        window.dispatchEvent(new Event('auth_logout'));

        isRefreshing = false;

        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;