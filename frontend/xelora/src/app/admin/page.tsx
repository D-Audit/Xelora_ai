import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockAdminStats } from '@/data/mock-admin';

export default function AdminPage() {
  const cards = [
    ['Total users', mockAdminStats.totalUsers],
    ['Active subscriptions', mockAdminStats.activeSubscriptions],
    ['Trial conversions', `${mockAdminStats.trialConversions}%`],
    ['MRR', `$${mockAdminStats.monthlyRecurringRevenue.toLocaleString()}`],
    ['AI usage today', mockAdminStats.aiActionsToday],
    ['Workflow runs today', mockAdminStats.workflowRunsToday],
  ];

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Admin"
        title="Platform overview"
        description="High-level mock metrics for the Xelora admin surface."
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map(([label, value]) => (
          <Card key={String(label)} className="p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-xelora-text">{String(value)}</p>
          </Card>
        ))}
      </div>
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-xelora-text">System snapshot</h2>
          <Badge variant="success">Healthy enough for demo</Badge>
        </div>
      </Card>
    </div>
  );
}
