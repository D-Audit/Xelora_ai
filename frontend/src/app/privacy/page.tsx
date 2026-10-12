import type { Metadata } from 'next';
import Link from 'next/link';
import { Bullets, LegalPage, type LegalSection } from '@/components/legal/legal-page';
import { site } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: `How ${site.name} collects, uses and protects your information.`,
};

const sections: LegalSection[] = [
  {
    id: 'who',
    title: 'Who we are',
    body: (
      <p>
        {site.legalName} provides {site.name} and is responsible for the personal information described in this policy. You can
        contact us about privacy at <a href={`mailto:${site.privacyEmail}`} className="text-xelora-green hover:underline">{site.privacyEmail}</a>.
      </p>
    ),
  },
  {
    id: 'collect',
    title: 'Information we collect',
    body: (
      <>
        <p><span className="font-medium text-xelora-text">Account information.</span> Your name, email address and a hashed version of your password. If you sign in with Google, we receive your name and verified email address from Google.</p>
        <p><span className="font-medium text-xelora-text">Your content.</span> The messages you send, your saved conversations, files you upload or that {site.name} saves to your workspace, and the spreadsheet content {site.name} reads while carrying out a task you asked for.</p>
        <p><span className="font-medium text-xelora-text">Task history and memory.</span> A record of the tasks you run, the actions taken and their results, and patterns {site.name} learns from them so it can handle similar requests better for you.</p>
        <p><span className="font-medium text-xelora-text">Device information.</span> For each Xelora Desktop installation: its name, the time it last connected and a device token.</p>
        <p><span className="font-medium text-xelora-text">Billing information.</span> Your plan, subscription status and invoices. Card payments are handled by Stripe; we never receive your full card number.</p>
        <p><span className="font-medium text-xelora-text">Usage and technical data.</span> How many AI actions and workflow runs you use, plus server logs such as IP address, browser type and error details, which we use to run and secure the Service.</p>
      </>
    ),
  },
  {
    id: 'use',
    title: 'How we use your information',
    body: (
      <Bullets
        items={[
          'To provide the Service: answer your questions, carry out the tasks you request, keep your conversations and files, and sync files with Xelora Desktop.',
          'To remember context, so follow-up requests and similar tasks work better for you.',
          'To manage your subscription, usage limits and payments.',
          'To keep the Service secure, prevent abuse and fix problems.',
          'To contact you about your account, security, billing and important changes.',
          'To understand overall use of the Service and improve it, using aggregated information wherever possible.',
          'To meet legal obligations.',
        ]}
      />
    ),
  },
  {
    id: 'ai',
    title: 'AI processing',
    body: (
      <>
        <p>
          To respond to a request, {site.name} sends the relevant content (your message, recent conversation and any spreadsheet data
          or web content needed for the task) to our AI model providers, currently Google (Gemini) and Anthropic (Claude). When a
          question needs current information, the search query is sent to a web search provider.
        </p>
        <p>
          These providers process the content to generate a response for you, under their terms for business API use. {site.name} does
          not use your content to train AI models.
        </p>
      </>
    ),
  },
  {
    id: 'legal-bases',
    title: 'Legal bases',
    body: (
      <>
        <p>Where data protection laws such as the GDPR apply, we rely on:</p>
        <Bullets
          items={[
            'Contract: to provide the Service you signed up for.',
            'Legitimate interests: to secure, maintain and improve the Service, in ways that do not override your rights.',
            'Legal obligation: to keep records such as invoices.',
            'Consent: where we ask for it. You can withdraw consent at any time.',
          ]}
        />
      </>
    ),
  },
  {
    id: 'sharing',
    title: 'Who we share information with',
    body: (
      <>
        <p>We do not sell your personal information. We share it only with:</p>
        <Bullets
          items={[
            'Service providers who run parts of the Service for us: cloud hosting and databases, file storage, AI model providers, web search, payments (Stripe), sign-in (Google) and email delivery. They may use your information only to provide their services to us.',
            'Members of your team, for content you share with them in a team workspace.',
            'Authorities, when required by law or to protect the rights, safety and security of our users, the public or us.',
            'A buyer or successor, if our business is merged or sold. We will tell you before your information becomes subject to a different policy.',
          ]}
        />
        <p>A current list of our service providers is available on request.</p>
      </>
    ),
  },
  {
    id: 'transfers',
    title: 'International transfers',
    body: (
      <p>
        Our providers may process information in countries other than yours, including the United States. Where required, we use
        safeguards such as standard contractual clauses to protect information transferred abroad.
      </p>
    ),
  },
  {
    id: 'retention',
    title: 'How long we keep information',
    body: (
      <Bullets
        items={[
          'Account information is kept while your account is open.',
          'Conversations and files are kept until you delete them or close your account.',
          'Task history and learned patterns are limited in size, and older entries are removed automatically.',
          'Server logs are kept for a limited period for security and troubleshooting.',
          'When you close your account we delete or anonymise your information within 30 days, except where we must keep it longer by law (for example invoices).',
        ]}
      />
    ),
  },
  {
    id: 'rights',
    title: 'Your rights and choices',
    body: (
      <>
        <p>Depending on where you live, you may have the right to:</p>
        <Bullets
          items={[
            'access the personal information we hold about you and get a copy of it;',
            'correct information that is wrong;',
            'delete your information;',
            'object to or restrict some processing;',
            'receive your information in a portable format; and',
            'withdraw consent where we rely on it.',
          ]}
        />
        <p>
          You can delete conversations and files yourself in the app. For other requests, email{' '}
          <a href={`mailto:${site.privacyEmail}`} className="text-xelora-green hover:underline">{site.privacyEmail}</a>. We will
          respond within 30 days. You may also complain to your local data protection authority.
        </p>
      </>
    ),
  },
  {
    id: 'security',
    title: 'Security',
    body: (
      <p>
        We use technical and organisational measures to protect your information, including encryption in transit, hashed passwords,
        secure session cookies and per-device tokens. No system is perfectly secure, but we work to protect your information and will
        notify you of a breach where the law requires. Read more on our{' '}
        <Link href="/security" className="text-xelora-green hover:underline">Security page</Link>.
      </p>
    ),
  },
  {
    id: 'children',
    title: 'Children',
    body: <p>{site.name} is not intended for people under 18, and we do not knowingly collect information from children.</p>,
  },
  {
    id: 'cookies',
    title: 'Cookies',
    body: (
      <p>
        We use only the cookies needed to keep you signed in and to protect sign-in. We do not use advertising or analytics cookies.
        See our <Link href="/cookies" className="text-xelora-green hover:underline">Cookie Policy</Link>.
      </p>
    ),
  },
  {
    id: 'changes',
    title: 'Changes to this policy',
    body: (
      <p>
        We will post any changes on this page and update the date at the top. For significant changes we will also notify you by email
        or in the app.
      </p>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      current="/privacy"
      title="Privacy Policy"
      intro={<p>This policy explains what information {site.name} collects, why, and the choices you have. We have kept it as plain as we can.</p>}
      sections={sections}
    />
  );
}
