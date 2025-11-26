/**
 * User notification preferences API client.
 */
import { apiClient } from '../utils/api';
import toast from 'react-hot-toast';

// Interfaces for notification preferences
export interface NotificationPreferences {
  emailNotificationsEnabled: boolean;
  webhookUrl?: string;
  notificationEvents?: string[];  // 'COMPLETED' | 'FAILED' | 'APPROVED' | 'REJECTED'
}

export interface UpdateNotificationPreferencesRequest {
  emailNotificationsEnabled?: boolean;
  webhookUrl?: string;
  notificationEvents?: string[];
}

export interface TestNotificationResponse {
  message: string;
  task_id: string;
  details: {
    email_enabled: boolean;
    has_webhook: boolean;
  };
}

// Allowed notification event types
export const NOTIFICATION_EVENT_TYPES = {
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
} as const;

export type NotificationEventType = typeof NOTIFICATION_EVENT_TYPES[keyof typeof NOTIFICATION_EVENT_TYPES];

// Event type labels for UI
export const EVENT_TYPE_LABELS: Record<NotificationEventType, string> = {
  COMPLETED: 'TA Generation Completed',
  FAILED: 'TA Validation Failed',
  APPROVED: 'Request Approved',
  REJECTED: 'Request Rejected',
};

/**
 * Get current user's notification preferences.
 */
export const getNotificationPreferences = async (): Promise<NotificationPreferences> => {
  try {
    const response = await apiClient.get<NotificationPreferences>('/users/me/notification-preferences');
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      toast.error('Authentication required. Please log in again.');
      throw new Error('Authentication required');
    }
    if (error.response?.status === 404) {
      toast.error('User not found.');
      throw new Error('User not found');
    }
    const message = error.response?.data?.detail || 'Failed to fetch notification preferences.';
    toast.error(message);
    throw new Error(message);
  }
};

/**
 * Update current user's notification preferences.
 */
export const updateNotificationPreferences = async (
  data: UpdateNotificationPreferencesRequest
): Promise<NotificationPreferences> => {
  try {
    const response = await apiClient.put<NotificationPreferences>(
      '/users/me/notification-preferences',
      data
    );
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 400) {
      // Validation errors
      const detail = error.response.data?.detail;
      let message = 'Invalid notification preferences.';
      if (typeof detail === 'string') {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = `Validation failed: ${detail.map(err => err.msg || err.message).join(', ')}`;
      }
      toast.error(message);
      throw new Error(message);
    }
    if (error.response?.status === 401) {
      toast.error('Authentication required. Please log in again.');
      throw new Error('Authentication required');
    }
    const message = error.response?.data?.detail || 'Failed to update notification preferences.';
    toast.error(message);
    throw new Error(message);
  }
};

/**
 * Send a test notification to verify settings.
 */
export const sendTestNotification = async (): Promise<TestNotificationResponse> => {
  try {
    const response = await apiClient.post<TestNotificationResponse>('/users/me/test-notification');
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      toast.error('Authentication required. Please log in again.');
      throw new Error('Authentication required');
    }
    if (error.response?.status === 500) {
      toast.error('Failed to send test notification. Please check your settings.');
      throw new Error('Failed to send test notification');
    }
    const message = error.response?.data?.detail || 'Failed to send test notification.';
    toast.error(message);
    throw new Error(message);
  }
};

/**
 * Validate webhook URL format.
 */
export const validateWebhookUrl = (url: string | undefined): string | null => {
  if (!url || url.trim() === '') {
    return null; // Empty is valid (no webhook)
  }

  const trimmedUrl = url.trim();

  // Check URL format
  if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
    return 'Webhook URL must start with http:// or https://';
  }

  // Check for whitespace
  if (/\s/.test(trimmedUrl)) {
    return 'Webhook URL cannot contain spaces';
  }

  // Check length
  if (trimmedUrl.length > 2048) {
    return 'Webhook URL cannot exceed 2048 characters';
  }

  // Basic URL validation
  try {
    new URL(trimmedUrl);
  } catch {
    return 'Invalid URL format';
  }

  return null; // Valid
};