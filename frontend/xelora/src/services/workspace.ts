/**
 * Client-side service for files, team, devices, notifications, and
 * workflows/templates. Calls our own Next.js API routes, which
 * forward to the FastAPI backend server-side.
 *
 * Types here are defined locally to match exactly what the backend
 * returns, rather than imported from src/types/index.ts - the
 * original mock types carry a few fields (creatorId, organisationId,
 * folderId, etc.) the backend doesn't model. See INTEGRATION.md.
 */

async function parseOrThrow<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { error?: string }).error || 'Request failed.');
  }
  return data as T;
}


export interface FileItem {
  id: string;
  name: string;
  type: string;
  sizeMB: number;
  status: string;
  rowCount: number | null;
  columnCount: number | null;
  tags: string[];
  uploadedAt: string;
  lastModifiedAt: string;
}

export async function getFiles(): Promise<FileItem[]> {
  const res = await fetch('/api/files', { cache: 'no-store' });
  const data = await parseOrThrow<{ files: FileItem[] }>(res);
  return data.files;
}

export async function getFileById(id: string): Promise<{ file: FileItem; versions: never[] }> {
  const res = await fetch(`/api/files/${id}`, { cache: 'no-store' });
  return parseOrThrow(res);
}

export async function uploadFile(file: File): Promise<FileItem> {
  const form = new FormData();
  form.append('upload', file);
  const res = await fetch('/api/files', { method: 'POST', body: form });
  return parseOrThrow<FileItem>(res);
}

export async function deleteFile(id: string): Promise<void> {
  const res = await fetch(`/api/files/${id}`, { method: 'DELETE' });
  await parseOrThrow(res);
}

export function fileDownloadUrl(id: string): string {
  return `/api/files/${id}/download`;
}


export interface TeamMemberItem {
  id: string;
  email: string;
  name: string | null;
  role: string;
  status: string;
  invitedAt: string | null;
  joinedAt: string | null;
  lastActiveAt: string | null;
}

export async function getTeamMembers(): Promise<TeamMemberItem[]> {
  const res = await fetch('/api/team', { cache: 'no-store' });
  const data = await parseOrThrow<{ members: TeamMemberItem[] }>(res);
  return data.members;
}

export async function inviteTeamMember(email: string, role: string): Promise<TeamMemberItem> {
  const res = await fetch('/api/team/invite', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, role }),
  });
  return parseOrThrow<TeamMemberItem>(res);
}

export async function removeTeamMember(id: string): Promise<void> {
  const res = await fetch(`/api/team/${id}`, { method: 'DELETE' });
  await parseOrThrow(res);
}

export async function resendTeamInvitation(id: string): Promise<TeamMemberItem> {
  const res = await fetch(`/api/team/${id}/resend`, { method: 'POST' });
  return parseOrThrow(res);
}


export interface DeviceItem {
  id: string;
  name: string;
  os: string;
  appVersion: string;
  region: string;
  status: string;
  isPrimary: boolean;
  authorisedAt: string | null;
  lastActiveAt: string | null;
}

export async function getDevices(): Promise<DeviceItem[]> {
  const res = await fetch('/api/devices', { cache: 'no-store' });
  const data = await parseOrThrow<{ devices: DeviceItem[] }>(res);
  return data.devices;
}

export async function removeDevice(id: string): Promise<void> {
  const res = await fetch(`/api/devices/${id}`, { method: 'DELETE' });
  await parseOrThrow(res);
}


export interface NotificationItem {
  id: string;
  category: string;
  title: string;
  message: string;
  priority: string;
  isRead: boolean;
  actionUrl: string | null;
  actionLabel: string | null;
  createdAt: string | null;
}

export async function getNotifications(): Promise<NotificationItem[]> {
  const res = await fetch('/api/notifications', { cache: 'no-store' });
  const data = await parseOrThrow<{ notifications: NotificationItem[] }>(res);
  return data.notifications;
}

export async function markNotificationRead(id: string): Promise<void> {
  const res = await fetch(`/api/notifications/${id}/read`, { method: 'POST' });
  await parseOrThrow(res);
}

export async function markAllNotificationsRead(): Promise<void> {
  const res = await fetch('/api/notifications/read-all', { method: 'POST' });
  await parseOrThrow(res);
}


export interface WorkflowStepItem {
  name: string;
  description?: string;
  type: string;
  isEnabled: boolean;
  requiresApproval: boolean;
  errorBehaviour: string;
  estimatedAiActions: number;
}

export interface WorkflowItem {
  id: string;
  name: string;
  description: string;
  status: string;
  steps: WorkflowStepItem[];
  tags: string[];
  isPublic: boolean;
  successRate: number;
  totalRuns: number;
  lastRunAt: string | null;
  lastRunStatus: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface WorkflowRunItem {
  id: string;
  workflowId: string;
  workflowName: string;
  taskId: number | null;
  status: string;
  stepsCompleted: number;
  totalSteps: number;
  aiActionsUsed: number;
  durationSeconds: number | null;
  startedAt: string | null;
  completedAt: string | null;
}

export async function getWorkflows(): Promise<WorkflowItem[]> {
  const res = await fetch('/api/workflows', { cache: 'no-store' });
  const data = await parseOrThrow<{ workflows: WorkflowItem[] }>(res);
  return data.workflows;
}

export async function getWorkflowById(id: string): Promise<WorkflowItem> {
  const res = await fetch(`/api/workflows/${id}`, { cache: 'no-store' });
  return parseOrThrow<WorkflowItem>(res);
}

export async function createWorkflow(data: {
  name: string;
  description?: string;
  steps?: WorkflowStepItem[];
  tags?: string[];
}): Promise<WorkflowItem> {
  const res = await fetch('/api/workflows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return parseOrThrow<WorkflowItem>(res);
}

export async function updateWorkflow(
  id: string,
  data: { name: string; description?: string; steps?: WorkflowStepItem[]; tags?: string[] }
): Promise<WorkflowItem> {
  const res = await fetch(`/api/workflows/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return parseOrThrow<WorkflowItem>(res);
}

export async function deleteWorkflow(id: string): Promise<void> {
  const res = await fetch(`/api/workflows/${id}`, { method: 'DELETE' });
  await parseOrThrow(res);
}

export async function runWorkflow(id: string): Promise<WorkflowRunItem> {
  const res = await fetch(`/api/workflows/${id}/run`, { method: 'POST' });
  return parseOrThrow<WorkflowRunItem>(res);
}

export async function getWorkflowRuns(): Promise<WorkflowRunItem[]> {
  const res = await fetch('/api/workflows/runs', { cache: 'no-store' });
  const data = await parseOrThrow<{ runs: WorkflowRunItem[] }>(res);
  return data.runs;
}

export async function getRunById(id: string): Promise<WorkflowRunItem> {
  const res = await fetch(`/api/workflows/runs/${id}`, { cache: 'no-store' });
  return parseOrThrow<WorkflowRunItem>(res);
}

export interface WorkflowTemplateItem {
  id: string;
  name: string;
  description: string;
  category: string;
  steps: WorkflowStepItem[];
}

export async function getTemplates(): Promise<WorkflowTemplateItem[]> {
  const res = await fetch('/api/templates', { cache: 'no-store' });
  const data = await parseOrThrow<{ templates: WorkflowTemplateItem[] }>(res);
  return data.templates;
}

export async function useTemplate(id: string): Promise<WorkflowItem> {
  const res = await fetch(`/api/templates/${id}/use`, { method: 'POST' });
  return parseOrThrow<WorkflowItem>(res);
}
