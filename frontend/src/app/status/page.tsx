import type { Metadata } from 'next';
import { CircleCheck, CircleAlert } from 'lucide-react';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { backendUrl } from '@/lib/backend';
import { getLatestInstallerInfo } from '@/lib/desktop-release';
import { site } from '@/lib/site';

export const metadata: Metadata = { title: 'Status', description: `Live status of ${site.name} services.` };
export const revalidate = 60;

async function apiReachable(): Promise<boolean> {
  try {
    const response = await fetch(backendUrl('/'), { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    return response.ok;
  } catch {
    return false;
  }
}

export default async function StatusPage() {
  const [api, installer] = await Promise.all([apiReachable(), getLatestInstallerInfo()]);
  const services = [
    { name: 'Website and web app', ok: true, detail: 'Serving pages' },
    { name: 'Xelora API (accounts, chat, files)', ok: api, detail: api ? 'Responding normally' : 'Not responding. It may be starting up; try again in a minute.' },
    { name: 'Desktop downloads and updates', ok: !!installer, detail: installer ? `Version ${installer.version} available` : 'Installer temporarily unavailable' },
  ];
  const allOk = services.every((service) => service.ok);

  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-semibold tracking-tight text-xelora-text">System status</h1>
          <div className={`mt-8 flex items-center gap-3 rounded-2xl border p-5 ${allOk ? 'border-xelora-green/30 bg-xelora-success-bg' : 'border-xelora-warning/30 bg-xelora-warning-bg'}`}>
            {allOk ? <CircleCheck className="h-5 w-5 text-xelora-green" /> : <CircleAlert className="h-5 w-5 text-xelora-warning" />}
            <p className="text-base font-medium text-xelora-text">{allOk ? 'All systems operational' : 'Some services are having problems'}</p>
          </div>
          <ul className="mt-8 divide-y divide-xelora-border rounded-2xl border border-xelora-border">
            {services.map((service) => (
              <li key={service.name} className="flex items-start justify-between gap-4 p-5">
                <div>
                  <p className="text-sm font-medium text-xelora-text">{service.name}</p>
                  <p className="mt-1 text-sm text-xelora-text-secondary">{service.detail}</p>
                </div>
                <span className={`shrink-0 text-xs font-medium ${service.ok ? 'text-xelora-green' : 'text-xelora-warning'}`}>
                  {service.ok ? 'Operational' : 'Degraded'}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-6 text-xs text-xelora-text-muted">Checked live, refreshed every minute.</p>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
