'use client';

import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { login } from '@/services/auth';
import { isDesktopApp, webAppEnabled } from '@/lib/is-desktop';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { AuthHeader, Divider, FieldError, OAuthButtons, PasswordInput, hasOAuthProviders } from '@/components/auth/auth-ui';

const schema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
});
type Values = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const setUser = useAuthStore((state) => state.setUser);
  const [rememberMe, setRememberMe] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get('error');
    if (error) {
      toast.error(error);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const onSubmit = async (values: Values) => {
    setFormError(null);
    try {
      const session = await login(values.email, values.password, rememberMe);
      setUser(session.user);
      const next = new URLSearchParams(window.location.search).get('next');
      const target = next && next.startsWith('/') && !next.startsWith('//') ? next : '/dashboard/agent';
      // On the website, sign-in ends with handing off to Xelora Desktop.
      router.push(isDesktopApp() || webAppEnabled ? target : `/open?path=${encodeURIComponent(target)}`);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Sign in failed. Please try again.');
    }
  };

  return (
    <>
      <AuthHeader title="Sign in to Xelora" subtitle="Welcome back. Pick up where you left off." />
      <OAuthButtons />
      {hasOAuthProviders() && <Divider label="or sign in with email" />}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" placeholder="you@company.com" error={!!errors.email} {...register('email')} />
          <FieldError message={errors.email?.message} />
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs font-medium text-xelora-green hover:underline">Forgot password?</Link>
          </div>
          <PasswordInput id="password" autoComplete="current-password" error={!!errors.password} {...register('password')} />
          <FieldError message={errors.password?.message} />
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="remember" checked={rememberMe} onCheckedChange={(checked) => setRememberMe(checked === true)} />
          <Label htmlFor="remember" className="cursor-pointer font-normal text-xelora-text-secondary">Keep me signed in for 7 days</Label>
        </div>
        {formError && <p className="rounded-lg bg-xelora-error-bg px-3 py-2.5 text-sm text-xelora-error" role="alert">{formError}</p>}
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-8 text-center text-sm text-xelora-text-secondary">
        New to Xelora? <Link href="/register" className="font-medium text-xelora-green hover:underline">Create an account</Link>
      </p>
    </>
  );
}
