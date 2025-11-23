/**
 * ApprovalDetail page component.
 *
 * Displays request details and attached samples for review, with approve/reject actions.
 */

import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import {
  getApprovalDetail,
  approveRequest,
  rejectRequest,
} from '../api/approvals';
import { downloadSample } from '../api/requests';
import { useAuth } from '../contexts/AuthContext';
import { formatDateTime, formatBytes } from '../utils/formatters';

const ApprovalDetail: React.FC = () => {
  const { requestId } = useParams<{ requestId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  // Modal states
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [approvalComment, setApprovalComment] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [validationError, setValidationError] = useState('');

  // Verify user has APPROVER or ADMIN role
  const hasApproverRole = user?.roles?.some(
    (role) => role === 'APPROVER' || role === 'ADMIN'
  );

  // Fetch request details
  const {
    data: request,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['approvalDetail', requestId],
    queryFn: () => getApprovalDetail(requestId!),
    enabled: !!requestId && hasApproverRole,
  });

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (comment: string) =>
      approveRequest(requestId!, { comment: comment || undefined }),
    onSuccess: () => {
      toast.success('Request approved successfully');
      queryClient.invalidateQueries({ queryKey: ['pendingApprovals'] });
      queryClient.invalidateQueries({ queryKey: ['approvalStatistics'] });
      navigate('/approvals');
    },
    onError: (error: any) => {
      toast.error(
        error.response?.data?.detail || 'Failed to approve request'
      );
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: (reason: string) => rejectRequest(requestId!, { reason }),
    onSuccess: () => {
      toast.success('Request rejected');
      queryClient.invalidateQueries({ queryKey: ['pendingApprovals'] });
      queryClient.invalidateQueries({ queryKey: ['approvalStatistics'] });
      navigate('/approvals');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to reject request');
    },
  });

  // Handle approve action
  const handleApprove = () => {
    setShowApproveModal(false);
    approveMutation.mutate(approvalComment);
  };

  // Handle reject action
  const handleReject = () => {
    // Validate rejection reason
    const trimmedReason = rejectionReason.trim();
    if (!trimmedReason) {
      setValidationError('Rejection reason is required');
      return;
    }
    if (trimmedReason.length < 10) {
      setValidationError('Rejection reason must be at least 10 characters');
      return;
    }

    setValidationError('');
    setShowRejectModal(false);
    rejectMutation.mutate(trimmedReason);
  };

  // Handle sample download
  const handleDownloadSample = async (sampleId: string, filename: string) => {
    try {
      const blob = await downloadSample(requestId!, sampleId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${filename}`);
    } catch (error: any) {
      toast.error(
        error.response?.data?.detail || 'Failed to download sample'
      );
    }
  };

  // Show error if user lacks role
  if (!hasApproverRole) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white shadow-md rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-semibold text-red-600 mb-2">
            Access Denied
          </h2>
          <p className="text-gray-700">
            You must have APPROVER or ADMIN role to access this page.
          </p>
        </div>
      </div>
    );
  }

  // Show error message if fetch fails
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white shadow-md rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-semibold text-red-600 mb-2">
            Error Loading Request
          </h2>
          <p className="text-gray-700 mb-4">
            {(error as Error)?.message || 'An unexpected error occurred'}
          </p>
          <div className="flex gap-4">
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Retry
            </button>
            <button
              onClick={() => navigate('/approvals')}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 transition-colors"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-500 border-t-transparent"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/approvals')}
            className="text-blue-600 hover:text-blue-800 mb-2 flex items-center"
          >
            <span className="mr-1">&larr;</span> Back to Dashboard
          </button>
          <h1 className="text-3xl font-bold text-gray-900">Request Details</h1>
          <p className="text-gray-600 mt-1">
            Review request information and attached samples
          </p>
        </div>

        {/* Request Details Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Request Information
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Source System
              </label>
              <p className="text-gray-900">{request?.sourceSystem}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                {request?.status}
              </span>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <p className="text-gray-900">
                {request?.description || 'No description provided'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                CIM Required
              </label>
              <p className="text-gray-900">
                {request?.cimRequired ? 'Yes' : 'No'}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Submitted Date
              </label>
              <p className="text-gray-900">
                {request?.submittedAt
                  ? formatDateTime(request.submittedAt)
                  : 'N/A'}
              </p>
            </div>
          </div>
        </div>

        {/* Samples Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">
            Attached Log Samples
          </h2>
          {request?.samples && request.samples.length > 0 ? (
            <div>
              <div className="mb-4 text-sm text-gray-600">
                {request.samples.length} file(s) •{' '}
                {formatBytes(
                  request.samples.reduce(
                    (sum, s) => sum + (s.sizeBytes || 0),
                    0
                  )
                )}{' '}
                total
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Filename
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Size
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Upload Date
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {request.samples.map((sample) => (
                      <tr key={sample.id}>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {sample.filename}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          {formatBytes(sample.sizeBytes || 0)}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          {formatDateTime(sample.uploadedAt)}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <button
                            onClick={() =>
                              handleDownloadSample(sample.id, sample.filename)
                            }
                            className="text-blue-600 hover:text-blue-900 font-medium"
                          >
                            Download
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">
              No samples attached to this request
            </p>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end gap-4">
          <button
            onClick={() => setShowRejectModal(true)}
            disabled={rejectMutation.isPending || approveMutation.isPending}
            className="px-6 py-3 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {rejectMutation.isPending ? (
              <span className="flex items-center">
                <span className="animate-spin mr-2">⏳</span> Rejecting...
              </span>
            ) : (
              'Reject'
            )}
          </button>
          <button
            onClick={() => setShowApproveModal(true)}
            disabled={approveMutation.isPending || rejectMutation.isPending}
            className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {approveMutation.isPending ? (
              <span className="flex items-center">
                <span className="animate-spin mr-2">⏳</span> Approving...
              </span>
            ) : (
              'Approve'
            )}
          </button>
        </div>
      </div>

      {/* Approve Modal */}
      {showApproveModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
          onClick={() => setShowApproveModal(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Approve Request
            </h3>
            <p className="text-gray-700 mb-4">
              Are you sure you want to approve this request? The TA generation
              process will begin automatically.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Approval Comment (Optional)
              </label>
              <textarea
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="Add any comments about this approval..."
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">
                {approvalComment.length}/1000 characters
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowApproveModal(false)}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleApprove}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
          onClick={() => {
            setShowRejectModal(false);
            setValidationError('');
          }}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Reject Request
            </h3>
            <p className="text-gray-700 mb-4">
              Please provide a reason for rejecting this request. The requestor
              will be notified.
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Rejection Reason <span className="text-red-500">*</span>
              </label>
              <textarea
                value={rejectionReason}
                onChange={(e) => {
                  setRejectionReason(e.target.value);
                  setValidationError('');
                }}
                maxLength={1000}
                rows={4}
                placeholder="Explain why this request is being rejected (minimum 10 characters)..."
                className={`w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-red-500 focus:border-transparent ${
                  validationError ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationError && (
                <p className="text-sm text-red-600 mt-1">{validationError}</p>
              )}
              <p className="text-xs text-gray-500 mt-1">
                {rejectionReason.length}/1000 characters
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRejectModal(false);
                  setValidationError('');
                }}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApprovalDetail;
