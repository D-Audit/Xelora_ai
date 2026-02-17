import { Card } from '@/components/ui/card';
import { SectionHeading } from '@/components/site/section-heading';

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-xelora-bg-main">
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Legal"
          title="Terms of Service"
          description="Demo terms content for the Xelora frontend."
        />
        <Card className="mt-8 p-6 space-y-4">
          <p className="text-sm text-xelora-text-secondary">
            Xelora is provided as a mock frontend for product demonstration. No production service commitments are implied here.
          </p>
          <p className="text-sm text-xelora-text-secondary">
            Replace these terms with your legal copy before launch.
          </p>
        </Card>
      </div>
    </main>
  );
}
