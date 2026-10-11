import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(dateString));
}

export function formatRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateString);
}

export function formatFileSize(sizeMB: number): string {
  if (sizeMB < 0.1) return `${Math.round(sizeMB * 1024)} KB`;
  if (sizeMB < 1024) return `${sizeMB.toFixed(1)} MB`;
  return `${(sizeMB / 1024).toFixed(2)} GB`;
}

export function formatStorageGB(gb: number): string {
  if (gb < 1) return `${(gb * 1024).toFixed(0)} MB`;
  return `${gb.toFixed(1)} GB`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-GB').format(n);
}

export function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : (plural ?? `${singular}s`);
}

export function getUsagePercentage(used: number, limit: number | 'unlimited' | 'custom'): number {
  if (limit === 'unlimited' || limit === 'custom') return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

export function getUsageColour(percentage: number): string {
  if (percentage >= 90) return 'text-xelora-error';
  if (percentage >= 75) return 'text-xelora-warning';
  return 'text-xelora-success';
}

export function getUsageBarColour(percentage: number): string {
  if (percentage >= 90) return 'bg-xelora-error';
  if (percentage >= 75) return 'bg-xelora-warning';
  return 'bg-xelora-green';
}
