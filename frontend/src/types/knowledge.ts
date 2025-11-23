/**
 * Type definitions for knowledge document management
 */

/**
 * Allowed knowledge document types
 */
export type KnowledgeDocumentType = 'pdf' | 'markdown' | 'ta_archive';

/**
 * Knowledge document entity
 */
export interface KnowledgeDocument {
  id: string;
  title: string;
  description: string | null;
  documentType: KnowledgeDocumentType;
  storageKey: string;
  storageBucket: string;
  fileSize: number | null;
  uploadedBy: string;
  uploadedByUsername: string;
  pineconeIndexed: boolean;
  pineconeIndexName: string | null;
  embeddingCount: number | null;
  extraMetadata: Record<string, any> | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

/**
 * Response for paginated list of knowledge documents
 */
export interface KnowledgeDocumentListResponse {
  documents: KnowledgeDocument[];
  total: number;
  skip: number;
  limit: number;
}

/**
 * Knowledge document statistics
 */
export interface KnowledgeDocumentStatistics {
  byType: Record<string, number>;
  indexingStatus: {
    indexed: number;
    unindexed: number;
  };
}

/**
 * Request for uploading a knowledge document
 */
export interface KnowledgeDocumentUploadRequest {
  title: string;
  description?: string;
  documentType: KnowledgeDocumentType;
  extraMetadata?: Record<string, any>;
}