'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import { ArrowLeft, Loader2, MailCheck } from 'lucide-react';

import { requestPasswordReset } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AuthHeader, FieldError } from '@/components/auth/auth-ui';

const schema = z.object({ email: z.string().trim().email('Enter a valid email address.') });
type Values = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = async ({ email }: Values) => {
    setFormError(null);
    try {
      await requestPasswordReset(email);
      setSentTo(email);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    }
  };

  if (sentTo) {
    return (
      <div className="text-center">
        <MailCheck className="mx-auto h-8 w-8 text-xelora-green" strokeWidth={1.75} />
        <AuthHeader title="Check your email" subtitle={<>If an account exists for <span className="font-medium text-xelora-text">{sentTo}</span>, we sent a link to reset your password. It expires in 60 minutes.</>} />
        <p className="text-sm text-xelora-text-secondary">
          No email? Check your spam folder or{' '}
          <button type="button" onClick={() => setSentTo(null)} className="font-medium text-xelora-green hover:underline">try again</button>.
        </p>
        <Button variant="outline" size="lg" className="mt-8 w-full" asChild><Link href="/login">Back to sign in</Link></Button>
      </div>
    );
  }

  return (
    <>
      <AuthHeader title="Reset your password" subtitle="Enter the email you use for Xelora and we will send you a reset link." />
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" placeholder="you@company.com" error={!!errors.email} {...register('email')} />
          <FieldError message={errors.email?.message} />
        </div>
        {formError && <p className="rounded-lg bg-xelora-error-bg px-3 py-2.5 text-sm text-xelora-error" role="alert">{formError}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Send reset link
        </Button>
      </form>
      <Link href="/login" className="mt-8 flex items-center justify-center gap-1.5 text-sm text-xelora-text-secondary hover:text-xelora-text">
        <ArrowLeft className="h-4 w-4" /> Back to sign in
      </Link>
    </>
  );
}
