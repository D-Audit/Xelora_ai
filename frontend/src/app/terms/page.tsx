import type { Metadata } from 'next';
import Link from 'next/link';
import { Bullets, LegalPage, type LegalSection } from '@/components/legal/legal-page';
import { site } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: `The terms that apply when you use ${site.name}.`,
};

const governingLaw = site.governingLaw
  ? `These Terms are governed by the laws of ${site.governingLaw}, without regard to its conflict-of-law rules. The courts of ${site.governingLaw} have exclusive jurisdiction over any dispute, except where the law of your country gives you the right to bring proceedings where you live.`
  : `These Terms are governed by the laws of the country in which ${site.legalName} is established, without regard to conflict-of-law rules. Nothing in these Terms removes rights you have under the consumer protection laws of the country where you live.`;

const sections: LegalSection[] = [
  {
    id: 'agreement',
    title: 'Agreement to these Terms',
    body: (
      <>
        <p>
          These Terms of Service (&ldquo;Terms&rdquo;) are an agreement between you and {site.legalName} (&ldquo;{site.name}&rdquo;,
          &ldquo;we&rdquo;, &ldquo;us&rdquo;). They apply to the {site.name} website, web application, Xelora Desktop and any related
          services (together, the &ldquo;Service&rdquo;).
        </p>
        <p>
          By creating an account or using the Service you agree to these Terms, our{' '}
          <Link href="/privacy" className="text-xelora-green hover:underline">Privacy Policy</Link> and our{' '}
          <Link href="/acceptable-use" className="text-xelora-green hover:underline">Acceptable Use Policy</Link>. If you use the
          Service for an organisation, you confirm that you are authorised to accept these Terms on its behalf.
        </p>
      </>
    ),
  },
  {
    id: 'service',
    title: 'The Service',
    body: (
      <>
        <p>
          {site.name} is an AI assistant for spreadsheet work. You describe what you need; {site.name} answers questions and, through
          Xelora Desktop, carries out tasks in Microsoft Excel on your computer. Workbook tasks need a Windows PC with Microsoft
          Excel installed, which you obtain and license separately.
        </p>
        <p>
          We work continuously to improve the Service and may add, change or remove features. If we remove a feature that is
          material to a paid plan, we will tell you in advance where reasonably possible.
        </p>
      </>
    ),
  },
  {
    id: 'accounts',
    title: 'Your account',
    body: (
      <Bullets
        items={[
          'You must be at least 18 years old, or the age of legal majority where you live, to create an account.',
          'Give accurate information and keep it up to date.',
          'Keep your password and devices secure. You are responsible for activity under your account.',
          `Tell us promptly at ${site.contactEmail} if you suspect unauthorised use of your account.`,
          'An account is for one person. Team plans let you add members within your plan’s limits.',
        ]}
      />
    ),
  },
  {
    id: 'plans',
    title: 'Free trial, plans and payment',
    body: (
      <>
        <p>
          New accounts start with a {site.trialDays}-day free trial with the limits shown on our{' '}
          <Link href="/pricing" className="text-xelora-green hover:underline">pricing page</Link>. To keep using the Service after
          the trial, choose a paid plan.
        </p>
        <Bullets
          items={[
            'Paid plans are billed in advance, monthly or yearly, through our payment processor Stripe. We do not store your full card details.',
            'Subscriptions renew automatically until you cancel. You can cancel at any time in Billing; cancellation takes effect at the end of the current billing period.',
            'Each plan includes usage limits, such as AI actions and file size. When a limit is reached, the related features pause until the next period or until you upgrade.',
            'Prices exclude taxes unless stated. You are responsible for applicable taxes.',
            'We may change prices with at least 30 days’ notice. Changes apply from your next billing period after the notice.',
            'Fees already paid are not refundable, except where required by law or where we state otherwise.',
          ]}
        />
      </>
    ),
  },
  {
    id: 'content',
    title: 'Your content',
    body: (
      <>
        <p>
          &ldquo;Your content&rdquo; means the messages you send, the files you upload and the spreadsheet data {site.name} reads or
          produces for you. You keep all rights to your content.
        </p>
        <p>
          You give us a limited permission to host, copy, process and transmit your content only as needed to provide, secure and
          support the Service for you, including sending it to the AI and search providers described in our Privacy Policy. We do
          not sell your content.
        </p>
        <p>You confirm that you have the rights needed to use your content with the Service.</p>
      </>
    ),
  },
  {
    id: 'ai',
    title: 'AI results and your responsibility',
    body: (
      <>
        <p>
          {site.name} uses artificial intelligence. Answers and spreadsheet changes can be incomplete or wrong, and web sources can
          be out of date. {site.name} checks workbook changes it makes, but these checks reduce errors rather than remove them.
        </p>
        <Bullets
          items={[
            'Review results before relying on them, especially for financial, legal, tax, medical or other important decisions.',
            `${site.name} changes workbooks when you ask it to, which can include editing or deleting data. Keep backups of important files.`,
            'The Service does not give professional advice. You remain responsible for decisions you make using it.',
          ]}
        />
      </>
    ),
  },
  {
    id: 'desktop',
    title: 'Xelora Desktop',
    body: (
      <>
        <p>
          We grant you a personal, non-exclusive, non-transferable and revocable licence to install and use Xelora Desktop on
          devices you own or control, for use with the Service and within your plan’s device limit.
        </p>
        <p>
          Xelora Desktop updates itself automatically. You may not copy, modify, distribute, sell or reverse engineer it, except to
          the extent the law allows this despite these Terms. Each installation uses a device token that you can revoke at any
          time from the Devices page.
        </p>
      </>
    ),
  },
  {
    id: 'acceptable-use',
    title: 'Acceptable use',
    body: (
      <p>
        You must follow our <Link href="/acceptable-use" className="text-xelora-green hover:underline">Acceptable Use Policy</Link>.
        We may limit, suspend or remove access to the Service if you break it.
      </p>
    ),
  },
  {
    id: 'third-parties',
    title: 'Third-party services',
    body: (
      <>
        <p>
          The Service works with products and services we do not control, including Microsoft Excel, Google sign-in, Stripe, AI model
          providers and websites found through search. Their own terms apply to your use of them, and we are not responsible for them.
        </p>
        <p>
          Microsoft and Excel are trademarks of the Microsoft group of companies. {site.name} is not affiliated with, sponsored by or
          endorsed by Microsoft.
        </p>
      </>
    ),
  },
  {
    id: 'feedback',
    title: 'Feedback',
    body: <p>If you send us ideas or feedback, we may use them to improve the Service without any obligation to you.</p>,
  },
  {
    id: 'termination',
    title: 'Suspension and termination',
    body: (
      <>
        <p>
          You can stop using the Service and cancel your subscription at any time. To close your account and delete its data, email{' '}
          {site.contactEmail} from the address on your account.
        </p>
        <p>
          We may suspend or end your access if you seriously or repeatedly break these Terms, if your use creates a security or legal
          risk, or if required by law. Where reasonable, we will tell you first and give you a chance to fix the problem. After your
          account ends we may delete your content, so download anything you want to keep.
        </p>
      </>
    ),
  },
  {
    id: 'disclaimers',
    title: 'Disclaimers',
    body: (
      <p>
        The Service is provided &ldquo;as is&rdquo; and &ldquo;as available&rdquo;. To the extent permitted by law, we make no warranties
        beyond those stated in these Terms, including implied warranties of merchantability, fitness for a particular purpose and
        non-infringement. We do not promise that the Service will be uninterrupted or error-free.
      </p>
    ),
  },
  {
    id: 'liability',
    title: 'Limitation of liability',
    body: (
      <>
        <p>
          To the extent permitted by law, {site.legalName} will not be liable for indirect, incidental, special, consequential or
          punitive damages, or for lost profits, revenue or data, arising from your use of the Service.
        </p>
        <p>
          Our total liability for all claims relating to the Service is limited to the greater of the amount you paid us in the 12
          months before the claim arose, or USD 100.
        </p>
        <p>
          Nothing in these Terms limits liability that cannot be limited by law, such as liability for fraud or for death or personal
          injury caused by negligence.
        </p>
      </>
    ),
  },
  {
    id: 'indemnity',
    title: 'Indemnity',
    body: (
      <p>
        If you use the Service for a business, you agree to compensate {site.legalName} for reasonable losses and costs arising from
        claims by third parties caused by your content or by your breach of these Terms.
      </p>
    ),
  },
  {
    id: 'changes',
    title: 'Changes to these Terms',
    body: (
      <p>
        We may update these Terms. For material changes we will notify you by email or in the app at least 14 days before they take
        effect. If you keep using the Service after that, the updated Terms apply. If you do not agree, cancel before they take effect.
      </p>
    ),
  },
  {
    id: 'law',
    title: 'Governing law',
    body: <p>{governingLaw}</p>,
  },
  {
    id: 'general',
    title: 'General',
    body: (
      <Bullets
        items={[
          'These Terms and the policies they refer to are the whole agreement between you and us about the Service.',
          'If any part of these Terms is found unenforceable, the rest stays in effect.',
          'If we do not enforce a right straight away, we do not give it up.',
          'You may not transfer these Terms without our consent. We may transfer them as part of a merger, acquisition or sale of assets, with notice to you.',
        ]}
      />
    ),
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      current="/terms"
      title="Terms of Service"
      intro={<p>Please read these Terms carefully. They explain your rights and responsibilities when you use {site.name}.</p>}
      sections={sections}
    />
  );
}
