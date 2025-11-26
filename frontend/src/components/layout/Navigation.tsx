/**
 * Navigation component for the application.
 */
import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import {
  HomeIcon,
  DocumentTextIcon,
  ClipboardDocumentCheckIcon,
  CogIcon,
  BellIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  ChevronDownIcon,
  FolderIcon
} from '@heroicons/react/24/outline';
import clsx from 'clsx';

export default function Navigation() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  // Check user roles
  const isApprover = user?.roles?.some((role) => role === 'APPROVER' || role === 'ADMIN');
  const isAdmin = user?.roles?.some((role) => role === 'ADMIN');
  const isKnowledgeManager = user?.roles?.some((role) => role === 'KNOWLEDGE_MANAGER' || role === 'ADMIN');

  const mainNavItems = [
    {
      path: '/',
      label: 'Dashboard',
      icon: HomeIcon,
      show: true
    },
    {
      path: '/requests',
      label: 'My Requests',
      icon: DocumentTextIcon,
      show: true
    },
    {
      path: '/requests/new',
      label: 'New Request',
      icon: DocumentTextIcon,
      show: true
    },
    {
      path: '/approvals',
      label: 'Approvals',
      icon: ClipboardDocumentCheckIcon,
      show: isApprover
    },
    {
      path: '/admin/knowledge',
      label: 'Knowledge Upload',
      icon: FolderIcon,
      show: isKnowledgeManager
    },
  ];

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and main navigation */}
          <div className="flex">
            {/* Logo */}
            <div className="flex-shrink-0 flex items-center">
              <h1 className="text-xl font-bold text-indigo-600">Splunk TA Generator</h1>
            </div>

            {/* Main navigation links */}
            <div className="hidden sm:ml-8 sm:flex sm:space-x-4">
              {mainNavItems
                .filter(item => item.show)
                .map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    className={clsx(
                      'inline-flex items-center px-3 py-2 text-sm font-medium rounded-md',
                      location.pathname === item.path
                        ? 'text-indigo-600 bg-indigo-50'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    )}
                  >
                    <item.icon className="h-4 w-4 mr-2" />
                    {item.label}
                  </Link>
                ))}
            </div>
          </div>

          {/* User menu */}
          <div className="flex items-center">
            <div className="relative ml-3">
              <div>
                <button
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  className="flex items-center text-sm rounded-full focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 p-2 hover:bg-gray-50"
                  id="user-menu-button"
                  aria-expanded={userMenuOpen}
                  aria-haspopup="true"
                >
                  <UserCircleIcon className="h-6 w-6 text-gray-600" />
                  <span className="ml-2 text-gray-700">{user?.username || 'User'}</span>
                  <ChevronDownIcon className="ml-1 h-4 w-4 text-gray-600" />
                </button>
              </div>

              {/* Dropdown menu */}
              {userMenuOpen && (
                <div
                  className="origin-top-right absolute right-0 mt-2 w-48 rounded-md shadow-lg py-1 bg-white ring-1 ring-black ring-opacity-5 focus:outline-none z-50"
                  role="menu"
                  aria-orientation="vertical"
                  aria-labelledby="user-menu-button"
                >
                  <div className="px-4 py-2 border-b border-gray-200">
                    <p className="text-sm text-gray-700 font-medium">{user?.full_name || user?.username}</p>
                    <p className="text-xs text-gray-500">{user?.email}</p>
                  </div>

                  <Link
                    to="/settings/notifications"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    role="menuitem"
                    onClick={() => setUserMenuOpen(false)}
                  >
                    <BellIcon className="h-4 w-4 mr-3 text-gray-500" />
                    Notification Settings
                  </Link>

                  {isAdmin && (
                    <Link
                      to="/admin"
                      className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                      role="menuitem"
                      onClick={() => setUserMenuOpen(false)}
                    >
                      <CogIcon className="h-4 w-4 mr-3 text-gray-500" />
                      Admin Settings
                    </Link>
                  )}

                  <button
                    onClick={() => {
                      setUserMenuOpen(false);
                      handleLogout();
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 border-t border-gray-200"
                    role="menuitem"
                  >
                    <ArrowRightOnRectangleIcon className="h-4 w-4 mr-3 text-gray-500" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile menu toggle - can be implemented if needed */}
      {/* This is a placeholder for mobile responsive navigation */}
    </nav>
  );
}