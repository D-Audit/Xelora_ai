'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';

const tabs = [
  {
    id: 'clean',
    label: 'Clean data',
    preview: (
      <div className="p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">
          Data cleaning result
        </p>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="bg-xelora-surface-2">
                {['Employee ID', 'Name', 'Department', 'Status'].map((heading) => (
                  <th key={heading} className="border border-xelora-border px-3 py-2 text-left font-medium text-xelora-text">
                    {heading}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                ['EMP-001', 'Sarah Johnson', 'Marketing', '✓'],
                ['EMP-002', 'david smith', 'Sales', '⚠ Fixed casing'],
                ['EMP-003', 'Emily   Clarke', 'HR', '⚠ Trimmed spaces'],
                ['EMP-004', 'Robert Chen', 'Finance', '✓'],
                ['EMP-005', 'MARIA GARCIA', 'Operations', '⚠ Fixed casing'],
              ].map((row, index) => (
                <tr key={index} className={row[3] !== '✓' ? 'bg-xelora-warning-bg' : ''}>
                  {row.map((cell, columnIndex) => (
                    <td
                      key={columnIndex}
                      className={`border border-xelora-border px-3 py-2 ${
                        columnIndex === 3 && cell !== '✓'
                          ? 'font-medium text-xelora-warning'
                          : columnIndex === 3
                            ? 'font-medium text-xelora-green'
                            : 'text-xelora-text'
                      }`}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-xelora-text-secondary">3 values corrected · 0 rows removed · Ready to approve</p>
      </div>
    ),
  },
  {
    id: 'formulas',
    label: 'Generate formulas',
    preview: (
      <div className="p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Formula assistant</p>
        <div className="mb-3 rounded-lg border border-xelora-border bg-xelora-surface-2 p-3">
          <p className="mb-1 text-xs text-xelora-text-secondary">You asked:</p>
          <p className="text-sm font-medium text-xelora-text">&quot;Calculate total revenue by region, only for completed orders&quot;</p>
        </div>
        <div className="mb-3 rounded-lg border border-xelora-border bg-white p-3">
          <p className="mb-2 text-xs text-xelora-text-secondary">Generated formula:</p>
          <code className="block rounded bg-xelora-info-bg px-2 py-1 font-mono text-xs text-xelora-info">
            =SUMIFS(C2:C1000, B2:B1000, F2, D2:D1000, &quot;Completed&quot;)
          </code>
        </div>
        <div className="text-xs leading-relaxed text-xelora-text-secondary">
          <strong className="text-xelora-text">How it works:</strong> Sums column C (Revenue) where column B matches the region in F2 and column D contains &quot;Completed&quot;.
        </div>
      </div>
    ),
  },
  {
    id: 'reports',
    label: 'Automate reports',
    preview: (
      <div className="p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Report workflow - 6 steps</p>
        <div className="space-y-2">
          {[
            { step: 'Analyse data structure', status: 'done' },
            { step: 'Group by region and product', status: 'done' },
            { step: 'Calculate monthly totals', status: 'done' },
            { step: 'Create summary sheet', status: 'running' },
            { step: 'Generate bar chart', status: 'pending' },
            { step: 'Format and export', status: 'pending' },
          ].map(({ step, status }) => (
            <div key={step} className="flex items-center gap-3">
              <span
                className={cn(
                  'h-2.5 w-2.5 shrink-0 rounded-full',
                  status === 'done'
                    ? 'bg-xelora-green'
                    : status === 'running'
                      ? 'animate-pulse bg-xelora-bright-green'
                      : 'bg-xelora-border'
                )}
              />
              <span
                className={cn(
                  'text-xs',
                  status === 'done'
                    ? 'text-xelora-text-muted line-through'
                    : status === 'running'
                      ? 'font-medium text-xelora-text'
                      : 'text-xelora-text-muted'
                )}
              >
                {step}
              </span>
              {status === 'running' && <span className="ml-auto text-[10px] font-medium text-xelora-green">Running...</span>}
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    id: 'files',
    label: 'Process files',
    preview: (
      <div className="p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Batch processing - 8 files</p>
        <div className="space-y-2">
          {[
            { name: 'Region_North.xlsx', status: 'Completed', colour: 'text-xelora-success' },
            { name: 'Region_South.xlsx', status: 'Completed', colour: 'text-xelora-success' },
            { name: 'Region_East.xlsx', status: 'Processing...', colour: 'text-xelora-info' },
            { name: 'Region_West.xlsx', status: 'Queued', colour: 'text-xelora-text-muted' },
            { name: 'Region_Central.xlsx', status: 'Queued', colour: 'text-xelora-text-muted' },
          ].map(({ name, status, colour }) => (
            <div key={name} className="flex items-center justify-between rounded border border-xelora-border bg-white px-3 py-2">
              <span className="text-xs text-xelora-text">{name}</span>
              <span className={`text-xs font-medium ${colour}`}>{status}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-xelora-text-secondary">2 of 8 complete · Est. 3 min remaining</p>
      </div>
    ),
  },
  {
    id: 'review',
    label: 'Review changes',
    preview: (
      <div className="p-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Change summary - step 4 approval</p>
        <div className="mb-3 rounded-lg border border-xelora-info bg-xelora-info-bg p-3">
          <p className="mb-1 text-xs font-semibold text-xelora-info">Ready to create Summary sheet</p>
          <p className="text-xs text-xelora-text-secondary">
            Xelora will create a new sheet named &quot;Summary&quot; with 6 columns and 12 rows of aggregated data.
          </p>
        </div>
        <div className="mb-4 space-y-1.5">
          {['+1 new sheet (Summary)', '+6 columns added', '~12 rows of aggregated data', 'No existing data modified'].map((change) => (
            <div key={change} className="flex items-center gap-2 text-xs">
              <span className="text-xelora-green">✓</span>
              <span className="text-xelora-text-secondary">{change}</span>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <div className="flex-1 cursor-pointer rounded bg-xelora-green py-2 text-center text-xs font-medium text-white">Approve and continue</div>
          <div className="cursor-pointer rounded border border-xelora-border px-3 py-2 text-center text-xs text-xelora-text-secondary">Skip step</div>
        </div>
      </div>
    ),
  },
];

export function ProductPreviewSection() {
  const [activeTab, setActiveTab] = useState('clean');
  const current = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];

  return (
    <section className="border-b border-xelora-border bg-xelora-surface-2 py-20" aria-labelledby="preview-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-10 max-w-2xl">
          <p className="mb-3 text-sm font-medium uppercase tracking-wide text-xelora-green">Product preview</p>
          <h2 id="preview-heading" className="text-3xl font-semibold leading-tight text-xelora-text">
            See what working with Xelora looks like
          </h2>
        </div>

        <div className="mb-6 flex flex-wrap gap-2" role="tablist" aria-label="Product preview tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`preview-panel-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'rounded-md border px-4 py-2 text-sm font-medium transition-all duration-150',
                activeTab === tab.id
                  ? 'border-xelora-green bg-xelora-green text-white'
                  : 'border-xelora-border bg-white text-xelora-text-secondary hover:border-xelora-green hover:text-xelora-text'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div
          id={`preview-panel-${activeTab}`}
          role="tabpanel"
          className="overflow-hidden rounded-xl border border-xelora-border bg-white shadow-sm"
        >
          <div className="flex items-center gap-2 border-b border-xelora-border bg-xelora-surface-2 px-4 py-2.5">
            <div className="flex gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-xelora-border" />
              <span className="h-2.5 w-2.5 rounded-full bg-xelora-border" />
              <span className="h-2.5 w-2.5 rounded-full bg-xelora-border" />
            </div>
            <span className="ml-2 text-xs text-xelora-text-muted">{current.label}</span>
          </div>
          {current.preview}
        </div>
      </div>
    </section>
  );
}
