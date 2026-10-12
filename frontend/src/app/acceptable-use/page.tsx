import type { Metadata } from 'next';
import { Bullets, LegalPage, type LegalSection } from '@/components/legal/legal-page';
import { site } from '@/lib/site';

export const metadata: Metadata = {
  title: 'Acceptable Use Policy',
  description: `What you may and may not do with ${site.name}.`,
};

const sections: LegalSection[] = [
  {
    id: 'not-allowed',
    title: 'What is not allowed',
    body: (
      <>
        <p>You may not use {site.name} to:</p>
        <Bullets
          items={[
            'break any law, or help anyone else break one;',
            'process personal or confidential data you do not have the right to use;',
            'infringe anyone’s intellectual property, privacy or other rights;',
            'create or spread malware, phishing, spam or fraudulent material;',
            'harass, threaten or harm others, or generate content that sexualises minors;',
            'make decisions with legal or similarly significant effects on people, such as credit, employment or housing decisions, without meaningful human review.',
          ]}
        />
      </>
    ),
  },
  {
    id: 'service',
    title: 'Protecting the Service',
    body: (
      <>
        <p>You may not:</p>
        <Bullets
          items={[
            'try to access accounts, data or systems that are not yours, or test our security without written permission;',
            'get around usage limits, plan restrictions or security controls;',
            'interfere with or overload the Service, or use bots to access it in ways we have not allowed;',
            'copy, resell or offer the Service to others without our written agreement;',
            'reverse engineer the Service or Xelora Desktop, except where the law allows it;',
            'use the Service to build a competing product, or to extract our models, prompts or data.',
          ]}
        />
      </>
    ),
  },
  {
    id: 'ai',
    title: 'Responsible use of AI',
    body: (
      <Bullets
        items={[
          'Check results before you rely on them, especially for financial, legal or other important work.',
          'Do not present AI-generated content as reviewed by a professional when it was not.',
          'Do not try to make the AI ignore its safety rules or act against these policies.',
        ]}
      />
    ),
  },
  {
    id: 'enforcement',
    title: 'Enforcement and reporting',
    body: (
      <>
        <p>
          If we believe this policy has been broken, we may remove content, limit features, or suspend or close the account involved.
          Where appropriate we will tell you first and explain why.
        </p>
        <p>
          To report misuse, email <a href={`mailto:${site.contactEmail}`} className="text-xelora-green hover:underline">{site.contactEmail}</a>.
        </p>
      </>
    ),
  },
];

export default function AcceptableUsePage() {
  return (
    <LegalPage
      current="/acceptable-use"
      title="Acceptable Use Policy"
      intro={<p>This policy is part of our Terms of Service. It keeps {site.name} safe and useful for everyone.</p>}
      sections={sections}
    />
  );
}
