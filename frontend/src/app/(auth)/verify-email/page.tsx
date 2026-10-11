'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Loader2, MailCheck } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { XeloraLogo } from '@/components/ui/xelora-logo';

const COOLDOWN_SECONDS = 60;

export default function VerifyEmailPage() {
  const [cooldown, setCooldown] = useState(0);
  const [isSending, setIsSending] = useState(false);
  const [sentCount, setSentCount] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(id);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [cooldown]);

  const handleResend = useCallback(async () => {
    if (cooldown > 0 || isSending) return;
    setIsSending(true);
    await new Promise((resolve) => setTimeout(resolve, 800));
    setIsSending(false);
    setSentCount((c) => c + 1);
    setCooldown(COOLDOWN_SECONDS);
  }, [cooldown, isSending]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-center">
        <Link href="/" aria-label="Go to homepage">
          <XeloraLogo size="lg" />
        </Link>
      </div>

      <Card>
        <CardHeader className="items-center text-center pb-2">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-xelora-success-bg mb-2">
            <MailCheck className="h-7 w-7 text-xelora-green" />
          </div>
          <CardTitle className="text-xl font-semibold text-xelora-text">
            Verify your email address
          </CardTitle>
          <CardDescription className="text-center">
            We&apos;ve sent a verification link to your email address. Click the link to activate
            your account.
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col items-center gap-4">
          {sentCount > 0 && (
            <p className="text-sm text-xelora-success text-center">
              Verification email resent. Please check your inbox (and spam folder).
            </p>
          )}

          <Button
            type="button"
            variant="outline"
            size="lg"
            className="w-full"
            onClick={handleResend}
            disabled={cooldown > 0 || isSending}
          >
            {isSending && <Loader2 className="h-4 w-4 animate-spin" />}
            {isSending
              ? 'Sending…'
              : cooldown > 0
              ? `Resend in ${cooldown}s`
              : 'Resend verification email'}
          </Button>

          <p className="text-xs text-xelora-text-muted text-center">
            Make sure to check your spam or junk folder if you don&apos;t see the email.
          </p>

          <Link
            href="/login"
            className="text-sm text-xelora-text-secondary hover:text-xelora-text transition-colors"
          >
            ← Back to sign in
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
