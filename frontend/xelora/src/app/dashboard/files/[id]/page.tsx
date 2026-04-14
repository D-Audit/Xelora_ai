'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowDownToLine, FolderOpen, History, Share2, Workflow, ShieldAlert } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatePanel } from '@/components/site/state-panel';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { mockFiles, mockFileVersions } from '@/data/mock-files';
import { mockWorkflows } from '@/data/mock-workflows';
import { formatDate, formatFileSize, formatRelativeTime } from '@/lib/utils';

export default function FileDetailPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 450);
    return () => clearTimeout(timer);
  }, []);

  const file = useMemo(() => mockFiles.find((item) => item.id === params.id), [params.id]);
  const versions = useMemo(() => mockFileVersions.filter((item) => item.fileId === params.id), [params.id]);
  const relatedWorkflows = useMemo(() => mockWorkflows.filter((workflow) => workflow.compatibleFileStructure?.length), []);

  if (!loading && !file) {
    return (
      <StatePanel
        kind="empty"
        title="File not found"
        description="This mock workbook does not exist in the current dataset, but the data itself is safe."
        actionLabel="Back to files"
        onAction={() => window.location.assign('/dashboard/files')}
      />
    );
  }

  if (loading || !file) {
    return (
      <StatePanel
        kind="loading"
        title="Loading file details"
        description="Fetching the mock workbook metadata and version history."
      />
    );
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Files"
        title={file.name}
        description="Review the workbook metadata, version history, and related workflows."
        actions={
          <>
            <Button variant="outline" onClick={() => window.alert('Open in desktop is simulated.')}>
              <FolderOpen className="h-4 w-4" />
              Open in Desktop
            </Button>
            <Button variant="outline">
              <ArrowDownToLine className="h-4 w-4" />
              Download
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success">{file.status}</Badge>
            <Badge variant="outline">{file.type}</Badge>
            <Badge variant="outline">{formatFileSize(file.sizeMB)}</Badge>
          </div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Owner</dt>
              <dd className="mt-1 text-sm text-xelora-text">{file.ownerName}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Modified</dt>
              <dd className="mt-1 text-sm text-xelora-text">{formatDate(file.lastModifiedAt)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Rows</dt>
              <dd className="mt-1 text-sm text-xelora-text">{file.rowCount ?? 'Unknown'}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Columns</dt>
              <dd className="mt-1 text-sm text-xelora-text">{file.columnCount ?? 'Unknown'}</dd>
            </div>
          </dl>
          <div className="mt-5 rounded-lg border border-xelora-border bg-xelora-surface-2 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-xelora-text">
              <ShieldAlert className="h-4 w-4 text-xelora-green" />
              Processing history
            </div>
            <p className="mt-2 text-sm text-xelora-text-secondary">
              The workbook has been reviewed by Xelora workflows and can be restored from prior versions.
            </p>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-xelora-green" />
            <h2 className="text-base font-semibold text-xelora-text">Version history</h2>
          </div>
          <div className="mt-4 space-y-3">
            {versions.map((version) => (
              <div key={version.id} className="rounded-lg border border-xelora-border p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-xelora-text">Version {version.versionNumber}</p>
                    <p className="text-xs text-xelora-text-muted">{version.note}</p>
                  </div>
                  <Badge variant={version.isAutoSave ? 'info' : 'default'}>{version.isAutoSave ? 'Auto-save' : 'Manual'}</Badge>
                </div>
                <p className="mt-3 text-xs text-xelora-text-secondary">
                  Created by {version.createdBy} on {formatRelativeTime(version.createdAt)} • {formatFileSize(version.sizeMB)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <Workflow className="h-4 w-4 text-xelora-green" />
            <h2 className="text-base font-semibold text-xelora-text">Related workflows</h2>
          </div>
          <div className="mt-4 space-y-3">
            {relatedWorkflows.slice(0, 3).map((workflow) => (
              <div key={workflow.id} className="rounded-lg border border-xelora-border p-4">
                <p className="text-sm font-medium text-xelora-text">{workflow.name}</p>
                <p className="mt-1 text-sm text-xelora-text-secondary">{workflow.description}</p>
                <Button className="mt-3" size="sm" variant="outline" asChild>
                  <Link href={`/dashboard/workflows/${workflow.id}`}>View workflow</Link>
                </Button>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-2">
            <Share2 className="h-4 w-4 text-xelora-green" />
            <h2 className="text-base font-semibold text-xelora-text">Sharing settings</h2>
          </div>
          <div className="mt-4 space-y-3 text-sm text-xelora-text-secondary">
            <p>Shared with workspace members only.</p>
            <p>Cloud copy disabled until you enable sync for this file.</p>
            <p>All workbook changes remain reversible from version history.</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
