'use client';

import { Eye, EyeOff } from 'lucide-react';
import * as React from 'react';
import { cn } from '../lib/cn';
import { Input, type InputProps } from './Input';

export type PasswordInputProps = Omit<InputProps, 'type'>;

/**
 * A password `Input` with a show/hide toggle - the toggle only ever changes
 * how the value is *displayed*; the field is still submitted the same way
 * either way, so this is safe to drop in wherever `<Input type="password">`
 * was.
 */
export const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, ...props }, ref) => {
    const [visible, setVisible] = React.useState(false);

    return (
      <div className="relative">
        <Input
          ref={ref}
          type={visible ? 'text' : 'password'}
          className={cn('pr-11', className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          className="text-muted-foreground hover:text-foreground focus-visible:ring-ring absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-md focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:outline-none"
        >
          {visible ? (
            <EyeOff className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Eye className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>
    );
  },
);
PasswordInput.displayName = 'PasswordInput';
