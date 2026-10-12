'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { Button } from '@/components/ui/button';
import { getTeamMembers, type TeamMemberItem } from '@/services/workspace';
import { formatRelativeTime } from '@/lib/utils';

export default function TeamInvitationsPage() {
  const [pending, setPending] = useState<TeamMemberItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTeamMembers()
      .then((members) => setPending(members.filter((member) => member.status === 'invited')))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load invitations.'));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <DashboardPageHeader
        title="Pending invitations"
        description="People you have invited who have not joined yet."
        actions={<Button variant="outline" asChild><Link href="/dashboard/team">Back to team</Link></Button>}
      />
      {error ? (
        <StatePanel kind="error" title="Could not load invitations" description={error} />
      ) : pending === null ? (
        <StatePanel kind="loading" title="Loading invitations" description="" />
      ) : pending.length === 0 ? (
        <StatePanel kind="empty" title="No pending invitations" description="Invite people from the Team page." />
      ) : (
        <ul className="divide-y divide-xelora-border rounded-xl border border-xelora-border bg-xelora-surface">
          {pending.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-3 px-4 py-3.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-xelora-text">{member.email}</p>
                <p className="text-xs capitalize text-xelora-text-secondary">{member.role}</p>
              </div>
              <span className="shrink-0 text-xs text-xelora-text-muted">
                Invited {member.invitedAt ? formatRelativeTime(member.invitedAt) : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
