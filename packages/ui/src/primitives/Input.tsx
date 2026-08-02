'use client';

import * as React from 'react';
import { cn } from '../lib/cn';

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

/**
 * Text input.
 *
 * Two mobile decisions are baked in and should not be overridden lightly:
 *
 * `h-11` is 44px, the minimum comfortable touch target. `h-10` looks tidier on
 * a laptop and is genuinely hard to hit on a phone.
 *
 * `text-base sm:text-sm` keeps the font at 16px on small screens. Safari on
 * iOS zooms the whole page whenever a focused input renders below 16px, and
 * it does not zoom back out - which silently breaks the layout mid-form. The
 * smaller size returns at the `sm` breakpoint where no phone is affected.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        'border-input bg-background flex h-11 w-full rounded-md border px-3 py-2',
        'text-base sm:text-sm',
        'placeholder:text-muted-foreground',
        'focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'aria-[invalid=true]:border-destructive aria-[invalid=true]:focus-visible:ring-destructive',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
