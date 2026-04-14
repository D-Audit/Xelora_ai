'use client';

import { useEffect, useMemo, useState } from 'react';
import type { ChangeEvent } from 'react';
import {
  Grid2X2, List, Search, Upload, Download, MoreHorizontal, Trash2,
  FileSpreadsheet, Loader2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getFiles, uploadFile, deleteFile, fileDownloadUrl } from '@/services/workspace';
import type { FileItem } from '@/services/workspace';
import { formatFileSize, formatRelativeTime } from '@/lib/utils';

const statusVariant: Record<string, 'default' | 'success' | 'info' | 'warning' | 'error'> = {
  ready: 'default',
  processing: 'info',
  completed: 'success',
  needs_review: 'warning',
  failed: 'error',
  archived: 'default',
};

const typeFilters = ['all', 'xlsx', 'csv', 'ods', 'xls', 'tsv'] as const;

export default function DashboardFilesPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [type, setType] = useState<(typeof typeFilters)[number]>('all');
  const [gridView, setGridView] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const load = () => {
    setLoading(true);
    getFiles()
      .then(setFiles)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load files.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const filteredFiles = useMemo(() => {
    return files
      .filter((file) => {
        const haystack = `${file.name} ${file.type} ${file.status}`.toLowerCase();
        const matchesSearch = haystack.includes(search.toLowerCase());
        const matchesType = type === 'all' || file.type === type;
        return matchesSearch && matchesType;
      })
      .sort((a, b) => new Date(b.lastModifiedAt ?? 0).getTime() - new Date(a.lastModifiedAt ?? 0).getTime());
  }, [files, search, type]);

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      const record = await uploadFile(file);
      setFiles((current) => [record, ...current]);
      toast.success(`${file.name} uploaded successfully.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setIsUploading(false);
      event.target.value = '';
    }
  };

  const handleDelete = async (file: FileItem) => {
    try {
      await deleteFile(file.id);
      setFiles((current) => current.filter((f) => f.id !== file.id));
      toast.success(`${file.name} deleted.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not delete file.');
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Files"
        title="Manage spreadsheet files"
        description="Upload, search, and manage the spreadsheet files stored with your Xelora account."
        actions={
          <Button variant="outline" asChild disabled={isUploading}>
            <label className="cursor-pointer">
              {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              Upload spreadsheet
              <input type="file" className="hidden" accept=".xlsx,.xls,.csv,.ods,.tsv" onChange={handleUpload} disabled={isUploading} />
            </label>
          </Button>
        }
      />

      <Card className="p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full lg:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search files" className="pl-9" />
          </div>
          <div className="flex flex-wrap gap-2">
            {typeFilters.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setType(item)}
                className={`rounded-md border px-3 py-2 text-xs font-medium capitalize transition-colors ${
                  type === item ? 'border-xelora-green bg-xelora-success-bg text-xelora-success' : 'border-xelora-border bg-white text-xelora-text-secondary hover:bg-xelora-surface-2'
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <Button variant={gridView ? 'outline' : 'secondary'} size="sm" onClick={() => setGridView(false)}>
              <List className="h-4 w-4" /> List
            </Button>
            <Button variant={gridView ? 'secondary' : 'outline'} size="sm" onClick={() => setGridView(true)}>
              <Grid2X2 className="h-4 w-4" /> Grid
            </Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <StatePanel kind="loading" title="Loading files" description="Fetching your files." />
      ) : filteredFiles.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No files yet"
          description="Upload a spreadsheet to get started."
          actionLabel="Clear filters"
          onAction={() => { setSearch(''); setType('all'); }}
        />
      ) : gridView ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredFiles.map((file) => (
            <Card key={file.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                    <FileSpreadsheet className="h-5 w-5 text-xelora-green" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-xelora-text">{file.name}</h3>
                    <p className="text-xs text-xelora-text-muted">{formatFileSize(file.sizeMB)}</p>
                  </div>
                </div>
                <Badge variant={statusVariant[file.status] ?? 'default'}>{file.status}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-xelora-text-secondary">
                <div>Type: {file.type}</div>
                <div>Modified: {file.lastModifiedAt ? formatRelativeTime(file.lastModifiedAt) : '—'}</div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" asChild>
                  <a href={fileDownloadUrl(file.id)} target="_blank" rel="noreferrer">
                    <Download className="h-4 w-4" /> Download
                  </a>
                </Button>
                <Button size="sm" variant="ghost" className="text-xelora-error" onClick={() => handleDelete(file)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-xelora-surface-2">
                <tr className="border-b border-xelora-border text-left">
                  <th className="px-5 py-3 font-medium text-xelora-text-secondary">Name</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Type</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Size</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Status</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Modified</th>
                  <th className="px-4 py-3 text-right font-medium text-xelora-text-secondary">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border bg-white">
                {filteredFiles.map((file) => (
                  <tr key={file.id} className="hover:bg-xelora-surface-2">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <FileSpreadsheet className="h-4 w-4 text-xelora-green" />
                        <span className="font-medium text-xelora-text">{file.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs uppercase text-xelora-text-secondary">{file.type}</td>
                    <td className="px-4 py-3 text-xelora-text-secondary">{formatFileSize(file.sizeMB)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant[file.status] ?? 'default'}>{file.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-xelora-text-secondary">{file.lastModifiedAt ? formatRelativeTime(file.lastModifiedAt) : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" aria-label={`Actions for ${file.name}`}>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <a href={fileDownloadUrl(file.id)} target="_blank" rel="noreferrer" className="flex items-center gap-2">
                              <Download className="h-4 w-4" /> Download
                            </a>
                          </DropdownMenuItem>
                          <DropdownMenuItem destructive onClick={() => handleDelete(file)} className="flex items-center gap-2">
                            <Trash2 className="h-4 w-4" /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
