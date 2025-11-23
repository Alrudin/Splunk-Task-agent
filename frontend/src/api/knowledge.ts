/**
 * API client for knowledge document management
 */

import api from '@/utils/api';
import {
  KnowledgeDocument,
  KnowledgeDocumentListResponse,
  KnowledgeDocumentStatistics,
  KnowledgeDocumentType
} from '@/types/knowledge';

/**
 * Upload a new knowledge document
 */
export async function uploadKnowledgeDocument(
  file: File,
  title: string,
  description?: string,
  documentType: KnowledgeDocumentType,
  extraMetadata?: Record<string, any>,
  onUploadProgress?: (progressEvent: any) => void
): Promise<KnowledgeDocument> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', title);

  if (description) {
    formData.append('description', description);
  }

  formData.append('document_type', documentType);

  if (extraMetadata) {
    formData.append('extra_metadata', JSON.stringify(extraMetadata));
  }

  const response = await api.post('/api/v1/admin/knowledge/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress
  });

  return response.data;
}

/**
 * List knowledge documents with optional filtering
 */
export async function listKnowledgeDocuments(
  skip: number = 0,
  limit: number = 50,
  documentType?: string,
  search?: string
): Promise<KnowledgeDocumentListResponse> {
  const params: any = { skip, limit };

  if (documentType) {
    params.document_type = documentType;
  }

  if (search) {
    params.search = search;
  }

  const response = await api.get('/api/v1/admin/knowledge', { params });
  return response.data;
}

/**
 * Get a specific knowledge document by ID
 */
export async function getKnowledgeDocument(documentId: string): Promise<KnowledgeDocument> {
  const response = await api.get(`/api/v1/admin/knowledge/${documentId}`);
  return response.data;
}

/**
 * Soft delete a knowledge document
 */
export async function deleteKnowledgeDocument(documentId: string): Promise<void> {
  await api.delete(`/api/v1/admin/knowledge/${documentId}`);
}

/**
 * Trigger re-indexing for a knowledge document
 */
export async function reindexKnowledgeDocument(
  documentId: string
): Promise<{ message: string; document_id: string }> {
  const response = await api.post(`/api/v1/admin/knowledge/${documentId}/reindex`);
  return response.data;
}

/**
 * Get knowledge document statistics
 */
export async function getKnowledgeStatistics(): Promise<KnowledgeDocumentStatistics> {
  const response = await api.get('/api/v1/admin/knowledge/statistics');
  return response.data;
}

/**
 * Get presigned download URL for a knowledge document
 */
export async function getKnowledgeDocumentDownloadUrl(
  documentId: string
): Promise<{ download_url: string; expires_in: number }> {
  const response = await api.get(`/api/v1/admin/knowledge/${documentId}/download`);
  return response.data;
}