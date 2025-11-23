/**
 * API client functions for approval operations.
 */

import { apiClient } from '../utils/api';
import { camelToSnake, snakeToCamel } from '../utils/formatters';
import {
  ApproveRequestData,
  RejectRequestData,
  ApprovalStatistics,
  PendingApprovalListResponse,
} from '../types/approval';
import { Request, RequestDetail } from '../types/request';

/**
 * Fetch paginated list of pending approval requests.
 *
 * @param skip - Number of records to skip (pagination offset)
 * @param limit - Maximum number of records to return
 * @returns Promise resolving to paginated list response
 */
export async function getPendingApprovals(
  skip: number = 0,
  limit: number = 100
): Promise<PendingApprovalListResponse> {
  const response = await apiClient.get<PendingApprovalListResponse>(
    `/approvals/pending`,
    {
      params: { skip, limit },
    }
  );

  return snakeToCamel(response.data) as PendingApprovalListResponse;
}

/**
 * Fetch request details for approval review.
 *
 * @param requestId - UUID of request to retrieve
 * @returns Promise resolving to request detail with samples
 */
export async function getApprovalDetail(
  requestId: string
): Promise<RequestDetail> {
  const response = await apiClient.get<RequestDetail>(
    `/approvals/${requestId}`
  );

  return snakeToCamel(response.data) as RequestDetail;
}

/**
 * Approve a request.
 *
 * @param requestId - UUID of request to approve
 * @param data - Approval data (optional comment)
 * @returns Promise resolving to updated request
 */
export async function approveRequest(
  requestId: string,
  data: ApproveRequestData
): Promise<Request> {
  const response = await apiClient.post<Request>(
    `/approvals/${requestId}/approve`,
    camelToSnake(data)
  );

  return snakeToCamel(response.data) as Request;
}

/**
 * Reject a request.
 *
 * @param requestId - UUID of request to reject
 * @param data - Rejection data (required reason)
 * @returns Promise resolving to updated request
 */
export async function rejectRequest(
  requestId: string,
  data: RejectRequestData
): Promise<Request> {
  const response = await apiClient.post<Request>(
    `/approvals/${requestId}/reject`,
    camelToSnake(data)
  );

  return snakeToCamel(response.data) as Request;
}

/**
 * Fetch approval statistics for dashboard.
 *
 * @returns Promise resolving to approval statistics
 */
export async function getApprovalStatistics(): Promise<ApprovalStatistics> {
  const response = await apiClient.get<ApprovalStatistics>(
    `/approvals/statistics`
  );

  return snakeToCamel(response.data) as ApprovalStatistics;
}
