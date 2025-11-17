/**
 * Step 2: Upload Log Samples
 */

import React, { useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { uploadSample, deleteSample, getSamples } from '../../api/requests';
import { Sample } from '../../types/request';
import { formatFileSize, formatRelativeTime } from '../../utils/formatters';
import { TrashIcon } from '@heroicons/react/24/outline';
import FileUpload, { FileUploadHandle } from '../../components/requests/FileUpload';

export interface UploadStepProps {
  requestId: string;
  onNext: () => void;
  onPrevious: () => void;
}

const UploadStep: React.FC<UploadStepProps> = ({
  requestId,
  onNext,
  onPrevious,
}) => {
  const fileUploadRef = useRef<FileUploadHandle>(null);

  // Fetch existing samples
  const { data: samplesData, refetch } = useQuery({
    queryKey: ['samples', requestId],
    queryFn: () => getSamples(requestId),
  });

  const samples = samplesData?.items || [];

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: ({ file }: { file: File }) =>
      uploadSample(requestId, file, (progress) => {
        fileUploadRef.current?.updateProgress(file.name, progress, 'uploading');
      }),
    onSuccess: (_, { file }) => {
      fileUploadRef.current?.updateProgress(file.name, 100, 'completed');
      refetch();
      toast.success('Sample uploaded successfully');
    },
    onError: (error: any, { file }) => {
      fileUploadRef.current?.updateProgress(
        file.name,
        0,
        'error',
        error.message || 'Upload failed'
      );
      toast.error(error.message || 'Upload failed');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (sampleId: string) => deleteSample(requestId, sampleId),
    onSuccess: () => {
      refetch();
      toast.success('Sample deleted');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Delete failed');
    },
  });

  const handleFilesSelected = (files: File[]) => {
    files.forEach((file) => uploadMutation.mutate({ file }));
  };

  const canProceed = samples.length > 0;

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <FileUpload
        ref={fileUploadRef}
        onUpload={handleFilesSelected}
        maxSize={500}
        maxFiles={10}
        acceptedTypes={[
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
        ]}
        multiple={true}
      />

      {/* Samples List */}
      {samples.length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2">
            Uploaded Samples ({samples.length})
          </h4>
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                  Filename
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                  Size
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">
                  Uploaded
                </th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {samples.map((sample: Sample) => (
                <tr key={sample.id}>
                  <td className="px-3 py-2 text-sm">{sample.filename}</td>
                  <td className="px-3 py-2 text-sm text-gray-500">
                    {formatFileSize(sample.fileSize)}
                  </td>
                  <td className="px-3 py-2 text-sm text-gray-500">
                    {formatRelativeTime(sample.createdAt)}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => deleteMutation.mutate(sample.id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={onPrevious}
          className="px-4 py-2 border rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Previous
        </button>
        <button
          onClick={onNext}
          disabled={!canProceed}
          className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default UploadStep;