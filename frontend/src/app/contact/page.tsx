'use client';

import Link from 'next/link';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SectionHeading } from '@/components/site/section-heading';

export default function ContactPage() {
  return (
    <main className="min-h-screen bg-xelora-bg-main">
      <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Contact"
          title="Talk to the Xelora team"
          description="This frontend uses simple contact details for demo purposes only."
        />
        <Card className="mt-8 p-6">
          <p className="text-sm text-xelora-text-secondary">
            Email us at <span className="font-medium text-xelora-text">hello@xelora.app</span> or use the support area in the dashboard for product help.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/register">Start free trial</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard/help">Open help centre</Link>
            </Button>
          </div>
        </Card>
      </div>
    </main>
  );
}
