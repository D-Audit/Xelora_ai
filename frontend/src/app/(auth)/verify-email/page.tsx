'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CircleAlert, CircleCheck, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { sendVerificationEmail, verifyEmail } from '@/services/auth';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { AuthHeader } from '@/components/auth/auth-ui';

type State = 'checking' | 'verified' | 'failed' | 'no-token';

export default function VerifyEmailPage() {
  return <Suspense fallback={null}><VerifyEmail /></Suspense>;
}

function VerifyEmail() {
  const token = useSearchParams().get('token');
  const [state, setState] = useState<State>(token ? 'checking' : 'no-token');
  const [message, setMessage] = useState('');
  const [resending, setResending] = useState(false);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialize = useAuthStore((s) => s.initialize);
  const started = useRef(false);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (started.current || !token) return;
    started.current = true;
    verifyEmail(token)
      .then(() => setState('verified'))
      .catch((err) => {
        setMessage(err instanceof Error ? err.message : 'This link is invalid or has expired.');
        setState('failed');
      });
  }, [token]);

  const resend = async () => {
    setResending(true);
    try {
      const result = await sendVerificationEmail();
      toast.success(result.alreadyVerified ? 'Your email is already confirmed.' : 'We sent you a new link.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not send the email.');
    } finally {
      setResending(false);
    }
  };

  if (state === 'checking') {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-sm text-xelora-text-secondary">
        <Loader2 className="h-5 w-5 animate-spin" /> Confirming your email…
      </div>
    );
  }

  if (state === 'verified') {
    return (
      <div className="text-center">
        <CircleCheck className="mx-auto h-8 w-8 text-xelora-green" strokeWidth={1.75} />
        <AuthHeader title="Email confirmed" subtitle="Thanks. Your email address is now verified." />
        <Button size="lg" className="w-full" asChild>
          <Link href={isAuthenticated ? '/dashboard/agent' : '/login'}>{isAuthenticated ? 'Continue to Xelora' : 'Sign in'}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="text-center">
      <CircleAlert className="mx-auto h-8 w-8 text-xelora-warning" strokeWidth={1.75} />
      <AuthHeader
        title={state === 'no-token' ? 'Confirm your email' : 'This link did not work'}
        subtitle={state === 'no-token' ? 'Open the link we emailed you to confirm your address.' : message}
      />
      {isAuthenticated ? (
        <Button size="lg" className="w-full" onClick={() => void resend()} disabled={resending}>
          {resending && <Loader2 className="h-4 w-4 animate-spin" />} Send a new link
        </Button>
      ) : (
        <Button size="lg" variant="outline" className="w-full" asChild><Link href="/login">Sign in to get a new link</Link></Button>
      )}
    </div>
  );
}
