'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

import { login } from '@/services/auth';
import { useAuthStore } from '@/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { XeloraLogo } from '@/components/ui/xelora-logo';

const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address.'),
  password: z.string().min(1, 'Password is required.'),
  rememberMe: z.boolean().optional(),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get('error');
    if (error) {
      toast.error(error);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);
  const setUser = useAuthStore((s) => s.setUser);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { rememberMe: false },
  });

  const rememberMe = watch('rememberMe');

  const onSubmit = async (values: LoginFormValues) => {
    try {
      const session = await login(values.email, values.password);
      setUser(session.user);
      router.push('/dashboard');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Sign in failed. Please try again.');
    }
  };

  return (
    <div className="auth-page auth-login-page flex flex-col gap-6">
      <div className="hidden">
        <Link href="/" aria-label="Go to homepage">
          <XeloraLogo size="lg" />
        </Link>
      </div>

      <Card className="auth-card">
        <CardHeader className="auth-card-header pb-2">
          <span className="auth-form-kicker">Welcome back</span>
          <CardTitle className="auth-form-title text-xelora-text">
            Sign in to your workspace
          </CardTitle>
          <CardDescription>
            Pick up where you left off and put your next workbook on autopilot.
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

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  error={!!errors.password}
                  className="pr-10"
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-xelora-text-muted hover:text-xelora-text transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-xs text-xelora-error">{errors.password.message}</p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="rememberMe"
                  checked={!!rememberMe}
                  onCheckedChange={(checked) =>
                    setValue('rememberMe', checked === true)
                  }
                />
                <Label htmlFor="rememberMe" className="font-normal cursor-pointer">
                  Remember me
                </Label>
              </div>
              <Link
                href="/forgot-password"
                className="text-sm text-xelora-green hover:underline"
              >
                Forgot password?
              </Link>
            </div>

            <Button
              type="submit"
              variant="default"
              size="lg"
              className="w-full mt-1"
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-xelora-border" />
            <span className="text-xs text-xelora-text-muted">or continue with</span>
            <div className="flex-1 h-px bg-xelora-border" />
          </div>

          <div className="flex flex-col gap-2">
            <Button
              variant="outline"
              size="lg"
              className="w-full"
              type="button"
              onClick={() => { window.location.href = '/api/auth/google/start'; }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                <path
                  d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"
                  fill="#4285F4"
                />
                <path
                  d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"
                  fill="#34A853"
                />
                <path
                  d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z"
                  fill="#FBBC05"
                />
                <path
                  d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z"
                  fill="#EA4335"
                />
              </svg>
              Continue with Google
            </Button>

            <Button
              variant="outline"
              size="lg"
              className="w-full"
              type="button"
              onClick={() => { window.location.href = '/api/auth/microsoft/start'; }}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                <rect x="1" y="1" width="7" height="7" fill="#F25022" />
                <rect x="10" y="1" width="7" height="7" fill="#7FBA00" />
                <rect x="1" y="10" width="7" height="7" fill="#00A4EF" />
                <rect x="10" y="10" width="7" height="7" fill="#FFB900" />
              </svg>
              Continue with Microsoft
            </Button>
          </div>

          <p className="text-center text-sm text-xelora-text-secondary mt-4">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-xelora-green font-medium hover:underline">
              Start free trial
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
