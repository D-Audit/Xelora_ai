import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockTemplates } from '@/data/mock-templates';

export default function AdminTemplatesPage() {
  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Template moderation" description="Approve and feature mock templates." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {mockTemplates.slice(0, 6).map((template) => (
          <Card key={template.id} className="p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-xelora-text">{template.name}</p>
              <Badge variant="outline">{template.category}</Badge>
            </div>
            <p className="mt-3 text-sm text-xelora-text-secondary">{template.description}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
