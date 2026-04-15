'use client';

import { useMemo, useState } from 'react';
import { Search, MessageSquareMore, LifeBuoy, BookOpen, Wrench } from 'lucide-react';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

const helpTopics = [
  { title: 'Getting started', description: 'Create an account, choose a plan, and open your first workbook.' },
  { title: 'Billing', description: 'Change plans, review invoices, and understand usage limits.' },
  { title: 'Desktop installation', description: 'Download and install Xelora Desktop for local processing.' },
  { title: 'Workflows', description: 'Build, edit, duplicate, and run automation workflows.' },
  { title: 'Files', description: 'Upload, organise, version, and share spreadsheet files.' },
  { title: 'Privacy and security', description: 'Understand local processing, retention, and account security.' },
  { title: 'Troubleshooting', description: 'Solve common installation and workflow issues.' },
];

export default function HelpPage() {
  const [search, setSearch] = useState('');
  const filtered = useMemo(
    () => helpTopics.filter((topic) => `${topic.title} ${topic.description}`.toLowerCase().includes(search.toLowerCase())),
    [search]
  );

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Help"
        title="Help centre"
        description="Search the mock help content or jump to a topic area."
      />
      <Card className="p-4">
        <div className="relative max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search help" className="pl-9" />
        </div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {filtered.map((topic) => (
          <Card key={topic.title} className="p-5">
            <h2 className="text-base font-semibold text-xelora-text">{topic.title}</h2>
            <p className="mt-2 text-sm text-xelora-text-secondary">{topic.description}</p>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {[
          { label: 'Contact support', icon: MessageSquareMore },
          { label: 'Getting started', icon: BookOpen },
          { label: 'Troubleshooting', icon: Wrench },
          { label: 'Help centre', icon: LifeBuoy },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.label} className="p-5 text-center">
              <Icon className="mx-auto h-5 w-5 text-xelora-green" />
              <p className="mt-3 text-sm font-medium text-xelora-text">{item.label}</p>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
