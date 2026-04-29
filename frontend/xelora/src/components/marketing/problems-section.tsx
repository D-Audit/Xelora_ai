import { RefreshCw, AlertTriangle, Code2, FileBarChart, Files, Search, Paintbrush } from 'lucide-react';

const problems = [
  { icon: RefreshCw, title: 'Repeating the same monthly process', desc: 'The same cleanup and summary every month, by hand, on the same files.' },
  { icon: AlertTriangle, title: 'Cleaning inconsistent data', desc: 'Names in different formats, blank rows, merged cells, each file a surprise.' },
  { icon: Code2, title: 'Writing difficult formulas', desc: 'VLOOKUP, nested IFs, array formulas, time-consuming and easy to break.' },
  { icon: FileBarChart, title: 'Preparing reports manually', desc: 'Copying, pasting, and formatting the same charts and tables from scratch.' },
  { icon: Files, title: 'Processing several similar files', desc: 'Running the same steps on 20 supplier files instead of once on all of them.' },
  { icon: Search, title: 'Finding spreadsheet errors', desc: 'Totals that do not add up, broken references, mismatched values hidden in thousands of rows.' },
  { icon: Paintbrush, title: 'Repeating formatting tasks', desc: 'Bold headers, colour coding, number formats, done manually every time.' },
];

export function ProblemsSection() {
  return (
    <section className="border-b border-xelora-border bg-white py-20" aria-labelledby="problems-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-12 max-w-2xl">
          <p className="mb-3 text-sm font-medium uppercase tracking-wide text-xelora-green">Sound familiar?</p>
          <h2 id="problems-heading" className="text-3xl font-semibold leading-tight text-xelora-text">
            Common spreadsheet work that should not take this long
          </h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {problems.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="rounded-lg border border-xelora-border bg-white p-5">
              <div className="mb-3 flex items-center gap-3">
                <Icon className="h-4 w-4 shrink-0 text-xelora-green" aria-hidden="true" />
                <h3 className="text-sm font-semibold leading-snug text-xelora-text">{title}</h3>
              </div>
              <p className="text-sm leading-relaxed text-xelora-text-secondary">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
