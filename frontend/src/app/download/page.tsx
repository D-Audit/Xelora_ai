import Link from 'next/link';
import type { Metadata } from 'next';
import { Check, Download, ShieldCheck } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { Button } from '@/components/ui/button';
import { getLatestInstallerInfo } from '@/lib/desktop-release';

export const metadata: Metadata = {
  title: 'Download Xelora for Windows',
  description: 'Install Xelora Desktop to let Xelora work in Microsoft Excel on your Windows PC.',
};
export const revalidate = 300;

const requirements = [
  'Windows 10 or Windows 11 (64-bit)',
  'Microsoft Excel for Windows (Microsoft 365, 2021, 2019 or 2016)',
  'An internet connection and a Xelora account',
];

const setup = [
  { title: 'Download and run the installer', text: 'Open Xelora-Setup.exe and follow the steps. It installs for your Windows user only.' },
  { title: 'Sign in', text: 'Use the same account as on the web. The app connects to your account automatically.' },
  { title: 'Start a chat', text: 'Ask for what you need. Xelora opens Excel only when a request needs a workbook.' },
];

export default async function DownloadPage() {
  const installer = await getLatestInstallerInfo();

  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <section className="border-b border-xelora-border">
          <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 lg:grid-cols-[1.2fr_1fr] lg:px-8">
            <div>
              <p className="text-sm font-medium text-xelora-green">Xelora Desktop</p>
              <h1 className="mt-2 text-4xl font-semibold tracking-tight text-xelora-text sm:text-5xl">Download for Windows</h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-xelora-text-secondary">
                Xelora Desktop lets Xelora carry out tasks in Microsoft Excel on your PC. It includes the full
                Xelora app, so you can chat, manage files and see your history in one window.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                {installer ? (
                  <Button size="lg" asChild>
                    <a href="/api/download/windows"><Download className="h-4 w-4" /> Download Xelora {installer.version}</a>
                  </Button>
                ) : (
                  <Button size="lg" disabled><Download className="h-4 w-4" /> Download unavailable, try again shortly</Button>
                )}
                <Button size="lg" variant="outline" asChild>
                  <Link href="/register">Create a free account</Link>
                </Button>
              </div>
              {installer && (
                <p className="mt-3 text-xs text-xelora-text-muted">
                  Version {installer.version} · {installer.sizeMB} MB · Updates install automatically
                </p>
              )}
            </div>
            <div className="rounded-2xl border border-xelora-border p-6">
              <h2 className="text-sm font-semibold text-xelora-text">System requirements</h2>
              <ul className="mt-4 space-y-3 text-sm text-xelora-text-secondary">
                {requirements.map((item) => (
                  <li key={item} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-xelora-green" />{item}</li>
                ))}
              </ul>
              <p className="mt-6 border-t border-xelora-border pt-4 text-xs leading-relaxed text-xelora-text-muted">
                Not on Windows? You can still chat, ask questions and manage files in the{' '}
                <Link href="/login" className="text-xelora-green hover:underline">web app</Link>. Workbook tasks run when you
                next use Xelora Desktop.
              </p>
            </div>
          </div>
        </section>

        <section className="bg-xelora-bg-main">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
            <h2 className="text-2xl font-semibold tracking-tight text-xelora-text">Set up in three steps</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3">
              {setup.map((step, index) => (
                <li key={step.title}>
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border border-xelora-border-strong bg-white text-sm font-semibold text-xelora-text">{index + 1}</span>
                  <h3 className="mt-4 text-base font-semibold text-xelora-text">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">{step.text}</p>
                </li>
              ))}
            </ol>
            <div className="mt-12 flex gap-3 rounded-2xl border border-xelora-border bg-white p-5 text-sm text-xelora-text-secondary">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-xelora-text" strokeWidth={1.75} />
              <p>
                Windows may show a SmartScreen notice for new apps. Choose <span className="font-medium text-xelora-text">More info</span>,
                check that the file name is Xelora-Setup, then select <span className="font-medium text-xelora-text">Run anyway</span>.
                Only download Xelora from this page.
              </p>
            </div>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
