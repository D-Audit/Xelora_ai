'use client';

/**
 * Connects Xelora Desktop's local agent (desktop/agent.js) to the signed-in
 * account. When the backend runs tasks on desktop agents (TASK_EXECUTION=agent),
 * the bridge pairs this PC once - or again when a different user signs in -
 * and keeps the agent running. The badge shows whether Excel tasks can run.
 */
import { useEffect, useState } from 'react';
import type { LocalAgentStatus } from '@/lib/is-desktop';

interface AgentLinkStatus {
  user_id: number;
  execution: 'server' | 'agent';
  online: boolean;
}

let syncing: Promise<void> | null = null;

async function syncLocalAgent(): Promise<void> {
  const agent = window.xeloraDesktop?.agent;
  if (!agent) return;

  const res = await fetch('/api/agent-link/status', { cache: 'no-store' });
  if (!res.ok) return;
  const cloud = (await res.json()) as AgentLinkStatus;
  if (cloud.execution !== 'agent') return; // tasks run on the backend itself

  const local = await agent.getStatus();
  if (local.paired && local.userId === String(cloud.user_id)) {
    if (local.state === 'stopped' || local.state === 'unpaired') await agent.start();
    return;
  }

  const pairRes = await fetch('/api/agent-link/pair', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: `Xelora Desktop (${window.xeloraDesktop?.platform ?? 'pc'})` }),
  });
  if (!pairRes.ok) return;
  const pair = (await pairRes.json()) as { token: string; token_id: number; api_url: string };
  await agent.pair({ apiUrl: pair.api_url, token: pair.token, tokenId: pair.token_id, userId: String(cloud.user_id) });
}

function requestSync() {
  syncing ??= syncLocalAgent()
    .catch(() => undefined)
    .finally(() => {
      syncing = null;
    });
  return syncing;
}

export function LocalAgentBridge() {
  useEffect(() => {
    const agent = window.xeloraDesktop?.agent;
    if (!agent) return;
    void requestSync();
    // Re-pair if the cloud rejects the token (the agent reports "unpaired").
    return agent.onChange((status) => {
      if (status.state === 'unpaired') void requestSync();
    });
  }, []);
  return null;
}

const LABELS: Record<LocalAgentStatus['state'], { text: string; tone: 'ok' | 'busy' | 'bad' }> = {
  running: { text: 'Excel agent connected', tone: 'ok' },
  starting: { text: 'Excel agent starting…', tone: 'busy' },
  stopped: { text: 'Excel agent stopped', tone: 'bad' },
  error: { text: 'Excel agent restarting…', tone: 'busy' },
  unpaired: { text: 'Excel agent not connected', tone: 'bad' },
  unavailable: { text: 'Excel agent unavailable', tone: 'bad' },
};

const DOT: Record<'ok' | 'busy' | 'bad', string> = {
  ok: 'bg-xelora-green',
  busy: 'bg-amber-500 animate-pulse',
  bad: 'bg-red-500',
};

export function LocalAgentBadge() {
  const [status, setStatus] = useState<LocalAgentStatus | null>(null);

  useEffect(() => {
    const agent = window.xeloraDesktop?.agent;
    if (!agent) return;
    void agent.getStatus().then(setStatus).catch(() => undefined);
    return agent.onChange(setStatus);
  }, []);

  // Nothing to show until this PC has been paired (server-mode installs never are).
  if (!status || (!status.paired && status.state === 'stopped')) return null;
  const label = LABELS[status.state];
  return (
    <span
      title={status.message || label.text}
      className="flex items-center gap-1.5 rounded-full border border-xelora-border bg-xelora-surface-2 px-3 py-1.5 text-xs font-medium text-xelora-text-secondary"
    >
      <span className={`h-2 w-2 rounded-full ${DOT[label.tone]}`} aria-hidden="true" />
      {label.text}
    </span>
  );
}
