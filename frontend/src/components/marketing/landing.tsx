import Link from 'next/link';
import {
  ArrowRight, Check, Cloud, Download, FolderSync, Globe, History, KeyRound,
  ListChecks, Lock, Monitor, ShieldCheck, Table2, Workflow,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { planHighlights, plans } from '@/data/plans';
import { site } from '@/lib/site';
import { HeroDemo } from '@/components/marketing/hero-demo';

function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className="text-sm font-medium text-xelora-green">{children}</p>;
}

function SectionTitle({ eyebrow, title, description, id }: { eyebrow: string; title: string; description?: string; id: string }) {
  return (
    <div className="max-w-2xl">
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 id={id} className="mt-2 text-3xl font-semibold tracking-tight text-xelora-text sm:text-4xl">{title}</h2>
      {description && <p className="mt-4 text-base leading-relaxed text-xelora-text-secondary">{description}</p>}
    </div>
  );
}

/* ── Hero ─────────────────────────────────────────────────────────────── */

export function Hero() {
  return (
    <section className="overflow-hidden border-b border-xelora-border bg-white" aria-labelledby="hero-heading">
      <div className="mx-auto max-w-6xl px-4 pb-20 pt-16 sm:px-6 lg:px-8 lg:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <p className="inline-flex items-center gap-2 rounded-full border border-xelora-border px-3 py-1 text-xs font-medium text-xelora-text-secondary">
            <Monitor className="h-3.5 w-3.5" aria-hidden="true" />
            For Microsoft Excel on Windows
          </p>
          <h1 id="hero-heading" className="mt-6 text-4xl font-semibold tracking-tight text-xelora-text sm:text-5xl lg:text-6xl">
            Describe the work.<br className="hidden sm:block" /> Xelora does it in Excel.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-xelora-text-secondary">
            Clean data, build pivot tables and charts, write formulas and format reports by asking in plain
            language. Xelora works in your own copy of Excel, checks every change, and asks before anything big.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" asChild>
              <Link href="/register">Get started free <ArrowRight className="h-4 w-4" /></Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/download"><Download className="h-4 w-4" /> Download for Windows</Link>
            </Button>
          </div>
          <p className="mt-4 text-xs text-xelora-text-muted">
            {site.trialDays}-day free trial · No credit card required · Needs Microsoft Excel for Windows
          </p>
        </div>
        <HeroDemo />
      </div>
    </section>
  );
}

/* ── Product ──────────────────────────────────────────────────────────── */

const capabilities = [
  {
    icon: Table2,
    title: 'Works in real Excel',
    text: 'Formulas, pivot tables, charts, conditional formatting, data validation, macros and more. 75 built-in Excel actions, run in your own copy of Excel.',
  },
  {
    icon: ShieldCheck,
    title: 'Checks its own work',
    text: 'After each change Xelora reads the workbook back. A task is only marked complete when the result is verified, and it tells you plainly when something did not work.',
  },
  {
    icon: ListChecks,
    title: 'Asks before big changes',
    text: 'For larger or destructive requests Xelora proposes a plan and waits for you to confirm. You can pause a running task at any time.',
  },
  {
    icon: Globe,
    title: 'Answers questions, with sources',
    text: 'Ask anything. When a question needs current facts, such as an exchange rate or a new regulation, Xelora searches the web and links the sources it used.',
  },
  {
    icon: FolderSync,
    title: 'Your files, kept in sync',
    text: 'Upload spreadsheets to your workspace with version history. Xelora Desktop keeps a local copy and saves the workbooks it changes back as new versions.',
  },
  {
    icon: History,
    title: 'Remembers the conversation',
    text: 'Every conversation is saved. Follow-ups like “now make it a chart” keep their context, and Xelora learns from tasks you have run before.',
  },
];

export function Product() {
  return (
    <section id="product" className="scroll-mt-20 border-b border-xelora-border bg-xelora-bg-main py-24" aria-labelledby="product-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionTitle
          id="product-heading"
          eyebrow="Product"
          title="An assistant that does the work, not just the explaining"
          description="Most AI tools tell you which formula to write. Xelora opens the workbook and makes the change, then shows you what it did."
        />
        <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-xelora-border bg-xelora-border sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map(({ icon: Icon, title, text }) => (
            <div key={title} className="bg-white p-7">
              <Icon className="h-5 w-5 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
              <h3 className="mt-5 text-base font-semibold text-xelora-text">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">{text}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 flex flex-col gap-4 rounded-2xl border border-xelora-border bg-white p-7 sm:flex-row sm:items-center">
          <Workflow className="h-5 w-5 shrink-0 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
          <div className="flex-1">
            <h3 className="text-base font-semibold text-xelora-text">Reusable workflows</h3>
            <p className="mt-1 text-sm leading-relaxed text-xelora-text-secondary">
              Save a multi-step process, such as a monthly clean-up and summary, and run it again with one click.
              Start from ready-made templates for cleaning, reporting and formatting.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Examples ─────────────────────────────────────────────────────────── */

const examples = [
  'Remove duplicate customers and trim extra spaces in every column',
  'Build a pivot table of sales by region and month, with a chart',
  'Add a column that flags invoices more than 30 days overdue',
  'Highlight any value more than 10% below target in red',
  'Put today’s EUR to USD rate in B2 and note the source',
  'Turn this CSV into a formatted table and export it as a PDF',
];

export function Examples() {
  return (
    <section className="border-b border-xelora-border bg-white py-24" aria-labelledby="examples-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionTitle
          id="examples-heading"
          eyebrow="Examples"
          title="Say it the way you would to a colleague"
          description="No formulas or menus to learn. These are the kinds of requests Xelora handles every day."
        />
        <ul className="mt-12 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {examples.map((example) => (
            <li key={example} className="rounded-xl border border-xelora-border bg-white px-5 py-4 text-sm leading-relaxed text-xelora-text">
              “{example}”
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* ── How it works ─────────────────────────────────────────────────────── */

const steps = [
  {
    title: 'Create your account',
    text: `Sign up with email or Google. Every account starts with a ${site.trialDays}-day free trial.`,
  },
  {
    title: 'Install Xelora Desktop',
    text: 'Download the Windows app and sign in. It connects to your account automatically and runs next to Excel on your PC.',
  },
  {
    title: 'Ask in plain language',
    text: 'Type what you need in the chat, from the desktop app or any browser. Attach a file or work on the workbook you have open.',
  },
  {
    title: 'Review the result',
    text: 'Watch each step as it happens. Xelora verifies the changes, explains what it did, and keeps the conversation for later.',
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-b border-xelora-border bg-xelora-bg-main py-24" aria-labelledby="how-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <SectionTitle id="how-heading" eyebrow="How it works" title="Up and running in a few minutes" />
        <ol className="mt-12 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, index) => (
            <li key={step.title}>
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-xelora-border-strong bg-white text-sm font-semibold text-xelora-text">
                {index + 1}
              </span>
              <h3 className="mt-4 text-base font-semibold text-xelora-text">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">{step.text}</p>
            </li>
          ))}
        </ol>

        <div className="mt-16 rounded-2xl border border-xelora-border bg-white p-6 sm:p-8">
          <h3 className="text-base font-semibold text-xelora-text">How the pieces fit together</h3>
          <div className="mt-6 grid items-stretch gap-4 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
            <ArchitectureBox
              icon={Globe}
              title="Xelora web app"
              text="Chat, files, history, workflows and billing. In any browser, and inside the desktop app."
            />
            <Connector />
            <ArchitectureBox
              icon={Cloud}
              title="Xelora cloud"
              text="Your account, saved conversations and files, and the AI models. Keys for the AI models stay here."
            />
            <Connector />
            <ArchitectureBox
              icon={Monitor}
              title="Xelora Desktop + Excel"
              text="Runs on your Windows PC and carries out tasks in your copy of Microsoft Excel."
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function ArchitectureBox({ icon: Icon, title, text }: { icon: typeof Globe; title: string; text: string }) {
  return (
    <div className="rounded-xl border border-xelora-border p-5">
      <Icon className="h-5 w-5 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
      <p className="mt-3 text-sm font-semibold text-xelora-text">{title}</p>
      <p className="mt-1 text-sm leading-relaxed text-xelora-text-secondary">{text}</p>
    </div>
  );
}

function Connector() {
  return (
    <div className="hidden items-center justify-center lg:flex" aria-hidden="true">
      <ArrowRight className="h-4 w-4 text-xelora-text-muted" />
    </div>
  );
}

/* ── Security ─────────────────────────────────────────────────────────── */

const securityPoints = [
  { icon: Monitor, title: 'Excel work happens on your PC', text: 'Xelora Desktop edits workbooks in your own Excel. Only files you upload are stored in your Xelora workspace.' },
  { icon: KeyRound, title: 'No AI keys on your computer', text: 'The desktop app uses a device token you can revoke at any time. AI provider keys never leave our servers.' },
  { icon: Lock, title: 'Private by default', text: 'Your files and conversations are only visible to your account, sent over HTTPS, and can be deleted whenever you choose.' },
];

export function Security() {
  return (
    <section className="border-b border-xelora-border bg-white py-24" aria-labelledby="security-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <SectionTitle id="security-heading" eyebrow="Security" title="Built to be trusted with real work" />
          <Link href="/security" className="inline-flex items-center gap-1 text-sm font-medium text-xelora-green hover:underline">
            How we protect your data <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="mt-12 grid gap-8 md:grid-cols-3">
          {securityPoints.map(({ icon: Icon, title, text }) => (
            <div key={title} className="border-t border-xelora-border pt-6">
              <Icon className="h-5 w-5 text-xelora-text" strokeWidth={1.75} aria-hidden="true" />
              <h3 className="mt-4 text-base font-semibold text-xelora-text">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">{text}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Pricing preview ──────────────────────────────────────────────────── */

export function PricingPreview() {
  return (
    <section className="border-b border-xelora-border bg-xelora-bg-main py-24" aria-labelledby="pricing-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
          <SectionTitle id="pricing-heading" eyebrow="Pricing" title="Start free. Upgrade when you are ready." />
          <Link href="/pricing" className="inline-flex items-center gap-1 text-sm font-medium text-xelora-green hover:underline">
            Compare all plans <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const featured = plan.tier === 'professional';
            return (
              <div
                key={plan.tier}
                className={`flex flex-col rounded-2xl border bg-white p-6 ${featured ? 'border-xelora-green ring-1 ring-xelora-green' : 'border-xelora-border'}`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-xelora-text">{plan.name}</h3>
                  {featured && <span className="rounded-full bg-xelora-success-bg px-2 py-0.5 text-[11px] font-medium text-xelora-green">Most popular</span>}
                </div>
                <p className="mt-4 text-3xl font-semibold tracking-tight text-xelora-text">
                  {plan.monthlyPrice === null ? 'Custom' : plan.monthlyPrice === 0 ? 'Free' : `$${plan.monthlyPrice}`}
                  {!!plan.monthlyPrice && <span className="text-sm font-normal text-xelora-text-muted"> / month</span>}
                </p>
                <p className="mt-2 min-h-10 text-sm text-xelora-text-secondary">{plan.description}</p>
                <ul className="mt-5 flex-1 space-y-2 text-sm text-xelora-text-secondary">
                  {planHighlights(plan).map((item) => (
                    <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-xelora-green" />{item}</li>
                  ))}
                </ul>
                <Button className="mt-6 w-full" variant={featured ? 'default' : 'outline'} asChild>
                  <Link href={plan.tier === 'business' ? '/contact' : '/register'}>
                    {plan.tier === 'business' ? 'Contact us' : plan.tier === 'trial' ? 'Start free trial' : 'Get started'}
                  </Link>
                </Button>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* ── FAQ ──────────────────────────────────────────────────────────────── */

const faqs = [
  {
    q: 'What do I need to use Xelora?',
    a: 'A Windows 10 or 11 PC with Microsoft Excel (desktop version) installed for workbook tasks. You can chat, ask questions and manage files from any browser.',
  },
  {
    q: 'Does Xelora work on a Mac or with Excel Online?',
    a: 'Not yet. Xelora Desktop drives the Windows version of Excel. The web app works on any computer, but changing workbooks needs the Windows app.',
  },
  {
    q: 'Will Xelora change my workbook without asking?',
    a: 'Only when you ask for a workbook change. Greetings and questions are answered without touching Excel. For larger or destructive changes Xelora shows a plan and waits for you to confirm, and you can pause a task at any time.',
  },
  {
    q: 'How do I know the result is right?',
    a: 'Xelora reads the workbook back after each action. Tasks are marked “Completed and verified” only when the check passes; otherwise it says what could not be confirmed so you can review it.',
  },
  {
    q: 'Which file types are supported?',
    a: 'You can upload .xlsx, .xls, .csv, .tsv and .ods files. The maximum file size depends on your plan.',
  },
  {
    q: 'What happens to my data?',
    a: 'Files you upload and your conversations are stored in your private Xelora workspace and you can delete them at any time. To answer a request, the relevant text is sent to our AI provider. Details are in our Privacy Policy.',
  },
  {
    q: 'What happens when the free trial ends?',
    a: 'Choose a plan to keep using Xelora. Your conversations and files stay in your account.',
  },
];

export function Faq() {
  return (
    <section className="border-b border-xelora-border bg-white py-24" aria-labelledby="faq-heading">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_2fr] lg:px-8">
        <SectionTitle id="faq-heading" eyebrow="FAQ" title="Questions, answered" />
        <div className="divide-y divide-xelora-border border-y border-xelora-border">
          {faqs.map(({ q, a }) => (
            <details key={q} className="group py-5">
              <summary className="flex list-none items-center justify-between gap-4 text-left text-base font-medium text-xelora-text [&::-webkit-details-marker]:hidden">
                {q}
                <span className="text-xl font-light text-xelora-text-muted transition-transform group-open:rotate-45" aria-hidden="true">+</span>
              </summary>
              <p className="mt-3 pr-8 text-sm leading-relaxed text-xelora-text-secondary">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Closing CTA ──────────────────────────────────────────────────────── */

export function ClosingCta() {
  return (
    <section className="bg-white py-24" aria-labelledby="cta-heading">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="relative overflow-hidden rounded-3xl border border-xelora-green/20 bg-xelora-success-bg px-6 py-16 text-center sm:px-12">
          <div
            className="pointer-events-none absolute inset-x-0 -top-24 h-64 bg-[radial-gradient(ellipse_at_center,rgba(14,122,90,0.14),transparent_70%)]"
            aria-hidden="true"
          />
          <h2 id="cta-heading" className="relative text-3xl font-semibold tracking-tight text-xelora-text sm:text-4xl">
            Hand Xelora your next spreadsheet task
          </h2>
          <p className="relative mx-auto mt-4 max-w-xl text-base text-xelora-text-secondary">
            Free for {site.trialDays} days. Set up takes a few minutes.
          </p>
          <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button size="lg" asChild>
              <Link href="/register">Get started free <ArrowRight className="h-4 w-4" /></Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/download"><Download className="h-4 w-4" /> Download for Windows</Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
