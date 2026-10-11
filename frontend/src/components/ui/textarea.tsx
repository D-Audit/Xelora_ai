import * as React from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          'flex min-h-[80px] w-full rounded-md border bg-white px-3 py-2 text-sm text-xelora-text',
          'placeholder:text-xelora-text-muted resize-none',
          'transition-colors duration-150',
          'focus:outline-none focus:ring-2 focus:ring-xelora-border-focus focus:border-xelora-border-focus',
          'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-xelora-surface-2',
          error ? 'border-xelora-error' : 'border-xelora-border',
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Textarea.displayName = 'Textarea';

export { Textarea };
