/**
 * Main App component with routing and authentication.
 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import NewRequest from './pages/NewRequest';
import ApproverDashboard from './pages/ApproverDashboard';
import ApprovalDetail from './pages/ApprovalDetail';
import KnowledgeUpload from './pages/Admin/KnowledgeUpload';
import TAOverride from './pages/TAOverride';
import UserSettings from './pages/UserSettings';

// Create QueryClient instance
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Placeholder components for protected routes
function Dashboard() {
  return (
    <Layout>
      <div className="p-8">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="mt-4 text-gray-600">Welcome to the Splunk TA Generator!</p>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
            <ul className="mt-4 space-y-2">
              <li>
                <a href="/requests/new" className="text-indigo-600 hover:text-indigo-800">
                  Create New Request →
                </a>
              </li>
              <li>
                <a href="/requests" className="text-indigo-600 hover:text-indigo-800">
                  View My Requests →
                </a>
              </li>
              <li>
                <a href="/settings/notifications" className="text-indigo-600 hover:text-indigo-800">
                  Configure Notifications →
                </a>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </Layout>
  );
}

function Requests() {
  return (
    <Layout>
      <div className="p-8">
        <h1 className="text-3xl font-bold">Requests</h1>
        <p className="mt-4 text-gray-600">View and manage your TA generation requests.</p>
      </div>
    </Layout>
  );
}


function Admin() {
  return (
    <Layout>
      <div className="p-8">
        <h1 className="text-3xl font-bold">Admin Panel</h1>
        <p className="mt-4 text-gray-600">System administration and configuration.</p>
      </div>
    </Layout>
  );
}

function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-900">404</h1>
        <p className="mt-4 text-xl text-gray-600">Page not found</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          {/* Toast notifications */}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#363636',
                color: '#fff',
              },
              success: {
                duration: 3000,
                iconTheme: {
                  primary: '#4ade80',
                  secondary: '#fff',
                },
              },
              error: {
                duration: 4000,
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#fff',
                },
              },
            }}
          />

          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/requests"
              element={
                <ProtectedRoute>
                  <Requests />
                </ProtectedRoute>
              }
            />
            <Route
              path="/requests/new"
              element={
                <ProtectedRoute requiredRole="REQUESTOR">
                  <NewRequest />
                </ProtectedRoute>
              }
            />
            <Route
              path="/approvals"
              element={
                <ProtectedRoute requiredAnyRole={['APPROVER', 'ADMIN']}>
                  <ApproverDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="/approvals/:requestId"
              element={
                <ProtectedRoute requiredAnyRole={['APPROVER', 'ADMIN']}>
                  <ApprovalDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/knowledge"
              element={
                <ProtectedRoute requiredAnyRole={['ADMIN', 'KNOWLEDGE_MANAGER']}>
                  <KnowledgeUpload />
                </ProtectedRoute>
              }
            />
            <Route
              path="/requests/:requestId/ta-override"
              element={
                <ProtectedRoute requiredAnyRole={['APPROVER', 'ADMIN']}>
                  <TAOverride />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings/notifications"
              element={
                <ProtectedRoute>
                  <UserSettings />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/*"
              element={
                <ProtectedRoute requiredRole="ADMIN">
                  <Admin />
                </ProtectedRoute>
              }
            />

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
