/**
 * API client functions for TA revision and validation operations.
 *
 * Provides type-safe functions for interacting with the backend API
 * for TA downloads, manual overrides, and re-validation.
 */

import { apiClient } from '../utils/api';
import {
  TARevision,
  TARevisionDetail,
  TARevisionListResponse,
  UploadTAOverrideResponse,
  RevalidateResponse,
  ValidationRun,
  ListTARevisionsParams,
} from '../types/ta';
import { camelToSnake, snakeToCamel } from '../utils/formatters';

/**
 * Get list of TA revisions for a request.
 *
 * @param requestId - Request ID
 * @param params - Query parameters (skip, limit)
 * @returns Paginated list of TA revisions
 */
export async function getTARevisions(
  requestId: string,
  params?: ListTARevisionsParams
): Promise<TARevisionListResponse> {
  const response = await apiClient.get<TARevisionListResponse>(
    `/ta/requests/${requestId}/revisions`,
    { params: camelToSnake(params) }
  );
  return snakeToCamel(response.data);
}

/**
 * Get detailed information about a specific TA revision.
 *
 * @param requestId - Request ID
 * @param version - TA version number
 * @returns TA revision details with validation runs
 */
export async function getTARevision(
  requestId: string,
  version: number
): Promise<TARevisionDetail> {
  const response = await apiClient.get<TARevisionDetail>(
    `/ta/requests/${requestId}/revisions/${version}`
  );
  return snakeToCamel(response.data);
}

/**
 * Get download URL for a TA package.
 *
 * Returns a presigned URL that redirects to the TA file.
 *
 * @param requestId - Request ID
 * @param version - TA version number
 * @returns Download URL (presigned, expires in 1 hour)
 */
export async function downloadTARevision(
  requestId: string,
  version: number
): Promise<string> {
  // Follow redirects to get the presigned URL
  const response = await apiClient.get<string>(
    `/ta/requests/${requestId}/revisions/${version}/download`,
    {
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400,
    }
  );

  // If we got a redirect, return the Location header
  if (response.status >= 300 && response.status < 400) {
    return response.headers.location || response.request.responseURL;
  }

  return response.config.url || '';
}

/**
 * Upload a manual TA override.
 *
 * @param requestId - Request ID
 * @param file - TA package file (.tgz or .tar.gz)
 * @param onProgress - Optional progress callback (percentage 0-100)
 * @returns Upload response with new revision and queued validation run
 */
export async function uploadTAOverride(
  requestId: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadTAOverrideResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadTAOverrideResponse>(
    `/ta/requests/${requestId}/revisions/override`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentage = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentage);
        }
      },
    }
  );

  return snakeToCamel(response.data);
}

/**
 * Trigger re-validation for a TA revision.
 *
 * @param requestId - Request ID
 * @param revisionId - TA revision ID
 * @returns Response with queued validation run
 */
export async function revalidateTARevision(
  requestId: string,
  revisionId: string
): Promise<RevalidateResponse> {
  const response = await apiClient.post<RevalidateResponse>(
    `/ta/requests/${requestId}/revisions/${revisionId}/revalidate`
  );
  return snakeToCamel(response.data);
}

/**
 * Get download URL for a debug bundle.
 *
 * @param requestId - Request ID
 * @param validationRunId - Validation run ID
 * @returns Download URL (presigned, expires in 1 hour)
 */
export async function downloadDebugBundle(
  requestId: string,
  validationRunId: string
): Promise<string> {
  const response = await apiClient.get<string>(
    `/ta/requests/${requestId}/validation-runs/${validationRunId}/debug-bundle`,
    {
      maxRedirects: 0,
      validateStatus: (status) => status >= 200 && status < 400,
    }
  );

  if (response.status >= 300 && response.status < 400) {
    return response.headers.location || response.request.responseURL;
  }

  return response.config.url || '';
}
