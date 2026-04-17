'use client';

import { useEffect, useState } from 'react';
import { UserPlus, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getTeamMembers, inviteTeamMember, removeTeamMember } from '@/services/workspace';
import type { TeamMemberItem } from '@/services/workspace';
import { formatDate } from '@/lib/utils';

const ROLES = ['administrator', 'editor', 'operator', 'viewer'];

export default function TeamPage() {
  const [members, setMembers] = useState<TeamMemberItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('viewer');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    getTeamMembers()
      .then(setMembers)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load team members.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleInvite = async () => {
    if (!email.trim()) {
      toast.error('Enter an email address.');
      return;
    }
    setIsSubmitting(true);
    try {
      const member = await inviteTeamMember(email.trim(), role);
      setMembers((current) => [member, ...current]);
      toast.success(`Invited ${email}.`);
      setInviteOpen(false);
      setEmail('');
      setRole('viewer');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not send invite.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemove = async (member: TeamMemberItem) => {
    try {
      await removeTeamMember(member.id);
      setMembers((current) => current.filter((m) => m.id !== member.id));
      toast.success(`Removed ${member.email}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not remove team member.');
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Team"
        title="Manage your team"
        description="Invite people to your workspace and manage their access. Seat limits are enforced by your plan."
        actions={
          <Button onClick={() => setInviteOpen(true)}>
            <UserPlus className="h-4 w-4" /> Invite member
          </Button>
        }
      />

      {loading ? (
        <StatePanel kind="loading" title="Loading team" description="Fetching your team members." />
      ) : members.length === 0 ? (
        <StatePanel kind="empty" title="No team members yet" description="Invite someone to collaborate." actionLabel="Invite member" onAction={() => setInviteOpen(true)} />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-xelora-surface-2">
                <tr className="border-b border-xelora-border text-left">
                  <th className="px-5 py-3 font-medium text-xelora-text-secondary">Member</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Role</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Status</th>
                  <th className="px-4 py-3 font-medium text-xelora-text-secondary">Invited</th>
                  <th className="px-4 py-3 text-right font-medium text-xelora-text-secondary">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-xelora-border bg-white">
                {members.map((member) => (
                  <tr key={member.id} className="hover:bg-xelora-surface-2">
                    <td className="px-5 py-3">
                      <p className="font-medium text-xelora-text">{member.name || member.email}</p>
                      <p className="text-xs text-xelora-text-muted">{member.email}</p>
                    </td>
                    <td className="px-4 py-3 capitalize text-xelora-text-secondary">{member.role}</td>
                    <td className="px-4 py-3">
                      <Badge variant={member.status === 'active' ? 'success' : 'warning'}>{member.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-xelora-text-secondary">{member.invitedAt ? formatDate(member.invitedAt) : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="ghost" size="icon" className="text-xelora-error" onClick={() => handleRemove(member)} aria-label={`Remove ${member.email}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite a team member</DialogTitle>
            <DialogDescription>They&apos;ll get access once they sign up with this email.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="colleague@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select value={role} onValueChange={setRole}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r} className="capitalize">{r}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteOpen(false)}>Cancel</Button>
            <Button onClick={handleInvite} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
              Send invite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
