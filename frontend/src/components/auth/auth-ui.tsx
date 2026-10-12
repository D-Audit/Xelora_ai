'use client';

import { forwardRef, useState } from 'react';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { Input, type InputProps } from '@/components/ui/input';
import { isDesktopApp } from '@/lib/is-desktop';
import { cn } from '@/lib/utils';

export function AuthHeader({ title, subtitle }: { title: string; subtitle?: React.ReactNode }) {
  return (
    <div className="mb-8 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-xelora-text">{title}</h1>
      {subtitle && <p className="mt-2 text-sm text-xelora-text-secondary">{subtitle}</p>}
    </div>
  );
}

export function FieldError({ message }: { message?: string }) {
  if (!message) return null;
  return <p className="text-xs text-xelora-error" role="alert">{message}</p>;
}

export function Divider({ label = 'or' }: { label?: string }) {
  return (
    <div className="my-6 flex items-center gap-3" role="separator">
      <div className="h-px flex-1 bg-xelora-border" />
      <span className="text-xs text-xelora-text-muted">{label}</span>
      <div className="h-px flex-1 bg-xelora-border" />
    </div>
  );
}

export const PasswordInput = forwardRef<HTMLInputElement, InputProps>(function PasswordInput({ className, ...props }, ref) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input ref={ref} type={visible ? 'text' : 'password'} className={cn('pr-10', className)} {...props} />
      <button
        type="button"
        onClick={() => setVisible((value) => !value)}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-xelora-text-muted transition-colors hover:text-xelora-text"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
});

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4" />
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853" />
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" fill="#FBBC05" />
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335" />
    </svg>
  );
}

function MicrosoftMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <rect x="1" y="1" width="7" height="7" fill="#F25022" />
      <rect x="10" y="1" width="7" height="7" fill="#7FBA00" />
      <rect x="1" y="10" width="7" height="7" fill="#00A4EF" />
      <rect x="10" y="10" width="7" height="7" fill="#FFB900" />
    </svg>
  );
}

const showGoogle = process.env.NEXT_PUBLIC_ENABLE_GOOGLE_SIGNIN !== 'false';
const showMicrosoft = process.env.NEXT_PUBLIC_ENABLE_MICROSOFT_SIGNIN === 'true';

export function hasOAuthProviders() {
  return showGoogle || showMicrosoft;
}

/**
 * "Continue with Google / Microsoft". In Xelora Desktop, Google refuses
 * sign-in inside an embedded app window, so the desktop app opens the
 * user's normal browser and receives the session back when it finishes.
 */
export function OAuthButtons() {
  const [pending, setPending] = useState<string | null>(null);

  const start = async (provider: 'google' | 'microsoft') => {
    setPending(provider);
    if (isDesktopApp() && window.xeloraDesktop?.signInWithBrowser) {
      try {
        await window.xeloraDesktop.signInWithBrowser(provider);
      } finally {
        setPending(null);
      }
      return;
    }
    window.location.href = `/api/auth/${provider}/start`;
  };

  if (!hasOAuthProviders()) return null;
  return (
    <div className="flex flex-col gap-2.5">
      {showGoogle && (
        <button
          type="button"
          onClick={() => void start('google')}
          disabled={pending !== null}
          className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border border-xelora-border bg-white text-sm font-medium text-xelora-text shadow-sm transition-colors hover:bg-xelora-surface-2 disabled:opacity-60"
        >
          {pending === 'google' ? <Loader2 className="h-4 w-4 animate-spin" /> : <GoogleMark />}
          Continue with Google
        </button>
      )}
      {showMicrosoft && (
        <button
          type="button"
          onClick={() => void start('microsoft')}
          disabled={pending !== null}
          className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border border-xelora-border bg-white text-sm font-medium text-xelora-text shadow-sm transition-colors hover:bg-xelora-surface-2 disabled:opacity-60"
        >
          {pending === 'microsoft' ? <Loader2 className="h-4 w-4 animate-spin" /> : <MicrosoftMark />}
          Continue with Microsoft
        </button>
      )}
      {pending && isDesktopApp() && (
        <p className="text-center text-xs text-xelora-text-muted">Finish signing in in your browser. Xelora will open when you are done.</p>
      )}
    </div>
  );
}
