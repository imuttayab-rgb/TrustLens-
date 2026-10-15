/** Use api form module; defines FormError, useApiForm. */
'use client';

import { toApiError } from '@trustlens/api-client';
import { useCallback, useState } from 'react';
import type { FieldValues, Path, UseFormSetError } from 'react-hook-form';

export interface FormError {
  message: string;
  // `| undefined` because the tsconfig sets exactOptionalPropertyTypes: an
  // optional property may be absent but may not be assigned undefined, and
  // this one is copied straight off ApiError.
  requestId: string | undefined;
}

/**
 * Turns an API failure into form state, the same way on every screen.
 *
 * The backend returns RFC 9457 with an `errors[]` array of field violations.
 * Those belong on the inputs the user typed into; anything else is a
 * form-level message. Doing this per-form drifts - one screen forgets the
 * field mapping and users see "Validation failed" with no idea which box is
 * wrong.
 *
 * Usage:
 *
 *     const { submit, formError, clearError } = useApiForm(setError);
 *     const onSubmit = handleSubmit((values) => submit(async () => {
 *       const r = await api.POST('/api/v1/auth/register', { body: values });
 *       if (r.error) throw r.error;
 *     }));
 */
export function useApiForm<T extends FieldValues>(setError: UseFormSetError<T>) {
  const [formError, setFormError] = useState<FormError | null>(null);

  const clearError = useCallback(() => setFormError(null), []);

  const submit = useCallback(
    async (action: () => Promise<void>): Promise<boolean> => {
      setFormError(null);
      try {
        await action();
        return true;
      } catch (raw) {
        const error = toApiError(raw);
        const fields = Object.entries(error.fieldErrors);
        for (const [field, message] of fields) {
          setError(field as Path<T>, { message });
        }
        // Only fall back to a banner when nothing landed on a field -
        // otherwise the user reads the same complaint twice.
        if (fields.length === 0) {
          setFormError({ message: error.message, requestId: error.requestId });
        }
        return false;
      }
    },
    [setError],
  );

  return { submit, formError, setFormError, clearError };
}
