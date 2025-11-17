/**
 * API client functions for request and sample operations.
 *
 * Provides type-safe functions for interacting with the backend API
 * for request submission, sample uploads, and related operations.
 */

import { apiClient } from '../utils/api';
import {
  CreateRequestData,
  UpdateRequestData,
  Request,
  RequestDetail,
  RequestListResponse,
  Sample,
  SampleListResponse,
  UploadSampleResponse,
  ListRequestsParams,
} from '../types/request';
import { camelToSnake, snakeToCamel } from '../utils/formatters';

/**
 * Create a new request.
 *
 * @param data - Request creation data
 * @returns Created request
 */
export async function createRequest(data: CreateRequestData): Promise<Request> {
  const response = await apiClient.post<Request>(
    '/requests',
    camelToSnake(data)
  );
  return snakeToCamel(response.data);
}

/**
 * Get list of requests with optional filters and pagination.
 *
 * @param params - Query parameters (skip, limit, status)
 * @returns Paginated list of requests
 */
export async function getRequests(
  params?: ListRequestsParams
): Promise<RequestListResponse> {
  const response = await apiClient.get<RequestListResponse>('/requests', {
    params: camelToSnake(params),
  });
  return snakeToCamel(response.data);
}

/**
 * Get detailed information about a specific request.
 *
 * @param id - Request ID
 * @returns Request details with samples
 */
export async function getRequest(id: string): Promise<RequestDetail> {
  const response = await apiClient.get<RequestDetail>(`/requests/${id}`);
  return snakeToCamel(response.data);
}

/**
 * Update request metadata.
 *
 * Only allowed when request status is NEW.
 *
 * @param id - Request ID
 * @param data - Update data
 * @returns Updated request
 */
export async function updateRequest(
  id: string,
  data: UpdateRequestData
): Promise<Request> {
  const response = await apiClient.put<Request>(
    `/requests/${id}`,
    camelToSnake(data)
  );
  return snakeToCamel(response.data);
}

/**
 * Upload a log sample file.
 *
 * @param requestId - Parent request ID
 * @param file - File to upload
 * @param onProgress - Optional progress callback (percentage 0-100)
 * @returns Upload response with sample details
 */
export async function uploadSample(
  requestId: string,
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadSampleResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<UploadSampleResponse>(
    `/requests/${requestId}/samples`,
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
 * Get all samples for a request.
 *
 * @param requestId - Request ID
 * @returns List of samples
 */
export async function getSamples(requestId: string): Promise<SampleListResponse> {
  const response = await apiClient.get<SampleListResponse>(
    `/requests/${requestId}/samples`
  );
  return snakeToCamel(response.data);
}

/**
 * Get details of a specific sample.
 *
 * @param requestId - Parent request ID
 * @param sampleId - Sample ID
 * @returns Sample details
 */
export async function getSample(
  requestId: string,
  sampleId: string
): Promise<Sample> {
  const response = await apiClient.get<Sample>(
    `/requests/${requestId}/samples/${sampleId}`
  );
  return snakeToCamel(response.data);
}

/**
 * Get download URL for a sample.
 *
 * Returns a presigned URL that redirects to the sample file.
 *
 * @param requestId - Parent request ID
 * @param sampleId - Sample ID
 * @returns Download URL (presigned, expires in 1 hour)
 */
export async function downloadSample(
  requestId: string,
  sampleId: string
): Promise<string> {
  // Follow redirects to get the presigned URL
  const response = await apiClient.get<string>(
    `/requests/${requestId}/samples/${sampleId}/download`,
    {
      maxRedirects: 0, // Don't follow redirects, get the redirect URL
      validateStatus: (status) => status >= 200 && status < 400, // Accept 3xx
    }
  );

  // If we got a redirect, return the Location header
  if (response.status >= 300 && response.status < 400) {
    return response.headers.location || response.request.responseURL;
  }

  // If we got the file directly (unlikely), return the request URL
  return response.config.url || '';
}

/**
 * Delete a sample.
 *
 * Only allowed when request status is NEW.
 *
 * @param requestId - Parent request ID
 * @param sampleId - Sample ID
 */
export async function deleteSample(
  requestId: string,
  sampleId: string
): Promise<void> {
  await apiClient.delete(`/requests/${requestId}/samples/${sampleId}`);
}

/**
 * Submit request for approval.
 *
 * Transitions status from NEW to PENDING_APPROVAL.
 * Requires at least one sample to be attached.
 *
 * @param requestId - Request ID
 * @returns Updated request
 */
export async function submitRequest(requestId: string): Promise<Request> {
  const response = await apiClient.post<Request>(
    `/requests/${requestId}/submit`
  );
  return snakeToCamel(response.data);
}