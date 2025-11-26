/**
 * ApproverDashboard page component.
 *
 * Displays pending approval requests with statistics and allows navigation
 * to request details for approval/rejection actions.
 */

import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

import { getPendingApprovals, getApprovalStatistics } from '../api/approvals';
import { useAuth } from '../contexts/AuthContext';
import { formatDateTime, formatBytes } from '../utils/formatters';
import Layout from '../components/layout/Layout';

const ApproverDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [skip, setSkip] = useState(0);
  const [limit] = useState(100);
  const [searchTerm, setSearchTerm] = useState('');

  // Verify user has APPROVER or ADMIN role
  const hasApproverRole = user?.roles?.some(
    (role) => role === 'APPROVER' || role === 'ADMIN'
  );

  // Fetch statistics
  const {
    data: statistics,
    isLoading: statsLoading,
    error: statsError,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ['approvalStatistics'],
    queryFn: getApprovalStatistics,
    enabled: hasApproverRole,
  });

  // Fetch pending approvals
  const {
    data: pendingApprovals,
    isLoading: approvalsLoading,
    error: approvalsError,
    refetch: refetchApprovals,
  } = useQuery({
    queryKey: ['pendingApprovals', skip, limit],
    queryFn: () => getPendingApprovals(skip, limit),
    enabled: hasApproverRole,
  });

  // Handle manual refresh
  const handleRefresh = () => {
    refetchStats();
    refetchApprovals();
    toast.success('Dashboard refreshed');
  };

  // Handle navigation to request detail
  const handleViewDetails = (requestId: string) => {
    navigate(`/approvals/${requestId}`);
  };

  // Client-side filtering by source system or description
  const filteredRequests = pendingApprovals?.items?.filter(
    (request) =>
      searchTerm === '' ||
      request.sourceSystem.toLowerCase().includes(searchTerm.toLowerCase()) ||
      request.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

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

  // Show error message if API calls fail
  if (statsError || approvalsError) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white shadow-md rounded-lg p-6 max-w-md">
          <h2 className="text-xl font-semibold text-red-600 mb-2">
            Error Loading Dashboard
          </h2>
          <p className="text-gray-700 mb-4">
            {(statsError as Error)?.message ||
              (approvalsError as Error)?.message ||
              'An unexpected error occurred'}
          </p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      <div className="py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Approval Dashboard
              </h1>
              <p className="text-gray-600 mt-1">
                Review and approve pending log onboarding requests
              </p>
            </div>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Statistics Cards */}
        {statsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="bg-white rounded-lg shadow p-6 animate-pulse"
              >
                <div className="h-4 bg-gray-200 rounded w-24 mb-2"></div>
                <div className="h-8 bg-gray-200 rounded w-16"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-yellow-50 border-l-4 border-yellow-500 rounded-lg shadow p-6">
              <p className="text-yellow-700 text-sm font-medium mb-1">
                Pending Approval
              </p>
              <p className="text-3xl font-bold text-yellow-900">
                {statistics?.pendingApproval ?? 0}
              </p>
            </div>
            <div className="bg-green-50 border-l-4 border-green-500 rounded-lg shadow p-6">
              <p className="text-green-700 text-sm font-medium mb-1">
                Approved
              </p>
              <p className="text-3xl font-bold text-green-900">
                {statistics?.approved ?? 0}
              </p>
            </div>
            <div className="bg-red-50 border-l-4 border-red-500 rounded-lg shadow p-6">
              <p className="text-red-700 text-sm font-medium mb-1">Rejected</p>
              <p className="text-3xl font-bold text-red-900">
                {statistics?.rejected ?? 0}
              </p>
            </div>
            <div className="bg-blue-50 border-l-4 border-blue-500 rounded-lg shadow p-6">
              <p className="text-blue-700 text-sm font-medium mb-1">Total</p>
              <p className="text-3xl font-bold text-blue-900">
                {statistics?.total ?? 0}
              </p>
            </div>
          </div>
        )}

        {/* Search and Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <input
            type="text"
            placeholder="Search by source system or description..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {/* Pending Requests Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">
              Pending Approvals
            </h2>
          </div>

          {approvalsLoading ? (
            <div className="p-8 flex justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
            </div>
          ) : filteredRequests && filteredRequests.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Source System
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Description
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Submitted Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Samples
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredRequests.map((request) => (
                    <tr key={request.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {request.sourceSystem}
                        </div>
                        {request.cimRequired && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 mt-1">
                            CIM Required
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">
                          {request.description
                            ? request.description.length > 60
                              ? `${request.description.substring(0, 60)}...`
                              : request.description
                            : 'No description'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDateTime(request.submittedAt)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {request.sampleCount ?? 0} files
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatBytes(request.totalSampleSize ?? 0)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <button
                          onClick={() => handleViewDetails(request.id)}
                          className="text-blue-600 hover:text-blue-900 font-medium"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              <p className="text-lg">No pending approvals</p>
              <p className="text-sm mt-1">
                All requests have been processed or there are no requests
                matching your search.
              </p>
            </div>
          )}
        </div>

        {/* Pagination (future enhancement) */}
        {pendingApprovals && pendingApprovals.total > limit && (
          <div className="mt-6 flex justify-center">
            <div className="bg-white rounded-lg shadow px-4 py-2">
              <p className="text-sm text-gray-700">
                Showing {skip + 1} to{' '}
                {Math.min(skip + limit, pendingApprovals.total)} of{' '}
                {pendingApprovals.total} requests
              </p>
            </div>
          </div>
        )}
        </div>
      </div>
    </Layout>
  );
};

export default ApproverDashboard;
