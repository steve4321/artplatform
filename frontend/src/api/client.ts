import axios from 'axios';

let isRedirecting = false;

function transformKeysToCamelCase<T>(obj: T): T {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(transformKeysToCamelCase) as unknown as T;
  }

  if (typeof obj === 'object' && !Array.isArray(obj)) {
    const result: Record<string, unknown> = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
        result[camelKey] = transformKeysToCamelCase((obj as Record<string, unknown>)[key]);
      }
    }
    return result as T;
  }

  return obj;
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

client.interceptors.response.use(
  (response) => {
    if (response.data) {
      response.data = transformKeysToCamelCase(response.data);
    }
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      if (!isRedirecting && !window.location.pathname.includes('/login')) {
        isRedirecting = true;
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default client;