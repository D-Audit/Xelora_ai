import { Card } from '@/components/ui/card';
import { SectionHeading } from '@/components/site/section-heading';

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-xelora-bg-main">
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Legal"
          title="Privacy Policy"
          description="Demo privacy content for the Xelora frontend."
        />
        <Card className="mt-8 p-6 space-y-4">
          <p className="text-sm text-xelora-text-secondary">
            Xelora keeps spreadsheet automation transparent and user-controlled. Files are only uploaded when the user chooses cloud processing or sync.
          </p>
          <p className="text-sm text-xelora-text-secondary">
            This frontend does not collect real personal data. Replace this page with production legal text when the backend is connected.
          </p>
        </Card>
      </div>
    </main>
  );
}
