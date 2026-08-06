// Xelora shared TypeScript types
// These types are designed to be shared between the web app and future desktop app

// ─── User & Auth ─────────────────────────────────────────────────────────────

export type UserRole = 'owner' | 'administrator' | 'editor' | 'operator' | 'viewer';

export interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  role: UserRole;
  plan: PlanTier;
  organisationId?: string;
  createdAt: string;
  lastActiveAt: string;
  isVerified: boolean;
  country?: string;
  primaryUse?: string;
  experience?: 'beginner' | 'intermediate' | 'advanced';
  objectives?: string[];
  onboardingCompleted: boolean;
  isAdmin?: boolean;
}

// ─── Organisation ─────────────────────────────────────────────────────────────

export interface Organisation {
  id: string;
  name: string;
  plan: PlanTier;
  ownerId: string;
  createdAt: string;
  memberCount: number;
}

// ─── Subscription & Plans ─────────────────────────────────────────────────────

export type PlanTier = 'trial' | 'starter' | 'professional' | 'business';
export type BillingCycle = 'monthly' | 'annual';

export interface PlanLimits {
  aiActionsPerMonth: number | 'unlimited' | 'custom';
  workflowRunsPerMonth: number | 'unlimited' | 'custom';
  maxFileSizeMB: number | 'unlimited' | 'custom';
  savedWorkflows: number | 'unlimited' | 'custom';
  cloudStorageGB: number | 'unlimited' | 'custom';
  devices: number | 'unlimited' | 'custom';
  historyDays: number | 'unlimited' | 'custom';
  teamMembers: number | 'unlimited' | 'custom';
  batchProcessing: boolean;
  apiAccess: boolean;
  prioritySupport: boolean;
  auditHistory: boolean;
  rolePermissions: boolean;
  customWorkspace: boolean;
}

export interface Plan {
  id: string;
  tier: PlanTier;
  name: string;
  description: string;
  monthlyPrice: number | null;
  annualPrice: number | null;
  limits: PlanLimits;
  isPopular?: boolean;
  isCustom?: boolean;
}

export interface Subscription {
  id: string;
  userId: string;
  planTier: PlanTier;
  billingCycle: BillingCycle;
  status: 'active' | 'trialing' | 'cancelled' | 'past_due' | 'paused';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  trialEndsAt?: string;
}

// ─── Usage ────────────────────────────────────────────────────────────────────

export interface UsageLimits {
  aiActionsUsed: number;
  aiActionsLimit: number;
  workflowRunsUsed: number;
  workflowRunsLimit: number;
  storageUsedGB: number;
  storageLimitGB: number;
  devicesUsed: number;
  devicesLimit: number;
  teamMembersUsed: number;
  teamMembersLimit: number;
  resetDate: string;
}

export interface DailyUsage {
  date: string;
  aiActions: number;
  workflowRuns: number;
  fileOperations: number;
}

// ─── Files ────────────────────────────────────────────────────────────────────

export type FileStatus = 'ready' | 'processing' | 'completed' | 'needs_review' | 'failed' | 'archived';
export type FileType = 'xlsx' | 'xls' | 'csv' | 'ods' | 'tsv';

export interface FileRecord {
  id: string;
  name: string;
  type: FileType;
  sizeMB: number;
  status: FileStatus;
  ownerId: string;
  ownerName: string;
  folderId?: string;
  lastModifiedAt: string;
  uploadedAt: string;
  rowCount?: number;
  columnCount?: number;
  tags?: string[];
}

export interface FileVersion {
  id: string;
  fileId: string;
  versionNumber: number;
  createdAt: string;
  createdBy: string;
  sizeMB: number;
  note?: string;
  isAutoSave: boolean;
}

// ─── Workflows ────────────────────────────────────────────────────────────────

export type WorkflowStatus = 'draft' | 'published' | 'archived' | 'running';
export type StepType =
  | 'analyse'
  | 'filter'
  | 'clean'
  | 'transform'
  | 'formula'
  | 'sort'
  | 'deduplicate'
  | 'format'
  | 'chart'
  | 'report'
  | 'export'
  | 'approval'
  | 'condition'
  | 'custom';

export interface WorkflowStep {
  id: string;
  workflowId: string;
  order: number;
  name: string;
  description?: string;
  type: StepType;
  isEnabled: boolean;
  requiresApproval: boolean;
  conditions?: string;
  errorBehaviour: 'stop' | 'skip' | 'retry';
  estimatedAiActions: number;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  steps: WorkflowStep[];
  creatorId: string;
  creatorName: string;
  lastRunAt?: string;
  lastRunStatus?: WorkflowRunStatus;
  successRate: number;
  totalRuns: number;
  isPublic: boolean;
  compatibleFileStructure?: string;
  tags?: string[];
  createdAt: string;
  updatedAt: string;
}

export type WorkflowRunStatus = 'completed' | 'completed_with_warnings' | 'failed' | 'cancelled' | 'paused' | 'awaiting_approval' | 'running';

export interface WorkflowRun {
  id: string;
  workflowId: string;
  workflowName: string;
  fileId: string;
  fileName: string;
  userId: string;
  userName: string;
  startedAt: string;
  completedAt?: string;
  status: WorkflowRunStatus;
  stepsCompleted: number;
  totalSteps: number;
  aiActionsUsed: number;
  durationSeconds?: number;
  outputFileId?: string;
  timeline?: WorkflowRunEvent[];
}

export interface WorkflowRunEvent {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

// ─── Devices ──────────────────────────────────────────────────────────────────

export type DeviceOS = 'windows' | 'macos' | 'linux';
export type DeviceStatus = 'active' | 'inactive' | 'pending' | 'removed';

export interface Device {
  id: string;
  userId: string;
  name: string;
  os: DeviceOS;
  appVersion: string;
  lastActiveAt: string;
  region: string;
  status: DeviceStatus;
  isPrimary: boolean;
  authorisedAt: string;
}

// ─── Team ─────────────────────────────────────────────────────────────────────

export type MemberStatus = 'active' | 'invited' | 'suspended' | 'removed';

export interface TeamMember {
  id: string;
  userId: string;
  organisationId: string;
  name: string;
  email: string;
  role: UserRole;
  status: MemberStatus;
  lastActiveAt?: string;
  workflowCount: number;
  joinedAt?: string;
  invitedAt?: string;
  avatarUrl?: string;
}

// ─── Notifications ────────────────────────────────────────────────────────────

export type NotificationCategory = 'workflow' | 'billing' | 'account' | 'team' | 'product';
export type NotificationPriority = 'low' | 'medium' | 'high';

export interface Notification {
  id: string;
  userId: string;
  category: NotificationCategory;
  title: string;
  message: string;
  isRead: boolean;
  priority: NotificationPriority;
  createdAt: string;
  actionUrl?: string;
  actionLabel?: string;
}

// ─── Billing & Invoices ───────────────────────────────────────────────────────

export type InvoiceStatus = 'paid' | 'pending' | 'failed' | 'refunded';

export interface Invoice {
  id: string;
  userId: string;
  amount: number;
  currency: string;
  status: InvoiceStatus;
  description: string;
  issuedAt: string;
  paidAt?: string;
  downloadUrl?: string;
  periodStart: string;
  periodEnd: string;
}

// ─── Desktop Releases ─────────────────────────────────────────────────────────

export type ReleaseStatus = 'stable' | 'beta' | 'deprecated' | 'coming_soon';
export type ReleaseOS = 'windows' | 'macos' | 'linux';

export interface DesktopRelease {
  id: string;
  version: string;
  os: ReleaseOS;
  status: ReleaseStatus;
  releasedAt: string;
  fileSizeMB: number;
  downloadCount: number;
  releaseNotes: string[];
  downloadUrl?: string;
  checksum?: string;
}

// ─── Templates ────────────────────────────────────────────────────────────────

export type TemplateCategory =
  | 'accounting'
  | 'sales'
  | 'payroll'
  | 'hr'
  | 'inventory'
  | 'education'
  | 'research'
  | 'data_cleaning'
  | 'reporting';

export interface Template {
  id: string;
  name: string;
  description: string;
  category: TemplateCategory;
  requiredColumns: string[];
  stepCount: number;
  estimatedAiActions: number;
  compatiblePlan: PlanTier;
  author: string;
  isOfficial: boolean;
  usageCount: number;
  createdAt: string;
  tags?: string[];
}

// ─── Admin ────────────────────────────────────────────────────────────────────

export interface AdminStats {
  totalUsers: number;
  activeSubscriptions: number;
  trialConversions: number;
  monthlyRecurringRevenue: number;
  aiActionsToday: number;
  workflowRunsToday: number;
  totalStorageGB: number;
  failedOperationsToday: number;
}

export interface SystemService {
  name: string;
  status: 'operational' | 'degraded' | 'outage' | 'maintenance';
  latencyMs?: number;
  uptime?: number;
  lastCheckedAt: string;
}
