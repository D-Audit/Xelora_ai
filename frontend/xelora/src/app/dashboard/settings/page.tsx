'use client';

import { useEffect, useRef, useState } from 'react';
import { Bell, Bot, Cloud, Download, KeyRound, Monitor, Moon, ShieldCheck, SlidersHorizontal, Sun, Trash2, UserRound } from 'lucide-react';
import { useTheme } from 'next-themes';
import { toast } from 'sonner';
import { DashboardPageHeader } from '@/components/dashboard/page-header';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const sections = [
  { id: 'profile', label: 'Profile', description: 'Identity and regional preferences', icon: UserRound },
  { id: 'appearance', label: 'Appearance', description: 'Theme and display', icon: SlidersHorizontal },
  { id: 'notifications', label: 'Notifications', description: 'Updates and alerts', icon: Bell },
  { id: 'security', label: 'Security', description: 'Password and access', icon: KeyRound },
  { id: 'privacy', label: 'Privacy', description: 'Data and processing controls', icon: ShieldCheck },
  { id: 'ai', label: 'AI preferences', description: 'How Xelora assists you', icon: Bot },
  { id: 'cloud', label: 'Cloud & desktop', description: 'Storage and local sync', icon: Cloud },
] as const;

type SectionId = (typeof sections)[number]['id'];

function SettingRow({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <div className="flex flex-col gap-4 py-5 sm:flex-row sm:items-center sm:justify-between"><div className="max-w-lg"><p className="font-medium text-xelora-text">{title}</p><p className="mt-1 text-sm leading-5 text-xelora-text-secondary">{description}</p></div>{children}</div>;
}

export default function SettingsPage() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [section, setSection] = useState<SectionId>('profile');
  const [cloudAllowed, setCloudAllowed] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [desktopNotifications, setDesktopNotifications] = useState(true);
  const [name, setName] = useState('Liliane Okonkwo');
  const [email, setEmail] = useState('liliane@xelora.app');
  const [language, setLanguage] = useState('en');
  const [timezone, setTimezone] = useState('africa-kigali');
  const [retention, setRetention] = useState('30');
  const hydrated = useRef(false);

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('xelora-settings') || '{}') as Partial<Record<string, string | boolean>>;
      if (typeof saved.name === 'string') setName(saved.name);
      if (typeof saved.email === 'string') setEmail(saved.email);
      if (typeof saved.language === 'string') setLanguage(saved.language);
      if (typeof saved.timezone === 'string') setTimezone(saved.timezone);
      if (typeof saved.retention === 'string') setRetention(saved.retention);
      if (typeof saved.cloudAllowed === 'boolean') setCloudAllowed(saved.cloudAllowed);
      if (typeof saved.emailNotifications === 'boolean') setEmailNotifications(saved.emailNotifications);
      if (typeof saved.desktopNotifications === 'boolean') setDesktopNotifications(saved.desktopNotifications);
    } catch { /* use defaults when local storage is unavailable */ }
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    localStorage.setItem('xelora-settings', JSON.stringify({ name, email, language, timezone, retention, cloudAllowed, emailNotifications, desktopNotifications }));
  }, [name, email, language, timezone, retention, cloudAllowed, emailNotifications, desktopNotifications]);
  const active = sections.find((item) => item.id === section)!;

  return <div className="space-y-6"><DashboardPageHeader eyebrow="Workspace settings" title="Settings" description="Control the way Xelora looks, works, and protects your information." />
    <div className="grid gap-6 xl:grid-cols-[255px_minmax(0,1fr)]">
      <aside className="h-fit rounded-xl border border-xelora-border bg-xelora-surface p-2 xl:sticky xl:top-6" aria-label="Settings sections">
        <div className="px-3 pb-3 pt-2"><p className="text-xs font-semibold uppercase tracking-[0.14em] text-xelora-text-muted">Preferences</p></div>
        <nav className="grid gap-1 sm:grid-cols-2 xl:grid-cols-1">{sections.map(({ id, label, description, icon: Icon }) => <button key={id} onClick={() => setSection(id)} className={cn('flex items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors', section === id ? 'bg-xelora-success-bg text-xelora-text' : 'text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text')}><Icon className={cn('mt-0.5 h-4 w-4 shrink-0', section === id ? 'text-xelora-green' : 'text-xelora-text-muted')} /><span><span className="block text-sm font-medium">{label}</span><span className="mt-0.5 block text-xs leading-4 text-xelora-text-muted">{description}</span></span></button>)}</nav>
      </aside>
      <section aria-labelledby="settings-panel-title"><Card className="overflow-hidden"><div className="border-b border-xelora-border px-5 py-5 sm:px-7"><div className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-xelora-success-bg text-xelora-green"><active.icon className="h-5 w-5" /></span><div><h2 id="settings-panel-title" className="font-semibold text-xelora-text">{active.label}</h2><p className="mt-0.5 text-sm text-xelora-text-secondary">{active.description}</p></div></div></div>
        <div className="px-5 sm:px-7">
          {section === 'profile' && <><div className="grid gap-5 py-6 md:grid-cols-2"><div><Label>Name</Label><Input className="mt-2" value={name} onChange={(event) => setName(event.target.value)} /></div><div><Label>Email address</Label><Input className="mt-2" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></div><div><Label>Language</Label><Select value={language} onValueChange={(value) => { setLanguage(value); toast.success('Language preference updated.'); }}><SelectTrigger className="mt-2"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="en">English</SelectItem><SelectItem value="fr">French</SelectItem><SelectItem value="de">German</SelectItem></SelectContent></Select></div><div><Label>Time zone</Label><Select value={timezone} onValueChange={(value) => { setTimezone(value); toast.success('Time zone updated.'); }}><SelectTrigger className="mt-2"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="africa-kigali">Africa/Kigali</SelectItem><SelectItem value="europe-london">Europe/London</SelectItem><SelectItem value="america-new-york">America/New York</SelectItem></SelectContent></Select></div></div><div className="border-t border-xelora-border py-5"><Button onClick={() => toast.success('Profile changes saved.')}>Save changes</Button></div></>}
          {section === 'appearance' && <div className="py-6"><p className="text-sm text-xelora-text-secondary">Choose a colour mode for this device. Your selection is saved automatically.</p><div className="mt-5 grid gap-3 md:grid-cols-3">{[{ value: 'light', label: 'Light', description: 'A crisp, bright workspace.', icon: Sun }, { value: 'dark', label: 'Dark', description: 'Comfortable in low-light rooms.', icon: Moon }, { value: 'system', label: 'System', description: 'Follows your device preference.', icon: Monitor }].map(({ value, label, description, icon: Icon }) => <button key={value} onClick={() => { setTheme(value); toast.success(`${label} theme selected.`); }} className={cn('rounded-xl border p-4 text-left transition-colors', theme === value ? 'border-xelora-green bg-xelora-success-bg ring-1 ring-xelora-green' : 'border-xelora-border bg-xelora-surface hover:border-xelora-border-strong')}><Icon className="h-5 w-5 text-xelora-green" /><p className="mt-5 font-medium text-xelora-text">{label}</p><p className="mt-1 text-xs leading-5 text-xelora-text-secondary">{description}</p>{theme === value && <p className="mt-4 text-xs font-medium text-xelora-green">Active{value === 'system' ? ` · ${resolvedTheme}` : ''}</p>}</button>)}</div></div>}
          {section === 'notifications' && <div className="divide-y divide-xelora-border"><SettingRow title="Email notifications" description="Receive important workspace, billing, and security updates by email."><Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} /></SettingRow><SettingRow title="Desktop notifications" description="Show task completion and approval alerts while Xelora Desktop is running."><Switch checked={desktopNotifications} onCheckedChange={setDesktopNotifications} /></SettingRow></div>}
          {section === 'security' && <><div className="grid gap-5 py-6 md:grid-cols-2"><div><Label>Current password</Label><Input className="mt-2" type="password" /></div><div><Label>New password</Label><Input className="mt-2" type="password" /></div></div><div className="border-t border-xelora-border py-5"><Button onClick={() => toast.success('Password updated.')}>Update password</Button></div></>}
          {section === 'privacy' && <div className="divide-y divide-xelora-border"><SettingRow title="File retention" description="Choose how long files remain available in your Xelora workspace."><Select value={retention} onValueChange={setRetention}><SelectTrigger className="w-full sm:w-36"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="7">7 days</SelectItem><SelectItem value="30">30 days</SelectItem><SelectItem value="90">90 days</SelectItem></SelectContent></Select></SettingRow><SettingRow title="Cloud processing" description="Allow workbook data to be processed through Xelora Cloud when local processing is unavailable."><Switch checked={cloudAllowed} onCheckedChange={setCloudAllowed} /></SettingRow></div>}
          {section === 'ai' && <><div className="grid gap-5 py-6 md:grid-cols-2"><div><Label>Default AI context</Label><Textarea className="mt-2 min-h-28" defaultValue="Use local workbook data only. Prefer concise explanations." /></div><div className="space-y-5"><div><Label>Explanation level</Label><Select defaultValue="detailed"><SelectTrigger className="mt-2"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="brief">Brief</SelectItem><SelectItem value="detailed">Detailed</SelectItem><SelectItem value="advanced">Advanced</SelectItem></SelectContent></Select></div><div><Label>Approval level</Label><Select defaultValue="standard"><SelectTrigger className="mt-2"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="standard">Standard</SelectItem><SelectItem value="strict">Always ask first</SelectItem></SelectContent></Select></div></div></div><div className="border-t border-xelora-border py-5"><Button onClick={() => toast.success('AI preferences saved.')}>Save AI preferences</Button></div></>}
          {section === 'cloud' && <div className="divide-y divide-xelora-border"><SettingRow title="Desktop sync" description="Keep your local desktop preferences aligned with this workspace."><Button variant="outline" onClick={() => toast.success('Desktop preferences synced.')}>Sync now</Button></SettingRow><SettingRow title="Account data" description="Download a portable copy of your account information."><Button variant="outline" onClick={() => toast.success('Your account data export is being prepared.')}><Download className="h-4 w-4" />Export data</Button></SettingRow><SettingRow title="Delete account" description="Permanently remove your workspace and associated data. This cannot be undone."><Button variant="ghost" className="text-xelora-error hover:bg-xelora-error-bg hover:text-xelora-error" onClick={() => toast.error('Account deletion requires confirmation.') }><Trash2 className="h-4 w-4" />Delete account</Button></SettingRow></div>}
        </div></Card></section>
    </div></div>;
}
