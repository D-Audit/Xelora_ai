'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowDownToLine, FolderOpen, History, Workflow, ShieldCheck } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatePanel } from '@/components/site/state-panel';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { fileDownloadUrl, getFileById, getWorkflows, type FileItem, type WorkflowItem } from '@/services/workspace';
import { formatDate, formatFileSize } from '@/lib/utils';

export default function FileDetailPage() {
  const params = useParams<{ id: string }>();
  const [file, setFile] = useState<FileItem | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getFileById(params.id), getWorkflows()])
      .then(([detail, items]) => { setFile(detail.file); setWorkflows(items); })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load file.'))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <StatePanel kind="loading" title="Loading file details" description="Fetching workbook metadata from your workspace." />;
  if (!file || error) return <StatePanel kind="empty" title="File not found" description={error || 'This workbook does not exist.'} actionLabel="Back to files" onAction={() => window.location.assign('/dashboard/files')} />;

  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Files" title={file.name} description="Review the persisted workbook metadata and workflows available in your workspace." actions={<><Button variant="outline" onClick={() => window.location.assign('/dashboard/agent?new=1')}><FolderOpen className="h-4 w-4" />Open with Xelora</Button><Button variant="outline" asChild><a href={fileDownloadUrl(file.id)}><ArrowDownToLine className="h-4 w-4" />Download</a></Button></>} />
      <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-2"><Badge variant={file.status === 'failed' ? 'error' : file.status === 'processing' ? 'info' : 'success'}>{file.status}</Badge><Badge variant="outline">{file.type}</Badge><Badge variant="outline">{formatFileSize(file.sizeMB * 1024 * 1024)}</Badge></div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Uploaded</dt><dd className="mt-1 text-sm">{file.uploadedAt ? formatDate(file.uploadedAt) : 'Unknown'}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Modified</dt><dd className="mt-1 text-sm">{file.lastModifiedAt ? formatDate(file.lastModifiedAt) : 'Unknown'}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Rows</dt><dd className="mt-1 text-sm">{file.rowCount ?? 'Not analysed'}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Columns</dt><dd className="mt-1 text-sm">{file.columnCount ?? 'Not analysed'}</dd></div>
          </dl>
          <div className="mt-5 rounded-lg border border-xelora-border bg-xelora-surface-2 p-4"><div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck className="h-4 w-4 text-xelora-green" />Stored securely</div><p className="mt-2 text-sm text-xelora-text-secondary">This metadata comes directly from Xelora storage. No sample workbook information is shown.</p></div>
        </Card>
        <Card className="p-5"><div className="flex items-center gap-2"><History className="h-4 w-4 text-xelora-green" /><h2 className="font-semibold">Version history</h2></div><StatePanel kind="empty" title="No versions recorded" description="Version snapshots will appear here after backend version capture is enabled for this workbook." /></Card>
      </div>
      <Card className="p-5"><div className="flex items-center gap-2"><Workflow className="h-4 w-4 text-xelora-green" /><h2 className="font-semibold">Workspace workflows</h2></div><div className="mt-4 grid gap-3 md:grid-cols-2">{workflows.length ? workflows.slice(0,4).map((workflow) => <div key={workflow.id} className="rounded-lg border border-xelora-border p-4"><p className="font-medium">{workflow.name}</p><p className="mt-1 text-sm text-xelora-text-secondary">{workflow.description || 'No description provided.'}</p><Button className="mt-3" size="sm" variant="outline" asChild><Link href={`/dashboard/workflows/${workflow.id}`}>View workflow</Link></Button></div>) : <p className="text-sm text-xelora-text-muted">No workflows have been created yet.</p>}</div></Card>
    </div>
  );
}
