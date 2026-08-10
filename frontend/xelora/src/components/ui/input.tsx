import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'flex h-9 w-full rounded-md border bg-xelora-surface px-3 py-2 text-sm text-xelora-text placeholder:text-xelora-text-muted',
          'transition-colors duration-150',
          'focus:outline-none focus:ring-2 focus:ring-xelora-border-focus focus:border-xelora-border-focus',
          'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-xelora-surface-2',
          error
            ? 'border-xelora-error focus:ring-xelora-error'
            : 'border-xelora-border',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
