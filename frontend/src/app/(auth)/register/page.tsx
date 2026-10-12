'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Check, Loader2 } from 'lucide-react';

import { register as registerUser } from '@/services/auth';
import { isDesktopApp, webAppEnabled } from '@/lib/is-desktop';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AuthHeader, Divider, FieldError, OAuthButtons, PasswordInput, hasOAuthProviders } from '@/components/auth/auth-ui';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';

const schema = z.object({
  name: z.string().trim().min(1, 'Enter your name.').max(200),
  email: z.string().trim().email('Enter a valid email address.'),
  password: z.string().min(8, 'Use at least 8 characters.').max(200),
});
type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const setUser = useAuthStore((state) => state.setUser);
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });
  const password = watch('password') ?? '';

  const onSubmit = async (values: Values) => {
    setFormError(null);
    try {
      const session = await registerUser({ ...values, country: '', primaryUse: '' });
      setUser(session.user);
      router.push(isDesktopApp() || webAppEnabled ? '/onboarding' : '/open?welcome=1');
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'We could not create your account. Please try again.');
    }
  };

  return (
    <>
      <AuthHeader title="Create your account" subtitle={`Start your ${site.trialDays}-day free trial. No credit card required.`} />
      <OAuthButtons />
      {hasOAuthProviders() && <Divider label="or sign up with email" />}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Full name</Label>
          <Input id="name" autoComplete="name" placeholder="Jane Doe" error={!!errors.name} {...register('name')} />
          <FieldError message={errors.name?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" placeholder="you@company.com" error={!!errors.email} {...register('email')} />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <PasswordInput id="password" autoComplete="new-password" error={!!errors.password} {...register('password')} />
          {errors.password ? (
            <FieldError message={errors.password.message} />
          ) : (
            <p className={cn('flex items-center gap-1.5 text-xs', password.length >= 8 ? 'text-xelora-green' : 'text-xelora-text-muted')}>
              <Check className="h-3.5 w-3.5" /> At least 8 characters
            </p>
          )}
        </div>
        {formError && <p className="rounded-lg bg-xelora-error-bg px-3 py-2.5 text-sm text-xelora-error" role="alert">{formError}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </Button>
        <p className="text-center text-xs leading-relaxed text-xelora-text-muted">
          By creating an account you agree to our{' '}
          <Link href="/terms" className="underline hover:text-xelora-text">Terms of Service</Link> and{' '}
          <Link href="/privacy" className="underline hover:text-xelora-text">Privacy Policy</Link>.
        </p>
      </form>

      <p className="mt-8 text-center text-sm text-xelora-text-secondary">
        Already have an account? <Link href="/login" className="font-medium text-xelora-green hover:underline">Sign in</Link>
      </p>
    </>
  );
}
