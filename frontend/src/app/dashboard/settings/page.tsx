'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { CircleCheck, Loader2, Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { FieldError, PasswordInput } from '@/components/auth/auth-ui';
import { changePassword, sendVerificationEmail, updateProfile } from '@/services/auth';
import { useAuthStore } from '@/stores/auth-store';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-b border-xelora-border py-8 last:border-b-0 lg:grid-cols-[260px_1fr]">
      <div>
        <h2 className="text-sm font-semibold text-xelora-text">{title}</h2>
        <p className="mt-1 text-sm leading-relaxed text-xelora-text-secondary">{description}</p>
      </div>
      <div className="max-w-xl">{children}</div>
    </section>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuthStore();
  const [name, setName] = useState(user?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);

  const save = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const updated = await updateProfile(name.trim());
      if (user) setUser({ ...user, name: updated.name });
      toast.success('Profile saved.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not save your profile.');
    } finally {
      setSaving(false);
    }
  };

  const resend = async () => {
    setSending(true);
    try {
      const result = await sendVerificationEmail();
      toast.success(result.alreadyVerified ? 'Your email is already confirmed.' : `We sent a confirmation link to ${user?.email}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not send the email.');
    } finally {
      setSending(false);
    }
  };

  return (
    <Section title="Profile" description="Your name is shown in the app and in emails from Xelora.">
      <div className="space-y-5">
        <div className="space-y-1.5">
          <Label htmlFor="name">Full name</Label>
          <Input id="name" value={name} onChange={(event) => setName(event.target.value)} maxLength={200} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input id="email" value={user?.email ?? ''} disabled />
          {user?.isVerified ? (
            <p className="flex items-center gap-1.5 text-xs text-xelora-green"><CircleCheck className="h-3.5 w-3.5" /> Confirmed</p>
          ) : (
            <p className="text-xs text-xelora-text-secondary">
              Not confirmed yet.{' '}
              <button type="button" onClick={() => void resend()} disabled={sending} className="font-medium text-xelora-green hover:underline disabled:opacity-50">
                {sending ? 'Sending…' : 'Send confirmation email'}
              </button>
            </p>
          )}
        </div>
        <Button onClick={() => void save()} disabled={saving || !name.trim() || name.trim() === user?.name}>
          {saving && <Loader2 className="h-4 w-4 animate-spin" />} Save changes
        </Button>
      </div>
    </Section>
  );
}

const passwordSchema = z.object({
  current: z.string(),
  next: z.string().min(8, 'Use at least 8 characters.').max(200),
});
type PasswordValues = z.infer<typeof passwordSchema>;

function PasswordSection() {
  const { user, setUser } = useAuthStore();
  const hasPassword = user?.hasPassword !== false;
  const { register, handleSubmit, reset, setError, formState: { errors, isSubmitting } } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: '', next: '' },
  });

  const onSubmit = async (values: PasswordValues) => {
    if (hasPassword && !values.current) {
      setError('current', { message: 'Enter your current password.' });
      return;
    }
    try {
      await changePassword(hasPassword ? values.current : null, values.next);
      reset({ current: '', next: '' });
      if (user && !hasPassword) setUser({ ...user, hasPassword: true });
      toast.success(hasPassword ? 'Password updated.' : 'Password set. You can now also sign in with your email.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update your password.');
    }
  };

  return (
    <Section
      title="Password"
      description={hasPassword ? 'Use at least 8 characters. Avoid passwords you use elsewhere.' : 'You sign in with Google. Set a password to also sign in with your email.'}
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
        {hasPassword && (
          <div className="space-y-1.5">
            <Label htmlFor="current">Current password</Label>
            <PasswordInput id="current" autoComplete="current-password" error={!!errors.current} {...register('current')} />
            <FieldError message={errors.current?.message} />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="next">New password</Label>
          <PasswordInput id="next" autoComplete="new-password" error={!!errors.next} {...register('next')} />
          <FieldError message={errors.next?.message} />
        </div>
        <div className="flex items-center gap-4">
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />} {hasPassword ? 'Update password' : 'Set password'}
          </Button>
          {hasPassword && <Link href="/forgot-password" className="text-sm text-xelora-text-secondary hover:text-xelora-text">Forgot it?</Link>}
        </div>
      </form>
    </Section>
  );
}

function AppearanceSection() {
  const { theme, setTheme } = useTheme();
  const options = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ];
  return (
    <Section title="Appearance" description="Choose how Xelora looks on this device.">
      <div className="grid grid-cols-3 gap-3" role="radiogroup" aria-label="Theme">
        {options.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={theme === value}
            onClick={() => setTheme(value)}
            className={cn(
              'flex flex-col items-start gap-3 rounded-xl border p-4 text-left text-sm transition-colors',
              theme === value ? 'border-xelora-text ring-1 ring-xelora-text' : 'border-xelora-border hover:border-xelora-border-strong'
            )}
          >
            <Icon className="h-4 w-4 text-xelora-text" strokeWidth={1.75} />
            <span className="font-medium text-xelora-text">{label}</span>
          </button>
        ))}
      </div>
    </Section>
  );
}

export default function SettingsPage() {
  const user = useAuthStore((state) => state.user);
  return (
    <div className="mx-auto max-w-5xl">
      <DashboardPageHeader title="Settings" description="Manage your profile, sign-in and preferences." />
      <div className="mt-2">
        <ProfileSection key={user?.id} />
        <PasswordSection />
        <AppearanceSection />
        <Section title="Xelora Desktop" description="The Windows app that carries out tasks in Excel on your PC.">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" asChild><Link href="/dashboard/devices">Manage devices</Link></Button>
            <Button variant="outline" asChild><Link href="/download">Download for Windows</Link></Button>
          </div>
        </Section>
        <Section title="Your data" description="Delete conversations and files at any time from Chat and Files. For a copy of your data or to close your account, contact us.">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" asChild>
              <a href={`mailto:${site.privacyEmail}?subject=${encodeURIComponent('Request a copy of my Xelora data')}&body=${encodeURIComponent(`Account email: ${user?.email ?? ''}`)}`}>Request a copy of my data</a>
            </Button>
            <Button variant="outline" className="text-xelora-error hover:text-xelora-error" asChild>
              <a href={`mailto:${site.privacyEmail}?subject=${encodeURIComponent('Close my Xelora account')}&body=${encodeURIComponent(`Please close my account and delete its data. Account email: ${user?.email ?? ''}`)}`}>Close my account</a>
            </Button>
          </div>
        </Section>
      </div>
    </div>
  );
}
