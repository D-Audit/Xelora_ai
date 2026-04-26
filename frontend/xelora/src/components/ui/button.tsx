'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-xelora-green text-white hover:bg-xelora-deep-green',
        primary: 'bg-xelora-green text-white hover:bg-xelora-deep-green',
        bright: 'bg-xelora-bright-green text-xelora-black font-semibold hover:bg-[#00d458]',
        destructive: 'bg-xelora-error text-white hover:bg-[#9b1e14]',
        outline: 'border border-xelora-border bg-white text-xelora-text hover:bg-xelora-surface-2',
        secondary: 'bg-xelora-surface-2 text-xelora-text hover:bg-xelora-border',
        ghost: 'text-xelora-text hover:bg-xelora-surface-2',
        link: 'text-xelora-info underline-offset-4 hover:underline p-0 h-auto',
        dark: 'bg-xelora-black text-white hover:bg-xelora-deep-green',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-7 px-3 text-xs',
        lg: 'h-11 px-6 text-base',
        xl: 'h-12 px-8 text-base',
        icon: 'h-9 w-9',
        'icon-sm': 'h-7 w-7',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
