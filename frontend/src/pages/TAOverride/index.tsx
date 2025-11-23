/**
 * TAOverride page for managing TA revisions and manual overrides.
 *
 * Displays revision history, allows downloads, uploads, and re-validation.
 */

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { getRequest } from '../../api/requests';
import { getTARevisions } from '../../api/ta';
import { ValidationStatus } from '../../types/ta';
import { formatRequestStatus, getStatusColorClass } from '../../utils/formatters';
import { useAuth } from '../../contexts/AuthContext';
import RevisionHistory from './RevisionHistory';
import UploadOverrideForm from './UploadOverrideForm';

export default function TAOverride() {
  const { requestId } = useParams<{ requestId: string }>();
  const { user } = useAuth();

  // Check if user has APPROVER or ADMIN role
  const canUploadOverride = user?.roles?.some(
    (role) => role === 'APPROVER' || role === 'ADMIN'
  ) ?? false;

  // Fetch request details
  const {
    data: request,
    isLoading: requestLoading,
    error: requestError,
  } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => getRequest(requestId!),
    enabled: !!requestId,
  });

  // Fetch TA revisions with auto-refresh when validation is running
  const {
    data: revisionsData,
    isLoading: revisionsLoading,
    error: revisionsError,
    refetch: refetchRevisions,
  } = useQuery({
    queryKey: ['taRevisions', requestId],
    queryFn: () => getTARevisions(requestId!),
    enabled: !!requestId,
    refetchInterval: (data) => {
      // Auto-refresh every 10 seconds if any validation is queued or running
      const hasActiveValidation = data?.items?.some(
        (r) =>
          r.latestValidationStatus === ValidationStatus.QUEUED ||
          r.latestValidationStatus === ValidationStatus.RUNNING
      );
      return hasActiveValidation ? 10000 : false;
    },
  });

  const handleUploadSuccess = () => {
    refetchRevisions();
  };

  if (requestLoading || revisionsLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (requestError || revisionsError) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600">
            {(requestError as Error)?.message ||
              (revisionsError as Error)?.message ||
              'Failed to load data'}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!request) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Request not found</p>
      </div>
    );
  }

  const revisions = revisionsData?.items || [];
  const hasActiveValidation = revisions.some(
    (r) =>
      r.latestValidationStatus === ValidationStatus.QUEUED ||
      r.latestValidationStatus === ValidationStatus.RUNNING
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link
                to="/approvals"
                className="text-gray-500 hover:text-gray-700"
              >
                <ArrowLeftIcon className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  TA Override
                </h1>
                <p className="text-sm text-gray-500">
                  {request.sourceSystem}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColorClass(
                  request.status
                )}`}
              >
                {formatRequestStatus(request.status)}
              </span>
              {hasActiveValidation && (
                <span className="flex items-center text-sm text-yellow-600">
                  <ArrowPathIcon className="h-4 w-4 animate-spin mr-1" />
                  Validation in progress
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Request Info Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Request Details
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Source System:</span>
              <p className="font-medium">{request.sourceSystem}</p>
            </div>
            <div>
              <span className="text-gray-500">CIM Required:</span>
              <p className="font-medium">{request.cimRequired ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <span className="text-gray-500">Samples:</span>
              <p className="font-medium">{request.sampleCount}</p>
            </div>
            <div>
              <span className="text-gray-500">Revisions:</span>
              <p className="font-medium">{revisions.length}</p>
            </div>
          </div>
          {request.description && (
            <div className="mt-4">
              <span className="text-gray-500 text-sm">Description:</span>
              <p className="mt-1 text-sm">{request.description}</p>
            </div>
          )}
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Revision History (2/3 width) */}
          <div className="lg:col-span-2">
            <RevisionHistory
              revisions={revisions}
              requestId={requestId!}
              canRevalidate={canUploadOverride}
            />
          </div>

          {/* Upload Form (1/3 width) */}
          {canUploadOverride && (
            <div className="lg:col-span-1">
              <UploadOverrideForm
                requestId={requestId!}
                onUploadSuccess={handleUploadSuccess}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
