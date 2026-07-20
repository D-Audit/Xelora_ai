import { CheckCircle2, ArrowRight, GitBranch, CircleDot, FileSpreadsheet, Download } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { MockWindow } from '@/components/site/mock-window';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { howItWorksJourney } from '@/data/mock-marketing';

const stages = [
  {
    title: 'Create and sign in',
    description: 'Set up the account in the browser and use the same sign-in for desktop.',
    icon: CheckCircle2,
  },
  {
    title: 'Open a spreadsheet',
    description: 'Choose a local workbook or a cloud-synced file to begin.',
    icon: FileSpreadsheet,
  },
  {
    title: 'Describe the work',
    description: 'Tell Xelora what outcome you need in plain language.',
    icon: CircleDot,
  },
  {
    title: 'Review and approve',
    description: 'Inspect the generated steps, then run, edit, or approve them.',
    icon: GitBranch,
  },
  {
    title: 'Save the result',
    description: 'Keep the workbook local or sync the approved version to the cloud.',
    icon: Download,
  },
];

export default function HowItWorksPage() {
  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <SectionHeading
              eyebrow="How It Works"
              title="A controlled workflow from account creation to final workbook"
              description="Xelora keeps the process visible at every step, from subscription and download through review and approval."
            />
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
            <div className="space-y-4">
              {howItWorksJourney.map((step, index) => (
                <Card key={step} className="flex items-start gap-4 p-5">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-xelora-success-bg text-sm font-semibold text-xelora-success">
                    {index + 1}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-xelora-text">{step}</h3>
                    <p className="mt-1 text-sm text-xelora-text-secondary">
                      {index === 0 && 'Create a web account and keep your preferences synced across web and desktop.'}
                      {index === 1 && 'Choose a plan and prepare the desktop app for local spreadsheet work.'}
                      {index === 2 && 'Use plain language so Xelora AI can draft a workflow that matches your goal.'}
                      {index === 3 && 'Read the steps, inspect the expected changes, and decide what should happen next.'}
                      {index === 4 && 'Keep the workbook local or sync it to Xelora Cloud when a shared copy is needed.'}
                    </p>
                  </div>
                </Card>
              ))}
            </div>

            <div className="space-y-4">
              <MockWindow title="Workflow journey" subtitle="Interface and step-by-step review">
                <div className="space-y-4 p-5">
                  <div className="rounded-lg border border-xelora-border bg-xelora-surface-2 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-xelora-text">
                      <ArrowRight className="h-4 w-4 text-xelora-green" />
                      Create account
                    </div>
                    <p className="mt-2 text-sm text-xelora-text-secondary">Choose a plan, download the desktop app, and reuse the same account on both surfaces.</p>
                  </div>
                  <div className="grid gap-3">
                    {stages.map((stage, index) => {
                      const Icon = stage.icon;
                      return (
                        <div key={stage.title} className="flex items-start gap-3 rounded-lg border border-xelora-border p-3">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-xelora-success-bg">
                            <Icon className="h-4 w-4 text-xelora-success" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-xelora-text">{index + 1}. {stage.title}</p>
                            <p className="text-sm text-xelora-text-secondary">{stage.description}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="rounded-lg border border-xelora-info bg-xelora-info-bg p-4">
                    <Badge variant="info">Approval point</Badge>
                    <p className="mt-2 text-sm text-xelora-text-secondary">
                      Xelora pauses when a step needs approval, lets you inspect the workbook, and continues only after you confirm.
                    </p>
                  </div>
                </div>
              </MockWindow>
            </div>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
