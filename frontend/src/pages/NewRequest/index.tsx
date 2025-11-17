/**
 * New Request Page - Multi-step wizard for log onboarding requests
 */

import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { createRequest, getRequest } from '../../api/requests';
import { RequestFormData } from '../../types/request';
import StepIndicator from './StepIndicator';
import MetadataStep from './MetadataStep';
import UploadStep from './UploadStep';
import ReviewStep from './ReviewStep';

const STEP_LABELS = ['Request Details', 'Upload Samples', 'Review & Submit'];

const NewRequest: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<Partial<RequestFormData>>({
    cimRequired: true,
  });
  const [requestId, setRequestId] = useState<string | null>(null);

  // Create request mutation (Step 1)
  const createMutation = useMutation({
    mutationFn: createRequest,
    onSuccess: (data) => {
      setRequestId(data.id);
      toast.success('Request created');
      setCurrentStep(2);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to create request');
    },
  });

  // Fetch request details for review
  const { data: requestDetail } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => getRequest(requestId!),
    enabled: !!requestId && currentStep === 3,
  });

  const handleMetadataNext = () => {
    if (formData.sourceSystem && formData.description) {
      createMutation.mutate({
        sourceSystem: formData.sourceSystem,
        description: formData.description,
        cimRequired: formData.cimRequired ?? true,
        metadata: formData.metadata,
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            New Log Onboarding Request
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Submit a request to generate a Splunk TA for your log source
          </p>
        </div>

        {/* Step Indicator */}
        <div className="mb-8">
          <StepIndicator
            currentStep={currentStep}
            totalSteps={3}
            stepLabels={STEP_LABELS}
          />
        </div>

        {/* Step Content */}
        <div className="bg-white shadow rounded-lg p-6">
          {currentStep === 1 && (
            <MetadataStep
              formData={formData}
              onUpdate={(data) => setFormData({ ...formData, ...data })}
              onNext={handleMetadataNext}
            />
          )}

          {currentStep === 2 && requestId && (
            <UploadStep
              requestId={requestId}
              onNext={() => setCurrentStep(3)}
              onPrevious={() => setCurrentStep(1)}
            />
          )}

          {currentStep === 3 && requestDetail && (
            <ReviewStep
              request={requestDetail}
              onPrevious={() => setCurrentStep(2)}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default NewRequest;