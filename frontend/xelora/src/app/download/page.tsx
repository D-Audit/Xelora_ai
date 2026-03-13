import { Download, FileCheck2, Monitor } from 'lucide-react';
import Link from 'next/link';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { SectionHeading } from '@/components/site/section-heading';
import { MockWindow } from '@/components/site/mock-window';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { downloadReleases } from '@/data/mock-marketing';
import { formatFileSize } from '@/lib/utils';

export default function DownloadPage() {
  const windowsRelease = downloadReleases.find((release) => release.os === 'windows');
  const downloadUrl = windowsRelease?.downloadUrl ?? '/api/download/windows';

  return (
    <>
      <MarketingNav />
      <main className="bg-xelora-bg-main">
        <div className="border-b border-xelora-border bg-xelora-warning-bg px-4 py-3">
          <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
            <p className="text-sm font-medium text-xelora-warning">
              The native Windows installer is available below. You can also open the desktop preview in your browser first.
            </p>
            <Button size="sm" variant="bright" className="shrink-0" asChild>
              <Link href="/desktop">
                <Monitor className="h-4 w-4" />
                Open Desktop Preview
              </Link>
            </Button>
          </div>
        </div>

        <section className="border-b border-xelora-border bg-white">
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <div className="grid gap-10 lg:grid-cols-[1.05fr_.95fr] lg:items-start">
              <div>
                <SectionHeading
                  eyebrow="Download"
                  title="Get the desktop app for local spreadsheet automation"
                  description="The web app manages your account, workflows, and files. The desktop app performs spreadsheet automation on your machine."
                />

                <Alert variant="info" className="mt-6">
                  <Monitor className="h-4 w-4" />
                  <AlertTitle>Desktop Preview available in your browser</AlertTitle>
                  <AlertDescription>
                    You can explore the full desktop interface, including task threads, workflow review, spreadsheet editing, and approval flows,
                    right now at <Link href="/desktop" className="font-medium underline">xelora.app/desktop</Link>.
                  </AlertDescription>
                </Alert>

                <div className="mt-6 flex flex-wrap gap-3">
                  {windowsRelease ? (
                    <Button variant="bright" asChild>
                      <a href={downloadUrl}>
                        <Download className="h-4 w-4" />
                        Download Xelora-Setup.exe
                      </a>
                    </Button>
                  ) : (
                    <Button variant="bright" disabled>
                      <Download className="h-4 w-4" />
                      Download coming soon
                    </Button>
                  )}
                  <Button variant="outline" asChild>
                    <Link href="/pricing">View plans</Link>
                  </Button>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {windowsRelease ? (
                    <>
                      <Badge variant="success">Stable version {windowsRelease.version}</Badge>
                      <Badge variant="outline">Windows 10+</Badge>
                      <Badge variant="outline">~{formatFileSize(windowsRelease.fileSizeMB)}</Badge>
                    </>
                  ) : (
                    <>
                      <Badge variant="success">Preview version 1.3.0</Badge>
                      <Badge variant="outline">Native installer coming soon</Badge>
                    </>
                  )}
                </div>
              </div>

              <MockWindow title="Xelora Desktop - browser preview" subtitle="No installation required">
                <div className="space-y-4 p-5">
                  <div className="rounded-lg border border-xelora-success bg-xelora-success-bg p-4 text-sm text-xelora-text-secondary">
                    The full desktop interface is running in your browser. Click Open Desktop Preview to use it now.
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Card className="p-4">
                      <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Preview system</p>
                      <p className="mt-1 text-sm text-xelora-text">Any modern browser - no install needed</p>
                    </Card>
                    <Card className="p-4">
                      <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Native installer</p>
                      <p className="mt-1 text-sm text-xelora-text">Windows 10+ - ~84 MB - Ready to download</p>
                    </Card>
                  </div>
                  <div className="rounded-lg border border-xelora-border p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-xelora-text">
                      <FileCheck2 className="h-4 w-4 text-xelora-green" />
                      v{windowsRelease?.version ?? '1.3.0'} includes
                    </div>
                    <ul className="mt-3 space-y-2 text-sm text-xelora-text-secondary">
                      {(windowsRelease?.releaseNotes ?? []).map((note) => (
                        <li key={note} className="flex gap-2">
                          <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-xelora-green" />
                          <span>{note}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Button className="w-full" variant="bright" asChild>
                      <a href={downloadUrl}>
                        <Download className="h-4 w-4" />
                        Download setup
                      </a>
                    </Button>
                    <Button className="w-full" variant="outline" asChild>
                      <Link href="/desktop">
                        <Monitor className="h-4 w-4" />
                        Open Desktop Preview
                      </Link>
                    </Button>
                  </div>
                </div>
              </MockWindow>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="border-xelora-green p-5 ring-1 ring-xelora-green">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-sm font-semibold text-xelora-text">Browser Preview</p>
                <Badge variant="success">Available now</Badge>
              </div>
              <p className="text-sm text-xelora-text-secondary">
                Experience the complete Xelora Desktop interface without installing anything.
              </p>
              <Button className="mt-4 w-full" variant="bright" asChild>
                <Link href="/desktop">
                  <Monitor className="h-4 w-4" />
                  Open Desktop Preview
                </Link>
              </Button>
            </Card>

            <Card className="p-5">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-sm font-semibold text-xelora-text">Windows</p>
                <Badge variant="success">Available now</Badge>
              </div>
              <p className="mt-2 text-sm text-xelora-text-secondary">
                Native Xelora-Setup.exe for Windows 10 and later. ~84 MB.
              </p>
              <Button className="mt-4 w-full" variant="bright" asChild>
                <a href={downloadUrl}>
                  <Download className="h-4 w-4" />
                  Download Xelora-Setup.exe
                </a>
              </Button>
              <p className="mt-3 text-xs text-xelora-text-muted">
                The button downloads the installer directly from {downloadUrl}.
              </p>
            </Card>

            <Card className="p-5 opacity-80">
              <div className="mb-1 flex items-center justify-between">
                <p className="text-sm font-semibold text-xelora-text">macOS &amp; Linux</p>
                <Badge variant="outline">Coming soon</Badge>
              </div>
              <p className="mt-2 text-sm text-xelora-text-secondary">
                macOS and Linux builds will follow the Windows release.
              </p>
              <Button className="mt-4 w-full" variant="outline" disabled>
                Coming soon
              </Button>
            </Card>
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h2 className="text-base font-semibold text-xelora-text">Setup steps</h2>
              <ol className="mt-3 space-y-2 text-sm text-xelora-text-secondary">
                <li>1. Download Xelora-Setup.exe from this page.</li>
                <li>2. Run the installer and follow the prompts.</li>
                <li>3. Sign in with your Xelora account credentials.</li>
                <li>4. Open a spreadsheet file to start your first task.</li>
              </ol>
            </Card>

            <Card className="p-5">
              <h2 className="text-base font-semibold text-xelora-text">Try the browser preview now</h2>
              <p className="mt-2 text-sm text-xelora-text-secondary">
                The Desktop Preview at <Link href="/desktop" className="text-xelora-info hover:underline">/desktop</Link> gives you
                the full experience: task threads, workflow review, spreadsheet editing, approval flows, and the command palette.
                Sign in first, then open the preview.
              </p>
              <Button variant="outline" className="mt-4" asChild>
                <Link href="/login">Sign in to access preview</Link>
              </Button>
            </Card>
          </div>
        </section>
      </main>
      <MarketingFooter />
    </>
  );
}
