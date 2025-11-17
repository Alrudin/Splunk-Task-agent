/**
 * Authentication context for managing user session state.
 */
import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiClient, setAuthToken, clearAuthToken } from '../utils/api';
import { AxiosError } from 'axios';

// Types
export interface User {
  id: string;
  username: string;
  email: string;
  fullName?: string;
  isActive: boolean;
  authProvider: string;
  roles: string[];
  lastLogin?: string;
  createdAt: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  expiresIn: number;
}

export interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithSSO: (provider: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  hasRole: (role: string) => boolean;
  hasAnyRole: (...roles: string[]) => boolean;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Custom hook to use auth context
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Auth provider component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = async () => {
      const accessToken = localStorage.getItem('access_token');
      const refreshToken = localStorage.getItem('refresh_token');

      if (accessToken && refreshToken) {
        try {
          // Set token in axios
          setAuthToken(accessToken);

          // Validate token by fetching user info
          const response = await apiClient.get('/auth/me');
          setUser(response.data);
          setTokens({
            accessToken,
            refreshToken,
            tokenType: 'bearer',
            expiresIn: 3600, // Default, will be updated on next refresh
          });
        } catch (error) {
          console.error('Failed to restore session:', error);
          clearAuthToken();
        }
      }

      setIsLoading(false);
    };

    initAuth();
  }, []);

  // Axios interceptor for automatic token refresh on 401
  useEffect(() => {
    const interceptor = apiClient.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // If 401 and not already retried
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            // Try to refresh token
            await refreshToken();
            // Retry original request
            return apiClient(originalRequest);
          } catch (refreshError) {
            // Refresh failed, logout
            await logout();
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );

    return () => {
      apiClient.interceptors.response.eject(interceptor);
    };
  }, []);

  /**
   * Login with username and password.
   */
  const login = async (username: string, password: string): Promise<void> => {
    try {
      const response = await apiClient.post('/auth/login/local', {
        username,
        password,
      });

      const { user: userData, tokens: tokenData } = response.data;

      // Store tokens
      localStorage.setItem('access_token', tokenData.access_token);
      localStorage.setItem('refresh_token', tokenData.refresh_token);

      // Set axios header
      setAuthToken(tokenData.access_token);

      // Update state
      setUser(userData);
      setTokens({
        accessToken: tokenData.access_token,
        refreshToken: tokenData.refresh_token,
        tokenType: tokenData.token_type,
        expiresIn: tokenData.expires_in,
      });
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  };

  /**
   * Login with SSO provider.
   */
  const loginWithSSO = async (provider: string): Promise<void> => {
    try {
      // Get provider configuration
      const response = await apiClient.get('/auth/providers');
      const providers = response.data;

      let authorizeUrl: string | null = null;

      switch (provider) {
        case 'saml':
          authorizeUrl = providers.saml_login_url;
          break;
        case 'oauth':
          authorizeUrl = providers.oauth_authorize_url;
          break;
        case 'oidc':
          authorizeUrl = providers.oidc_authorize_url;
          break;
      }

      if (!authorizeUrl) {
        throw new Error(`${provider} is not enabled`);
      }

      // Redirect to SSO provider
      window.location.href = authorizeUrl;
    } catch (error) {
      console.error('SSO login failed:', error);
      throw error;
    }
  };

  /**
   * Logout user.
   */
  const logout = async (): Promise<void> => {
    try {
      // Call logout endpoint
      await apiClient.post('/auth/logout');
    } catch (error) {
      console.error('Logout request failed:', error);
    } finally {
      // Clear state regardless of API call result
      setUser(null);
      setTokens(null);
      clearAuthToken();
    }
  };

  /**
   * Refresh access token.
   */
  const refreshToken = async (): Promise<void> => {
    const refreshTokenValue = localStorage.getItem('refresh_token');
    if (!refreshTokenValue) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await apiClient.post('/auth/refresh', {
        refresh_token: refreshTokenValue,
      });

      const tokenData = response.data;

      // Store new access token
      localStorage.setItem('access_token', tokenData.access_token);

      // Set axios header
      setAuthToken(tokenData.access_token);

      // Update state
      setTokens((prev) => ({
        ...prev!,
        accessToken: tokenData.access_token,
        expiresIn: tokenData.expires_in,
      }));
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw error;
    }
  };

  /**
   * Check if user has a specific role.
   */
  const hasRole = (role: string): boolean => {
    return user?.roles.includes(role) || false;
  };

  /**
   * Check if user has any of the specified roles.
   */
  const hasAnyRole = (...roles: string[]): boolean => {
    return roles.some((role) => hasRole(role));
  };

  const value: AuthContextType = {
    user,
    tokens,
    isAuthenticated: !!user,
    isLoading,
    login,
    loginWithSSO,
    logout,
    refreshToken,
    hasRole,
    hasAnyRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
