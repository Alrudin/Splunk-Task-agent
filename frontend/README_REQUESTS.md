# Request Submission & Sample Upload - Frontend UI

## Overview

This module implements a multi-step wizard for submitting log onboarding requests with sample file uploads. Built with React, TypeScript, React Hook Form, and Tailwind CSS.

## User Flow

1. **Step 1: Request Metadata**
   - Enter source system name
   - Provide detailed description
   - Select CIM compliance requirement
   - Optionally add JSON metadata

2. **Step 2: Upload Samples**
   - Upload log sample files (drag-and-drop or click)
   - View upload progress in real-time
   - Review uploaded samples (filename, size, upload date)
   - Delete samples if needed

3. **Step 3: Review & Submit**
   - Review request details
   - Verify attached samples
   - Submit for approval (transitions to PENDING_APPROVAL)

## Components

### Main Page

**`frontend/src/pages/NewRequest/index.tsx`**
- Orchestrates 3-step wizard
- Manages form state across steps
- Handles API mutations (create, upload, submit)
- Navigation logic between steps

### Step Components

**`StepIndicator.tsx`**
- Visual progress indicator
- Shows completed (green), active (blue), upcoming (gray) steps
- Displays step labels below circles

**`MetadataStep.tsx`**
- React Hook Form with Zod validation
- Validates source system (alphanumeric + spaces/hyphens/underscores)
- Validates description (min 10, max 5000 chars)
- JSON metadata validation on blur
- Displays inline validation errors

**`UploadStep.tsx`**
- Uses React Query for sample fetching
- Integrates file input for uploads
- Displays uploaded samples in table format
- Delete button for each sample
- Validates at least 1 sample before proceeding

**`ReviewStep.tsx`**
- Displays request metadata summary
- Lists all attached samples with sizes
- Shows total sample size
- Submit button with loading state
- Navigates to request detail page on success

### Shared Components

**`FileUpload.tsx`** (not used in current UploadStep but available)
- Reusable drag-and-drop component
- React Dropzone integration
- Progress bars for each file
- Client-side validation (size, type)
- Status indicators (pending, uploading, completed, error)

## API Integration

**`frontend/src/api/requests.ts`**

Functions:
- `createRequest(data)` - POST /requests
- `getRequests(params)` - GET /requests
- `getRequest(id)` - GET /requests/{id}
- `updateRequest(id, data)` - PUT /requests/{id}
- `uploadSample(requestId, file, onProgress)` - POST /requests/{id}/samples
- `getSamples(requestId)` - GET /requests/{id}/samples
- `deleteSample(requestId, sampleId)` - DELETE /requests/{id}/samples/{sampleId}
- `submitRequest(requestId)` - POST /requests/{id}/submit

All functions use axios with interceptors for:
- JWT token injection
- snake_case ↔ camelCase conversion
- Error transformation
- Upload progress tracking

## Type Definitions

**`frontend/src/types/request.ts`**

Key types:
- `RequestStatus` - Enum matching backend
- `CreateRequestData` - Form submission data
- `Request` - Request response
- `RequestDetail` - Request with samples/revisions/runs
- `Sample` - Sample file metadata
- `RequestFormData` - Wizard form data

Utility functions:
- `snakeToCamel(obj)` - Convert API responses
- `camelToSnake(obj)` - Convert API requests

## Formatting Utilities

**`frontend/src/utils/formatters.ts`**

- `formatFileSize(bytes)` → "1.23 MB"
- `formatDate(date)` → "Jan 17, 2025, 10:00 AM"
- `formatRelativeTime(date)` → "2 hours ago"
- `truncateText(text, maxLength)` → "Text..."
- `formatRequestStatus(status)` → "Pending Approval"
- `getStatusColorClass(status)` → "bg-yellow-100 text-yellow-800"

## State Management

Uses React Query for server state:
- `useQuery` for fetching samples
- `useMutation` for create, upload, delete, submit operations
- Automatic cache invalidation with `refetch()`

Uses React Hook Form for form state:
- Zod schema validation
- `mode: 'onChange'` for real-time validation
- Controlled inputs with `register()`

## Styling

Tailwind CSS with custom classes:
- Card layouts (`bg-white shadow rounded-lg p-6`)
- Form inputs (`border-gray-300 focus:border-blue-500`)
- Buttons (`bg-blue-600 hover:bg-blue-700`)
- Status badges (`bg-green-100 text-green-800`)
- Progress bars (`bg-blue-600 h-1.5 rounded-full`)

## Accessibility

- ARIA labels on step indicator
- Screen reader support for form validation errors
- Keyboard navigation through wizard
- Focus management on step transitions

## Error Handling

- React Hot Toast for notifications
- API errors transformed to user-friendly messages
- Inline validation errors on forms
- Disabled states prevent invalid submissions

## Routing

**Protected Route:** `/requests/new`
- Requires authentication
- Requires REQUESTOR role
- Redirects to login if unauthenticated

Added to `App.tsx`:
```tsx
<Route
  path="/requests/new"
  element={
    <ProtectedRoute requiredRole="REQUESTOR">
      <NewRequest />
    </ProtectedRoute>
  }
/>
```

## Example Usage

```tsx
// Navigate to new request page
import { useNavigate } from 'react-router-dom';

const navigate = useNavigate();
navigate('/requests/new');
```

## Testing

```bash
# Install dependencies
cd frontend
npm install

# Run development server
npm run dev

# Access at
open http://localhost:5173/requests/new
```

## Dependencies

Required packages (already in `package.json`):
- `react-hook-form` - Form state management
- `@hookform/resolvers` - Zod integration
- `zod` - Schema validation
- `@tanstack/react-query` - Server state
- `react-router-dom` - Routing
- `react-hot-toast` - Notifications
- `react-dropzone` - Drag-and-drop (optional)
- `@heroicons/react` - Icons
- `date-fns` - Date formatting
- `axios` - HTTP client

## Future Enhancements

- Resume incomplete requests (save draft to localStorage)
- Batch file uploads with parallel processing
- Sample preview modal (first 100 lines)
- Validation progress indicators
- Request templates for common log sources
- Autocomplete for source system names