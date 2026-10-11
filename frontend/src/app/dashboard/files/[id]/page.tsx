'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft, ArrowDownToLine, FileSpreadsheet, History, Loader2,
  RefreshCw, Table2, Trash2, Upload, AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { StatePanel } from '@/components/site/state-panel';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import {
  deleteFileVersion, fileDownloadUrl, fileVersionDownloadUrl, getFile,
  reprocessFile, uploadFileVersion,
} from '@/services/workspace';
import type { FileDetail, FileSheet, FileVersionItem } from '@/services/workspace';
import { formatDate, formatFileSize, formatRelativeTime } from '@/lib/utils';

const statusVariant: Record<string, 'default' | 'success' | 'info' | 'warning' | 'error'> = {
  ready: 'default',
  processing: 'info',
  completed: 'success',
  needs_review: 'warning',
  failed: 'error',
  archived: 'default',
};

function displayDate(date: string | null) {
  return date ? formatDate(date) : 'Unknown';
}

function PreviewTable({ sheet }: { sheet: FileSheet }) {
  if (!sheet.headers.length && !sheet.sampleRows.length) {
    return <p className="text-sm text-xelora-text-secondary">This sheet has no rows to preview.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-xelora-border">
      <table className="w-full min-w-max text-left text-xs">
        <thead className="bg-xelora-surface-2 text-xelora-text-secondary">
          <tr>
            {sheet.headers.map((header, index) => <th key={`${header}-${index}`} className="whitespace-nowrap px-3 py-2 font-medium">{header || `Column ${index + 1}`}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-xelora-border bg-white text-xelora-text">
          {sheet.sampleRows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {sheet.headers.map((_, cellIndex) => <td key={cellIndex} className="max-w-52 truncate px-3 py-2">{row[cellIndex] || '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function FileDetailPage() {
  const params = useParams<{ id: string }>();
  const fileId = params.id;
  const [file, setFile] = useState<FileDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [deletingVersionId, setDeletingVersionId] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const details = await getFile(fileId);
      setFile(details);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load this file.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [fileId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (file?.status !== 'processing') return;
    const timer = window.setInterval(() => { void load(true); }, 1500);
    return () => window.clearInterval(timer);
  }, [file?.status, load]);

  const previewSheet = useMemo(() => file?.sheetSummary.sheets[0], [file]);

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const newVersion = event.target.files?.[0];
    if (!newVersion) return;
    setIsUploading(true);
    try {
      await uploadFileVersion(fileId, newVersion);
      toast.success('New version uploaded. Processing has started.');
      await load(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not upload the new version.');
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  const handleReprocess = async () => {
    setIsReprocessing(true);
    try {
      await reprocessFile(fileId);
      toast.success('Reprocessing started.');
      await load(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not reprocess the file.');
    } finally {
      setIsReprocessing(false);
    }
  };

  const handleDeleteVersion = async (version: FileVersionItem) => {
    if (!file || file.versions.length <= 1) return;
    if (!window.confirm(`Delete version ${version.versionNumber}? This cannot be undone.`)) return;
    setDeletingVersionId(version.id);
    try {
      await deleteFileVersion(fileId, version.id);
      toast.success(`Version ${version.versionNumber} deleted.`);
      await load(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not delete the version.');
    } finally {
      setDeletingVersionId(null);
    }
  };

  if (loading) {
    return <StatePanel kind="loading" title="Loading file details" description="Fetching the workbook metadata and version history." />;
  }

  if (error || !file) {
    return (
      <StatePanel
        kind={error?.toLowerCase().includes('not found') ? 'empty' : 'error'}
        title={error?.toLowerCase().includes('not found') ? 'File not found' : 'Could not load file'}
        description={error || 'This file is unavailable.'}
        actionLabel="Back to files"
        onAction={() => window.location.assign('/dashboard/files')}
      />
    );
  }

  const isProcessing = file.status === 'processing';
  const statusMessage = file.processingError || (isProcessing ? 'Xelora is extracting workbook metadata and a small preview.' : null);

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Files"
        title={file.name}
        description="Review workbook metadata, preview a safe sample, and manage immutable file versions."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link href="/dashboard/files"><ArrowLeft className="h-4 w-4" />All files</Link>
            </Button>
            <Button variant="outline" onClick={handleReprocess} disabled={isReprocessing || isProcessing}>
              {isReprocessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Reprocess
            </Button>
            <Button variant="outline" asChild>
              <a href={fileDownloadUrl(file.id)} target="_blank" rel="noreferrer"><ArrowDownToLine className="h-4 w-4" />Download</a>
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={statusVariant[file.status] ?? 'default'}>{file.status.replace('_', ' ')}</Badge>
            <Badge variant="outline">.{file.type}</Badge>
            <Badge variant="outline">{formatFileSize(file.sizeMB)}</Badge>
            <Badge variant="outline">Version {file.currentVersionNumber}</Badge>
          </div>
          <dl className="mt-5 grid gap-4 sm:grid-cols-2">
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Uploaded</dt><dd className="mt-1 text-sm text-xelora-text">{displayDate(file.uploadedAt)}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Last modified</dt><dd className="mt-1 text-sm text-xelora-text">{displayDate(file.lastModifiedAt)}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Rows</dt><dd className="mt-1 text-sm text-xelora-text">{file.rowCount ?? 'Not available'}</dd></div>
            <div><dt className="text-xs font-medium uppercase tracking-wide text-xelora-text-muted">Columns</dt><dd className="mt-1 text-sm text-xelora-text">{file.columnCount ?? 'Not available'}</dd></div>
          </dl>
          {statusMessage ? (
            <div className={`mt-5 flex gap-3 rounded-lg border p-4 ${file.status === 'failed' ? 'border-xelora-error bg-xelora-error-bg' : 'border-xelora-border bg-xelora-surface-2'}`}>
              {isProcessing ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-xelora-info" /> : <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-xelora-warning" />}
              <p className="text-sm text-xelora-text-secondary">{statusMessage}</p>
            </div>
          ) : null}
          <div className="mt-5 rounded-lg border border-xelora-border bg-xelora-surface-2 p-4 text-sm text-xelora-text-secondary">
            Your spreadsheet stays in private storage. The checksum and all stored versions are kept server-side and are never exposed as storage paths.
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2"><History className="h-4 w-4 text-xelora-green" /><h2 className="text-base font-semibold text-xelora-text">Version history</h2></div>
            <Button variant="outline" size="sm" asChild disabled={isUploading}>
              <label className="cursor-pointer">
                {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                Upload version
                <input type="file" className="hidden" accept=".xlsx,.xls,.csv,.ods,.tsv" onChange={handleUpload} disabled={isUploading} />
              </label>
            </Button>
          </div>
          <div className="mt-4 space-y-3">
            {file.versions.map((version) => (
              <div key={version.id} className="rounded-lg border border-xelora-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-xelora-text">Version {version.versionNumber}</p>
                    <p className="mt-1 text-xs text-xelora-text-muted">{version.name} · {formatFileSize(version.sizeMB)}</p>
                  </div>
                  <Badge variant={statusVariant[version.status] ?? 'default'}>{version.status.replace('_', ' ')}</Badge>
                </div>
                {version.processingError ? <p className="mt-2 text-xs text-xelora-warning">{version.processingError}</p> : null}
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-xelora-text-secondary">{version.createdAt ? `Uploaded ${formatRelativeTime(version.createdAt)}` : 'Upload time unavailable'}</p>
                  <div className="flex items-center gap-1">
                    <Button size="icon-sm" variant="ghost" asChild><a href={fileVersionDownloadUrl(file.id, version.id)} target="_blank" rel="noreferrer" aria-label={`Download version ${version.versionNumber}`}><ArrowDownToLine className="h-4 w-4" /></a></Button>
                    {file.versions.length > 1 ? <Button size="icon-sm" variant="ghost" className="text-xelora-error" onClick={() => void handleDeleteVersion(version)} disabled={deletingVersionId === version.id} aria-label={`Delete version ${version.versionNumber}`}>{deletingVersionId === version.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}</Button> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2"><Table2 className="h-4 w-4 text-xelora-green" /><h2 className="text-base font-semibold text-xelora-text">Workbook preview</h2></div>
          {file.sheetSummary.sheets.length ? <p className="text-xs text-xelora-text-muted">{file.sheetSummary.sheets.length} sheet{file.sheetSummary.sheets.length === 1 ? '' : 's'} detected</p> : null}
        </div>
        {previewSheet ? (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-xelora-text-secondary">
              <FileSpreadsheet className="h-4 w-4 text-xelora-green" />
              <span className="font-medium text-xelora-text">{previewSheet.name}</span>
              <span>{previewSheet.rowCount} rows</span><span>·</span><span>{previewSheet.columnCount} columns</span>
              {previewSheet.truncated ? <Badge variant="warning">Preview limited</Badge> : null}
            </div>
            <PreviewTable sheet={previewSheet} />
            {file.sheetSummary.sheets.length > 1 ? <p className="text-xs text-xelora-text-muted">Additional sheets: {file.sheetSummary.sheets.slice(1).map((sheet) => sheet.name).join(', ')}</p> : null}
          </div>
        ) : (
          <div className="mt-4 rounded-lg border border-dashed border-xelora-border p-6 text-center text-sm text-xelora-text-secondary">
            {isProcessing ? 'A preview will appear when processing finishes.' : 'A preview is not available for this file format.'}
          </div>
        )}
      </Card>
    </div>
  );
}
