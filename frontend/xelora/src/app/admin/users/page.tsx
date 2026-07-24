'use client';

import { useEffect, useMemo, useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { StatePanel } from '@/components/site/state-panel';
import { formatDate } from '@/lib/utils';

interface AdminUser {
  id: string;
  name: string;
  email: string;
  isAdmin: boolean;
  planTier: string;
  subscriptionStatus: string | null;
  createdAt: string | null;
}

const PLAN_TIERS = ['trial', 'starter', 'professional', 'business'];

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    fetch('/api/admin/users', { cache: 'no-store' })
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Could not load users.');
        setUsers(data.users);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load users.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(
    () => users.filter((u) => `${u.name} ${u.email}`.toLowerCase().includes(search.toLowerCase())),
    [users, search]
  );

  const handlePlanChange = async (user: AdminUser, planTier: string) => {
    setUpdatingId(user.id);
    try {
      const res = await fetch(`/api/admin/users/${user.id}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ planTier }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Could not update plan.');
      setUsers((current) => current.map((u) => (u.id === user.id ? { ...u, planTier } : u)));
      toast.success(`${user.name}'s plan set to ${planTier}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update plan.');
    } finally {
      setUpdatingId(null);
    }
  };

  if (!loading && error) {
    return (
      <div className="space-y-6">
        <DashboardPageHeader eyebrow="Admin" title="Users" description="Search and manage customer accounts." />
        <StatePanel kind="empty" title="Could not load users" description={error} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader eyebrow="Admin" title="Users" description="Search and manage customer accounts and their plan tier." />
      <Card className="p-4">
        <div className="relative w-full lg:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-xelora-text-muted" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search users" className="pl-9" />
        </div>
      </Card>
      {loading ? (
        <StatePanel kind="loading" title="Loading users" description="Fetching accounts." />
      ) : (
        <div className="space-y-3">
          {filtered.map((user) => (
            <Card key={user.id} className="flex flex-wrap items-center justify-between gap-3 p-5">
              <div>
                <p className="text-sm font-semibold text-xelora-text">{user.name} {user.isAdmin && <Badge variant="dark" className="ml-1">Admin</Badge>}</p>
                <p className="text-sm text-xelora-text-secondary">{user.email}</p>
                <p className="text-xs text-xelora-text-muted">Joined {user.createdAt ? formatDate(user.createdAt) : '—'}</p>
              </div>
              <div className="flex items-center gap-2">
                {user.subscriptionStatus && <Badge variant={user.subscriptionStatus === 'active' ? 'success' : 'outline'}>{user.subscriptionStatus}</Badge>}
                <Select value={user.planTier} onValueChange={(v) => handlePlanChange(user, v)} disabled={updatingId === user.id}>
                  <SelectTrigger className="w-36">
                    {updatingId === user.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <SelectValue />}
                  </SelectTrigger>
                  <SelectContent>
                    {PLAN_TIERS.map((tier) => <SelectItem key={tier} value={tier} className="capitalize">{tier}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
