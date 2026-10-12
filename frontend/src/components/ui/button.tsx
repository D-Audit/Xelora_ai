'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-xelora-green text-white shadow-sm hover:bg-xelora-deep-green',
        primary: 'bg-xelora-green text-white shadow-sm hover:bg-xelora-deep-green',
        // Kept for existing call sites; now the same calm primary style.
        bright: 'bg-xelora-green text-white shadow-sm hover:bg-xelora-deep-green',
        destructive: 'bg-xelora-error text-white shadow-sm hover:bg-[#991B1B]',
        outline: 'border border-xelora-border bg-xelora-surface text-xelora-text shadow-sm hover:border-xelora-border-strong hover:bg-xelora-surface-2',
        secondary: 'bg-xelora-surface-2 text-xelora-text hover:bg-xelora-border',
        ghost: 'text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text',
        link: 'text-xelora-green underline-offset-4 hover:underline p-0 h-auto',
        dark: 'bg-xelora-text text-xelora-surface shadow-sm hover:opacity-90',
      },
      size: {
        default: 'h-9 px-4',
        sm: 'h-8 px-3 text-[13px]',
        lg: 'h-11 px-5 text-[15px]',
        xl: 'h-12 px-7 text-base',
        icon: 'h-9 w-9',
        'icon-sm': 'h-8 w-8',
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
