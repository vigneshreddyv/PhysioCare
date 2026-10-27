import axios from 'axios';

// Same-origin is the safe default in every environment. Deployments with a
// separate API origin must opt in through VITE_API_URL and the API CORS list.
const API_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

let csrfToken = null;

export function setCsrfToken(value) {
  csrfToken = value || null;
}

export function clearCsrfToken() {
  csrfToken = null;
}

export async function initializeCsrfToken() {
  const response = await api.get('/auth/csrf', { skipAuthRefresh: true });
  setCsrfToken(response.data.csrf_token);
  return response.data.csrf_token;
}

api.interceptors.request.use(
  (config) => {
    const method = (config.method || 'get').toLowerCase();
    if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(method)) {
      config.headers.set('X-CSRF-Token', csrfToken);
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// ===================== TOKEN REFRESH =====================

let isRefreshing = false;
let failedQueue = [];

const processQueue = (error) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve();
  });
  failedQueue = [];
};

const isSessionEndpoint = (url = '') => (
  ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout', '/auth/csrf']
    .some((path) => url.endsWith(path))
);

// ===================== RESPONSE INTERCEPTOR =====================

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status !== 401
      || !originalRequest
      || originalRequest._retry
      || originalRequest.skipAuthRefresh
      || isSessionEndpoint(originalRequest.url)
    ) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
        .then(() => api(originalRequest));
    }

    originalRequest._retry = true;
    isRefreshing = true;

    try {
      if (!csrfToken) await initializeCsrfToken();
      const response = await api.post('/auth/refresh', null, { skipAuthRefresh: true });
      setCsrfToken(response.data.csrf_token);
      processQueue(null);
      return api(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError);
      clearCsrfToken();
      window.dispatchEvent(new Event('auth_logout'));
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;
