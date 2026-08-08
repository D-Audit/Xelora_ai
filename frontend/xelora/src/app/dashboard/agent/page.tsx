'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import {
  ArrowUp, Loader2, Pause, Play, Bot, User, AlertTriangle, ArrowUpRight,
  MonitorSpeaker, Plus, Paperclip, X, Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { isDesktopApp } from '@/lib/is-desktop';
import { useAuthStore } from '@/stores/auth-store';
import { startTask, getTaskProgress, pauseTask, resumeTask, getTaskReveal } from '@/services/agent';
import { uploadFile } from '@/services/workspace';
import type { TaskProgressResponse } from '@/services/agent';
import type { FileItem } from '@/services/workspace';

const POLL_INTERVAL_MS = 1500;

const QUICK_ACTIONS = [
  { label: 'Clean up data', instruction: 'Remove blank rows, trim whitespace, and delete duplicate rows in the active sheet.' },
  { label: 'Build a pivot table', instruction: 'Build a pivot table summarising the data by the most relevant category, then add a chart.' },
  { label: 'Add formulas', instruction: 'Add formulas to calculate totals and averages for the numeric columns.' },
  { label: 'Format the sheet', instruction: 'Apply consistent number, currency, and date formatting across the sheet.' },
];

type ChatMessage =
  | { id: string; role: 'user'; text: string; attachment?: string }
  | { id: string; role: 'agent'; taskId: number; steps: string[]; currentTask?: string; status: 'running' | 'paused' | 'done' | 'error'; error?: string };

export default function AgentPage() {
  // Client-only check - starts null (renders nothing) to avoid a
  // flash of the wrong state before we know if we're in the desktop
  // wrapper or a browser tab.
  const [desktop, setDesktop] = useState<boolean | null>(null);
  useEffect(() => setDesktop(isDesktopApp()), []);

  const user = useAuthStore((s) => s.user);

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [attachedFile, setAttachedFile] = useState<FileItem | null>(null);
  const [isAttaching, setIsAttaching] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const updateAgentMessage = (id: string, patch: Partial<Extract<ChatMessage, { role: 'agent' }>>) => {
    setMessages((current) =>
      current.map((m) => (m.id === id && m.role === 'agent' ? { ...m, ...patch } : m))
    );
  };

  const pollProgress = (messageId: string, taskId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data: TaskProgressResponse = await getTaskProgress(taskId);
        const stepNames = (data.completed_actions ?? []).map((s) => s.tool_name);
        updateAgentMessage(messageId, {
          steps: stepNames,
          currentTask: data.is_done ? undefined : data.current_task,
        });
        if (data.is_done) {
          if (pollRef.current) clearInterval(pollRef.current);
          updateAgentMessage(messageId, { status: 'done' });
          getTaskReveal(taskId).catch(() => null);
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        updateAgentMessage(messageId, { status: 'error', error: 'Lost connection while checking progress.' });
      }
    }, POLL_INTERVAL_MS);
  };

  const handleAttachClick = () => fileInputRef.current?.click();

  const handleFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setIsAttaching(true);
    try {
      const record = await uploadFile(file);
      setAttachedFile(record);
      toast.success(`${file.name} attached.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not attach the file.');
    } finally {
      setIsAttaching(false);
    }
  };

  const sendMessage = async (text: string) => {
    if (!text.trim() || isSending) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsgId = `u-${Date.now()}`;
    setMessages((current) => [...current, { id: userMsgId, role: 'user', text, attachment: attachedFile?.name }]);
    setIsSending(true);

    // The agent controls whichever Excel workbook is already open on
    // your machine - it doesn't read the uploaded file's bytes
    // directly. Attaching a file gives the AI context about it by
    // name and hints which open window to target if one shares that
    // name; open the file in Excel yourself for the agent to act on
    // it directly.
    const instruction = attachedFile
      ? `Regarding the file "${attachedFile.name}": ${text.trim()}`
      : text.trim();
    const workbookHint = attachedFile?.name;
    setAttachedFile(null);

    try {
      const res = await startTask(instruction, workbookHint);
      const agentMsgId = `a-${Date.now()}`;
      setMessages((current) => [
        ...current,
        { id: agentMsgId, role: 'agent', taskId: res.task_id, steps: [], status: 'running' },
      ]);
      pollProgress(agentMsgId, res.task_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not start the task.';
      // A 402/403 from the backend's plan-limit middleware lands here -
      // this is the real, server-enforced subscription protection,
      // shown inline in the chat rather than a silent failure.
      const agentMsgId = `a-${Date.now()}`;
      setMessages((current) => [
        ...current,
        { id: agentMsgId, role: 'agent', taskId: -1, steps: [], status: 'error', error: message },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handlePauseResume = async (msg: Extract<ChatMessage, { role: 'agent' }>) => {
    try {
      if (msg.status === 'running') {
        await pauseTask(msg.taskId);
        if (pollRef.current) clearInterval(pollRef.current);
        updateAgentMessage(msg.id, { status: 'paused' });
      } else if (msg.status === 'paused') {
        await resumeTask(msg.taskId);
        updateAgentMessage(msg.id, { status: 'running' });
        pollProgress(msg.id, msg.taskId);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not update the task.');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  // Not in the desktop app - this page is desktop-only. Avoid
  // rendering anything until we know for sure (desktop === null) to
  // prevent a flash of this message inside the real desktop app.
  if (desktop === false) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-xelora-surface-2">
          <MonitorSpeaker className="h-7 w-7 text-xelora-text-secondary" />
        </div>
        <h1 className="text-lg font-semibold text-xelora-text">AI Agent is a desktop feature</h1>
        <p className="max-w-md text-sm text-xelora-text-secondary">
          Running instructions against a live workbook needs the Xelora Desktop app, which talks
          to Excel directly on your machine. The web dashboard covers everything else - Workflows,
          Files, Billing, and more.
        </p>
        <Button asChild variant="outline">
          <Link href="/dashboard">
            Back to dashboard <ArrowUpRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>
    );
  }

  if (desktop === null) {
    return null;
  }

  const hasMessages = messages.length > 0;

  const attachmentChip = attachedFile && (
    <div className="mb-2 flex w-fit items-center gap-2 rounded-lg border border-xelora-border bg-xelora-surface-2 px-3 py-1.5 text-xs text-xelora-text">
      <Paperclip className="h-3.5 w-3.5 text-xelora-text-muted" />
      {attachedFile.name}
      <button onClick={() => setAttachedFile(null)} className="text-xelora-text-muted hover:text-xelora-text" aria-label="Remove attachment">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );

  const inputBar = (
    <div className="mx-auto w-full max-w-2xl">
      {attachmentChip}
      <div className="flex items-end gap-2 rounded-2xl border border-xelora-border bg-white p-2 shadow-sm focus-within:border-xelora-green">
        <input ref={fileInputRef} type="file" className="hidden" accept=".xlsx,.xls,.csv,.ods,.tsv" onChange={handleFileSelected} />
        <Button
          size="icon"
          variant="ghost"
          className="flex-shrink-0 rounded-full text-xelora-text-secondary"
          onClick={handleAttachClick}
          disabled={isAttaching}
          aria-label="Attach a file"
        >
          {isAttaching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
        </Button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); autoGrow(e.target); }}
          onKeyDown={handleKeyDown}
          placeholder="How can I help with your workbook?"
          rows={1}
          className="max-h-[200px] min-h-[28px] flex-1 resize-none bg-transparent px-1 py-1.5 text-sm text-xelora-text outline-none placeholder:text-xelora-text-muted"
        />
        <Button
          size="icon"
          onClick={() => sendMessage(input)}
          disabled={isSending || !input.trim()}
          className="flex-shrink-0 rounded-full"
        >
          {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </Button>
      </div>
      <p className="mt-2 text-center text-xs text-xelora-text-muted">
        Each message counts as one workflow run against your plan.
      </p>
    </div>
  );

  if (!hasMessages) {
    // Empty state: centered greeting + input, quick actions below -
    // shown once, before the first message.
    return (
      <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-6 px-4">
        <div className="flex flex-col items-center gap-3 text-center">
          <Sparkles className="h-8 w-8 text-xelora-green" />
          <h1 className="text-2xl font-semibold text-xelora-text">
            What would you like to do{user?.name ? `, ${user.name.split(' ')[0]}` : ''}?
          </h1>
        </div>
        {inputBar}
        <div className="flex flex-wrap justify-center gap-2">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.label}
              onClick={() => setInput(action.instruction)}
              className="rounded-full border border-xelora-border bg-white px-4 py-2 text-sm text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="-m-4 flex h-[calc(100vh-3.5rem)] flex-col sm:-m-6">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-2xl flex-col gap-6">
          {messages.map((msg) =>
            msg.role === 'user' ? (
              <div key={msg.id} className="flex justify-end gap-3">
                <div className="max-w-[85%] space-y-1.5">
                  {msg.attachment && (
                    <div className="ml-auto flex w-fit items-center gap-1.5 rounded-lg bg-white/15 px-2.5 py-1 text-xs text-white">
                      <Paperclip className="h-3 w-3" /> {msg.attachment}
                    </div>
                  )}
                  <div className="rounded-2xl rounded-tr-sm bg-xelora-green px-4 py-2.5 text-sm text-white">
                    {msg.text}
                  </div>
                </div>
                <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-xelora-surface-2">
                  <User className="h-4 w-4 text-xelora-text-secondary" />
                </div>
              </div>
            ) : (
              <div key={msg.id} className="flex gap-3">
                <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-xelora-success-bg">
                  <Bot className="h-4 w-4 text-xelora-green" />
                </div>
                <div className="max-w-[85%] flex-1 space-y-2">
                  {msg.status === 'error' ? (
                    <div className="flex items-start gap-2 rounded-2xl rounded-tl-sm border border-xelora-error/30 bg-xelora-error-bg px-4 py-3 text-sm">
                      <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-xelora-error" />
                      <div>
                        <p className="text-xelora-text">{msg.error}</p>
                        <Link href="/dashboard/billing/plans" className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-xelora-green hover:underline">
                          Upgrade plan <ArrowUpRight className="h-3 w-3" />
                        </Link>
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-2xl rounded-tl-sm bg-xelora-surface-2 px-4 py-3 text-sm">
                      {msg.steps.length === 0 && !msg.currentTask ? (
                        <p className="flex items-center gap-2 text-xelora-text-muted">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…
                        </p>
                      ) : (
                        <ul className="space-y-1.5">
                          {msg.steps.map((step, i) => (
                            <li key={i} className="flex items-center gap-2 text-xelora-text">
                              <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-xelora-green" />
                              {step}
                            </li>
                          ))}
                        </ul>
                      )}
                      {msg.status === 'running' && msg.currentTask && (
                        <p className="mt-2 flex items-center gap-2 text-xs text-xelora-text-muted">
                          <Loader2 className="h-3 w-3 animate-spin" /> {msg.currentTask}
                        </p>
                      )}
                      {msg.status === 'done' && (
                        <p className="mt-2 text-xs font-medium text-xelora-success">Done.</p>
                      )}
                      {msg.status === 'paused' && (
                        <p className="mt-2 text-xs font-medium text-xelora-warning">Paused.</p>
                      )}
                    </div>
                  )}
                  {(msg.status === 'running' || msg.status === 'paused') && (
                    <Button size="sm" variant="outline" onClick={() => handlePauseResume(msg)}>
                      {msg.status === 'running' ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                      {msg.status === 'running' ? 'Pause' : 'Resume'}
                    </Button>
                  )}
                </div>
              </div>
            )
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-xelora-border bg-white p-4">
        {inputBar}
      </div>
    </div>
  );
}
