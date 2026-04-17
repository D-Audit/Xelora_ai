'use client';

import { useState } from 'react';
import { Download, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export default function SettingsPage() {
  const [retainDays, setRetainDays] = useState('30');
  const [aiExplanation, setAiExplanation] = useState('detailed');
  const [approvalLevel, setApprovalLevel] = useState('standard');
  const [cloudAllowed, setCloudAllowed] = useState(true);

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Settings"
        title="Configure your workspace"
        description="Profile, security, notification, privacy, and AI preferences are all simulated here."
      />

      <Tabs defaultValue="profile">
        <TabsList className="flex flex-wrap h-auto gap-2 bg-transparent p-0">
          {['profile', 'security', 'notifications', 'privacy', 'ai', 'desktop', 'cloud', 'account'].map((tab) => (
            <TabsTrigger key={tab} value={tab} className="rounded-md border border-xelora-border bg-white px-4 py-2 text-sm data-[state=active]:bg-xelora-success-bg data-[state=active]:text-xelora-success">
              {tab}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="profile" className="mt-4">
          <Card className="p-5 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Name</Label>
                <Input defaultValue="Liliane Okonkwo" />
              </div>
              <div>
                <Label>Email</Label>
                <Input defaultValue="liliane@xelora.app" />
              </div>
              <div>
                <Label>Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="fr">French</SelectItem>
                    <SelectItem value="de">German</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Time zone</Label>
                <Select defaultValue="africa-cairo">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="africa-cairo">Africa/Cairo</SelectItem>
                    <SelectItem value="europe-london">Europe/London</SelectItem>
                    <SelectItem value="america-new_york">America/New_York</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button onClick={() => toast.success('Profile saved.')}>Save changes</Button>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-4">
          <Card className="p-5 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Current password</Label>
                <Input type="password" />
              </div>
              <div>
                <Label>New password</Label>
                <Input type="password" />
              </div>
            </div>
            <Button onClick={() => toast.success('Password updated.')}>Update password</Button>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-4">
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-xelora-text">Email notifications</p>
                <p className="text-sm text-xelora-text-secondary">Receive workflow and billing updates by email.</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-xelora-text">Desktop notifications</p>
                <p className="text-sm text-xelora-text-secondary">Show notifications in Xelora Desktop.</p>
              </div>
              <Switch defaultChecked />
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="privacy" className="mt-4">
          <Card className="p-5 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>File retention period</Label>
                <Select value={retainDays} onValueChange={setRetainDays}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7">7 days</SelectItem>
                    <SelectItem value="30">30 days</SelectItem>
                    <SelectItem value="90">90 days</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Cloud processing permission</Label>
                <div className="mt-3 flex items-center gap-3">
                  <Switch checked={cloudAllowed} onCheckedChange={setCloudAllowed} />
                  <span className="text-sm text-xelora-text-secondary">{cloudAllowed ? 'Enabled' : 'Disabled'}</span>
                </div>
              </div>
            </div>
            <Button onClick={() => toast.success('Privacy settings saved.')}>Save privacy settings</Button>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="mt-4">
          <Card className="p-5 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>Default AI context</Label>
                <Textarea defaultValue="Use local workbook data only. Prefer concise explanations." />
              </div>
              <div>
                <Label>AI explanation level</Label>
                <Select value={aiExplanation} onValueChange={setAiExplanation}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="brief">Brief</SelectItem>
                    <SelectItem value="detailed">Detailed</SelectItem>
                    <SelectItem value="advanced">Advanced</SelectItem>
                  </SelectContent>
                </Select>
                <div className="mt-4">
                  <Label>Approval level</Label>
                  <Select value={approvalLevel} onValueChange={setApprovalLevel}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="standard">Standard</SelectItem>
                      <SelectItem value="strict">Strict</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
            <Button onClick={() => toast.success('AI preferences saved.')}>Save AI preferences</Button>
          </Card>
        </TabsContent>

        <TabsContent value="desktop" className="mt-4">
          <Card className="p-5 space-y-4">
            <p className="text-sm text-xelora-text-secondary">Manage desktop preferences, update channel, and local sync behaviour.</p>
            <Button variant="outline" onClick={() => toast.info('Desktop preferences updated.')}>Sync desktop preferences</Button>
          </Card>
        </TabsContent>

        <TabsContent value="cloud" className="mt-4">
          <Card className="p-5 space-y-4">
            <p className="text-sm text-xelora-text-secondary">Control Xelora Cloud uploads and retention. This demo does not connect to cloud storage.</p>
            <Button variant="outline" onClick={() => toast.success('Cloud storage preferences updated.')}>Update cloud storage</Button>
          </Card>
        </TabsContent>

        <TabsContent value="account" className="mt-4">
          <Card className="p-5 space-y-4">
            <Button variant="outline" onClick={() => toast.success('Account data export prepared.')}>
              <Download className="h-4 w-4" />
              Download account data
            </Button>
            <Button variant="ghost" className="text-xelora-error" onClick={() => toast.error('Delete account confirmation would open here.')}>
              <Trash2 className="h-4 w-4" />
              Delete account
            </Button>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
