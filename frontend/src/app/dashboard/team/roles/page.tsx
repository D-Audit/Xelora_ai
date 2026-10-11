import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';

const roles = [
  { name: 'Owner', can: 'Full access, billing control, security and workspace management.' },
  { name: 'Administrator', can: 'Manage users, settings, and workspace policies.' },
  { name: 'Editor', can: 'Create and edit workflows, files, and templates.' },
  { name: 'Operator', can: 'Run approved workflows and review outputs.' },
  { name: 'Viewer', can: 'View content and track progress without editing access.' },
];

export default function TeamRolesPage() {
  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Team"
        title="Role matrix"
        description="A simple description of the permissions model used in the mock workspace."
      />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {roles.map((role) => (
          <Card key={role.name} className="p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-xelora-text">{role.name}</h2>
              <Badge variant="outline">{role.name}</Badge>
            </div>
            <p className="mt-3 text-sm text-xelora-text-secondary">{role.can}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
