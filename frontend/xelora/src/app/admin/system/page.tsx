import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockSystemServices } from '@/data/mock-admin';

export default function AdminSystemPage() {
  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="System status" description="Mock service health indicators." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {mockSystemServices.map((service) => (
          <Card key={service.name} className="p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-xelora-text">{service.name}</p>
              <Badge variant={service.status === 'operational' ? 'success' : service.status === 'degraded' ? 'warning' : 'info'}>{service.status}</Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
