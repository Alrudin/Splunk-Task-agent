/**
 * Step 3: Review & Submit
 */

import React from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { submitRequest } from '../../api/requests';
import { RequestDetail, Sample } from '../../types/request';
import { formatFileSize } from '../../utils/formatters';

export interface ReviewStepProps {
  request: RequestDetail;
  onPrevious: () => void;
}

const ReviewStep: React.FC<ReviewStepProps> = ({ request, onPrevious }) => {
  const navigate = useNavigate();

  const submitMutation = useMutation({
    mutationFn: () => submitRequest(request.id),
    onSuccess: () => {
      toast.success('Request submitted for approval!');
      navigate(`/requests/${request.id}`);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Submission failed');
    },
  });

  return (
    <div className="space-y-6">
      {/* Request Details */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium mb-4">Request Details</h3>
        <dl className="grid grid-cols-1 gap-4">
          <div>
            <dt className="text-sm font-medium text-gray-500">Source System</dt>
            <dd className="mt-1 text-sm text-gray-900">{request.sourceSystem}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Description</dt>
            <dd className="mt-1 text-sm text-gray-900">{request.description}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">CIM Required</dt>
            <dd className="mt-1">
              <span
                className={`inline-flex rounded-full px-2 text-xs font-semibold ${
                  request.cimRequired
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}
              >
                {request.cimRequired ? 'Yes' : 'No'}
              </span>
            </dd>
          </div>
        </dl>
      </div>

      {/* Samples Summary */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium mb-4">
          Samples ({request.samples.length})
        </h3>
        <div className="space-y-2">
          {request.samples.map((sample: Sample) => (
            <div key={sample.id} className="flex justify-between text-sm">
              <span className="text-gray-900">{sample.filename}</span>
              <span className="text-gray-500">
                {formatFileSize(sample.fileSize)}
              </span>
            </div>
          ))}
          <div className="border-t pt-2 flex justify-between font-medium">
            <span>Total</span>
            <span>{formatFileSize(request.totalSampleSize)}</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={onPrevious}
          className="px-4 py-2 border rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Previous
        </button>
        <button
          onClick={() => submitMutation.mutate()}
          disabled={submitMutation.isPending}
          className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
        >
          {submitMutation.isPending ? 'Submitting...' : 'Submit for Approval'}
        </button>
      </div>
    </div>
  );
};

export default ReviewStep;