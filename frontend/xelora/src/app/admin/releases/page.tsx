import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockAdminReleases } from '@/data/mock-admin';
import { formatDate, formatFileSize } from '@/lib/utils';

export default function AdminReleasesPage() {
  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Desktop releases" description="Track mock release notes and download counts." />
      <div className="space-y-4">
        {mockAdminReleases.map((release) => (
          <Card key={release.id} className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-xelora-text">{release.version}</p>
                <p className="text-sm text-xelora-text-secondary">{formatDate(release.releasedAt)} • {formatFileSize(release.fileSizeMB)}</p>
              </div>
              <Badge variant={release.status === 'stable' ? 'success' : 'outline'}>{release.status}</Badge>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
