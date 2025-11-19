/**
 * TypeScript types for approval operations.
 */

import { Request } from './request';

/**
 * Data for approving a request.
 */
export interface ApproveRequestData {
  /** Optional approval comment */
  comment?: string;
}

/**
 * Data for rejecting a request.
 */
export interface RejectRequestData {
  /** Required rejection reason (minimum 10 characters) */
  reason: string;
}

/**
 * Dashboard statistics for approval counts.
 */
export interface ApprovalStatistics {
  /** Count of PENDING_APPROVAL requests */
  pendingApproval: number;
  /** Count of APPROVED requests */
  approved: number;
  /** Count of REJECTED requests */
  rejected: number;
  /** Total requests */
  total: number;
}

/**
 * Paginated list of pending approval requests.
 */
export interface PendingApprovalListResponse {
  /** Array of Request objects with PENDING_APPROVAL status */
  items: Request[];
  /** Total count of pending approvals */
  total: number;
  /** Pagination offset */
  skip: number;
  /** Page size */
  limit: number;
}
