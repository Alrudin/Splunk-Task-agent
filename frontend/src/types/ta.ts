/**
 * TypeScript types for TA revision and validation entities.
 *
 * These types match the backend Pydantic schemas and provide
 * type safety for TA operations in the frontend.
 */

// TA Revision Type Enum
export enum TARevisionType {
  AUTO = 'AUTO',
  MANUAL = 'MANUAL',
}

// Validation Status Enum
export enum ValidationStatus {
  QUEUED = 'QUEUED',
  RUNNING = 'RUNNING',
  PASSED = 'PASSED',
  FAILED = 'FAILED',
}

// Validation Run Response
export interface ValidationRun {
  id: string;
  requestId: string;
  taRevisionId: string;
  status: ValidationStatus;
  /**
   * Validation results following the ValidationResults shape.
   * Backend uses snake_case which is transformed to camelCase by API layer.
   * All fields are optional except overallStatus when results are present.
   */
  resultsJson?: ValidationResults;
  debugBundleKey?: string;
  debugBundleBucket?: string;
  errorMessage?: string;
  startedAt?: string;
  completedAt?: string;
  durationSeconds?: number;
  createdAt: string;
}

// TA Revision Response
export interface TARevision {
  id: string;
  requestId: string;
  version: number;
  storageKey: string;
  storageBucket: string;
  generatedBy: TARevisionType;
  generatedByUser?: string;
  fileSize?: number;
  checksum?: string;
  configSummary?: Record<string, any>;
  generationMetadata?: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  latestValidationStatus?: ValidationStatus;
}

// TA Revision Detail Response (with validation runs)
export interface TARevisionDetail extends TARevision {
  validationRuns: ValidationRun[];
}

// Paginated List Response
export interface TARevisionListResponse {
  items: TARevision[];
  total: number;
  skip: number;
  limit: number;
}

// Upload TA Override Response
export interface UploadTAOverrideResponse {
  revision: TARevision;
  validationRun: ValidationRun;
}

// Revalidate Response
export interface RevalidateResponse {
  validationRun: ValidationRun;
}

// API Query Params
export interface ListTARevisionsParams {
  skip?: number;
  limit?: number;
}

// Validation Results Summary (from resultsJson)
export interface ValidationResults {
  overallStatus: string;
  fieldCoverage?: number;
  eventsIngested?: number;
  cimCompliance?: boolean;
  extractedFields?: string[];
  expectedFields?: string[];
  errors?: string[];
}
