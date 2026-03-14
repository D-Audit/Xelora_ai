'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bot,
  ShieldCheck,
  FolderOpen,
  BarChart3,
  Briefcase,
  Users,
  TrendingUp,
  BookOpen,
  Search,
  Star,
  CheckCircle2,
  Download,
  ArrowRight,
  ChevronLeft,
} from 'lucide-react';
import { toast } from 'sonner';

import { useAuthStore } from '@/stores/auth-store';
import { updateSession } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { cn } from '@/lib/utils';
import { mockPlans } from '@/data/mock-plans';
import type { Plan } from '@/types';

const WINDOWS_INSTALLER_URL = '/api/download/windows';

// ─── Types ───────────────────────────────────────────────────────────────────

type Experience = 'beginner' | 'intermediate' | 'advanced';

interface OnboardingAnswers {
  intendedUse: string;
  experience: Experience | '';
  objectives: string[];
  selectedPlan: string;
}

const TOTAL_STEPS = 7;

// ─── Step data ────────────────────────────────────────────────────────────────

interface UseOption {
  id: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const USE_OPTIONS: UseOption[] = [
  { id: 'accounting', label: 'Accounting', description: 'Reconciliations, reports, payroll', icon: BarChart3 },
  { id: 'business-operations', label: 'Business Operations', description: 'Workflows, data processing', icon: Briefcase },
  { id: 'human-resources', label: 'Human Resources', description: 'Payroll, onboarding, headcount', icon: Users },
  { id: 'data-analysis', label: 'Data Analysis', description: 'Cleaning, transforming, reporting', icon: TrendingUp },
  { id: 'education', label: 'Education', description: 'Grade books, research data', icon: BookOpen },
  { id: 'research', label: 'Research', description: 'Survey data, academic analysis', icon: Search },
  { id: 'personal-productivity', label: 'Personal Productivity', description: 'Household budgets, personal tracking', icon: Star },
];

interface ExperienceOption {
  id: Experience;
  label: string;
  description: string;
}

const EXPERIENCE_OPTIONS: ExperienceOption[] = [
  { id: 'beginner', label: 'Beginner', description: 'I use spreadsheets occasionally and keep things simple' },
  { id: 'intermediate', label: 'Intermediate', description: "I'm comfortable with formulas and data organisation" },
  { id: 'advanced', label: 'Advanced', description: 'I build complex models and use advanced functions regularly' },
];

interface ObjectiveOption {
  id: string;
  label: string;
}

const OBJECTIVE_OPTIONS: ObjectiveOption[] = [
  { id: 'automate-tasks', label: 'Automate repetitive tasks' },
  { id: 'clean-data', label: 'Clean spreadsheet data' },
  { id: 'generate-formulas', label: 'Generate formulas' },
  { id: 'create-reports', label: 'Create reports' },
  { id: 'process-files', label: 'Process multiple files' },
  { id: 'build-workflows', label: 'Build reusable workflows' },
];

// Only show starter / professional / business in the plan picker
const SELECTABLE_PLAN_TIERS = ['starter', 'professional', 'business'];

// ─── Helper: format plan limit ────────────────────────────────────────────────

function formatLimit(value: number | string): string {
  if (value === 'unlimited' || value === 'custom') return String(value);
  return new Intl.NumberFormat('en-US').format(value as number);
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface StepHeaderProps {
  heading: string;
  subtext?: string;
}

function StepHeader({ heading, subtext }: StepHeaderProps) {
  return (
    <div className="mb-8 text-center">
      <h1 className="text-2xl font-semibold text-xelora-text sm:text-3xl">{heading}</h1>
      {subtext && <p className="mt-2 text-sm text-xelora-text-secondary sm:text-base">{subtext}</p>}
    </div>
  );
}

// ─── Step 1: Welcome ──────────────────────────────────────────────────────────

interface Step1Props {
  onNext: () => void;
}

function StepWelcome({ onNext }: Step1Props) {
  const features = [
    { icon: Bot, label: 'AI-powered automation', description: 'Let AI handle complex spreadsheet tasks for you' },
    { icon: ShieldCheck, label: 'Full control over changes', description: 'Review every change before it is applied' },
    { icon: FolderOpen, label: 'Works with your existing files', description: 'No migration — bring your own xlsx, csv, or ods files' },
  ];

  return (
    <section aria-labelledby="welcome-heading" className="flex flex-col items-center text-center">
      <h1 id="welcome-heading" className="text-3xl font-semibold text-xelora-text sm:text-4xl">
        Welcome to Xelora
      </h1>
      <p className="mt-3 text-base text-xelora-text-secondary sm:text-lg">
        Let&apos;s get you set up in a few quick steps.
      </p>

      <ul className="mt-10 grid w-full max-w-xl gap-4 text-left sm:grid-cols-1" role="list">
        {features.map(({ icon: Icon, label, description }) => (
          <li key={label} className="flex items-start gap-4 rounded-lg border border-xelora-border bg-white p-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-xelora-surface-2">
              <Icon className="h-5 w-5 text-xelora-green" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-medium text-xelora-text">{label}</p>
              <p className="mt-0.5 text-xs text-xelora-text-secondary">{description}</p>
            </div>
          </li>
        ))}
      </ul>

      <Button size="lg" className="mt-10 w-full max-w-xs" onClick={onNext}>
        Get started <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </section>
  );
}

// ─── Step 2: Intended use ─────────────────────────────────────────────────────

interface Step2Props {
  selected: string;
  onSelect: (id: string) => void;
}

function StepIntendedUse({ selected, onSelect }: Step2Props) {
  return (
    <section aria-labelledby="use-heading">
      <StepHeader heading="What will you mainly use Xelora for?" />
      <fieldset>
        <legend className="sr-only">Intended use</legend>
        <ul
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
          role="list"
        >
          {USE_OPTIONS.map(({ id, label, description, icon: Icon }) => {
            const isSelected = selected === id;
            return (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onSelect(id)}
                  aria-pressed={isSelected}
                  className={cn(
                    'w-full rounded-lg border p-4 text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus',
                    isSelected
                      ? 'border-xelora-green bg-xelora-success-bg'
                      : 'border-xelora-border bg-white hover:border-xelora-green/50 hover:bg-xelora-surface-2'
                  )}
                >
                  <span className="flex items-center gap-3">
                    <span
                      className={cn(
                        'flex h-9 w-9 shrink-0 items-center justify-center rounded-md',
                        isSelected ? 'bg-xelora-green' : 'bg-xelora-surface-2'
                      )}
                    >
                      <Icon
                        className={cn('h-4 w-4', isSelected ? 'text-white' : 'text-xelora-text-secondary')}
                        aria-hidden="true"
                      />
                    </span>
                    <span>
                      <span className="block text-sm font-medium text-xelora-text">{label}</span>
                      <span className="block text-xs text-xelora-text-secondary">{description}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </fieldset>
    </section>
  );
}

// ─── Step 3: Experience ───────────────────────────────────────────────────────

interface Step3Props {
  selected: Experience | '';
  onSelect: (id: Experience) => void;
}

function StepExperience({ selected, onSelect }: Step3Props) {
  return (
    <section aria-labelledby="experience-heading">
      <StepHeader heading="How comfortable are you with spreadsheets?" />
      <fieldset>
        <legend className="sr-only">Spreadsheet experience level</legend>
        <ul className="flex flex-col gap-3" role="list">
          {EXPERIENCE_OPTIONS.map(({ id, label, description }) => {
            const isSelected = selected === id;
            return (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onSelect(id)}
                  aria-pressed={isSelected}
                  className={cn(
                    'w-full rounded-lg border p-5 text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus',
                    isSelected
                      ? 'border-xelora-green bg-xelora-success-bg'
                      : 'border-xelora-border bg-white hover:border-xelora-green/50 hover:bg-xelora-surface-2'
                  )}
                >
                  <span className="flex items-center justify-between">
                    <span>
                      <span className="block text-base font-medium text-xelora-text">{label}</span>
                      <span className="mt-1 block text-sm text-xelora-text-secondary">{description}</span>
                    </span>
                    {isSelected && (
                      <CheckCircle2 className="ml-4 h-5 w-5 shrink-0 text-xelora-green" aria-hidden="true" />
                    )}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </fieldset>
    </section>
  );
}

// ─── Step 4: Objectives ───────────────────────────────────────────────────────

interface Step4Props {
  selected: string[];
  onToggle: (id: string) => void;
}

function StepObjectives({ selected, onToggle }: Step4Props) {
  return (
    <section aria-labelledby="objectives-heading">
      <StepHeader
        heading="What do you want Xelora to help with?"
        subtext="Select all that apply"
      />
      <fieldset>
        <legend className="sr-only">Objectives — select all that apply</legend>
        <ul className="grid gap-3 sm:grid-cols-2" role="list">
          {OBJECTIVE_OPTIONS.map(({ id, label }) => {
            const isSelected = selected.includes(id);
            return (
              <li key={id}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={isSelected}
                  onClick={() => onToggle(id)}
                  className={cn(
                    'w-full rounded-lg border p-4 text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus',
                    isSelected
                      ? 'border-xelora-green bg-xelora-success-bg'
                      : 'border-xelora-border bg-white hover:border-xelora-green/50 hover:bg-xelora-surface-2'
                  )}
                >
                  <span className="flex items-center gap-3">
                    <span
                      className={cn(
                        'flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors',
                        isSelected
                          ? 'border-xelora-green bg-xelora-green'
                          : 'border-xelora-border bg-white'
                      )}
                      aria-hidden="true"
                    >
                      {isSelected && (
                        <svg viewBox="0 0 12 12" className="h-3 w-3 text-white" fill="none" stroke="currentColor" strokeWidth="2">
                          <polyline points="2,6 5,9 10,3" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </span>
                    <span className="text-sm font-medium text-xelora-text">{label}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </fieldset>
    </section>
  );
}

// ─── Step 5: Plan selection ───────────────────────────────────────────────────

interface Step5Props {
  selectedPlan: string;
  onSelect: (id: string) => void;
}

function StepPlan({ selectedPlan, onSelect }: Step5Props) {
  const plans = mockPlans.filter((p) => SELECTABLE_PLAN_TIERS.includes(p.tier));

  return (
    <section aria-labelledby="plan-heading">
      <StepHeader
        heading="Choose your plan"
        subtext="Start with a 14-day free trial, then choose a plan."
      />
      <fieldset>
        <legend className="sr-only">Subscription plan</legend>
        <ul className="grid gap-4 sm:grid-cols-3" role="list">
          {plans.map((plan: Plan) => {
            const isSelected = selectedPlan === plan.id;
            return (
              <li key={plan.id}>
                <button
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelect(plan.id)}
                  className={cn(
                    'relative w-full rounded-lg border p-5 text-left transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-xelora-border-focus',
                    isSelected
                      ? 'border-xelora-green bg-xelora-success-bg'
                      : 'border-xelora-border bg-white hover:border-xelora-green/50 hover:bg-xelora-surface-2'
                  )}
                >
                  {plan.isPopular && (
                    <Badge variant="green" className="absolute right-3 top-3 text-[10px]">
                      Popular
                    </Badge>
                  )}
                  <span className="block text-base font-semibold text-xelora-text">{plan.name}</span>
                  <span className="mt-1 block text-xl font-bold text-xelora-text">
                    {plan.monthlyPrice === null ? 'Custom' : `$${plan.monthlyPrice}/mo`}
                  </span>
                  <ul className="mt-3 space-y-1.5 text-xs text-xelora-text-secondary" role="list">
                    <li>{formatLimit(plan.limits.aiActionsPerMonth)} AI actions/mo</li>
                    <li>{formatLimit(plan.limits.workflowRunsPerMonth)} workflow runs/mo</li>
                    <li>{formatLimit(plan.limits.savedWorkflows)} saved workflows</li>
                    <li>{formatLimit(plan.limits.devices)} device{plan.limits.devices === 1 ? '' : 's'}</li>
                    {plan.limits.batchProcessing && <li>Batch processing</li>}
                    {plan.limits.apiAccess && <li>API access</li>}
                    {plan.limits.prioritySupport && <li>Priority support</li>}
                  </ul>
                  {isSelected && (
                    <span className="mt-3 flex items-center gap-1 text-xs font-medium text-xelora-green">
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                      Selected
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </fieldset>
    </section>
  );
}

// ─── Step 6: Desktop download ─────────────────────────────────────────────────

interface Step6Props {
  onDownload: () => void;
  onSkip: () => void;
}

function StepDownload({ onDownload, onSkip }: Step6Props) {
  return (
    <section aria-labelledby="download-heading" className="flex flex-col items-center text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-xelora-surface-2">
        <Download className="h-8 w-8 text-xelora-green" aria-hidden="true" />
      </span>

      <h1 id="download-heading" className="mt-5 text-2xl font-semibold text-xelora-text sm:text-3xl">
        Download Xelora Desktop to get started
      </h1>

      <p className="mt-3 max-w-md text-sm text-xelora-text-secondary sm:text-base">
        Your web dashboard manages everything - workflows, files, and settings. Automation and AI
        tasks run through the lightweight desktop app installed on your machine.
      </p>

      <div className="mt-8 flex w-full max-w-xs flex-col gap-3">
        <Button size="lg" onClick={onDownload} className="w-full">
          <Download className="h-4 w-4" aria-hidden="true" />
          Download for Windows
        </Button>
        <Button variant="ghost" size="lg" onClick={onSkip} className="w-full">
          I&apos;ll download later
        </Button>
      </div>
    </section>
  );
}

// ─── Step 7: Complete ─────────────────────────────────────────────────────────

interface Step7Props {
  userName: string;
  answers: OnboardingAnswers;
  onGoToDashboard: () => void;
}

function StepComplete({ userName, answers, onGoToDashboard }: Step7Props) {
  const firstName = userName.split(' ')[0] ?? userName;

  const intendedUseLabel = USE_OPTIONS.find((o) => o.id === answers.intendedUse)?.label ?? answers.intendedUse;
  const selectedPlanName = mockPlans.find((p) => p.id === answers.selectedPlan)?.name ?? answers.selectedPlan;
  const objectiveLabels = answers.objectives
    .map((id) => OBJECTIVE_OPTIONS.find((o) => o.id === id)?.label ?? id)
    .join(', ');

  const summaryItems = [
    { label: 'Intended use', value: intendedUseLabel },
    { label: 'Experience', value: answers.experience || '—' },
    { label: 'Objectives', value: objectiveLabels || 'None selected' },
    { label: 'Plan', value: selectedPlanName || '—' },
  ];

  return (
    <section aria-labelledby="complete-heading" className="flex flex-col items-center text-center">
      <span
        className="flex h-16 w-16 items-center justify-center rounded-full bg-xelora-success-bg"
        aria-hidden="true"
      >
        <CheckCircle2 className="h-8 w-8 text-xelora-green" />
      </span>

      <h1 id="complete-heading" className="mt-5 text-2xl font-semibold text-xelora-text sm:text-3xl">
        You&apos;re all set, {firstName}!
      </h1>
      <p className="mt-2 text-sm text-xelora-text-secondary">
        Here&apos;s a summary of your preferences.
      </p>

      <Card className="mt-8 w-full max-w-sm text-left">
        <dl className="divide-y divide-xelora-border">
          {summaryItems.map(({ label, value }) => (
            <div key={label} className="flex flex-col gap-0.5 px-5 py-3 sm:flex-row sm:justify-between sm:gap-4">
              <dt className="text-xs font-medium text-xelora-text-secondary">{label}</dt>
              <dd className="text-sm font-medium capitalize text-xelora-text sm:text-right">{value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Button size="lg" className="mt-8 w-full max-w-xs" onClick={onGoToDashboard}>
        Go to dashboard <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Button>
    </section>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const { user, setUser } = useAuthStore();

  const [currentStep, setCurrentStep] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [answers, setAnswers] = useState<OnboardingAnswers>({
    intendedUse: '',
    experience: '',
    objectives: [],
    selectedPlan: mockPlans.find((p) => p.tier === 'professional')?.id ?? '',
  });

  // Focus the main content area on step change for screen-reader announcements
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
  }, [currentStep]);

  const progressValue = Math.round((currentStep / TOTAL_STEPS) * 100);

  // ── Navigation ────────────────────────────────────────────────────────────

  function canAdvance(): boolean {
    if (currentStep === 2) return answers.intendedUse !== '';
    if (currentStep === 3) return answers.experience !== '';
    if (currentStep === 5) return answers.selectedPlan !== '';
    return true;
  }

  async function handleNext() {
    if (!canAdvance()) {
      const messages: Record<number, string> = {
        2: 'Please select how you intend to use Xelora.',
        3: 'Please select your experience level.',
        5: 'Please choose a subscription plan.',
      };
      toast.error(messages[currentStep] ?? 'Please complete this step to continue.');
      return;
    }

    if (currentStep === TOTAL_STEPS - 1) {
      // Persist answers before the final step
      await persistAnswers();
    }

    setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function handleBack() {
    setCurrentStep((s) => Math.max(s - 1, 1));
  }

  async function persistAnswers() {
    setIsLoading(true);
    try {
      const updates = {
        primaryUse: answers.intendedUse,
        experience: answers.experience as 'beginner' | 'intermediate' | 'advanced' | undefined,
        objectives: answers.objectives,
        onboardingCompleted: true,
      };
      updateSession(updates);
      if (user) {
        setUser({ ...user, ...updates });
      }
    } catch {
      toast.error('Failed to save your preferences. You can update them later in settings.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleGoToDashboard() {
    router.push('/dashboard');
  }

  function startWindowsInstallerDownload() {
    const link = document.createElement('a');
    link.href = WINDOWS_INSTALLER_URL;
    link.rel = 'noopener';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function handleDownload() {
    startWindowsInstallerDownload();
    toast.success('Download started — Xelora-Setup.exe is being prepared.');
    setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function handleSkipDownload() {
    setCurrentStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function toggleObjective(id: string) {
    setAnswers((prev) => ({
      ...prev,
      objectives: prev.objectives.includes(id)
        ? prev.objectives.filter((o) => o !== id)
        : [...prev.objectives, id],
    }));
  }

  // ── Render steps ─────────────────────────────────────────────────────────

  function renderStep() {
    switch (currentStep) {
      case 1:
        return <StepWelcome onNext={handleNext} />;

      case 2:
        return (
          <StepIntendedUse
            selected={answers.intendedUse}
            onSelect={(id) => setAnswers((prev) => ({ ...prev, intendedUse: id }))}
          />
        );

      case 3:
        return (
          <StepExperience
            selected={answers.experience}
            onSelect={(id) => setAnswers((prev) => ({ ...prev, experience: id }))}
          />
        );

      case 4:
        return (
          <StepObjectives
            selected={answers.objectives}
            onToggle={toggleObjective}
          />
        );

      case 5:
        return (
          <StepPlan
            selectedPlan={answers.selectedPlan}
            onSelect={(id) => setAnswers((prev) => ({ ...prev, selectedPlan: id }))}
          />
        );

      case 6:
        return <StepDownload onDownload={handleDownload} onSkip={handleSkipDownload} />;

      case 7:
        return (
          <StepComplete
            userName={user?.name ?? 'there'}
            answers={answers}
            onGoToDashboard={handleGoToDashboard}
          />
        );

      default:
        return null;
    }
  }

  // Steps where navigation buttons are rendered by the step itself
  const stepHandlesOwnNav = currentStep === 1 || currentStep === 6 || currentStep === 7;

  return (
    <div className="flex min-h-screen flex-col bg-xelora-surface">
      {/* ── Header ── */}
      <header className="flex h-14 items-center justify-between border-b border-xelora-border bg-white px-4 sm:px-6">
        <XeloraLogo size="sm" />
        <p className="text-xs text-xelora-text-secondary" aria-live="polite">
          Step {currentStep} of {TOTAL_STEPS}
        </p>
      </header>

      {/* ── Progress bar ── */}
      <div className="bg-white px-4 pb-3 pt-2 sm:px-6">
        <Progress
          value={progressValue}
          aria-label={`Onboarding progress: step ${currentStep} of ${TOTAL_STEPS}`}
          className="h-1.5"
        />
      </div>

      {/* ── Main content ── */}
      <main
        ref={mainRef}
        tabIndex={-1}
        className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 outline-none sm:px-6"
        aria-label={`Onboarding step ${currentStep}`}
      >
        {renderStep()}

        {/* ── Navigation buttons (for steps that don't manage their own) ── */}
        {!stepHandlesOwnNav && (
          <div className="mt-10 flex items-center justify-between gap-4">
            <Button
              variant="outline"
              size="lg"
              onClick={handleBack}
              disabled={currentStep === 1}
              className="gap-1.5"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Back
            </Button>

            <Button
              size="lg"
              onClick={handleNext}
              disabled={isLoading}
              className="min-w-[130px] gap-1.5"
            >
              {isLoading ? (
                'Saving…'
              ) : (
                <>
                  {currentStep === TOTAL_STEPS - 1 ? 'Finish' : 'Continue'}
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </>
              )}
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
