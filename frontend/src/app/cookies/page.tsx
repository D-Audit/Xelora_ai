import type { Metadata } from 'next';
import { LegalPage, type LegalSection } from '@/components/legal/legal-page';
import { site } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Cookie Policy',
  description: `The cookies and browser storage ${site.name} uses.`,
};

const items = [
  { name: 'xelora_session', type: 'Cookie, essential', purpose: 'Keeps you signed in. It cannot be read by scripts on the page.', duration: 'Until you sign out, or up to 7 days' },
  { name: 'xelora_oauth_state', type: 'Cookie, essential', purpose: 'Protects Google sign-in against request forgery.', duration: '10 minutes' },
  { name: 'theme', type: 'Local storage', purpose: 'Remembers whether you chose the light or dark theme.', duration: 'Until you clear it' },
];

const sections: LegalSection[] = [
  {
    id: 'what',
    title: 'What we use',
    body: (
      <>
        <p>
          {site.name} uses only what it needs to work. We do not use advertising cookies, analytics cookies or third-party tracking.
        </p>
        <div className="overflow-x-auto rounded-xl border border-xelora-border">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="bg-xelora-bg-main text-xelora-text">
              <tr>
                <th scope="col" className="px-4 py-2.5 font-medium">Name</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Type</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Purpose</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Duration</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-xelora-border">
              {items.map((item) => (
                <tr key={item.name}>
                  <td className="px-4 py-2.5 font-mono text-xs text-xelora-text">{item.name}</td>
                  <td className="px-4 py-2.5">{item.type}</td>
                  <td className="px-4 py-2.5">{item.purpose}</td>
                  <td className="px-4 py-2.5">{item.duration}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    ),
  },
  {
    id: 'third-party',
    title: 'Third-party pages',
    body: (
      <p>
        When you pay, you are taken to Stripe’s checkout, and when you sign in with Google you use Google’s sign-in page. Those pages
        set their own cookies under their own policies.
      </p>
    ),
  },
  {
    id: 'control',
    title: 'Your choices',
    body: (
      <p>
        Because these cookies are essential, they do not need consent. You can block or delete cookies in your browser settings, but
        you will not be able to stay signed in to {site.name} without the session cookie.
      </p>
    ),
  },
];

export default function CookiesPage() {
  return (
    <LegalPage
      current="/cookies"
      title="Cookie Policy"
      intro={<p>This policy lists every cookie and browser storage item {site.name} uses, and why.</p>}
      sections={sections}
    />
  );
}
