'use client';
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

const faqs = [
  { q: 'Does Xelora replace Excel?', a: 'No. Xelora works alongside Excel and other spreadsheet applications. You keep using the tools you already have — Xelora automates the repetitive parts without replacing your existing workflow.' },
  { q: 'Do I need the desktop app?', a: 'The Xelora Web dashboard manages your account, workflows, files, and settings. To run automations and AI tasks on your spreadsheets, you install Xelora Desktop on your machine. Both are included in every plan.' },
  { q: 'Can Xelora work offline?', a: 'Xelora Desktop can run workflows entirely offline when local processing is enabled. The web dashboard requires an internet connection. Cloud sync is optional.' },
  { q: 'What happens when my trial expires?', a: 'When your 14-day trial ends, your account moves to read-only mode. Your workflows and files are preserved. You can upgrade to a paid plan at any time to continue running automations.' },
  { q: 'Are my spreadsheet files uploaded automatically?', a: 'No. Files are only uploaded to Xelora Cloud if you explicitly enable cloud sync for that file or workflow. Local processing is the default for all automations.' },
  { q: 'Can I edit my spreadsheet while an automation is running?', a: 'Yes. You can pause any workflow, make changes to the spreadsheet, and then resume. Xelora will re-read the file before continuing with the next step.' },
  { q: 'Which spreadsheet formats are supported?', a: 'Xelora supports .xlsx, .xls, .csv, .ods, and .tsv files. Excel-specific features like macros and VBA are not currently supported.' },
];

export function FaqSection() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <section className="py-20 bg-xelora-surface-2 border-b border-xelora-border" aria-labelledby="faq-heading">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 id="faq-heading" className="text-3xl font-semibold text-xelora-text mb-10 text-center">
          Frequently asked questions
        </h2>
        <dl className="divide-y divide-xelora-border rounded-lg border border-xelora-border bg-white overflow-hidden">
          {faqs.map(({ q, a }, i) => (
            <div key={i}>
              <dt>
                <button
                  className="flex w-full items-center justify-between gap-4 px-6 py-4 text-left text-sm font-medium text-xelora-text hover:bg-xelora-surface-2 transition-colors"
                  onClick={() => setOpen(open === i ? null : i)}
                  aria-expanded={open === i}
                  aria-controls={`faq-answer-${i}`}
                >
                  <span>{q}</span>
                  <ChevronDown className={cn('h-4 w-4 text-xelora-text-muted shrink-0 transition-transform duration-150', open === i && 'rotate-180')} aria-hidden="true" />
                </button>
              </dt>
              <dd
                id={`faq-answer-${i}`}
                className={cn('overflow-hidden transition-all duration-200', open === i ? 'max-h-48' : 'max-h-0')}
              >
                <p className="px-6 pb-4 text-sm text-xelora-text-secondary leading-relaxed">{a}</p>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
