'use client';
import { useState } from 'react';
import { toast } from 'sonner';
import { Switch } from '@/components/ui/switch';

const sections = ['General', 'Files', 'AI preferences', 'Privacy', 'Notifications', 'Appearance', 'Account', 'About Xelora'];

export function SettingsWorkspace() {
  const [activeSection, setActiveSection] = useState('General');
  const [cloudEnabled, setCloudEnabled] = useState(true);
  const [notifications, setNotifications] = useState(true);

  return (
    <div className="flex h-full overflow-hidden">
      <nav className="w-52 shrink-0 border-r border-xelora-border bg-xelora-surface-2 py-4 overflow-y-auto">
        {sections.map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`w-full px-4 py-2 text-left text-sm transition-colors ${activeSection === s ? 'text-xelora-green font-medium bg-xelora-success-bg' : 'text-xelora-text-secondary hover:bg-xelora-border'}`}
          >
            {s}
          </button>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto px-8 py-6">
        <h2 className="text-lg font-semibold text-xelora-text mb-5">{activeSection}</h2>

        {activeSection === 'General' && (
          <div className="space-y-5 max-w-lg">
            <SettingRow label="Default save location" description="Where Xelora Desktop saves output files." value="C:/Users/Liliane/Documents/Xelora" />
            <SettingRow label="Auto-save interval" description="Automatically save a checkpoint before running a step." value="Before each step" />
            <SettingRow label="Language" description="Interface language for the desktop app." value="English (UK)" />
          </div>
        )}

        {activeSection === 'AI preferences' && (
          <div className="space-y-5 max-w-lg">
            <SettingRow label="AI explanation level" description="How much detail Xelora includes when describing its actions." value="Detailed" />
            <SettingRow label="Approval level" description="Which steps require your approval before running." value="Deletions and new sheets" />
            <SettingRow label="Context scope" description="What data Xelora reads when generating a workflow." value="Current worksheet" />
          </div>
        )}

        {activeSection === 'Privacy' && (
          <div className="space-y-5 max-w-lg">
            <div className="flex items-start justify-between gap-4 py-3 border-b border-xelora-border">
              <div>
                <p className="text-sm font-medium text-xelora-text">Cloud processing</p>
                <p className="text-xs text-xelora-text-secondary mt-0.5">Allow Xelora to use cloud compute for large files.</p>
              </div>
              <Switch checked={cloudEnabled} onCheckedChange={setCloudEnabled} />
            </div>
            <SettingRow label="File retention" description="How long Xelora keeps processing logs locally." value="30 days" />
          </div>
        )}

        {activeSection === 'Notifications' && (
          <div className="space-y-5 max-w-lg">
            <div className="flex items-start justify-between gap-4 py-3 border-b border-xelora-border">
              <div>
                <p className="text-sm font-medium text-xelora-text">Desktop notifications</p>
                <p className="text-xs text-xelora-text-secondary mt-0.5">Show system notifications when a task completes or needs approval.</p>
              </div>
              <Switch checked={notifications} onCheckedChange={setNotifications} />
            </div>
          </div>
        )}

        {activeSection === 'About Xelora' && (
          <div className="space-y-3 max-w-lg">
            <div className="rounded-lg border border-xelora-border p-4 space-y-2 text-sm text-xelora-text-secondary">
              <p><span className="font-medium text-xelora-text">Xelora Desktop</span> v1.3.0</p>
              <p>Platform simulation — this is a frontend demo, not a native application.</p>
              <p>© 2026 Xelora. All rights reserved.</p>
            </div>
            <button onClick={() => toast.info('Update check: you are on the latest version.')} className="rounded-md border border-xelora-border px-4 py-2 text-sm text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors">
              Check for updates
            </button>
          </div>
        )}

        {!['General', 'AI preferences', 'Privacy', 'Notifications', 'About Xelora'].includes(activeSection) && (
          <div className="max-w-lg rounded-lg border border-xelora-border p-5 text-sm text-xelora-text-secondary">
            {activeSection} settings are simulated in this demo. In a connected desktop app, these controls would modify the local configuration.
            <button onClick={() => toast.success(`${activeSection} settings saved.`)} className="mt-4 flex rounded-md bg-xelora-green px-4 py-2 text-xs font-medium text-white hover:bg-xelora-deep-green transition-colors">
              Save changes
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SettingRow({ label, description, value }: { label: string; description: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-xelora-border">
      <div>
        <p className="text-sm font-medium text-xelora-text">{label}</p>
        <p className="text-xs text-xelora-text-secondary mt-0.5">{description}</p>
      </div>
      <span className="text-sm text-xelora-text-secondary shrink-0 rounded border border-xelora-border bg-xelora-surface-2 px-2.5 py-1">{value}</span>
    </div>
  );
}
