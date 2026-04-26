import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'bg-xelora-surface-2 text-xelora-text border border-xelora-border',
        success: 'bg-xelora-success-bg text-xelora-success',
        info: 'bg-xelora-info-bg text-xelora-info',
        warning: 'bg-xelora-warning-bg text-xelora-warning',
        error: 'bg-xelora-error-bg text-xelora-error',
        green: 'bg-xelora-green text-white',
        dark: 'bg-xelora-black text-white',
        outline: 'border border-xelora-border text-xelora-text-secondary bg-transparent',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
