/**
 * RevisionHistory component for displaying TA revision history.
 *
 * Shows all TA revisions with validation status, download, and re-validate actions.
 */

import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDownTrayIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';
import { TARevision, TARevisionDetail, ValidationStatus } from '../../types/ta';
import {
  formatDate,
  formatRelativeTime,
  formatFileSize,
  formatValidationStatus,
  formatTARevisionType,
} from '../../utils/formatters';
import { downloadTARevision, revalidateTARevision, getTARevision } from '../../api/ta';
import ValidationResults from './ValidationResults';

interface RevisionHistoryProps {
  revisions: TARevision[];
  requestId: string;
  canRevalidate: boolean;
}

export default function RevisionHistory({
  revisions,
  requestId,
  canRevalidate,
}: RevisionHistoryProps) {
  const [expandedRevision, setExpandedRevision] = useState<number | null>(null);
  const [revisionDetails, setRevisionDetails] = useState<Record<number, TARevisionDetail>>({});
  const [loadingDetails, setLoadingDetails] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const revalidateMutation = useMutation({
    mutationFn: ({ revisionId }: { revisionId: string }) =>
      revalidateTARevision(requestId, revisionId),
    onSuccess: () => {
      toast.success('Re-validation triggered successfully');
      queryClient.invalidateQueries({ queryKey: ['taRevisions', requestId] });
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to trigger re-validation');
    },
  });

  const handleDownload = async (version: number) => {
    try {
      const url = await downloadTARevision(requestId, version);
      window.open(url, '_blank');
      toast.success('Download started');
    } catch (error: any) {
      toast.error(error.message || 'Failed to download TA');
    }
  };

  const handleRevalidate = (revisionId: string) => {
    revalidateMutation.mutate({ revisionId });
  };

  const handleToggleExpand = async (version: number) => {
    if (expandedRevision === version) {
      setExpandedRevision(null);
      return;
    }

    setExpandedRevision(version);

    // Load details if not already loaded
    if (!revisionDetails[version]) {
      setLoadingDetails(version);
      try {
        const details = await getTARevision(requestId, version);
        setRevisionDetails((prev) => ({ ...prev, [version]: details }));
      } catch (error: any) {
        toast.error('Failed to load revision details');
      } finally {
        setLoadingDetails(null);
      }
    }
  };

  const isValidationRunning = (status?: ValidationStatus) =>
    status === ValidationStatus.QUEUED || status === ValidationStatus.RUNNING;

  if (revisions.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center">
        <p className="text-gray-500">No TA revisions yet</p>
        <p className="text-sm text-gray-400 mt-1">
          TA revisions will appear here after generation or manual upload
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Revision History</h3>
      </div>

      <div className="divide-y divide-gray-200">
        {revisions.map((revision) => {
          const statusInfo = revision.latestValidationStatus
            ? formatValidationStatus(revision.latestValidationStatus)
            : null;
          const typeInfo = formatTARevisionType(revision.generatedBy);
          const isExpanded = expandedRevision === revision.version;
          const details = revisionDetails[revision.version];
          const isLoadingThisDetail = loadingDetails === revision.version;
          const validationRunning = isValidationRunning(revision.latestValidationStatus);

          return (
            <div key={revision.id} className="px-6 py-4">
              {/* Revision Header */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  {/* Version Badge */}
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-sm font-bold bg-gray-100 text-gray-900">
                    v{revision.version}
                  </span>

                  {/* Type Badge */}
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${typeInfo.color}`}>
                    {typeInfo.label}
                  </span>

                  {/* Validation Status */}
                  {statusInfo && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusInfo.color}`}>
                      {validationRunning && (
                        <span className="inline-block animate-spin mr-1">
                          <ArrowPathIcon className="h-3 w-3" />
                        </span>
                      )}
                      {statusInfo.label}
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleDownload(revision.version)}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                  >
                    <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                    Download
                  </button>

                  {canRevalidate && (
                    <button
                      onClick={() => handleRevalidate(revision.id)}
                      disabled={validationRunning || revalidateMutation.isPending}
                      className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ArrowPathIcon className={`h-4 w-4 mr-1 ${revalidateMutation.isPending ? 'animate-spin' : ''}`} />
                      Re-validate
                    </button>
                  )}

                  <button
                    onClick={() => handleToggleExpand(revision.version)}
                    className="p-1.5 text-gray-400 hover:text-gray-600"
                  >
                    {isExpanded ? (
                      <ChevronUpIcon className="h-5 w-5" />
                    ) : (
                      <ChevronDownIcon className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Revision Info */}
              <div className="mt-2 flex items-center space-x-4 text-sm text-gray-500">
                <span>{formatRelativeTime(revision.createdAt)}</span>
                {revision.fileSize && (
                  <span>{formatFileSize(revision.fileSize)}</span>
                )}
              </div>

              {/* Expanded Details */}
              {isExpanded && (
                <div className="mt-4 border-t border-gray-100 pt-4">
                  {isLoadingThisDetail ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full" />
                      <span className="ml-2 text-sm text-gray-500">Loading details...</span>
                    </div>
                  ) : details?.validationRuns && details.validationRuns.length > 0 ? (
                    <div className="space-y-4">
                      <h4 className="text-sm font-medium text-gray-900">
                        Validation Runs ({details.validationRuns.length})
                      </h4>
                      {details.validationRuns.map((run) => (
                        <ValidationResults
                          key={run.id}
                          validationRun={run}
                          requestId={requestId}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">
                      No validation runs yet
                    </p>
                  )}

                  {/* Config Summary */}
                  {details?.configSummary && Object.keys(details.configSummary).length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">
                        Configuration Summary
                      </h4>
                      <div className="grid grid-cols-3 gap-2">
                        {Object.entries(details.configSummary).map(([key, value]) => (
                          <div key={key} className="text-sm">
                            <span className="text-gray-500">{key}:</span>
                            <span className="ml-1 font-medium">
                              {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata */}
                  {details?.generationMetadata && Object.keys(details.generationMetadata).length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">
                        Generation Details
                      </h4>
                      <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(details.generationMetadata, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
