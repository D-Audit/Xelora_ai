'use client';

import React, { useState, useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { Eye, EyeOff, Loader2 } from 'lucide-react';

import { register as registerUser } from '@/services/auth';
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
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { XeloraLogo } from '@/components/ui/xelora-logo';

const registerSchema = z
  .object({
    name: z.string().min(2, 'Name must be at least 2 characters.'),
    email: z.string().email('Please enter a valid email address.'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters.')
      .refine((v) => /[A-Z]/.test(v), 'Password must contain at least one uppercase letter.')
      .refine((v) => /[0-9]/.test(v), 'Password must contain at least one number.'),
    confirmPassword: z.string().min(1, 'Please confirm your password.'),
    country: z.string().min(1, 'Please select your country.'),
    primaryUse: z.string().min(1, 'Please select your primary use.'),
    agreeToTerms: z
      .boolean()
      .refine((value) => value, 'You must agree to the terms to continue.'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

const COUNTRIES = [
  { value: 'us', label: 'Rwanda' },
  { value: 'gb', label: 'Uganda' },
  { value: 'ca', label: 'Kenya' },
  { value: 'au', label: 'Burundi' },
  { value: 'de', label: 'United States' },
  { value: 'fr', label: 'France' },
  { value: 'in', label: 'India' },
  { value: 'br', label: 'Brazil' },
  { value: 'ng', label: 'Nigeria' },
  { value: 'za', label: 'South Africa' },
];

const PRIMARY_USE_OPTIONS = [
  { value: 'accounting', label: 'Accounting' },
  { value: 'business-operations', label: 'Business Operations' },
  { value: 'human-resources', label: 'Human Resources' },
  { value: 'data-analysis', label: 'Data Analysis' },
  { value: 'education', label: 'Education' },
  { value: 'research', label: 'Research' },
  { value: 'personal-productivity', label: 'Personal Productivity' },
];

function getPasswordStrength(password: string): {
  label: string;
  level: 0 | 1 | 2 | 3;
} {
  if (!password) return { label: '', level: 0 };
  const hasUpper = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const score = (password.length >= 8 ? 1 : 0) + (hasUpper ? 1 : 0) + (hasNumber ? 1 : 0) + (hasSpecial ? 1 : 0);
  if (score <= 1) return { label: 'Weak', level: 1 };
  if (score <= 2) return { label: 'Fair', level: 2 };
  return { label: 'Strong', level: 3 };
}

const strengthColors: Record<number, string> = {
  1: 'bg-xelora-error',
  2: 'bg-xelora-warning',
  3: 'bg-xelora-success',
};

const strengthTextColors: Record<number, string> = {
  1: 'text-xelora-error',
  2: 'text-xelora-warning',
  3: 'text-xelora-success',
};

export default function RegisterPage() {
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
  const [showConfirm, setShowConfirm] = useState(false);

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { agreeToTerms: false },
  });

  const passwordValue = watch('password') ?? '';
  const agreeToTerms = watch('agreeToTerms');
  const strength = getPasswordStrength(passwordValue);

  const onSubmit = async (values: RegisterFormValues) => {
    try {
      const session = await registerUser({
        name: values.name,
        email: values.email,
        password: values.password,
        country: values.country,
        primaryUse: values.primaryUse,
      });
      setUser(session.user);
      router.push('/onboarding');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    }
  };

  return (
    <div className="auth-page auth-register-page flex flex-col gap-6">
      <div className="hidden">
        <Link href="/" aria-label="Go to homepage">
          <XeloraLogo size="lg" />
        </Link>
      </div>

      <Card className="auth-card">
        <CardHeader className="auth-card-header pb-2">
          <span className="auth-form-kicker">Create your workspace</span>
          <CardTitle className="auth-form-title text-xelora-text">
            Create your account
          </CardTitle>
          <CardDescription>
            Start your 14-day free trial. No credit card required.
          </CardDescription>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="name">Full name</Label>
              <Input
                id="name"
                type="text"
                autoComplete="name"
                placeholder="Jane Smith"
                error={!!errors.name}
                {...register('name')}
              />
              {errors.name && (
                <p className="text-xs text-xelora-error">{errors.name.message}</p>
              )}
            </div>

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
                  autoComplete="new-password"
                  placeholder="Min. 8 characters"
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
              {passwordValue.length > 0 && (
                <div className="flex flex-col gap-1">
                  <div className="flex gap-1">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                          strength.level >= i
                            ? strengthColors[strength.level]
                            : 'bg-xelora-border'
                        }`}
                      />
                    ))}
                  </div>
                  <p className={`text-xs font-medium ${strengthTextColors[strength.level]}`}>
                    {strength.label}
                  </p>
                </div>
              )}
              {errors.password && (
                <p className="text-xs text-xelora-error">{errors.password.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  type={showConfirm ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  error={!!errors.confirmPassword}
                  className="pr-10"
                  {...register('confirmPassword')}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-xelora-text-muted hover:text-xelora-text transition-colors"
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirmPassword && (
                <p className="text-xs text-xelora-error">{errors.confirmPassword.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="country">Country</Label>
              <Controller
                name="country"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger id="country" className={errors.country ? 'border-xelora-error' : ''}>
                      <SelectValue placeholder="Select your country" />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                          {c.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.country && (
                <p className="text-xs text-xelora-error">{errors.country.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="primaryUse">Primary use</Label>
              <Controller
                name="primaryUse"
                control={control}
                render={({ field }) => (
                  <Select onValueChange={field.onChange} value={field.value}>
                    <SelectTrigger id="primaryUse" className={errors.primaryUse ? 'border-xelora-error' : ''}>
                      <SelectValue placeholder="How will you use Xelora?" />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIMARY_USE_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
              {errors.primaryUse && (
                <p className="text-xs text-xelora-error">{errors.primaryUse.message}</p>
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <div className="flex items-start gap-2">
                <Checkbox
                  id="agreeToTerms"
                  checked={!!agreeToTerms}
                  onCheckedChange={(checked) =>
                    setValue('agreeToTerms', checked === true, { shouldValidate: true })
                  }
                  className="auth-terms-checkbox mt-0.5"
                />
                <Label htmlFor="agreeToTerms" className="font-normal cursor-pointer leading-snug">
                  I agree to the{' '}
                  <Link
                    href="/terms"
                    className="text-xelora-green hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Terms of Service
                  </Link>
                </Label>
              </div>
              {errors.agreeToTerms && (
                <p className="text-xs text-xelora-error">{errors.agreeToTerms.message}</p>
              )}
            </div>

            <Button
              type="submit"
              variant="default"
              size="lg"
              className="w-full mt-1"
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </Button>
          </form>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-xelora-border" />
            <span className="text-xs text-xelora-text-muted">or continue with</span>
            <div className="flex-1 h-px bg-xelora-border" />
          </div>

          <div className="flex flex-col gap-2">
            <Button variant="outline" size="lg" className="w-full" type="button" onClick={() => { window.location.href = '/api/auth/google/start'; }}>
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

            <Button variant="outline" size="lg" className="w-full" type="button" onClick={() => { window.location.href = '/api/auth/microsoft/start'; }}>
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
            Already have an account?{' '}
            <Link href="/login" className="text-xelora-green font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
