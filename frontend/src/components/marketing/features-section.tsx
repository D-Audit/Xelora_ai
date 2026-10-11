import { Bot, Wand2, FileSearch, GitBranch, BarChart3, Layers, History, CheckSquare, HardDrive, CloudCog } from 'lucide-react';

const features = [
  { icon: Bot, title: 'AI spreadsheet assistant', desc: 'Describe any task in plain language. Xelora AI understands your spreadsheet and builds a plan.' },
  { icon: GitBranch, title: 'Guided workflow automation', desc: 'Multi-step workflows that run one step at a time, with controls at every stage.' },
  { icon: FileSearch, title: 'Data cleaning', desc: 'Remove duplicates, fix inconsistent values, standardise formats, and fill gaps automatically.' },
  { icon: Wand2, title: 'Formula generation', desc: 'Generate complex formulas with plain-English descriptions. Every formula is explained clearly.' },
  { icon: BarChart3, title: 'Reports and charts', desc: 'Create summary sheets and charts from your data without touching a pivot table.' },
  { icon: Layers, title: 'Reusable workflows', desc: 'Save any workflow and reuse it across files. Share with your team or keep it private.' },
  { icon: History, title: 'Undo and version history', desc: 'Every change is tracked. Undo individual steps, restore previous versions, or compare differences.' },
  { icon: CheckSquare, title: 'Approval controls', desc: 'Set approval checkpoints on any step. Xelora pauses and waits for your confirmation.' },
  { icon: HardDrive, title: 'Local and cloud files', desc: 'Work entirely offline or sync to Xelora Cloud. Your data is never uploaded without your permission.' },
  { icon: CloudCog, title: 'Batch processing', desc: 'Run the same workflow across dozens of files at once. Available on Professional and Business plans.' },
];

export function FeaturesSection() {
  return (
    <section className="py-20 bg-white border-b border-xelora-border" aria-labelledby="features-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-14">
          <p className="text-sm font-medium text-xelora-green uppercase tracking-wide mb-3">Capabilities</p>
          <h2 id="features-heading" className="text-3xl font-semibold text-xelora-text leading-tight">
            Everything you need to work faster with spreadsheets
          </h2>
        </div>
        <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="flex gap-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-xelora-border bg-xelora-surface-2">
                <Icon className="h-4 w-4 text-xelora-green" aria-hidden="true" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-xelora-text mb-1">{title}</h3>
                <p className="text-sm text-xelora-text-secondary leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
