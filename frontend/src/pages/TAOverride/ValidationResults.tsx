/**
 * ValidationResults component for displaying validation run details.
 *
 * Shows validation status, timing, results summary, and debug bundle download.
 */

import React, { useState } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowDownTrayIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import { ValidationRun, ValidationStatus, ValidationResults as ValidationResultsType } from '../../types/ta';
import {
  formatDate,
  formatDuration,
  formatValidationStatus,
} from '../../utils/formatters';
import { downloadDebugBundle } from '../../api/ta';
import toast from 'react-hot-toast';

interface ValidationResultsProps {
  validationRun: ValidationRun;
  requestId: string;
}

/**
 * Type guard to check if results has the expected ValidationResults shape.
 * Defensively validates the presence and types of fields.
 */
function isValidationResults(results: unknown): results is ValidationResultsType {
  if (!results || typeof results !== 'object') {
    return false;
  }
  // At minimum, overallStatus should be present when results exist
  return 'overallStatus' in results && typeof (results as any).overallStatus === 'string';
}

export default function ValidationResults({
  validationRun,
  requestId,
}: ValidationResultsProps) {
  const [showRawJson, setShowRawJson] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const statusInfo = formatValidationStatus(validationRun.status);

  // Defensively validate results shape before using
  const rawResults = validationRun.resultsJson;
  const results = isValidationResults(rawResults) ? rawResults : undefined;

  const handleDownloadDebugBundle = async () => {
    if (!validationRun.debugBundleKey) {
      toast.error('Debug bundle not available');
      return;
    }

    setIsDownloading(true);
    try {
      const url = await downloadDebugBundle(requestId, validationRun.id);
      window.open(url, '_blank');
      toast.success('Debug bundle download started');
    } catch (error: any) {
      toast.error(error.message || 'Failed to download debug bundle');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      {/* Status Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          {validationRun.status === ValidationStatus.PASSED ? (
            <CheckCircleIcon className="h-6 w-6 text-green-500" />
          ) : validationRun.status === ValidationStatus.FAILED ? (
            <XCircleIcon className="h-6 w-6 text-red-500" />
          ) : (
            <ClockIcon className="h-6 w-6 text-yellow-500" />
          )}
          <span className={`px-2.5 py-0.5 rounded-full text-sm font-medium ${statusInfo.color}`}>
            {statusInfo.label}
          </span>
        </div>
        <span className="text-sm text-gray-500">
          {formatDate(validationRun.createdAt)}
        </span>
      </div>

      {/* Timing Info */}
      <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
        <div>
          <span className="text-gray-500">Started:</span>
          <p className="font-medium">
            {validationRun.startedAt ? formatDate(validationRun.startedAt) : '-'}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Completed:</span>
          <p className="font-medium">
            {validationRun.completedAt ? formatDate(validationRun.completedAt) : '-'}
          </p>
        </div>
        <div>
          <span className="text-gray-500">Duration:</span>
          <p className="font-medium">
            {formatDuration(validationRun.durationSeconds)}
          </p>
        </div>
      </div>

      {/* Results Summary */}
      {results && (
        <div className="border-t border-gray-200 pt-4 mb-4">
          <h4 className="text-sm font-medium text-gray-900 mb-3">Results Summary</h4>
          <div className="grid grid-cols-2 gap-4 text-sm">
            {results.fieldCoverage !== undefined && (
              <div>
                <span className="text-gray-500">Field Coverage:</span>
                <p className={`font-medium ${results.fieldCoverage >= 70 ? 'text-green-600' : 'text-red-600'}`}>
                  {results.fieldCoverage.toFixed(1)}%
                </p>
              </div>
            )}
            {results.eventsIngested !== undefined && (
              <div>
                <span className="text-gray-500">Events Ingested:</span>
                <p className="font-medium">{results.eventsIngested.toLocaleString()}</p>
              </div>
            )}
            {results.cimCompliance !== undefined && (
              <div>
                <span className="text-gray-500">CIM Compliance:</span>
                <p className={`font-medium ${results.cimCompliance ? 'text-green-600' : 'text-yellow-600'}`}>
                  {results.cimCompliance ? 'Yes' : 'No'}
                </p>
              </div>
            )}
            {results.overallStatus && (
              <div>
                <span className="text-gray-500">Overall Status:</span>
                <p className="font-medium">{results.overallStatus}</p>
              </div>
            )}
          </div>

          {/* Extracted Fields */}
          {results.extractedFields && results.extractedFields.length > 0 && (
            <div className="mt-4">
              <span className="text-gray-500 text-sm">Extracted Fields:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {results.extractedFields.map((field: string) => (
                  <span
                    key={field}
                    className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
                  >
                    {field}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Errors */}
          {results.errors && results.errors.length > 0 && (
            <div className="mt-4">
              <span className="text-red-600 text-sm font-medium">Errors:</span>
              <ul className="list-disc list-inside mt-1 text-sm text-red-600">
                {results.errors.map((error: string, idx: number) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Error Message */}
      {validationRun.errorMessage && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
          <p className="text-sm text-red-700">{validationRun.errorMessage}</p>
        </div>
      )}

      {/* Debug Bundle Download */}
      {validationRun.status === ValidationStatus.FAILED && validationRun.debugBundleKey && (
        <div className="border-t border-gray-200 pt-4 mb-4">
          <button
            onClick={handleDownloadDebugBundle}
            disabled={isDownloading}
            className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
          >
            <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
            {isDownloading ? 'Downloading...' : 'Download Debug Bundle'}
          </button>
          <p className="mt-1 text-xs text-gray-500">
            Contains TA files, Splunk logs, and validation errors
          </p>
        </div>
      )}

      {/* Raw JSON Toggle - uses rawResults to show data even if it doesn't match expected shape */}
      {rawResults && (
        <div className="border-t border-gray-200 pt-4">
          <button
            onClick={() => setShowRawJson(!showRawJson)}
            className="flex items-center text-sm text-gray-600 hover:text-gray-900"
          >
            {showRawJson ? (
              <ChevronUpIcon className="h-4 w-4 mr-1" />
            ) : (
              <ChevronDownIcon className="h-4 w-4 mr-1" />
            )}
            {showRawJson ? 'Hide' : 'Show'} Raw Results
          </button>
          {showRawJson && (
            <pre className="mt-2 p-3 bg-gray-100 rounded-md overflow-x-auto text-xs">
              {JSON.stringify(rawResults, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
