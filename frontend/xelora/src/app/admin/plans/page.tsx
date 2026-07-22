'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockAdminPlanRows } from '@/data/mock-admin';
import { toast } from 'sonner';

export default function AdminPlansPage() {

  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Plan management" description="Edit mock plan prices and limits." />
      <div className="space-y-4">
        {mockAdminPlanRows.map((row) => (
          <Card key={row.plan} className="grid gap-4 p-5 md:grid-cols-4">
            <Input defaultValue={String(row.plan)} />
            <Input defaultValue={String(row.monthlyPrice)} />
            <Input defaultValue={String(row.annualPrice)} />
            <Button onClick={() => toast.success(`Updated ${row.plan}.`)}>
              Save
            </Button>
          </Card>
        ))}
      </div>
    </div>
  );
}
