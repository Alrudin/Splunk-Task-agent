/**
 * UploadOverrideForm component for uploading manual TA overrides.
 *
 * Provides drag-and-drop file upload with progress tracking and validation.
 */

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CloudArrowUpIcon,
  XMarkIcon,
  DocumentIcon,
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { uploadTAOverride } from '../../api/ta';
import { formatFileSize } from '../../utils/formatters';

interface UploadOverrideFormProps {
  requestId: string;
  onUploadSuccess: () => void;
}

const MAX_FILE_SIZE_MB = 100;
const ALLOWED_EXTENSIONS = ['.tgz', '.tar.gz'];

export default function UploadOverrideForm({
  requestId,
  onUploadSuccess,
}: UploadOverrideFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      return uploadTAOverride(requestId, file, setUploadProgress);
    },
    onSuccess: (data) => {
      toast.success(`TA v${data.revision.version} uploaded successfully. Validation queued.`);
      setSelectedFile(null);
      setUploadProgress(0);
      queryClient.invalidateQueries({ queryKey: ['taRevisions', requestId] });
      onUploadSuccess();
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to upload TA override');
      setUploadProgress(0);
    },
  });

  const validateFile = useCallback((file: File): string | null => {
    const maxSizeBytes = MAX_FILE_SIZE_MB * 1024 * 1024;

    if (file.size > maxSizeBytes) {
      return `File size exceeds maximum of ${MAX_FILE_SIZE_MB}MB`;
    }

    const fileName = file.name.toLowerCase();
    const hasValidExtension = ALLOWED_EXTENSIONS.some(ext =>
      fileName.endsWith(ext)
    );

    if (!hasValidExtension) {
      return `Invalid file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }

    return null;
  }, []);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setFileError(null);

      if (acceptedFiles.length === 0) {
        return;
      }

      const file = acceptedFiles[0];
      const error = validateFile(file);

      if (error) {
        setFileError(error);
        return;
      }

      setSelectedFile(file);
    },
    [validateFile]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/gzip': ['.tgz', '.tar.gz'],
      'application/x-gzip': ['.tgz', '.tar.gz'],
      'application/x-tar': ['.tgz', '.tar.gz'],
    },
    maxFiles: 1,
    disabled: uploadMutation.isPending,
  });

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setFileError(null);
    setUploadProgress(0);
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">
        Upload Manual Override
      </h3>

      {/* Instructions */}
      <div className="mb-4 text-sm text-gray-600">
        <p>Upload a manually edited TA package (.tgz or .tar.gz)</p>
        <p className="mt-1">The TA will be automatically validated after upload</p>
        <p className="mt-1 text-gray-500">Maximum file size: {MAX_FILE_SIZE_MB}MB</p>
      </div>

      {/* Dropzone */}
      {!selectedFile && (
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-lg p-6 text-center cursor-pointer
            transition-colors duration-200
            ${isDragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
            }
            ${uploadMutation.isPending ? 'opacity-50 cursor-not-allowed' : ''}
          `}
        >
          <input {...getInputProps()} />
          <CloudArrowUpIcon className="mx-auto h-10 w-10 text-gray-400" />
          <p className="mt-2 text-sm text-gray-600">
            {isDragActive ? (
              <span className="text-blue-600 font-medium">Drop file here...</span>
            ) : (
              <>
                <span className="font-medium text-gray-900">Click to upload</span>{' '}
                or drag and drop
              </>
            )}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            {ALLOWED_EXTENSIONS.join(', ')} (max {MAX_FILE_SIZE_MB}MB)
          </p>
        </div>
      )}

      {/* File Error */}
      {fileError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{fileError}</p>
        </div>
      )}

      {/* Selected File */}
      {selectedFile && (
        <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <DocumentIcon className="h-8 w-8 text-gray-400" />
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {selectedFile.name}
                </p>
                <p className="text-xs text-gray-500">
                  {formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
            {!uploadMutation.isPending && (
              <button
                onClick={handleRemoveFile}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            )}
          </div>

          {/* Progress Bar */}
          {uploadMutation.isPending && (
            <div className="mt-3">
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-gray-500 text-center">
                {uploadProgress}% uploaded
              </p>
            </div>
          )}
        </div>
      )}

      {/* Upload Button */}
      {selectedFile && !uploadMutation.isPending && (
        <button
          onClick={handleUpload}
          className="mt-4 w-full inline-flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <CloudArrowUpIcon className="h-5 w-5 mr-2" />
          Upload and Validate
        </button>
      )}

      {/* Uploading State */}
      {uploadMutation.isPending && (
        <div className="mt-4 text-center text-sm text-gray-600">
          <div className="animate-spin inline-block w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full mr-2" />
          Uploading and queueing validation...
        </div>
      )}
    </div>
  );
}
