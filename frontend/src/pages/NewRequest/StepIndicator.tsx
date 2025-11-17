/**
 * Step indicator component for multi-step wizard.
 *
 * Shows progress through wizard steps with visual indicators for
 * completed, active, and upcoming steps.
 */

import React from 'react';
import { CheckIcon } from '@heroicons/react/24/solid';

export interface StepIndicatorProps {
  currentStep: number;
  totalSteps: number;
  stepLabels: string[];
}

const StepIndicator: React.FC<StepIndicatorProps> = ({
  currentStep,
  totalSteps,
  stepLabels,
}) => {
  return (
    <nav aria-label="Progress">
      <ol role="list" className="flex items-center">
        {Array.from({ length: totalSteps }, (_, index) => {
          const stepNumber = index + 1;
          const isCompleted = stepNumber < currentStep;
          const isActive = stepNumber === currentStep;
          const isUpcoming = stepNumber > currentStep;

          return (
            <li
              key={stepNumber}
              className={`
                relative
                ${index !== totalSteps - 1 ? 'pr-8 sm:pr-20' : ''}
                ${index === 0 ? '' : 'flex-1'}
              `}
            >
              {/* Connector Line */}
              {index !== totalSteps - 1 && (
                <div
                  className="absolute inset-0 flex items-center"
                  aria-hidden="true"
                >
                  <div
                    className={`h-0.5 w-full ${
                      isCompleted ? 'bg-green-600' : 'bg-gray-200'
                    }`}
                  />
                </div>
              )}

              {/* Step Circle */}
              <div className="relative flex items-center justify-center">
                {isCompleted ? (
                  <div className="h-8 w-8 rounded-full bg-green-600 flex items-center justify-center">
                    <CheckIcon className="h-5 w-5 text-white" />
                  </div>
                ) : isActive ? (
                  <div className="h-8 w-8 rounded-full border-2 border-blue-600 bg-white flex items-center justify-center">
                    <span className="text-blue-600 font-semibold text-sm">
                      {stepNumber}
                    </span>
                  </div>
                ) : (
                  <div className="h-8 w-8 rounded-full border-2 border-gray-300 bg-white flex items-center justify-center">
                    <span className="text-gray-500 font-semibold text-sm">
                      {stepNumber}
                    </span>
                  </div>
                )}

                {/* Step Label */}
                <span
                  className={`
                    absolute top-10 w-max text-xs font-medium
                    ${isActive ? 'text-blue-600' : 'text-gray-500'}
                  `}
                >
                  {stepLabels[index]}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

export default StepIndicator;