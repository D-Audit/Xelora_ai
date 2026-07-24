import { Card } from '@/components/ui/card';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockAdminStats } from '@/data/mock-admin';

export default function AdminUsagePage() {
  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Platform usage" description="Mock platform usage summary." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ['AI actions', mockAdminStats.aiActionsToday],
          ['Workflow runs', mockAdminStats.workflowRunsToday],
          ['Storage GB', mockAdminStats.totalStorageGB],
          ['Failed ops', mockAdminStats.failedOperationsToday],
        ].map(([label, value]) => (
          <Card key={String(label)} className="p-5">
            <p className="text-xs uppercase tracking-wide text-xelora-text-muted">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-xelora-text">{String(value)}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
