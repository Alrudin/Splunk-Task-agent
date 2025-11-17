/**
 * Step 1: Request Metadata Form
 *
 * Collects basic information about the log onboarding request including
 * source system, description, CIM requirement, and optional metadata.
 */

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { RequestFormData } from '../../types/request';

// Validation schema
const metadataSchema = z.object({
  sourceSystem: z
    .string()
    .min(1, 'Source system is required')
    .max(255, 'Source system must be less than 255 characters')
    .regex(
      /^[a-zA-Z0-9\s\-_]+$/,
      'Only alphanumeric characters, spaces, hyphens, and underscores allowed'
    ),
  description: z
    .string()
    .min(10, 'Description must be at least 10 characters')
    .max(5000, 'Description must be less than 5000 characters'),
  cimRequired: z.boolean(),
  metadataJson: z.string().optional(),
});

type MetadataFormData = z.infer<typeof metadataSchema>;

export interface MetadataStepProps {
  formData: Partial<RequestFormData>;
  onUpdate: (data: Partial<RequestFormData>) => void;
  onNext: () => void;
}

const MetadataStep: React.FC<MetadataStepProps> = ({
  formData,
  onUpdate,
  onNext,
}) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    watch,
  } = useForm<MetadataFormData>({
    resolver: zodResolver(metadataSchema),
    mode: 'onChange',
    defaultValues: {
      sourceSystem: formData.sourceSystem || '',
      description: formData.description || '',
      cimRequired: formData.cimRequired ?? true,
      metadataJson: formData.metadata
        ? JSON.stringify(formData.metadata, null, 2)
        : '',
    },
  });

  const onSubmit = (data: MetadataFormData) => {
    // Parse metadata JSON if provided
    let metadata: Record<string, any> | undefined;
    if (data.metadataJson?.trim()) {
      try {
        metadata = JSON.parse(data.metadataJson);
      } catch (error) {
        // Validation already handled by Zod, this is a fallback
        metadata = undefined;
      }
    }

    onUpdate({
      sourceSystem: data.sourceSystem.trim(),
      description: data.description.trim(),
      cimRequired: data.cimRequired,
      metadata,
    });
    onNext();
  };

  // Validate JSON on blur
  const [jsonError, setJsonError] = React.useState<string>('');
  const validateJson = (value: string) => {
    if (!value.trim()) {
      setJsonError('');
      return;
    }
    try {
      JSON.parse(value);
      setJsonError('');
    } catch (error) {
      setJsonError('Invalid JSON format');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Source System */}
      <div>
        <label
          htmlFor="sourceSystem"
          className="block text-sm font-medium text-gray-700"
        >
          Source System <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="sourceSystem"
          {...register('sourceSystem')}
          placeholder="e.g., Apache, Cisco ASA, AWS CloudTrail"
          className={`
            mt-1 block w-full rounded-md shadow-sm sm:text-sm
            ${
              errors.sourceSystem
                ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
            }
          `}
        />
        {errors.sourceSystem && (
          <p className="mt-1 text-sm text-red-600">
            {errors.sourceSystem.message}
          </p>
        )}
        <p className="mt-1 text-sm text-gray-500">
          Name of the log source system to be onboarded
        </p>
      </div>

      {/* Description */}
      <div>
        <label
          htmlFor="description"
          className="block text-sm font-medium text-gray-700"
        >
          Description <span className="text-red-500">*</span>
        </label>
        <textarea
          id="description"
          rows={6}
          {...register('description')}
          placeholder="Describe the log source and ingestion requirements..."
          className={`
            mt-1 block w-full rounded-md shadow-sm sm:text-sm
            ${
              errors.description
                ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
            }
          `}
        />
        {errors.description && (
          <p className="mt-1 text-sm text-red-600">
            {errors.description.message}
          </p>
        )}
        <p className="mt-1 text-sm text-gray-500">
          Detailed description of the log source and what needs to be ingested
        </p>
      </div>

      {/* CIM Required */}
      <div className="flex items-start">
        <div className="flex items-center h-5">
          <input
            type="checkbox"
            id="cimRequired"
            {...register('cimRequired')}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
        </div>
        <div className="ml-3 text-sm">
          <label htmlFor="cimRequired" className="font-medium text-gray-700">
            Require CIM (Common Information Model) compliance
          </label>
          <p className="text-gray-500">
            When enabled, the generated TA will include CIM field mappings
          </p>
        </div>
      </div>

      {/* Additional Metadata (Optional) */}
      <div>
        <label
          htmlFor="metadataJson"
          className="block text-sm font-medium text-gray-700"
        >
          Additional Metadata (Optional)
        </label>
        <textarea
          id="metadataJson"
          rows={4}
          {...register('metadataJson')}
          onBlur={(e) => validateJson(e.target.value)}
          placeholder='{"environment": "production", "log_format": "combined"}'
          className={`
            mt-1 block w-full rounded-md shadow-sm sm:text-sm font-mono
            ${
              jsonError
                ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
            }
          `}
        />
        {jsonError && (
          <p className="mt-1 text-sm text-red-600">{jsonError}</p>
        )}
        <p className="mt-1 text-sm text-gray-500">
          Optional JSON object with additional metadata (e.g., environment,
          log format, etc.)
        </p>
      </div>

      {/* Navigation Buttons */}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={!isValid || !!jsonError}
          className="
            px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium
            text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2
            focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Next
        </button>
      </div>
    </form>
  );
};

export default MetadataStep;