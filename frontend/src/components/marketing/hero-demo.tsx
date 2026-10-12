'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { ArrowUp, Check, CircleCheck, Loader2, MessageSquare, Pause, Play, Plus, Table2 } from 'lucide-react';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { cn } from '@/lib/utils';

/**
 * The hero's product walkthrough: a scaled, static-size sketch of Xelora
 * Desktop that plays a request from prompt to verified result. It pauses
 * when off screen, in a background tab, or when the visitor pauses it, and
 * shows the finished result when the visitor prefers reduced motion.
 */

const STEPS = [
  { id: 'ask', label: 'Ask', caption: 'Describe the task in plain language.' },
  { id: 'plan', label: 'Plan', caption: 'Xelora reads the workbook and plans the changes.' },
  { id: 'build', label: 'Build', caption: 'It does the work in your own copy of Excel.' },
  { id: 'verify', label: 'Verify', caption: 'Every change is checked before a task is marked done.' },
] as const;
const STEP_MS = 5200;

const PROMPT = 'Summarise sales by region and add a chart';
const ANSWER = 'Done. North leads with 412,380, about 33% of total sales. The chart sits next to the table on the Summary sheet.';

const SALES = [
  ['02 Sep', 'North', 'Laptops', '18', '21,400'],
  ['02 Sep', 'East', 'Monitors', '42', '9,870'],
  ['03 Sep', 'South', 'Laptops', '11', '13,090'],
  ['03 Sep', 'West', 'Docks', '35', '4,515'],
  ['04 Sep', 'North', 'Monitors', '27', '6,345'],
  ['04 Sep', 'East', 'Laptops', '16', '19,040'],
  ['05 Sep', 'South', 'Docks', '52', '6,708'],
  ['05 Sep', 'West', 'Laptops', '9', '10,710'],
];
const PIVOT = [
  ['North', '412,380', 92],
  ['East', '351,902', 78],
  ['South', '298,145', 66],
  ['West', '187,604', 42],
] as const;

/* ── Hooks ───────────────────────────────────────────────────────────── */

function subscribeReducedMotion(callback: () => void) {
  const query = window.matchMedia('(prefers-reduced-motion: reduce)');
  query.addEventListener('change', callback);
  return () => query.removeEventListener('change', callback);
}
function useReducedMotion() {
  return useSyncExternalStore(subscribeReducedMotion, () => window.matchMedia('(prefers-reduced-motion: reduce)').matches, () => false);
}

function subscribeVisibility(callback: () => void) {
  document.addEventListener('visibilitychange', callback);
  return () => document.removeEventListener('visibilitychange', callback);
}
function usePageVisible() {
  return useSyncExternalStore(subscribeVisibility, () => !document.hidden, () => true);
}

function useInView<T extends Element>() {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { threshold: 0.15 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, inView] as const;
}

/** Types `text` out once after `delayMs`; mount it fresh to replay. */
function useTyped(text: string, active: boolean, delayMs = 0, speedMs = 28) {
  const [count, setCount] = useState(active ? 0 : text.length);
  useEffect(() => {
    if (!active) return;
    let interval = 0;
    const timeout = window.setTimeout(() => {
      interval = window.setInterval(() => {
        setCount((value) => {
          if (value >= text.length) window.clearInterval(interval);
          return Math.min(value + 1, text.length);
        });
      }, speedMs);
    }, delayMs);
    return () => {
      window.clearTimeout(timeout);
      window.clearInterval(interval);
    };
  }, [active, delayMs, speedMs, text]);
  return { typed: text.slice(0, count), done: count >= text.length };
}

/* ── Building blocks ─────────────────────────────────────────────────── */

function Reveal({ animate, delay = 0, className, children }: { animate: boolean; delay?: number; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn(animate && 'xl-enter', className)} style={animate ? { animationDelay: `${delay}s` } : undefined}>
      {children}
    </div>
  );
}

/** A task step: spins while running, then turns into a check. */
function WorkStep({ text, animate, delay = 0 }: { text: string; animate: boolean; delay?: number }) {
  return (
    <Reveal animate={animate} delay={delay} className="flex items-center gap-2 text-[12px] text-xelora-text-secondary">
      <span className="relative h-3.5 w-3.5 shrink-0">
        {animate && (
          <span className="xl-fade-out absolute inset-0" style={{ animationDelay: `${delay + 0.8}s` }}>
            <Loader2 className="h-3.5 w-3.5 animate-spin text-xelora-text-muted" />
          </span>
        )}
        <Check className={cn('absolute inset-0 h-3.5 w-3.5 text-xelora-green', animate && 'xl-pop')} style={animate ? { animationDelay: `${delay + 0.8}s` } : undefined} />
      </span>
      {text}
    </Reveal>
  );
}

function TypingComposer({ animate }: { animate: boolean }) {
  const { typed, done } = useTyped(PROMPT, animate, 400, 34);
  return (
    <>
      <span className="min-w-0 flex-1 truncate text-xelora-text">
        {typed}
        {!done && <span className="xl-caret ml-px inline-block h-3.5 w-px translate-y-0.5 bg-xelora-text" />}
      </span>
      <span className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-colors duration-300', done ? 'bg-xelora-text text-xelora-surface' : 'bg-xelora-surface-2 text-xelora-text-muted')}>
        <ArrowUp className="h-3.5 w-3.5" />
      </span>
    </>
  );
}

function TypedAnswer({ animate }: { animate: boolean }) {
  const { typed } = useTyped(ANSWER, animate, 1300, 18);
  return <p className="min-h-[54px] text-[12.5px] leading-relaxed text-xelora-text">{typed}</p>;
}

/* ── The app sketch (1000 × 560, scaled to fit) ──────────────────────── */

function AppSketch({ step, animate }: { step: number; animate: boolean }) {
  /** Animate only what the current step adds; earlier steps render settled. */
  const on = (owner: number) => animate && step === owner;
  const working = step === 1 || step === 2;

  return (
    <div className="flex h-full w-full bg-xelora-surface text-xelora-text">
      {/* Sidebar */}
      <aside className="flex w-[168px] shrink-0 flex-col border-r border-xelora-border bg-xelora-bg-main px-3 py-4">
        <XeloraLogo size="sm" className="px-1" />
        <div className="mt-5 flex h-8 items-center gap-2 rounded-lg border border-xelora-border bg-xelora-surface px-2.5 text-[12px] font-medium">
          <Plus className="h-3.5 w-3.5" /> New chat
        </div>
        <p className="mt-5 px-1 text-[10.5px] font-medium text-xelora-text-muted">Today</p>
        <div className="mt-1.5 space-y-0.5 text-[12px]">
          {['Sales by region', 'Clean customer list', 'Q3 budget formulas', 'Invoice tracker'].map((title, index) => (
            <div key={title} className={cn('flex h-[28px] items-center gap-2 rounded-md px-2', index === 0 ? 'bg-xelora-surface-2 font-medium text-xelora-text' : 'text-xelora-text-secondary')}>
              <MessageSquare className="h-3 w-3 shrink-0 opacity-60" />
              <span className="truncate">{title}</span>
            </div>
          ))}
        </div>
        <div className="mt-auto flex items-center gap-2 px-1">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-xelora-text text-[10px] font-semibold text-xelora-surface">A</span>
          <span className="text-[11.5px] text-xelora-text-secondary">Amina K.</span>
          <span className="ml-auto rounded-full border border-xelora-border px-1.5 text-[10px] text-xelora-text-muted">Pro</span>
        </div>
      </aside>

      {/* Chat */}
      <section className="flex w-[352px] shrink-0 flex-col border-r border-xelora-border">
        <div className="flex h-11 items-center justify-between border-b border-xelora-border px-5 text-[12.5px]">
          <span className="font-medium">Sales by region</span>
          <span className="flex items-center gap-1.5 text-[11px] text-xelora-text-muted">
            <span className={cn('h-1.5 w-1.5 rounded-full', working ? 'animate-pulse bg-xelora-warning' : 'bg-xelora-green')} />
            {working ? 'Working in Excel' : 'Desktop connected'}
          </span>
        </div>

        <div className="flex-1 space-y-4 overflow-hidden px-5 py-5">
          {step >= 1 && (
            <Reveal animate={on(1)} className="ml-auto w-fit max-w-[85%] rounded-2xl bg-xelora-surface-2 px-3.5 py-2 text-[12.5px]">
              {PROMPT}
            </Reveal>
          )}
          {step >= 1 && (
            <Reveal animate={on(1)} delay={0.3} className="space-y-2">
              <p className="text-[11px] font-medium text-xelora-text-muted">Worked in Excel</p>
              <WorkStep animate={on(1)} delay={0.6} text="Read Sales · 1,248 rows, 6 columns" />
              <WorkStep animate={on(1)} delay={1.7} text="Planned 2 changes on a new sheet" />
              {step >= 2 && <WorkStep animate={on(2)} delay={0.4} text="Created a PivotTable on Summary" />}
              {step >= 2 && <WorkStep animate={on(2)} delay={1.8} text="Added a clustered column chart" />}
              {step >= 3 && <WorkStep animate={on(3)} delay={0.2} text="Checked totals against the source data" />}
            </Reveal>
          )}
          {step >= 3 && (
            <Reveal animate={on(3)} delay={1.1} className="space-y-2.5">
              <TypedAnswer animate={on(3)} />
              <Reveal animate={on(3)} delay={3.6} className="flex items-center gap-1.5 text-[11.5px] font-medium text-xelora-green">
                <CircleCheck className="h-3.5 w-3.5" /> Completed and verified
              </Reveal>
            </Reveal>
          )}
        </div>

        <div className="p-4 pt-0">
          <div className="flex h-11 items-center gap-2 rounded-xl border border-xelora-border-strong bg-xelora-surface pl-3.5 pr-2 text-[12.5px] shadow-sm">
            {step === 0 ? <TypingComposer key="typing" animate={animate} /> : (
              <>
                <span className="flex-1 text-xelora-text-muted">Ask Xelora anything…</span>
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-xelora-surface-2 text-xelora-text-muted"><ArrowUp className="h-3.5 w-3.5" /></span>
              </>
            )}
          </div>
        </div>
      </section>

      {/* Excel */}
      <section className="flex min-w-0 flex-1 flex-col bg-xelora-bg-main">
        <div className="flex h-11 items-center gap-2 border-b border-xelora-border px-4 text-[11.5px]">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-[#107C41] text-[10px] font-bold text-white">X</span>
          <span className="font-medium">Sales.xlsx</span>
          <span className="ml-3 flex gap-3 text-xelora-text-muted">
            {['Home', 'Insert', 'Data', 'Review'].map((tab) => <span key={tab} className={cn(tab === 'Insert' && step === 2 && 'font-medium text-xelora-text')}>{tab}</span>)}
          </span>
        </div>
        <div className="flex h-8 items-center gap-2 border-b border-xelora-border px-4 font-mono text-[11px] text-xelora-text-secondary">
          <span className="w-10 text-xelora-text-muted">{step >= 2 ? 'B7' : 'A1'}</span>
          <span className="text-xelora-text-muted">fx</span>
          <span className="truncate">{step >= 2 ? '=GETPIVOTDATA("Revenue",$A$2)' : 'Date'}</span>
        </div>

        <div className="relative flex-1 overflow-hidden p-4">
          {step < 2 ? (
            <div className="relative">
              <table className="w-full border-collapse text-[11px]">
                <thead>
                  <tr className="bg-xelora-surface-2 text-left text-xelora-text-secondary">
                    {['Date', 'Region', 'Product', 'Units', 'Revenue'].map((h) => <th key={h} className="border border-xelora-border px-2 py-1.5 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {SALES.map((row, index) => (
                    <tr key={index} className="bg-xelora-surface">
                      {row.map((cell, col) => <td key={col} className={cn('border border-xelora-border px-2 py-[5px]', col >= 3 && 'text-right tabular-nums')}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
              {step === 1 && (
                <Reveal animate={on(1)} delay={0.9} className="pointer-events-none absolute inset-0 rounded-sm border-2 border-xelora-green bg-xelora-green/[0.07]">
                  <span className="absolute -bottom-6 right-0 rounded bg-xelora-green px-1.5 py-0.5 text-[10px] font-medium text-white">A1:E1249 · reading</span>
                </Reveal>
              )}
              <p className="mt-3 text-center text-[10.5px] text-xelora-text-muted">1,240 more rows</p>
            </div>
          ) : (
            <div className="grid grid-cols-[1fr_1.1fr] gap-5">
              <div>
                <Reveal animate={on(2)} delay={0.2}>
                  <table className="w-full border-collapse text-[11px]">
                    <thead>
                      <tr className="bg-xelora-green/10 text-left text-xelora-text">
                        <th className="border border-xelora-border px-2 py-1.5 font-medium">Region</th>
                        <th className="border border-xelora-border px-2 py-1.5 text-right font-medium">Sum of Revenue</th>
                      </tr>
                    </thead>
                  </table>
                </Reveal>
                {PIVOT.map(([region, total], index) => (
                  <Reveal key={region} animate={on(2)} delay={0.45 + index * 0.15}>
                    <div className="grid grid-cols-2 border-x border-b border-xelora-border bg-xelora-surface text-[11px]">
                      <span className="border-r border-xelora-border px-2 py-[5px]">{region}</span>
                      <span className="px-2 py-[5px] text-right tabular-nums">{total}</span>
                    </div>
                  </Reveal>
                ))}
                <Reveal animate={on(2)} delay={1.1}>
                  <div className="grid grid-cols-2 border-x border-b border-xelora-border bg-xelora-surface text-[11px] font-semibold">
                    <span className="border-r border-xelora-border px-2 py-[5px]">Grand Total</span>
                    <span className="flex items-center justify-end gap-1 px-2 py-[5px] tabular-nums">
                      {step === 3 && <Check className={cn('h-3 w-3 text-xelora-green', on(3) && 'xl-pop')} style={on(3) ? { animationDelay: '0.9s' } : undefined} />}
                      1,250,031
                    </span>
                  </div>
                </Reveal>
              </div>

              <Reveal animate={on(2)} delay={1.3} className="rounded-lg border border-xelora-border bg-xelora-surface p-3">
                <p className="text-[11px] font-medium">Revenue by region</p>
                <div className="mt-3 flex h-[150px] items-end gap-3 border-b border-l border-xelora-border px-3">
                  {PIVOT.map(([region, , height], index) => (
                    <div key={region} className="flex h-full flex-1 items-end">
                      <div
                        className={cn('w-full rounded-t bg-xelora-green/85', on(2) && 'xl-grow')}
                        style={{ height: `${height}%`, ...(on(2) ? { animationDelay: `${1.6 + index * 0.12}s` } : {}) }}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-1 flex gap-3 px-3 text-[10px] text-xelora-text-muted">
                  {PIVOT.map(([region]) => <span key={region} className="flex-1 text-center">{region}</span>)}
                </div>
              </Reveal>
            </div>
          )}

          {step === 3 && (
            <Reveal animate={on(3)} delay={0.9} className="absolute bottom-4 right-4 flex items-center gap-1.5 rounded-full border border-xelora-border bg-xelora-surface px-3 py-1.5 text-[11px] font-medium shadow-sm">
              <CircleCheck className="h-3.5 w-3.5 text-xelora-green" /> Totals match the source data
            </Reveal>
          )}
        </div>

        <div className="flex h-8 items-end gap-0.5 border-t border-xelora-border px-3 text-[11px]">
          <span className={cn('rounded-t px-3 py-1', step < 2 ? 'bg-xelora-surface font-medium text-xelora-green' : 'text-xelora-text-muted')}>Sales</span>
          {step >= 2 && (
            <Reveal animate={on(2)} delay={0.1} className="rounded-t bg-xelora-surface px-3 py-1 font-medium text-xelora-green">Summary</Reveal>
          )}
        </div>
      </section>
    </div>
  );
}

/** Renders a fixed 1000 × 560 canvas scaled to the available width. */
function Scaled({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver(() => setScale(node.clientWidth / 1000));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className="relative w-full" style={{ aspectRatio: '1000 / 560' }}>
      <div
        className="absolute left-0 top-0 origin-top-left"
        style={{ width: 1000, height: 560, transform: `scale(${scale})`, visibility: scale ? 'visible' : 'hidden' }}
        aria-hidden="true"
        inert
      >
        {children}
      </div>
    </div>
  );
}

export function HeroDemo() {
  const reducedMotion = useReducedMotion();
  const pageVisible = usePageVisible();
  const [ref, inView] = useInView<HTMLDivElement>();
  const [paused, setPaused] = useState(false);
  const [chosenStep, setStep] = useState(0);
  const step = reducedMotion ? STEPS.length - 1 : chosenStep;
  const playing = !reducedMotion && !paused && inView && pageVisible;

  useEffect(() => {
    if (!playing) return;
    const timeout = window.setTimeout(() => setStep((value) => (value + 1) % STEPS.length), STEP_MS);
    return () => window.clearTimeout(timeout);
  }, [playing, chosenStep]);

  return (
    <div ref={ref} className="relative isolate mt-16">
      <div
        className="pointer-events-none absolute -inset-x-10 -top-16 bottom-1/3 -z-10 bg-[radial-gradient(ellipse_at_center,rgba(14,122,90,0.16),transparent_65%)] blur-2xl"
        aria-hidden="true"
      />
      <figure
        className="mx-auto w-full max-w-5xl rounded-[1.75rem] bg-xelora-surface-2 p-2 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.35)] ring-1 ring-xelora-border sm:p-2.5"
        aria-label="Xelora Desktop turning a plain-language request into a verified pivot table and chart in Excel"
      >
        <div className="overflow-hidden rounded-[1.25rem] bg-xelora-surface ring-1 ring-xelora-border">
          <div className="flex h-9 items-center border-b border-xelora-border bg-xelora-bg-main pl-4 text-[11px] text-xelora-text-muted" aria-hidden="true">
            <span className="flex items-center gap-2">
              <Table2 className="h-3.5 w-3.5 text-xelora-green" />
              Xelora <span className="text-xelora-border-strong">—</span> <span className="text-xelora-text">Sales.xlsx</span>
            </span>
            <span className="ml-auto flex h-full">
              <span className="flex w-10 items-center justify-center">─</span>
              <span className="flex w-10 items-center justify-center">☐</span>
              <span className="flex w-10 items-center justify-center">✕</span>
            </span>
          </div>
          <Scaled>
            <AppSketch step={step} animate={!reducedMotion} />
          </Scaled>
        </div>
      </figure>

      <div className="mx-auto mt-10 flex max-w-3xl items-start gap-4">
        {!reducedMotion && (
          <button
            type="button"
            onClick={() => setPaused((value) => !value)}
            aria-label={paused ? 'Play walkthrough' : 'Pause walkthrough'}
            className="-mt-2 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-xelora-surface-2 text-xelora-text-secondary transition-colors hover:bg-xelora-border hover:text-xelora-text"
          >
            {paused ? <Play className="h-3 w-3 translate-x-px" /> : <Pause className="h-3 w-3" />}
          </button>
        )}
        <div className="min-w-0 flex-1">
          <div role="tablist" aria-label="How Xelora works" className="grid grid-cols-4 gap-2 sm:gap-3">
            {STEPS.map((item, index) => {
              const active = index === step;
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  aria-controls="hero-demo-caption"
                  onClick={() => setStep(index)}
                  className="group text-left"
                >
                  <span className="relative block h-[3px] overflow-hidden rounded-full bg-xelora-text/10">
                    {active && (
                      <span
                        key={`${step}-${playing}`}
                        className={cn('absolute inset-y-0 left-0 w-full rounded-full bg-xelora-green', playing && 'xl-progress')}
                        style={playing ? { animationDuration: `${STEP_MS}ms` } : undefined}
                      />
                    )}
                    {index < step && <span className="absolute inset-0 rounded-full bg-xelora-text/35" />}
                  </span>
                  <span className={cn('mt-3 block text-[13px] font-medium transition-colors sm:text-sm', active ? 'text-xelora-text' : 'text-xelora-text-muted group-hover:text-xelora-text')}>
                    <span className="mr-1.5 hidden tabular-nums text-xelora-text-muted sm:inline">0{index + 1}</span>
                    {item.label}
                  </span>
                </button>
              );
            })}
          </div>
          <p id="hero-demo-caption" role="tabpanel" aria-live="polite" className="mt-4 text-center text-sm text-xelora-text-secondary">
            {STEPS[step].caption}
          </p>
        </div>
      </div>
    </div>
  );
}
