'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowRight, Check, Download, FolderOpen, ShieldCheck, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { useAuthStore } from '@/stores/auth-store';
import { useIsDesktop } from '@/lib/is-desktop';
import { site } from '@/lib/site';
import { cn } from '@/lib/utils';

const intro = [
  { icon: Table2, title: 'Works in real Excel', text: 'Describe a task. Xelora carries it out in Excel on your PC and checks the result.' },
  { icon: ShieldCheck, title: 'You stay in control', text: 'Larger changes wait for your confirmation, and you can pause a task at any time.' },
  { icon: FolderOpen, title: 'Use the files you have', text: 'Work on the open workbook, or attach .xlsx, .xls, .csv, .tsv and .ods files.' },
];

const firstPrompts = [
  'Remove duplicate rows and trim extra spaces in the active sheet',
  'Build a pivot table that summarises sales by region, with a chart',
  'What is the difference between VLOOKUP and XLOOKUP?',
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, initialize } = useAuthStore();
  const desktop = useIsDesktop();
  const [step, setStep] = useState(0);
  const steps = desktop ? ['Welcome', 'Get started'] : ['Welcome', 'Xelora Desktop', 'Get started'];
  const current = steps[step];

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/login');
  }, [isLoading, isAuthenticated, router]);

  const next = () => setStep((value) => Math.min(value + 1, steps.length - 1));
  const startChat = (prompt?: string) => {
    router.push(prompt ? `/dashboard/agent?prompt=${encodeURIComponent(prompt)}` : '/dashboard/agent');
  };

  return (
    <div className="flex min-h-dvh flex-col bg-white">
      <header className="flex items-center justify-between px-6 py-5">
        <XeloraLogo size="sm" />
        <button onClick={() => startChat()} className="text-sm text-xelora-text-secondary hover:text-xelora-text">Skip</button>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-lg">
          <ol className="mb-10 flex items-center justify-center gap-2" aria-label="Progress">
            {steps.map((label, index) => (
              <li key={label} className={cn('h-1 w-10 rounded-full', index <= step ? 'bg-xelora-text' : 'bg-xelora-border')}>
                <span className="sr-only">{label}{index === step ? ' (current)' : ''}</span>
              </li>
            ))}
          </ol>

          {current === 'Welcome' && (
            <section aria-labelledby="welcome-title">
              <h1 id="welcome-title" className="text-center text-3xl font-semibold tracking-tight text-xelora-text">
                Welcome{user?.name ? `, ${user.name.split(' ')[0]}` : ''}
              </h1>
              <p className="mt-3 text-center text-xelora-text-secondary">
                Your {site.trialDays}-day free trial has started. Here is what Xelora does.
              </p>
              <ul className="mt-10 space-y-6">
                {intro.map(({ icon: Icon, title, text }) => (
                  <li key={title} className="flex gap-4">
                    <Icon className="mt-0.5 h-5 w-5 shrink-0 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
                    <div>
                      <p className="text-sm font-semibold text-xelora-text">{title}</p>
                      <p className="mt-1 text-sm leading-relaxed text-xelora-text-secondary">{text}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <Button size="lg" className="mt-10 w-full" onClick={next}>Continue <ArrowRight className="h-4 w-4" /></Button>
            </section>
          )}

          {current === 'Xelora Desktop' && (
            <section aria-labelledby="desktop-title" className="text-center">
              <Download className="mx-auto h-8 w-8 text-xelora-text" strokeWidth={1.5} aria-hidden="true" />
              <h1 id="desktop-title" className="mt-5 text-3xl font-semibold tracking-tight text-xelora-text">Install Xelora Desktop</h1>
              <p className="mx-auto mt-3 max-w-md text-xelora-text-secondary">
                To let Xelora work in Excel, install the Windows app and sign in with this account. You can still chat and ask
                questions in the browser without it.
              </p>
              <ul className="mx-auto mt-8 max-w-sm space-y-2 text-left text-sm text-xelora-text-secondary">
                {['Windows 10 or 11', 'Microsoft Excel for Windows', 'Connects to your account automatically'].map((item) => (
                  <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-xelora-green" />{item}</li>
                ))}
              </ul>
              <div className="mt-10 flex flex-col gap-3">
                <Button size="lg" asChild>
                  <a href="/api/download/windows" onClick={() => window.setTimeout(next, 300)}>
                    <Download className="h-4 w-4" /> Download for Windows
                  </a>
                </Button>
                <Button size="lg" variant="ghost" onClick={next}>I will do this later</Button>
              </div>
            </section>
          )}

          {current === 'Get started' && (
            <section aria-labelledby="start-title">
              <h1 id="start-title" className="text-center text-3xl font-semibold tracking-tight text-xelora-text">You are all set</h1>
              <p className="mt-3 text-center text-xelora-text-secondary">Try one of these, or ask anything.</p>
              <div className="mt-8 space-y-2">
                {firstPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => startChat(prompt)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl border border-xelora-border px-4 py-3 text-left text-sm text-xelora-text transition-colors hover:border-xelora-border-strong hover:bg-xelora-surface-2"
                  >
                    {prompt}
                    <ArrowRight className="h-4 w-4 shrink-0 text-xelora-text-muted" />
                  </button>
                ))}
              </div>
              <Button size="lg" className="mt-8 w-full" onClick={() => startChat()}>Open Xelora</Button>
              <p className="mt-4 text-center text-xs text-xelora-text-muted">
                Change your plan any time in <Link href="/dashboard/billing/plans" className="underline">Plan and billing</Link>.
              </p>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
