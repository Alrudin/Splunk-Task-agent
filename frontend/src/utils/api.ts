/**
 * API client configuration using axios.
 */
import axios, { AxiosError, AxiosInstance } from 'axios';

// API client instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor to inject auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = getAuthToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      // Transform to ApiError
      throw new ApiError(
        error.response.status,
        (error.response.data as any)?.detail || error.message,
        error.response.data
      );
    } else if (error.request) {
      // Network error
      throw new ApiError(0, 'Network error. Please check your connection.', null);
    } else {
      // Other errors
      throw new ApiError(0, error.message, null);
    }
  }
);

/**
 * Custom API error class.
 */
export class ApiError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public details: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Set authorization token in axios default headers.
 */
export function setAuthToken(token: string | null): void {
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
}

/**
 * Get auth token from localStorage.
 */
export function getAuthToken(): string | null {
  return localStorage.getItem('access_token');
}

/**
 * Clear auth token from localStorage and axios headers.
 */
export function clearAuthToken(): void {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  delete apiClient.defaults.headers.common['Authorization'];
}
