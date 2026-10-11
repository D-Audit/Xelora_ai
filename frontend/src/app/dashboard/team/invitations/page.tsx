'use client';

import { MailCheck, RefreshCcw } from 'lucide-react';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { mockTeamMembers } from '@/data/mock-team';

export default function TeamInvitationsPage() {
  const pending = mockTeamMembers.filter((member) => member.status === 'invited');
  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Team"
        title="Pending invitations"
        description="Track outstanding invites and resend them when needed."
      />
      <div className="space-y-4">
        {pending.map((member) => (
          <Card key={member.id} className="flex items-center justify-between gap-3 p-5">
            <div>
              <p className="text-sm font-semibold text-xelora-text">{member.email}</p>
              <p className="text-sm text-xelora-text-secondary">{member.role}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="warning">Pending</Badge>
              <Button variant="outline" size="sm" onClick={() => toast.success(`Invitation resent to ${member.email}.`)}>
                <RefreshCcw className="h-4 w-4" />
                Resend
              </Button>
            </div>
          </Card>
        ))}
        {pending.length === 0 ? (
          <Card className="p-6 text-center">
            <MailCheck className="mx-auto h-8 w-8 text-xelora-green" />
            <p className="mt-3 text-sm text-xelora-text-secondary">No pending invitations.</p>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
