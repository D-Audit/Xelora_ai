'use client';

import { useEffect, useState } from 'react';
import { MailCheck, RefreshCcw } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { StatePanel } from '@/components/site/state-panel';
import { getTeamMembers, resendTeamInvitation, type TeamMemberItem } from '@/services/workspace';

export default function TeamInvitationsPage() {
  const [pending, setPending] = useState<TeamMemberItem[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { getTeamMembers().then((items) => setPending(items.filter((item) => item.status === 'invited'))).catch((err) => toast.error(err.message)).finally(() => setLoading(false)); }, []);

  const resend = (member: TeamMemberItem) => {
    resendTeamInvitation(member.id).then((updated) => { setPending((items) => items.map((item) => item.id === updated.id ? updated : item)); toast.success(`Invitation resent to ${member.email}.`); }).catch((err) => toast.error(err.message));
  };

  return <div className="space-y-6">
    <DashboardPageHeader eyebrow="Team" title="Pending invitations" description="Track outstanding invites stored in your workspace." />
    {loading ? <StatePanel kind="loading" title="Loading invitations" description="Checking your team records." /> : <div className="space-y-4">
      {pending.map((member) => <Card key={member.id} className="flex items-center justify-between gap-3 p-5"><div><p className="text-sm font-semibold text-xelora-text">{member.email}</p><p className="text-sm text-xelora-text-secondary">{member.role}</p></div><div className="flex items-center gap-2"><Badge variant="warning">Pending</Badge><Button variant="outline" size="sm" onClick={() => resend(member)}><RefreshCcw className="h-4 w-4" />Resend</Button></div></Card>)}
      {!pending.length && <Card className="p-6 text-center"><MailCheck className="mx-auto h-8 w-8 text-xelora-green" /><p className="mt-3 text-sm text-xelora-text-secondary">No pending invitations.</p></Card>}
    </div>}
  </div>;
}
