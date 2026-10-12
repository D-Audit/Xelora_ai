'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import Link from 'next/link';
import { CircleCheck, Loader2 } from 'lucide-react';

import { resetPassword } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { AuthHeader, FieldError, PasswordInput } from '@/components/auth/auth-ui';

const schema = z.object({
  password: z.string().min(8, 'Use at least 8 characters.').max(200),
  confirm: z.string(),
}).refine((values) => values.password === values.confirm, { message: 'The passwords do not match.', path: ['confirm'] });
type Values = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  return <Suspense fallback={null}><ResetPasswordForm /></Suspense>;
}

function ResetPasswordForm() {
  const token = useSearchParams().get('token');
  const [done, setDone] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = async ({ password }: Values) => {
    if (!token) return;
    setFormError(null);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'We could not reset your password. Please try again.');
    }
  };

  if (!token) {
    return (
      <div className="text-center">
        <AuthHeader title="This link is not valid" subtitle="Open the link from your email again, or request a new one." />
        <Button size="lg" className="w-full" asChild><Link href="/forgot-password">Request a new link</Link></Button>
      </div>
    );
  }

  if (done) {
    return (
      <div className="text-center">
        <CircleCheck className="mx-auto h-8 w-8 text-xelora-green" strokeWidth={1.75} />
        <AuthHeader title="Password updated" subtitle="You can now sign in with your new password." />
        <Button size="lg" className="w-full" asChild><Link href="/login">Sign in</Link></Button>
      </div>
    );
  }

  return (
    <>
      <AuthHeader title="Choose a new password" subtitle="Use at least 8 characters. Avoid passwords you use elsewhere." />
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="password">New password</Label>
          <PasswordInput id="password" autoComplete="new-password" error={!!errors.password} {...register('password')} />
          <FieldError message={errors.password?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="confirm">Confirm new password</Label>
          <PasswordInput id="confirm" autoComplete="new-password" error={!!errors.confirm} {...register('confirm')} />
          <FieldError message={errors.confirm?.message} />
        </div>
        {formError && (
          <p className="rounded-lg bg-xelora-error-bg px-3 py-2.5 text-sm text-xelora-error" role="alert">
            {formError} <Link href="/forgot-password" className="font-medium underline">Request a new link</Link>
          </p>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          Update password
        </Button>
      </form>
    </>
  );
}
