/**
 * User notification preferences settings page.
 */
import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Switch } from '@headlessui/react';
import { BellIcon, LinkIcon, CheckCircleIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { useForm, Controller } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import toast from 'react-hot-toast';
import clsx from 'clsx';
import Layout from '../components/layout/Layout';

import {
  getNotificationPreferences,
  updateNotificationPreferences,
  sendTestNotification,
  validateWebhookUrl,
  NotificationPreferences,
  NOTIFICATION_EVENT_TYPES,
  EVENT_TYPE_LABELS,
  NotificationEventType,
} from '../api/users';

// Form validation schema
const preferencesSchema = z.object({
  emailNotificationsEnabled: z.boolean(),
  webhookUrl: z
    .string()
    .optional()
    .refine(
      (val) => !val || validateWebhookUrl(val) === null,
      (val) => ({ message: validateWebhookUrl(val) || 'Invalid URL' })
    ),
  notificationEvents: z.array(z.string()).optional(),
});

type PreferencesFormData = z.infer<typeof preferencesSchema>;

export default function UserSettings() {
  const queryClient = useQueryClient();
  const [isTesting, setIsTesting] = useState(false);

  // Fetch current preferences
  const { data: preferences, isLoading, error } = useQuery({
    queryKey: ['notificationPreferences'],
    queryFn: getNotificationPreferences,
    retry: 1,
  });

  // Update preferences mutation
  const updateMutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(['notificationPreferences'], data);
      toast.success('Notification preferences updated successfully');
    },
    onError: (error: Error) => {
      // Error toast already shown in API client
      console.error('Failed to update preferences:', error);
    },
  });

  // Test notification mutation
  const testMutation = useMutation({
    mutationFn: sendTestNotification,
    onSuccess: (data) => {
      toast.success(data.message || 'Test notification sent successfully');
    },
    onError: (error: Error) => {
      // Error toast already shown in API client
      console.error('Failed to send test notification:', error);
    },
  });

  // Form setup
  const {
    control,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isDirty },
  } = useForm<PreferencesFormData>({
    resolver: zodResolver(preferencesSchema),
    defaultValues: {
      emailNotificationsEnabled: true,
      webhookUrl: '',
      notificationEvents: Object.values(NOTIFICATION_EVENT_TYPES),
    },
  });

  // Update form when preferences are loaded
  useEffect(() => {
    if (preferences) {
      reset({
        emailNotificationsEnabled: preferences.emailNotificationsEnabled,
        webhookUrl: preferences.webhookUrl || '',
        notificationEvents: preferences.notificationEvents || Object.values(NOTIFICATION_EVENT_TYPES),
      });
    }
  }, [preferences, reset]);

  const onSubmit = async (data: PreferencesFormData) => {
    // Clean up webhook URL if empty
    const cleanedData = {
      ...data,
      webhookUrl: data.webhookUrl?.trim() || undefined,
    };
    updateMutation.mutate(cleanedData);
  };

  const handleTestNotification = async () => {
    setIsTesting(true);
    try {
      await testMutation.mutateAsync();
    } finally {
      setIsTesting(false);
    }
  };

  const watchEmailEnabled = watch('emailNotificationsEnabled');
  const watchEvents = watch('notificationEvents');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading preferences...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <ExclamationCircleIcon className="h-12 w-12 text-red-500 mx-auto" />
          <p className="mt-4 text-gray-600">Failed to load notification preferences</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      <div className="py-12">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Page Header */}
        <div className="bg-white shadow-sm rounded-lg mb-8">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center">
              <BellIcon className="h-6 w-6 text-gray-400 mr-3" />
              <h1 className="text-2xl font-semibold text-gray-900">Notification Settings</h1>
            </div>
            <p className="mt-2 text-sm text-gray-600">
              Configure how you receive notifications about your TA generation requests
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Email Notifications Section */}
          <div className="bg-white shadow-sm rounded-lg">
            <div className="px-6 py-5">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Email Notifications</h2>

              <Controller
                control={control}
                name="emailNotificationsEnabled"
                render={({ field }) => (
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <label htmlFor="email-toggle" className="text-sm font-medium text-gray-700">
                        Enable Email Notifications
                      </label>
                      <p className="text-sm text-gray-500">
                        Receive email notifications for request updates
                      </p>
                    </div>
                    <Switch
                      id="email-toggle"
                      checked={field.value}
                      onChange={field.onChange}
                      className={clsx(
                        field.value ? 'bg-indigo-600' : 'bg-gray-200',
                        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2'
                      )}
                    >
                      <span
                        className={clsx(
                          field.value ? 'translate-x-6' : 'translate-x-1',
                          'inline-block h-4 w-4 transform rounded-full bg-white transition-transform'
                        )}
                      />
                    </Switch>
                  </div>
                )}
              />
            </div>
          </div>

          {/* Webhook Integration Section */}
          <div className="bg-white shadow-sm rounded-lg">
            <div className="px-6 py-5">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                <LinkIcon className="inline h-5 w-5 mr-2" />
                Webhook Integration
              </h2>

              <Controller
                control={control}
                name="webhookUrl"
                render={({ field }) => (
                  <div>
                    <label htmlFor="webhook-url" className="block text-sm font-medium text-gray-700">
                      Webhook URL
                    </label>
                    <p className="mt-1 text-sm text-gray-500">
                      Configure a webhook URL for external integrations (e.g., Slack, Teams, CI/CD)
                    </p>
                    <input
                      type="url"
                      id="webhook-url"
                      {...field}
                      placeholder="https://hooks.slack.com/services/..."
                      className={clsx(
                        'mt-2 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                        errors.webhookUrl && 'border-red-300'
                      )}
                    />
                    {errors.webhookUrl && (
                      <p className="mt-1 text-sm text-red-600">{errors.webhookUrl.message}</p>
                    )}
                    <p className="mt-2 text-xs text-gray-500">
                      Leave empty to disable webhook notifications. Maximum 2048 characters.
                    </p>
                  </div>
                )}
              />
            </div>
          </div>

          {/* Event Selection Section */}
          <div className="bg-white shadow-sm rounded-lg">
            <div className="px-6 py-5">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Event Selection</h2>
              <p className="text-sm text-gray-500 mb-4">
                Select which events you want to be notified about
              </p>

              <Controller
                control={control}
                name="notificationEvents"
                render={({ field }) => (
                  <div className="space-y-3">
                    {Object.entries(EVENT_TYPE_LABELS).map(([eventType, label]) => {
                      const isChecked = field.value?.includes(eventType) || false;
                      return (
                        <label
                          key={eventType}
                          className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              const newValue = e.target.checked
                                ? [...(field.value || []), eventType]
                                : (field.value || []).filter(v => v !== eventType);
                              field.onChange(newValue);
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="ml-3 text-sm font-medium text-gray-700">
                            {label}
                          </span>
                          <span className="ml-2 text-xs text-gray-500">
                            ({eventType})
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-between">
            <button
              type="button"
              onClick={handleTestNotification}
              disabled={isTesting || testMutation.isPending}
              className={clsx(
                'inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500',
                (isTesting || testMutation.isPending) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isTesting || testMutation.isPending ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-700 mr-2"></div>
                  Sending Test...
                </>
              ) : (
                <>
                  <CheckCircleIcon className="h-4 w-4 mr-2" />
                  Send Test Notification
                </>
              )}
            </button>

            <div className="flex space-x-3">
              <button
                type="button"
                onClick={() => reset()}
                disabled={!isDirty}
                className={clsx(
                  'px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500',
                  !isDirty && 'opacity-50 cursor-not-allowed'
                )}
              >
                Reset
              </button>
              <button
                type="submit"
                disabled={updateMutation.isPending || !isDirty}
                className={clsx(
                  'px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500',
                  (updateMutation.isPending || !isDirty) && 'opacity-50 cursor-not-allowed'
                )}
              >
                {updateMutation.isPending ? (
                  <>
                    <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Saving...
                  </>
                ) : (
                  'Save Changes'
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Info Section */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-sm font-medium text-blue-900 mb-2">How Notifications Work</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Email notifications are sent to your registered email address</li>
            <li>• Webhook URLs receive JSON payloads with event details</li>
            <li>• You can enable both email and webhook notifications simultaneously</li>
            <li>• Test notifications help verify your settings are working correctly</li>
          </ul>
        </div>
        </div>
      </div>
    </Layout>
  );
}