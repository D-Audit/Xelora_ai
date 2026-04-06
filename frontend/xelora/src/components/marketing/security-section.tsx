import { HardDrive, CloudCog, Eye, RotateCcw, Settings, Shield } from 'lucide-react';

const items = [
  { icon: HardDrive, title: 'Local file processing', desc: 'By default, all automation runs on your machine. Your files are never uploaded unless you explicitly enable cloud sync.' },
  { icon: CloudCog, title: 'User-controlled cloud uploads', desc: 'Cloud processing is opt-in. You choose which files and workflows can use Xelora Cloud, and when.' },
  { icon: Shield, title: 'Encryption in transit and at rest', desc: 'All files transmitted to Xelora Cloud are encrypted using TLS 1.3. Stored files are encrypted at rest using AES-256.' },
  { icon: Eye, title: 'Transparent AI context', desc: 'You can see exactly what data Xelora AI reads when generating workflows. No hidden context. No background sending.' },
  { icon: RotateCcw, title: 'Reversible changes', desc: 'Every action is tracked and reversible. Use version history to restore any previous state of your spreadsheet.' },
  { icon: Settings, title: 'Clear data-retention settings', desc: 'Set your own retention period for cloud-stored files. Delete your data at any time from the settings page.' },
];

export function SecuritySection() {
  return (
    <section className="py-20 bg-xelora-surface-2 border-b border-xelora-border" aria-labelledby="security-heading">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="max-w-2xl mb-14">
          <p className="text-sm font-medium text-xelora-green uppercase tracking-wide mb-3">Security and privacy</p>
          <h2 id="security-heading" className="text-3xl font-semibold text-xelora-text leading-tight">
            Your files stay yours
          </h2>
          <p className="mt-4 text-base text-xelora-text-secondary leading-relaxed">
            Xelora is designed around the principle that your data should never leave your machine without your explicit permission.
          </p>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="rounded-lg border border-xelora-border bg-white p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-md bg-xelora-success-bg">
                  <Icon className="h-4 w-4 text-xelora-green" aria-hidden="true" />
                </div>
                <h3 className="text-sm font-semibold text-xelora-text">{title}</h3>
              </div>
              <p className="text-sm text-xelora-text-secondary leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
