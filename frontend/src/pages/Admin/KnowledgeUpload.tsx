/**
 * Knowledge Document Upload and Management Component
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  uploadKnowledgeDocument,
  listKnowledgeDocuments,
  deleteKnowledgeDocument,
  reindexKnowledgeDocument,
  getKnowledgeStatistics,
  getKnowledgeDocumentDownloadUrl
} from '@/api/knowledge';
import {
  KnowledgeDocument,
  KnowledgeDocumentType,
  KnowledgeDocumentStatistics
} from '@/types/knowledge';
import { formatBytes, formatDate } from '@/utils/formatters';
import { useAuth } from '@/contexts/AuthContext';
import { UserRoleEnum } from '@/types/user';
import toast from 'react-hot-toast';

const KnowledgeUpload: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // State management
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [documentType, setDocumentType] = useState<KnowledgeDocumentType>('pdf');
  const [extraMetadata, setExtraMetadata] = useState('');
  const [filterDocumentType, setFilterDocumentType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(0);
  const [pageSize] = useState(20);
  const [isDragging, setIsDragging] = useState(false);

  // Check user permissions
  const hasAccess = user?.roles?.some((role: { name: string }) =>
    [UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER].includes(role.name as UserRoleEnum)
  );

  // Fetch documents query
  const { data: documentsData, isLoading: isLoadingDocuments, refetch: refetchDocuments } = useQuery({
    queryKey: ['knowledgeDocuments', currentPage, pageSize, filterDocumentType, searchQuery],
    queryFn: () => listKnowledgeDocuments(
      currentPage * pageSize,
      pageSize,
      filterDocumentType || undefined,
      searchQuery || undefined
    ),
    refetchInterval: 10000, // Auto-refresh every 10 seconds
    enabled: hasAccess
  });

  // Fetch statistics query
  const { data: statistics } = useQuery({
    queryKey: ['knowledgeStatistics'],
    queryFn: getKnowledgeStatistics,
    enabled: hasAccess
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('No file selected');

      let parsedMetadata = undefined;
      if (extraMetadata.trim()) {
        try {
          parsedMetadata = JSON.parse(extraMetadata);
        } catch {
          throw new Error('Invalid JSON in extra metadata');
        }
      }

      return uploadKnowledgeDocument(
        selectedFile,
        title,
        description || undefined,
        documentType,
        parsedMetadata,
        (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeDocuments'] });
      queryClient.invalidateQueries({ queryKey: ['knowledgeStatistics'] });
      toast.success('Document uploaded successfully');
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Upload failed');
    }
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteKnowledgeDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeDocuments'] });
      queryClient.invalidateQueries({ queryKey: ['knowledgeStatistics'] });
      toast.success('Document deleted successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Delete failed');
    }
  });

  // Reindex mutation
  const reindexMutation = useMutation({
    mutationFn: reindexKnowledgeDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledgeDocuments'] });
      toast.success('Reindexing queued');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Reindex failed');
    }
  });

  // Reset form
  const resetForm = () => {
    setSelectedFile(null);
    setTitle('');
    setDescription('');
    setDocumentType('pdf');
    setExtraMetadata('');
    setUploadProgress(0);
  };

  // Handle file selection
  const handleFileSelect = (file: File) => {
    const filename = file.name.toLowerCase();

    // Auto-detect document type based on extension
    if (filename.endsWith('.pdf')) {
      setDocumentType('pdf');
    } else if (filename.endsWith('.md') || filename.endsWith('.markdown')) {
      setDocumentType('markdown');
    } else if (filename.endsWith('.tgz') || filename.endsWith('.tar.gz')) {
      setDocumentType('ta_archive');
    }

    setSelectedFile(file);
  };

  // Handle drag and drop
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  }, []);

  // Handle download
  const handleDownload = async (document: KnowledgeDocument) => {
    try {
      const { download_url } = await getKnowledgeDocumentDownloadUrl(document.id);
      window.open(download_url, '_blank');
    } catch (error: any) {
      toast.error('Failed to generate download URL');
    }
  };

  // Handle delete with confirmation
  const handleDelete = (document: KnowledgeDocument) => {
    if (window.confirm(`Are you sure you want to delete "${document.title}"? This will soft-delete the document.`)) {
      deleteMutation.mutate(document.id);
    }
  };

  // Handle reindex with confirmation
  const handleReindex = (document: KnowledgeDocument) => {
    if (window.confirm(`Are you sure you want to reindex "${document.title}"?`)) {
      reindexMutation.mutate(document.id);
    }
  };

  // Check access
  if (!hasAccess) {
    return (
      <div className="container mx-auto p-8">
        <div className="bg-red-50 border border-red-200 text-red-700 px-6 py-4 rounded-lg">
          <p className="font-semibold">Access Denied</p>
          <p>You need ADMIN or KNOWLEDGE_MANAGER role to access this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8">Knowledge Document Management</h1>

      {/* Statistics Dashboard */}
      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Total Documents</h3>
            <p className="text-2xl font-bold text-gray-900">
              {Object.values(statistics.byType).reduce((a, b) => a + b, 0)}
            </p>
            <div className="mt-2 text-sm text-gray-600">
              {Object.entries(statistics.byType).map(([type, count]) => (
                <div key={type}>
                  {type}: {count}
                </div>
              ))}
            </div>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Indexed</h3>
            <p className="text-2xl font-bold text-green-600">
              {statistics.indexingStatus.indexed}
            </p>
          </div>
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Pending</h3>
            <p className="text-2xl font-bold text-yellow-600">
              {statistics.indexingStatus.unindexed}
            </p>
          </div>
        </div>
      )}

      {/* Upload Form */}
      <div className="bg-white shadow rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Upload New Document</h2>

        {/* File Drop Zone */}
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center mb-4 transition-colors ${
            isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {selectedFile ? (
            <div>
              <p className="text-lg font-medium">{selectedFile.name}</p>
              <p className="text-sm text-gray-500">{formatBytes(selectedFile.size)}</p>
              <button
                onClick={() => setSelectedFile(null)}
                className="mt-2 text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ) : (
            <div>
              <p className="text-gray-500 mb-2">Drop a file here or</p>
              <label className="cursor-pointer">
                <input
                  type="file"
                  className="hidden"
                  accept=".pdf,.md,.markdown,.tgz,.tar.gz"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
                <span className="text-blue-600 hover:text-blue-700">browse</span>
              </label>
            </div>
          )}
        </div>

        {/* Document Type Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Document Type
          </label>
          <div className="flex space-x-4">
            <label className="flex items-center">
              <input
                type="radio"
                value="pdf"
                checked={documentType === 'pdf'}
                onChange={(e) => setDocumentType(e.target.value as KnowledgeDocumentType)}
                className="mr-2"
              />
              PDF
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                value="markdown"
                checked={documentType === 'markdown'}
                onChange={(e) => setDocumentType(e.target.value as KnowledgeDocumentType)}
                className="mr-2"
              />
              Markdown
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                value="ta_archive"
                checked={documentType === 'ta_archive'}
                onChange={(e) => setDocumentType(e.target.value as KnowledgeDocumentType)}
                className="mr-2"
              />
              TA Archive
            </label>
          </div>
        </div>

        {/* Title */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            maxLength={500}
            required
          />
        </div>

        {/* Description */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            rows={3}
          />
        </div>

        {/* Extra Metadata */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Extra Metadata (JSON)
          </label>
          <textarea
            value={extraMetadata}
            onChange={(e) => setExtraMetadata(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            rows={3}
            placeholder='{"key": "value"}'
          />
        </div>

        {/* Upload Progress */}
        {uploadProgress > 0 && uploadProgress < 100 && (
          <div className="mb-4">
            <div className="bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 mt-1">Uploading... {uploadProgress}%</p>
          </div>
        )}

        {/* Upload Button */}
        <button
          onClick={() => uploadMutation.mutate()}
          disabled={!selectedFile || !title.trim() || uploadMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {uploadMutation.isPending ? 'Uploading...' : 'Upload Document'}
        </button>
      </div>

      {/* Document List */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Documents</h2>

        {/* Filters */}
        <div className="flex space-x-4 mb-4">
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(0);
            }}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          />
          <select
            value={filterDocumentType}
            onChange={(e) => {
              setFilterDocumentType(e.target.value);
              setCurrentPage(0);
            }}
            className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Types</option>
            <option value="pdf">PDF</option>
            <option value="markdown">Markdown</option>
            <option value="ta_archive">TA Archive</option>
          </select>
        </div>

        {/* Documents Table */}
        {isLoadingDocuments ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          </div>
        ) : documentsData?.documents.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No documents found</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Title
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Uploaded By
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Size
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Created
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {documentsData?.documents.map((doc: KnowledgeDocument) => (
                    <tr key={doc.id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {doc.title}
                          </div>
                          {doc.description && (
                            <div className="text-sm text-gray-500">
                              {doc.description}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="capitalize">{doc.documentType.replace('_', ' ')}</span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {doc.uploadedByUsername}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {doc.fileSize ? formatBytes(doc.fileSize) : '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {doc.pineconeIndexed ? (
                          <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">
                            Indexed ({doc.embeddingCount || 0} chunks)
                          </span>
                        ) : (
                          <span className="inline-flex px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800">
                            Indexing...
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatDate(doc.createdAt)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        <div className="flex space-x-2">
                          <button
                            onClick={() => handleDownload(doc)}
                            className="text-blue-600 hover:text-blue-900"
                          >
                            Download
                          </button>
                          <button
                            onClick={() => handleReindex(doc)}
                            className="text-yellow-600 hover:text-yellow-900"
                          >
                            Reindex
                          </button>
                          <button
                            onClick={() => handleDelete(doc)}
                            className="text-red-600 hover:text-red-900"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {documentsData && documentsData.total > pageSize && (
              <div className="flex justify-between items-center mt-4">
                <div className="text-sm text-gray-700">
                  Showing {currentPage * pageSize + 1} to{' '}
                  {Math.min((currentPage + 1) * pageSize, documentsData.total)} of{' '}
                  {documentsData.total} documents
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setCurrentPage(currentPage - 1)}
                    disabled={currentPage === 0}
                    className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage(currentPage + 1)}
                    disabled={(currentPage + 1) * pageSize >= documentsData.total}
                    className="px-3 py-1 border border-gray-300 rounded-md hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default KnowledgeUpload;