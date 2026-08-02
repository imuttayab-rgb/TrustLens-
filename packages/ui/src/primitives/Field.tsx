'use client';

import * as React from 'react';
import { cn } from '../lib/cn';

/**
 * Optional props are written `?: T | undefined` throughout this package.
 * The tsconfig sets `exactOptionalPropertyTypes`, under which a plain `?: T`
 * property may be *omitted* but may not be *assigned* undefined - and every
 * caller here passes `errors.field?.message`, which is exactly that.
 */
export interface FieldProps {
  /** Must match the control's `id`, or the label clicks through to nothing. */
  htmlFor: string;
  label: string;
  /** Shown below the control until an error replaces it. */
  hint?: string | undefined;
  error?: string | undefined;
  required?: boolean | undefined;
  className?: string | undefined;
  children: React.ReactNode;
}

/**
 * Label + control + message, with the ARIA wiring done once.
 *
 * Every form in the app repeats the same three mistakes otherwise: the error
 * is not linked to the input, so a screen reader never announces it; the
 * message lacks `role="alert"`, so it is not announced when it appears; and
 * the hint id is forgotten, so the control describes itself as invalid with
 * no explanation. Doing it here means no screen can get it wrong.
 *
 * Pass the ids through to the control with {@link fieldAria}.
 */
export function Field({ htmlFor, label, hint, error, required, className, children }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="block text-sm font-medium">
        {label}
        {required && (
          <span className="text-destructive ml-0.5" aria-hidden="true">
            *
          </span>
        )}
      </label>

      {children}

      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-destructive text-sm">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${htmlFor}-hint`} className="text-muted-foreground text-sm">
            {hint}
          </p>
        )
      )}
    </div>
  );
}

/** The aria attributes a control inside a {@link Field} needs. */
export function fieldAria(id: string, error?: string, hint?: string) {
  return {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error ? `${id}-error` : hint ? `${id}-hint` : undefined,
  } as const;
}
