/**
 * FileUpload component with drag-and-drop, progress tracking, and validation.
 *
 * Provides a user-friendly interface for uploading log sample files
 * with real-time progress feedback and client-side validation.
 */

import React, { useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  CloudArrowUpIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import { formatFileSize } from '../../utils/formatters';

export interface FileUploadProps {
  onUpload: (files: File[]) => void;
  maxSize?: number; // in MB
  maxFiles?: number;
  acceptedTypes?: string[];
  multiple?: boolean;
  disabled?: boolean;
}

interface FileWithProgress {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export interface FileUploadHandle {
  updateProgress: (filename: string, progress: number, status?: 'uploading' | 'completed' | 'error', error?: string) => void;
}

const FileUpload = forwardRef<FileUploadHandle, FileUploadProps>(({
  onUpload,
  maxSize = 500, // 500 MB default
  maxFiles = 10,
  acceptedTypes = [
    'text/plain',
    'text/csv',
    'application/gzip',
    'application/x-gzip',
    'application/zip',
    '.log',
    '.txt',
    '.csv',
    '.gz',
    '.gzip',
    '.zip',
    '.json',
  ],
  multiple = true,
  disabled = false,
}, ref) => {
  const [files, setFiles] = useState<FileWithProgress[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const maxSizeBytes = maxSize * 1024 * 1024;

  // Validate file size and type
  const validateFile = useCallback(
    (file: File): string | null => {
      // Check file size
      if (file.size > maxSizeBytes) {
        return `File size exceeds maximum of ${maxSize}MB`;
      }

      // Check file extension
      const extension = '.' + file.name.split('.').pop()?.toLowerCase();
      const hasValidExtension = acceptedTypes.some((type) =>
        type.startsWith('.') ? type === extension : false
      );

      const hasValidMimeType = acceptedTypes.some(
        (type) =>
          !type.startsWith('.') && file.type && file.type.match(type)
      );

      if (!hasValidExtension && !hasValidMimeType) {
        return `File type not allowed. Allowed: ${acceptedTypes
          .filter((t) => t.startsWith('.'))
          .join(', ')}`;
      }

      return null;
    },
    [maxSize, maxSizeBytes, acceptedTypes]
  );

  // Handle file drop
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const currentFileCount = files.filter((f) => f.status !== 'error').length;

      if (currentFileCount + acceptedFiles.length > maxFiles) {
        setErrors((prev) => ({
          ...prev,
          maxFiles: `Maximum ${maxFiles} files allowed`,
        }));
        return;
      }

      const newErrors: Record<string, string> = {};
      const validFiles: File[] = [];

      acceptedFiles.forEach((file) => {
        const error = validateFile(file);
        if (error) {
          newErrors[file.name] = error;
        } else {
          validFiles.push(file);
        }
      });

      setErrors(newErrors);

      if (validFiles.length > 0) {
        const newFiles: FileWithProgress[] = validFiles.map((file) => ({
          file,
          progress: 0,
          status: 'pending',
        }));

        setFiles((prev) => [...prev, ...newFiles]);
        onUpload(validFiles);
      }
    },
    [files, maxFiles, validateFile, onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: acceptedTypes.reduce((acc, type) => {
      if (type.startsWith('.')) {
        // Extension-based accept
        if (!acc['application/octet-stream']) {
          acc['application/octet-stream'] = [];
        }
        acc['application/octet-stream'].push(type);
      } else {
        // MIME type-based accept
        if (!acc[type]) {
          acc[type] = [];
        }
      }
      return acc;
    }, {} as Record<string, string[]>),
    multiple,
    disabled,
    maxSize: maxSizeBytes,
  });

  // Remove file from list
  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // Update file progress (called from parent)
  const updateProgress = useCallback(
    (filename: string, progress: number, status?: 'uploading' | 'completed' | 'error', error?: string) => {
      setFiles((prev) =>
        prev.map((f) =>
          f.file.name === filename
            ? { ...f, progress, status: status || f.status, error }
            : f
        )
      );
    },
    []
  );

  // Expose updateProgress method to parent via ref
  useImperativeHandle(
    ref,
    () => ({
      updateProgress,
    }),
    [updateProgress]
  );

  return (
    <div className="space-y-4">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors duration-200
          ${
            isDragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          }
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input {...getInputProps()} />
        <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          {isDragActive ? (
            <span className="text-blue-600 font-medium">Drop files here...</span>
          ) : (
            <>
              <span className="font-medium text-gray-900">
                Click to upload
              </span>{' '}
              or drag and drop
            </>
          )}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          {acceptedTypes.filter((t) => t.startsWith('.')).join(', ')} (max{' '}
          {maxSize}MB per file)
        </p>
      </div>

      {/* Error Messages */}
      {Object.keys(errors).length > 0 && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <ExclamationCircleIcon className="h-5 w-5 text-red-400 flex-shrink-0" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Upload Errors
              </h3>
              <div className="mt-2 text-sm text-red-700">
                <ul className="list-disc list-inside space-y-1">
                  {Object.entries(errors).map(([key, error]) => (
                    <li key={key}>{error}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-900">
            Files ({files.length})
          </h4>
          <ul className="divide-y divide-gray-200 border border-gray-200 rounded-md">
            {files.map((item, index) => (
              <li key={index} className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3">
                      {/* Status Icon */}
                      {item.status === 'completed' && (
                        <CheckCircleIcon className="h-5 w-5 text-green-500 flex-shrink-0" />
                      )}
                      {item.status === 'error' && (
                        <ExclamationCircleIcon className="h-5 w-5 text-red-500 flex-shrink-0" />
                      )}
                      {(item.status === 'pending' || item.status === 'uploading') && (
                        <div className="h-5 w-5 flex-shrink-0">
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                        </div>
                      )}

                      {/* File Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {item.file.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {formatFileSize(item.file.size)}
                        </p>
                        {item.error && (
                          <p className="text-xs text-red-600 mt-1">
                            {item.error}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Progress Bar */}
                    {item.status === 'uploading' && (
                      <div className="mt-2">
                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                          <div
                            className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${item.progress}%` }}
                          ></div>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {item.progress}%
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Remove Button */}
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    disabled={item.status === 'uploading'}
                    className="ml-4 p-1 text-gray-400 hover:text-gray-500 disabled:opacity-50"
                  >
                    <XMarkIcon className="h-5 w-5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
});

FileUpload.displayName = 'FileUpload';

export default FileUpload;
export type { FileWithProgress };