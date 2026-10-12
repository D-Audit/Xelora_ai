import type { Metadata } from 'next';
import Link from 'next/link';
import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { site } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Security',
  description: 'How Xelora protects your account, your files and your spreadsheets.',
};

const sections = [
  {
    title: 'Where your data lives',
    points: [
      'Workbooks you open on your PC stay on your PC. Xelora Desktop edits them in your own copy of Excel.',
      'Files you upload, files Xelora saves to your workspace, and your conversations are stored in your Xelora account with our cloud hosting providers.',
      'Your files and conversations are only visible to your account. You can delete any of them at any time.',
    ],
  },
  {
    title: 'How AI requests are handled',
    points: [
      'To answer a request, Xelora sends your message, the recent conversation and the workbook content it needs to our AI provider.',
      'The keys for our AI providers are held on our servers only. Xelora Desktop never stores them; it reaches the models through our API with its own device token.',
      'Text from web pages and files is treated as data, never as instructions to Xelora.',
    ],
  },
  {
    title: 'Xelora Desktop',
    points: [
      'Each installation gets its own device token. You can see your connected devices and revoke any of them from the Devices page.',
      'The desktop app can only use the AI models while one of your tasks is running.',
      'Workbook changes are checked after they are made, and larger or destructive changes wait for your confirmation.',
    ],
  },
  {
    title: 'Account security',
    points: [
      'Passwords are stored only as salted bcrypt hashes. We never see or store your password in plain text.',
      'Your session is kept in a secure, HTTP-only cookie that scripts on the page cannot read.',
      'You can sign in with Google instead of a password.',
      'All traffic between your browser, the desktop app and our servers is encrypted with HTTPS.',
    ],
  },
  {
    title: 'Web access',
    points: [
      'When Xelora reads a web page, requests to private, local or internal network addresses are blocked, and downloads are size-limited.',
      'Search results and pages are shown with their source so you can check them yourself.',
    ],
  },
];

export default function SecurityPage() {
  return (
    <>
      <MarketingNav />
      <main className="bg-white">
        <div className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
          <p className="text-sm font-medium text-xelora-green">Security</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight text-xelora-text">How we protect your work</h1>
          <p className="mt-5 text-lg leading-relaxed text-xelora-text-secondary">
            Xelora works with your spreadsheets, so we keep its design simple: your workbooks are edited on your own PC,
            your account data is private to you, and nothing changes in Excel unless you ask.
          </p>

          <div className="mt-14 space-y-12">
            {sections.map((section) => (
              <section key={section.title}>
                <h2 className="text-xl font-semibold text-xelora-text">{section.title}</h2>
                <ul className="mt-4 space-y-3">
                  {section.points.map((point) => (
                    <li key={point} className="flex gap-3 text-[15px] leading-relaxed text-xelora-text-secondary">
                      <span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-xelora-text-muted" aria-hidden="true" />
                      {point}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>

          <div className="mt-16 rounded-2xl border border-xelora-border bg-xelora-bg-main p-6">
            <h2 className="text-base font-semibold text-xelora-text">Report a security issue</h2>
            <p className="mt-2 text-sm leading-relaxed text-xelora-text-secondary">
              If you believe you have found a vulnerability, email{' '}
              <a href={`mailto:${site.contactEmail}`} className="text-xelora-green hover:underline">{site.contactEmail}</a>{' '}
              with the details. Please give us a reasonable time to fix it before sharing it publicly. See also our{' '}
              <Link href="/privacy" className="text-xelora-green hover:underline">Privacy Policy</Link>.
            </p>
          </div>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
