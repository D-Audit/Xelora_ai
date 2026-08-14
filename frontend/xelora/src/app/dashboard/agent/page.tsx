'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  ArrowUp, Loader2, Pause, Play, Bot, User, AlertTriangle, ArrowUpRight,
  MonitorSpeaker, Plus, Paperclip, X, Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { isDesktopApp } from '@/lib/is-desktop';
import { useAuthStore } from '@/stores/auth-store';
import {
  startTask, getTaskProgress, pauseTask, resumeTask, getTaskReveal,
  getChat,
} from '@/services/agent';
import { uploadFile } from '@/services/workspace';
import type { TaskProgressResponse } from '@/services/agent';
import type { FileItem } from '@/services/workspace';
import type { ChatMessage } from '@/types/agent-chat';

const POLL_INTERVAL_MS = 1500;

const QUICK_ACTIONS = [
  { label: 'Clean up data', instruction: 'Remove blank rows, trim whitespace, and delete duplicate rows in the active sheet.' },
  { label: 'Build a pivot table', instruction: 'Build a pivot table summarising the data by the most relevant category, then add a chart.' },
  { label: 'Add formulas', instruction: 'Add formulas to calculate totals and averages for the numeric columns.' },
  { label: 'Format the sheet', instruction: 'Apply consistent number, currency, and date formatting across the sheet.' },
];

export default function AgentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [desktop, setDesktop] = useState<boolean | null>(null);
  useEffect(() => setDesktop(isDesktopApp()), []);

  const user = useAuthStore((s) => s.user);

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [attachedFile, setAttachedFile] = useState<FileItem | null>(null);
  const [isAttaching, setIsAttaching] = useState(false);
  const [isFloatingMode, setIsFloatingMode] = useState(false);
  useEffect(() => {
    if (!desktop) return;
    void window.xeloraDesktop?.getFloatingMode().then(setIsFloatingMode);
    return window.xeloraDesktop?.onFloatingModeChange(setIsFloatingMode);
  }, [desktop]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [currentTaskId, setCurrentTaskId] = useState<number | null>(null);

  const [openingChatId, setOpeningChatId] = useState<number | null>(null);
  const hydratedRouteRef = useRef<string | null>(null);
  const chatRequestRef = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const refreshChatList = () => window.dispatchEvent(new Event('xelora:chats-updated'));

  const updateAgentMessage = (id: string, patch: Partial<Extract<ChatMessage, { role: 'agent' }>>) => {
    setMessages((current) =>
      current.map((m) => (m.id === id && m.role === 'agent' ? { ...m, ...patch } : m))
    );
  };

  const pollProgress = (messageId: string, taskId: number) => {
    if (pollRef.current) clearInterval(pollRef.current);
    const checkProgress = async () => {
      try {
        const data: TaskProgressResponse = await getTaskProgress(taskId);
        const stepNames = (data.completed_actions ?? []).map((s) => s.tool_name);
        updateAgentMessage(messageId, {
          steps: stepNames,
          currentTask: data.is_done ? undefined : data.current_task,
          response: data.final_response ?? undefined,
        });
        if (data.is_done) {
          if (pollRef.current) clearInterval(pollRef.current);
          updateAgentMessage(messageId, { status: 'done', response: data.final_response ?? undefined });
          refreshChatList(); // this conversation just changed - refresh its entry (title/status) in the sidebar
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        updateAgentMessage(messageId, { status: 'error', error: 'Lost connection while checking progress.' });
      }
    };
    void checkProgress();
    pollRef.current = setInterval(() => { void checkProgress(); }, POLL_INTERVAL_MS);
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

  const startNewChat = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setCurrentTaskId(null);
    setMessages([]);
    setAttachedFile(null);
    setInput('');
  };

  const openChat = async (chatId: number) => {
    if (openingChatId !== null) return;
    hydratedRouteRef.current = `chat:${chatId}`;
    const requestId = ++chatRequestRef.current;
    setOpeningChatId(chatId);
    if (pollRef.current) clearInterval(pollRef.current);
    try {
      const chat = await getChat(chatId);
      const transcript = Array.isArray(chat.transcript) ? chat.transcript : [];
      const savedTurns = transcript.length > 0
        ? transcript
        : [{ role: 'user' as const, text: chat.instruction, timestamp: chat.created_at ?? new Date().toISOString() }];
      const restored: ChatMessage[] = savedTurns.map((turn, i) => (
        turn.role === 'user'
          ? { id: `${chatId}-${i}-u`, role: 'user', text: turn.text }
          : { id: `${chatId}-${i}-a`, role: 'agent', taskId: chatId, steps: [], response: turn.text, status: 'done' }
      ));
      if (requestId !== chatRequestRef.current) return;
      setMessages(restored);
      setCurrentTaskId(chat.resumable ? chat.id : null);
      if (!chat.resumable) {
        toast.info('This conversation ended in a previous session - sending a new message will start a fresh one.');
      }

      if (chat.resumable && transcript.every((turn) => turn.role !== 'assistant')) {
        try {
          const progress = await getTaskProgress(chatId);
          const recoveredResponse = progress.final_response;
          if (requestId !== chatRequestRef.current) return;
          setMessages((current) => [
            ...current,
            {
              id: `${chatId}-recovered-response`, role: 'agent', taskId: chatId,
              steps: (progress.completed_actions ?? []).map((step) => step.tool_name),
              currentTask: progress.is_done ? undefined : progress.current_task,
              response: recoveredResponse ?? undefined,
              status: progress.is_done ? 'done' : 'running',
            },
          ]);
          if (!progress.is_done && !progress.is_paused) {
            pollProgress(`${chatId}-recovered-response`, chatId);
          }
        } catch {
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Could not open that conversation.');
    } finally {
      setOpeningChatId(null);
    }
  };

  useEffect(() => {
    const chatId = Number(searchParams.get('chat'));
    if (Number.isInteger(chatId) && chatId > 0) {
      if (chatId === currentTaskId && messages.length > 0) {
        hydratedRouteRef.current = `chat:${chatId}`;
        return;
      }
      if (hydratedRouteRef.current === `chat:${chatId}`) return;
      openChat(chatId);
      return;
    }

    if (searchParams.get('new') === '1' && hydratedRouteRef.current !== 'new') {
      hydratedRouteRef.current = 'new';
      ++chatRequestRef.current;
      startNewChat();
    }
  }, [searchParams, currentTaskId, messages.length]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isSending || conversationBusy) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsgId = `u-${Date.now()}`;
    const agentMsgId = `a-${Date.now()}`;
    setMessages((current) => [
      ...current,
      { id: userMsgId, role: 'user', text, attachment: attachedFile?.name },
      { id: agentMsgId, role: 'agent', taskId: -1, steps: [], status: 'running' },
    ]);
    setIsSending(true);

    const requestedText = text.trim();
    const useOpenWorkbook = /^(use|work with|use data from) (your |the )?(own |existing )?(data|workbook|spreadsheet)$/i.test(requestedText);
    const instruction = attachedFile
      ? `Regarding the file "${attachedFile.name}": ${requestedText}`
      : useOpenWorkbook
        ? 'Use the data in the active Excel workbook already open on my computer. Inspect the workbook first, then continue the report requested above using its real data. Do not ask me to paste data unless no workbook or usable data is open.'
        : requestedText;
    const workbookHint = attachedFile?.name;
    setAttachedFile(null);

    try {
      if (currentTaskId !== null) {
        try {
          await resumeTask(currentTaskId, instruction);
          updateAgentMessage(agentMsgId, { taskId: currentTaskId, status: 'running' });
          pollProgress(agentMsgId, currentTaskId);
        } catch (err) {
          if (err instanceof Error && err.message.includes('still processing')) {
            throw err;
          }
          toast.info('That earlier session had ended - continuing as a new conversation.');
          const res = await startTask(instruction, workbookHint);
          setCurrentTaskId(res.task_id);
          hydratedRouteRef.current = `chat:${res.task_id}`;
          router.replace(`/dashboard/agent?chat=${res.task_id}`);
          updateAgentMessage(agentMsgId, { taskId: res.task_id, status: 'running' });
          pollProgress(agentMsgId, res.task_id);
        }
      } else {
        const res = await startTask(instruction, workbookHint);
        setCurrentTaskId(res.task_id);
        hydratedRouteRef.current = `chat:${res.task_id}`;
        router.replace(`/dashboard/agent?chat=${res.task_id}`);
        updateAgentMessage(agentMsgId, { taskId: res.task_id, status: 'running' });
        pollProgress(agentMsgId, res.task_id);
      }
      refreshChatList();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not start the task.';
      updateAgentMessage(agentMsgId, { status: 'error', error: message });
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
  const welcomeComposer = !hasMessages;
  const conversationBusy = messages.some(
    (message) => message.role === 'agent' && (message.status === 'running' || message.status === 'paused')
  );

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
    <div className={`mx-auto w-full ${welcomeComposer ? 'max-w-5xl' : 'max-w-3xl'}`}>
      {attachmentChip}
      <div className={`xelora-chat-composer flex items-end gap-2 border border-xelora-border bg-white p-3 shadow-sm ${welcomeComposer ? 'min-h-36 rounded-[28px]' : 'rounded-2xl p-2'}`}>
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
          placeholder={welcomeComposer ? 'How can Xelora help with your workbook today?' : 'Message Xelora…'}
          rows={welcomeComposer ? 3 : 1}
          className={`max-h-[200px] flex-1 resize-none bg-transparent px-2 py-2 text-xelora-text outline-none ring-0 focus:outline-none focus-visible:outline-none focus-visible:ring-0 placeholder:text-xelora-text-muted ${welcomeComposer ? 'min-h-24 text-lg' : 'min-h-[28px] text-sm'}`}
        />
        <Button
          size="icon"
          onClick={() => sendMessage(input)}
          disabled={isSending || conversationBusy || !input.trim()}
          className={`flex-shrink-0 rounded-full ${welcomeComposer ? 'h-11 w-11' : ''}`}
        >
          {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </Button>
      </div>
      <p className="mt-3 text-center text-xs text-xelora-text-muted">
        Excel is only changed when you explicitly ask for a workbook action.
      </p>
    </div>
  );

  const floatingModeButton = desktop && (
    <button
      onClick={() => void window.xeloraDesktop?.setFloatingMode(!isFloatingMode)}
      className="flex items-center gap-1.5 rounded-full border border-xelora-border bg-xelora-surface-2 px-3 py-1.5 text-xs font-medium text-xelora-text-secondary transition-colors hover:border-xelora-green/40 hover:text-xelora-green"
    >
      {isFloatingMode ? 'Exit Floating Mode' : 'Floating Mode'}
    </button>
  );
  const floatingWindowDragClass = isFloatingMode
    ? '[-webkit-app-region:drag] [&_a]:[-webkit-app-region:no-drag] [&_button]:[-webkit-app-region:no-drag] [&_input]:[-webkit-app-region:no-drag] [&_textarea]:[-webkit-app-region:no-drag] [&_select]:[-webkit-app-region:no-drag]'
    : '';

  if (!hasMessages) {
    return (
      <div className={`flex h-full flex-col items-center justify-center gap-8 px-6 pb-20 ${floatingWindowDragClass}`}>
          <div className="flex w-full max-w-5xl flex-col gap-4 text-left">
            <XeloraLogo size="lg" showWordmark={false} />
            <h1 className="max-w-4xl text-4xl font-semibold tracking-[-0.035em] text-xelora-text sm:text-5xl">
              What can we build together{user?.name ? `, ${user.name.split(' ')[0]}` : ''}?
            </h1>
          </div>
          <div className="flex w-full max-w-5xl items-center justify-end">
            {floatingModeButton}
          </div>
          {inputBar}
          <div className="flex w-full max-w-5xl flex-wrap gap-2">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.label}
                onClick={() => setInput(action.instruction)}
                className="rounded-lg border border-xelora-border bg-white px-4 py-2.5 text-sm font-medium text-xelora-text-secondary transition-colors hover:border-xelora-green/40 hover:bg-xelora-success-bg hover:text-xelora-green"
              >
                {action.label}
              </button>
            ))}
          </div>
      </div>
    );
  }

  return (
    <div className={`flex h-full flex-col ${floatingWindowDragClass}`}>
        <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-xelora-border px-5">
          <div className="flex items-center gap-2 text-sm font-medium text-xelora-text"><Sparkles className="h-4 w-4 text-xelora-green" /> Xelora</div>
          <span className="ml-2 text-sm text-xelora-text-muted">
            {currentTaskId !== null ? `Conversation #${currentTaskId}` : 'New task'}
          </span>
          <div className="ml-auto flex items-center gap-2">
            {floatingModeButton}
          </div>
        </header>
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="mx-auto flex max-w-3xl flex-col gap-7">
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
                        {msg.steps.length === 0 && !msg.currentTask && msg.status === 'running' ? (
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
                          <>
                            {msg.response && <p className="mt-3 whitespace-pre-wrap text-xelora-text">{msg.response}</p>}
                            <p className="mt-2 text-xs font-medium text-xelora-success">Done.</p>
                          </>
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

        <div className="border-t border-xelora-border bg-[#fcfcfb] p-4">
          {inputBar}
        </div>
    </div>
  );
}
