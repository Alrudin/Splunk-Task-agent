/**
 * TypeScript types for request and sample entities.
 *
 * These types match the backend Pydantic schemas and provide
 * type safety for request operations in the frontend.
 */

// Request Status Enum
export enum RequestStatus {
  NEW = 'NEW',
  PENDING_APPROVAL = 'PENDING_APPROVAL',
  APPROVED = 'APPROVED',
  REJECTED = 'REJECTED',
  GENERATING_TA = 'GENERATING_TA',
  VALIDATING = 'VALIDATING',
  COMPLETED = 'COMPLETED',
  FAILED = 'FAILED',
}

// Request Creation Data
export interface CreateRequestData {
  sourceSystem: string;
  description: string;
  cimRequired: boolean;
  metadata?: Record<string, any>;
}

// Request Update Data
export interface UpdateRequestData {
  sourceSystem?: string;
  description?: string;
  cimRequired?: boolean;
  metadata?: Record<string, any>;
}

// Request Response
export interface Request {
  id: string;
  createdBy: string;
  status: RequestStatus;
  sourceSystem: string;
  description: string;
  cimRequired: boolean;
  approvedBy?: string;
  approvedAt?: string;
  rejectionReason?: string;
  completedAt?: string;
  metadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  sampleCount: number;
  totalSampleSize: number;
}

// Sample Response
export interface Sample {
  id: string;
  requestId: string;
  filename: string;
  fileSize: number;
  mimeType?: string;
  storageKey: string;
  storageBucket: string;
  checksum: string;
  samplePreview?: string;
  retentionUntil?: string;
  deletedAt?: string;
  createdAt: string;
  updatedAt: string;
}

// Request Detail Response (with related entities)
export interface RequestDetail extends Request {
  samples: Sample[];
  taRevisions?: any[];
  validationRuns?: any[];
}

// List Response Types
export interface RequestListResponse {
  items: Request[];
  total: number;
  skip: number;
  limit: number;
}

export interface SampleListResponse {
  items: Sample[];
  total: number;
}

export interface UploadSampleResponse {
  sample: Sample;
  uploadUrl?: string;
}

// Form Data for Multi-Step Wizard
export interface RequestFormData {
  // Step 1: Metadata
  sourceSystem: string;
  description: string;
  cimRequired: boolean;
  metadata?: Record<string, any>;

  // Step 2: Files (handled separately)
  // Step 3: Review (derived from above)
}

// Utility Types
export interface UploadProgress {
  [filename: string]: number; // filename -> percentage (0-100)
}

export interface UploadError {
  [filename: string]: string; // filename -> error message
}

// API Query Params
export interface ListRequestsParams {
  skip?: number;
  limit?: number;
  status?: RequestStatus;
}