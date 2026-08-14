'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import { Loader2, MailCheck } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { XeloraLogo } from '@/components/ui/xelora-logo';

const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email address.'),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    setSubmittedEmail(values.email);
    setSubmitted(true);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-center">
        <Link href="/" aria-label="Go to homepage">
          <XeloraLogo size="lg" />
        </Link>
      </div>

      <Card>
        {submitted ? (
          <CardContent className="pt-8 pb-8">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-xelora-success-bg">
                <MailCheck className="h-7 w-7 text-xelora-green" />
              </div>
              <div className="flex flex-col gap-1">
                <h2 className="text-base font-semibold text-xelora-text">Check your email</h2>
                <p className="text-sm text-xelora-text-secondary">
                  We&apos;ve sent a reset link to{' '}
                  <span className="font-medium text-xelora-text">{submittedEmail}</span>.
                  Follow the instructions in the email to reset your password.
                </p>
              </div>
              <p className="text-xs text-xelora-text-muted">
                Didn&apos;t receive the email? Check your spam folder, or{' '}
                <button
                  type="button"
                  onClick={() => setSubmitted(false)}
                  className="text-xelora-green hover:underline"
                >
                  try a different email
                </button>
                .
              </p>
            </div>
          </CardContent>
        ) : (
          <>
            <CardHeader className="text-center pb-2">
              <CardTitle className="text-xl font-semibold text-xelora-text">
                Reset your password
              </CardTitle>
              <CardDescription>
                Enter your email address and we&apos;ll send you a link to reset your password.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    error={!!errors.email}
                    {...register('email')}
                  />
                  {errors.email && (
                    <p className="text-xs text-xelora-error">{errors.email.message}</p>
                  )}
                </div>

                <Button
                  type="submit"
                  variant="default"
                  size="lg"
                  className="w-full"
                  disabled={isSubmitting}
                >
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isSubmitting ? 'Sending…' : 'Send reset link'}
                </Button>
              </form>
            </CardContent>
          </>
        )}

        <div className="flex justify-center pb-5">
          <Link
            href="/login"
            className="text-sm text-xelora-text-secondary hover:text-xelora-text transition-colors"
          >
            ← Back to sign in
          </Link>
        </div>
      </Card>
    </div>
  );
}
