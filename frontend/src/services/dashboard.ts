/**
 * Mock dashboard service.
 * Replace individual functions with real API calls when connecting to a backend.
 */
import { delay } from '@/lib/utils';
import { mockUsage, mockDailyUsage } from '@/data/mock-usage';
import { mockFiles } from '@/data/mock-files';
import { mockWorkflows, mockWorkflowRuns } from '@/data/mock-workflows';
import { mockSubscription } from '@/data/mock-billing';
import { mockNotifications } from '@/data/mock-notifications';
import { mockDevices } from '@/data/mock-devices';
import { mockTeamMembers } from '@/data/mock-team';
import type { UsageLimits, DailyUsage, FileRecord, Workflow, WorkflowRun, Subscription, Notification, Device, TeamMember } from '@/types';

export async function getDashboardSummary() {
  await delay(600);
  return {
    usage: mockUsage,
    subscription: mockSubscription,
    recentFiles: mockFiles.slice(0, 5),
    recentRuns: mockWorkflowRuns.slice(0, 3),
    alerts: mockNotifications.filter((n) => !n.isRead && n.priority === 'medium'),
  };
}

export async function getUsage(): Promise<{ summary: UsageLimits; daily: DailyUsage[] }> {
  await delay(500);
  return { summary: mockUsage, daily: mockDailyUsage };
}

export async function getFiles(): Promise<FileRecord[]> {
  await delay(400);
  return mockFiles;
}

export async function uploadFile(file: File): Promise<FileRecord> {
  await delay(1500);
  const newFile: FileRecord = {
    id: `file-${Date.now()}`,
    name: file.name,
    type: file.name.endsWith('.csv') ? 'csv' : 'xlsx',
    sizeMB: file.size / (1024 * 1024),
    status: 'ready',
    ownerId: 'user-1',
    ownerName: 'Liliane Okonkwo',
    lastModifiedAt: new Date().toISOString(),
    uploadedAt: new Date().toISOString(),
  };
  return newFile;
}

export async function getWorkflows(): Promise<Workflow[]> {
  await delay(500);
  return mockWorkflows;
}

export async function getWorkflowById(id: string): Promise<Workflow | null> {
  await delay(300);
  return mockWorkflows.find((w) => w.id === id) ?? null;
}

export async function createWorkflow(data: Partial<Workflow>): Promise<Workflow> {
  await delay(800);
  const newWorkflow: Workflow = {
    id: `wf-${Date.now()}`,
    name: data.name ?? 'Untitled Workflow',
    description: data.description ?? '',
    status: 'draft',
    steps: data.steps ?? [],
    creatorId: 'user-1',
    creatorName: 'Liliane Okonkwo',
    successRate: 0,
    totalRuns: 0,
    isPublic: false,
    tags: data.tags ?? [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  return newWorkflow;
}

export async function getWorkflowRuns(): Promise<WorkflowRun[]> {
  await delay(400);
  return mockWorkflowRuns;
}

export async function getRunById(id: string): Promise<WorkflowRun | null> {
  await delay(300);
  return mockWorkflowRuns.find((r) => r.id === id) ?? null;
}

export async function getSubscription(): Promise<Subscription> {
  await delay(300);
  return mockSubscription;
}

export async function changePlan(planTier: string, billingCycle: string): Promise<{ success: boolean }> {
  await delay(1200);
  return { success: true };
}

export async function getDevices(): Promise<Device[]> {
  await delay(400);
  return mockDevices;
}

export async function removeDevice(deviceId: string): Promise<{ success: boolean }> {
  await delay(600);
  return { success: true };
}

export async function getTeamMembers(): Promise<TeamMember[]> {
  await delay(400);
  return mockTeamMembers;
}

export async function inviteTeamMember(email: string, role: string): Promise<{ success: boolean }> {
  await delay(800);
  return { success: true };
}

export async function getNotifications(): Promise<Notification[]> {
  await delay(300);
  return mockNotifications;
}

export async function markNotificationRead(id: string): Promise<{ success: boolean }> {
  await delay(200);
  return { success: true };
}
