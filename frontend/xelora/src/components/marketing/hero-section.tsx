import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Play } from 'lucide-react';

export function HeroSection() {
  return (
    <section className="bg-white border-b border-xelora-border" aria-labelledby="hero-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-20 lg:py-28">
        <div className="max-w-3xl">
          <p className="text-sm font-medium text-xelora-green tracking-wide uppercase mb-4">
            AI-powered spreadsheet automation
          </p>
          <h1
            id="hero-heading"
            className="text-4xl font-semibold text-xelora-black leading-tight sm:text-5xl lg:text-[52px] lg:leading-[1.15]"
          >
            Spreadsheet work should not feel repetitive.
          </h1>
          <p className="mt-5 text-lg text-xelora-text-secondary leading-relaxed max-w-2xl">
            Open a spreadsheet, describe the outcome you need, review the suggested steps, and let
            Xelora complete the repetitive work while you remain in control.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button variant="bright" size="lg" asChild>
              <Link href="/register">
                Start Free Trial <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
            <Button variant="outline" size="lg" asChild>
              <Link href="/how-it-works">
                <Play className="h-4 w-4" />
                See How It Works
              </Link>
            </Button>
          </div>
          <p className="mt-4 text-xs text-xelora-text-muted">
            14-day free trial · No credit card required · Cancel any time
          </p>
        </div>

        {/* Product interface preview */}
        <div className="mt-16 rounded-xl border border-xelora-border bg-white shadow-sm overflow-hidden">
          {/* Browser chrome */}
          <div className="flex items-center gap-2 px-4 py-3 bg-xelora-surface-2 border-b border-xelora-border">
            <div className="flex gap-1.5">
              <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
              <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
              <span className="h-3 w-3 rounded-full bg-[#28c840]" />
            </div>
            <div className="flex-1 mx-4">
              <div className="max-w-sm mx-auto rounded-md bg-white border border-xelora-border px-3 py-1 text-xs text-xelora-text-muted text-center">
                app.xelora.app/dashboard
              </div>
            </div>
          </div>

          {/* App shell preview */}
          <div className="flex h-[420px] sm:h-[480px]">
            {/* Sidebar */}
            <div className="hidden sm:flex w-52 flex-col bg-xelora-nav border-r border-white/10 py-4">
              <div className="px-4 mb-6">
                <div className="flex items-center gap-2">
                  <div className="h-6 w-6 rounded bg-xelora-green" />
                  <span className="text-sm font-semibold text-white">Xelora</span>
                </div>
              </div>
              {['Overview', 'Workflows', 'Files', 'History', 'Templates', 'Usage'].map((item, i) => (
                <div
                  key={item}
                  className={`flex items-center gap-2.5 px-4 py-2 text-xs ${
                    i === 0
                      ? 'bg-white/10 text-white'
                      : 'text-white/60'
                  }`}
                >
                  <div className={`h-3.5 w-3.5 rounded-sm ${i === 0 ? 'bg-xelora-bright-green' : 'bg-white/30'}`} />
                  {item}
                </div>
              ))}
            </div>

            {/* Main content */}
            <div className="flex-1 p-5 overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <div className="h-5 w-48 bg-xelora-text rounded" />
                  <div className="h-3 w-64 bg-xelora-surface-2 rounded mt-1.5" />
                </div>
                <div className="flex gap-2">
                  <div className="h-8 w-24 rounded bg-xelora-surface-2 border border-xelora-border" />
                  <div className="h-8 w-28 rounded bg-xelora-green" />
                </div>
              </div>

              {/* Workflow steps panel */}
              <div className="rounded-lg border border-xelora-border bg-white p-4 mb-3">
                <div className="flex items-center gap-2 mb-3">
                  <div className="h-4 w-4 rounded-full bg-xelora-green" />
                  <span className="text-xs font-medium text-xelora-text">Monthly Sales Summary — running</span>
                  <span className="ml-auto text-xs text-xelora-text-muted">Step 4 of 8</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-xelora-surface-2 mb-3">
                  <div className="h-1.5 w-1/2 rounded-full bg-xelora-green" />
                </div>
                <div className="space-y-2">
                  {[
                    { label: 'Workbook opened', done: true },
                    { label: '4,218 rows detected', done: true },
                    { label: '42 duplicate rows removed', done: true },
                    { label: 'Standardising district names…', done: false, active: true },
                    { label: 'Adding revenue formula', done: false },
                    { label: 'Generating summary sheet', done: false },
                  ].map((step) => (
                    <div key={step.label} className="flex items-center gap-2">
                      <span className={`h-3 w-3 rounded-full shrink-0 ${step.done ? 'bg-xelora-green' : step.active ? 'bg-xelora-bright-green animate-pulse' : 'bg-xelora-border'}`} />
                      <span className={`text-xs ${step.active ? 'text-xelora-text font-medium' : step.done ? 'text-xelora-text-secondary line-through decoration-xelora-border' : 'text-xelora-text-muted'}`}>
                        {step.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Approval prompt */}
              <div className="rounded-lg border border-xelora-info bg-xelora-info-bg p-3 flex items-start gap-3">
                <div className="h-4 w-4 rounded-full bg-xelora-info shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-xelora-info">Review required</p>
                  <p className="text-xs text-xelora-text-secondary mt-0.5">
                    Xelora is about to create the Summary sheet. Approve to continue.
                  </p>
                </div>
                <div className="flex gap-1.5">
                  <div className="h-6 w-14 rounded bg-xelora-green text-white text-xs flex items-center justify-center font-medium">Approve</div>
                  <div className="h-6 w-12 rounded border border-xelora-border text-xelora-text-secondary text-xs flex items-center justify-center">Skip</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
