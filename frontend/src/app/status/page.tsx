import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { SectionHeading } from '@/components/site/section-heading';

const services = [
  { name: 'Authentication', status: 'operational' },
  { name: 'Billing', status: 'operational' },
  { name: 'AI service', status: 'degraded' },
  { name: 'File processing', status: 'operational' },
  { name: 'Cloud storage', status: 'maintenance' },
  { name: 'Notifications', status: 'operational' },
] as const;

export default function StatusPage() {
  return (
    <main className="min-h-screen bg-xelora-bg-main">
      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <SectionHeading
          eyebrow="Status"
          title="Xelora service status"
          description="Mock operational updates for the web frontend. No live incident data is connected."
        />
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {services.map((service) => (
            <Card key={service.name} className="p-5">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-xelora-text">{service.name}</p>
                <Badge
                  variant={
                    service.status === 'operational'
                      ? 'success'
                      : service.status === 'degraded'
                        ? 'warning'
                        : 'info'
                  }
                >
                  {service.status}
                </Badge>
              </div>
              <p className="mt-2 text-sm text-xelora-text-secondary">Last checked a few moments ago.</p>
            </Card>
          ))}
        </div>
      </div>
    </main>
  );
}
