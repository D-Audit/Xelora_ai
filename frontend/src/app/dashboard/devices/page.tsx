'use client';

import { useEffect, useState } from 'react';
import { MonitorSpeaker, Trash2, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { StatePanel } from '@/components/site/state-panel';
import { getDevices, removeDevice } from '@/services/workspace';
import type { DeviceItem } from '@/services/workspace';
import { formatDate } from '@/lib/utils';

export default function DevicesPage() {
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDevices()
      .then(setDevices)
      .catch((err) => toast.error(err instanceof Error ? err.message : 'Could not load devices.'))
      .finally(() => setLoading(false));
  }, []);

  const handleRemove = async (device: DeviceItem) => {
    try {
      await removeDevice(device.id);
      setDevices((current) => current.filter((d) => d.id !== device.id));
      toast.success(`${device.name} removed.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not remove device.');
    }
  };

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow="Devices"
        title="Authorised devices"
        description="Devices running the Xelora desktop agent under your account. Your plan limits how many can be active at once."
      />

      {loading ? (
        <StatePanel kind="loading" title="Loading devices" description="Fetching your authorised devices." />
      ) : devices.length === 0 ? (
        <StatePanel
          kind="empty"
          title="No devices registered yet"
          description="Install Xelora Desktop and sign in to register your first device."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {devices.map((device) => (
            <Card key={device.id} className="p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-md bg-xelora-surface-2">
                    <MonitorSpeaker className="h-5 w-5 text-xelora-green" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-xelora-text">{device.name}</h3>
                    <p className="text-xs text-xelora-text-muted capitalize">{device.os} {device.appVersion && `· v${device.appVersion}`}</p>
                  </div>
                </div>
                {device.isPrimary && <Badge variant="success"><ShieldCheck className="h-3 w-3" /> Primary</Badge>}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-xelora-text-secondary">
                <div>Status: {device.status}</div>
                <div>Authorised: {device.authorisedAt ? formatDate(device.authorisedAt) : '—'}</div>
                <div className="col-span-2">Last active: {device.lastActiveAt ? formatDate(device.lastActiveAt) : '—'}</div>
              </div>
              <div className="mt-4">
                <Button size="sm" variant="ghost" className="text-xelora-error" onClick={() => handleRemove(device)}>
                  <Trash2 className="h-4 w-4" /> Revoke access
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
