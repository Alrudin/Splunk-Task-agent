/**
 * Utility functions for data formatting.
 *
 * Provides formatting for file sizes, dates, and text truncation.
 */

import { format, formatDistanceToNow, parseISO } from 'date-fns';

/**
 * Format file size in bytes to human-readable format.
 *
 * @param bytes - File size in bytes
 * @returns Formatted string (e.g., "1.23 MB", "456 KB")
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${units[i]}`;
}

/**
 * Format ISO date string to localized format.
 *
 * @param date - ISO date string or Date object
 * @param formatStr - Date format string (default: 'PPpp' = localized date and time)
 * @returns Formatted date string
 */
export function formatDate(date: string | Date, formatStr: string = 'PPpp'): string {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return format(dateObj, formatStr);
  } catch (error) {
    console.error('Error formatting date:', error);
    return String(date);
  }
}

/**
 * Format date as relative time (e.g., "2 hours ago", "3 days ago").
 *
 * @param date - ISO date string or Date object
 * @returns Relative time string
 */
export function formatRelativeTime(date: string | Date): string {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return formatDistanceToNow(dateObj, { addSuffix: true });
  } catch (error) {
    console.error('Error formatting relative time:', error);
    return String(date);
  }
}

/**
 * Truncate text with ellipsis.
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated text with ellipsis if needed
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return text.substring(0, maxLength) + '...';
}

/**
 * Convert object keys from camelCase to snake_case recursively.
 *
 * @param obj - Object to convert
 * @returns Object with snake_case keys
 */
export function camelToSnake(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(camelToSnake);
  }

  if (typeof obj === 'object' && obj.constructor === Object) {
    return Object.keys(obj).reduce((acc: any, key: string) => {
      const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
      acc[snakeKey] = camelToSnake(obj[key]);
      return acc;
    }, {});
  }

  return obj;
}

/**
 * Convert object keys from snake_case to camelCase recursively.
 *
 * @param obj - Object to convert
 * @returns Object with camelCase keys
 */
export function snakeToCamel(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(snakeToCamel);
  }

  if (typeof obj === 'object' && obj.constructor === Object) {
    return Object.keys(obj).reduce((acc: any, key: string) => {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      acc[camelKey] = snakeToCamel(obj[key]);
      return acc;
    }, {});
  }

  return obj;
}

/**
 * Format request status for display.
 *
 * @param status - Request status enum value
 * @returns Formatted status string
 */
export function formatRequestStatus(status: string): string {
  return status
    .split('_')
    .map(word => word.charAt(0) + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Get color class for request status badge.
 *
 * @param status - Request status enum value
 * @returns Tailwind CSS color classes
 */
export function getStatusColorClass(status: string): string {
  const colorMap: Record<string, string> = {
    NEW: 'bg-gray-100 text-gray-800',
    PENDING_APPROVAL: 'bg-yellow-100 text-yellow-800',
    APPROVED: 'bg-blue-100 text-blue-800',
    REJECTED: 'bg-red-100 text-red-800',
    GENERATING_TA: 'bg-purple-100 text-purple-800',
    VALIDATING: 'bg-indigo-100 text-indigo-800',
    COMPLETED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
  };

  return colorMap[status] || 'bg-gray-100 text-gray-800';
}