'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  ArrowUp, Check, ChevronDown, CircleAlert, CircleCheck, FileSpreadsheet, Filter, Loader2, ListChecks, Maximize2,
  Menu, MonitorSmartphone, Paintbrush, Pause, Paperclip, PictureInPicture2, Play, RotateCw, Sigma, Table2, TriangleAlert, X,
} from 'lucide-react';
import { XeloraLogo } from '@/components/ui/xelora-logo';
import { useIsDesktop } from '@/lib/is-desktop';
import { LocalAgentBadge } from '@/components/desktop/local-agent';
import { useAuthStore } from '@/stores/auth-store';
import { useUIStore } from '@/stores/ui-store';
import { Markdown } from '@/components/chat/markdown';
import {
  startTask, quickChatStream, getTaskProgress, pauseTask, resumeTask,
  getChat,
} from '@/services/agent';
import { uploadFile } from '@/services/workspace';
import type { QuickChatResponse, TaskProgressResponse } from '@/services/agent';
import type { FileItem } from '@/services/workspace';
import type { ChatMessage } from '@/types/agent-chat';

const POLL_INTERVAL_MS = 1500;

const ACTION_LABELS: Record<string, string> = {
  create_new_workbook: 'Creating a new Excel workbook',
  create_sheet: 'Adding a worksheet',
  rename_sheet: 'Renaming a worksheet',
  write_cell: 'Writing to a cell',
  write_table: 'Writing a data table',
  insert_formula: 'Calculating with an Excel formula',
  apply_formatting: 'Applying workbook formatting',
  conditional_formatting: 'Applying conditional formatting',
  freeze_panes: 'Freezing header rows or columns',
  auto_fit_columns: 'Sizing columns to fit the content',
  create_chart: 'Creating an Excel chart',
  create_pivot_table: 'Creating a PivotTable',
  activate_ribbon_tab: 'Opening the requested Excel tab',
  go_to_range: 'Selecting the requested cell or range',
  hotkey: 'Using an Excel keyboard shortcut',
  press_key: 'Using an Excel key command',
  type_text: 'Entering information in Excel',
  parse_screen: 'Checking the relevant Excel area',
  click: 'Selecting an Excel control',
  double_click: 'Opening an Excel control',
  scroll: 'Navigating Excel',
};

function actionLabel(toolName: string) {
  return ACTION_LABELS[toolName] ?? 'Completing an Excel action';
}

const QUICK_ACTIONS = [
  { icon: Filter, label: 'Clean up my data', instruction: 'Remove blank rows, trim extra spaces and delete duplicate rows in the active sheet.' },
  { icon: Table2, label: 'Summarise with a pivot table', instruction: 'Build a pivot table that summarises the data by the most useful category, then add a chart.' },
  { icon: Sigma, label: 'Add totals and averages', instruction: 'Add formulas that calculate totals and averages for the numeric columns.' },
  { icon: Paintbrush, label: 'Format it as a report', instruction: 'Format the sheet as a clean report: bold headers, consistent number, currency and date formats, and fitted columns.' },
];

export default function AgentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const desktop = useIsDesktop();

  const user = useAuthStore((s) => s.user);

  // Onboarding links here with ?prompt= to start from an example request.
  const [input, setInput] = useState(() => searchParams.get('prompt') ?? '');
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
  const sendCountRef = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // Start a sleeping backend booting while the user is still typing.
  useEffect(() => { void fetch('/api/warm', { method: 'POST' }).catch(() => {}); }, []);

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
        const stepNames = (data.completed_actions ?? []).map((s) => actionLabel(s.tool_name));
        const checkpointSteps = (data.visual_checkpoints ?? []).map(
          (checkpoint) => `Capturing a visible Excel checkpoint after ${actionLabel(checkpoint.after_tool).toLowerCase()}`
        );
        updateAgentMessage(messageId, {
          steps: [...stepNames, ...checkpointSteps],
          currentTask: data.is_done ? undefined : data.current_task,
          waitingForDesktop: !data.is_done && data.recovery?.phase === 'waiting_for_agent',
          response: data.final_response ?? undefined,
        });
        if (data.is_done) {
          if (pollRef.current) clearInterval(pollRef.current);
          updateAgentMessage(messageId, {
            status: 'done',
            response: data.final_response ?? undefined,
            completionStatus: data.status,
            ...(data.status === 'answered' ? { kind: 'chat' as const, sources: data.sources ?? [] } : {}),
          });
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
          : {
              id: `${chatId}-${i}-a`, role: 'agent', taskId: chatId, steps: [],
              response: turn.text, status: 'done', completionStatus: chat.status,
              ...(turn.kind === 'chat' ? { kind: 'chat' as const, sources: turn.sources ?? [] } : {}),
            }
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
              steps: (progress.completed_actions ?? []).map((step) => actionLabel(step.tool_name)),
              currentTask: progress.is_done ? undefined : progress.current_task,
              response: recoveredResponse ?? undefined,
              status: progress.is_done ? 'done' : 'running',
              completionStatus: progress.is_done ? progress.status : undefined,
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

  const sendMessage = async (text: string, attachment: FileItem | null = attachedFile) => {
    if (!text.trim() || isSending || conversationBusy) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const sendId = ++sendCountRef.current;
    const userMsgId = `u-${sendId}`;
    const agentMsgId = `a-${sendId}`;
    setMessages((current) => [
      ...current,
      { id: userMsgId, role: 'user', text, attachment: attachment?.name },
      { id: agentMsgId, role: 'agent', taskId: -1, steps: [], status: 'running' },
    ]);
    setIsSending(true);

    const requestedText = text.trim();
    const useOpenWorkbook = /^(use|work with|use data from) (your |the )?(own |existing )?(data|workbook|spreadsheet)$/i.test(requestedText);
    const instruction = attachment
      ? `Regarding the file "${attachment.name}": ${requestedText}`
      : useOpenWorkbook
        ? 'Use the data in the active Excel workbook already open on my computer. Inspect the workbook first, then continue the report requested above using its real data. Do not ask me to paste data unless no workbook or usable data is open.'
        : requestedText;
    const workbookHint = attachment?.name;
    const retry = { text, attachment: attachment ?? undefined };
    setAttachedFile(null);

    // A sleeping backend (Render's free plan) can take a while to answer the
    // first message; say so instead of showing a spinner that looks stuck.
    let heardBack = false;
    const wakeTimer = window.setTimeout(() => {
      if (!heardBack) updateAgentMessage(agentMsgId, { currentTask: 'Connecting to Xelora. The first message after a quiet spell can take up to a minute' });
    }, 6000);

    try {
      // The backend decides: questions get a quick answer (searching the web
      // when needed) and only workbook requests start an Excel task. A failed
      // answer is shown as an error with Retry; it never becomes an Excel task.
      let quick: QuickChatResponse;
      try {
        quick = await quickChatStream(requestedText, {
          workbookName: workbookHint,
          hasWorkbookContext: currentTaskId !== null,
          taskId: currentTaskId,
          // Failed exchanges (and a retried one still on screen) are not context.
          history: messages
            .filter((m, i) => {
              const reply = m.role === 'user' ? messages[i + 1] : m;
              return !(reply?.role === 'agent' && reply.status === 'error');
            })
            .slice(-12)
            .flatMap((m): { role: 'user' | 'assistant'; text: string }[] =>
              m.role === 'user'
                ? [{ role: 'user', text: m.text }]
                : m.response ? [{ role: 'assistant', text: m.response }] : []),
        }, {
          onRoute: (route) => {
            heardBack = true;
            updateAgentMessage(agentMsgId, route === 'chat'
              ? { kind: 'chat', currentTask: undefined }
              : { kind: 'task', currentTask: 'Getting your Excel task ready' });
          },
          onStatus: (status) => {
            heardBack = true;
            updateAgentMessage(agentMsgId, { currentTask: status });
          },
        });
      } finally {
        heardBack = true;
        window.clearTimeout(wakeTimer);
      }

      if (quick.route === 'chat') {
        if (quick.failed || !quick.reply) {
          updateAgentMessage(agentMsgId, {
            status: 'error', currentTask: undefined, retry,
            error: quick.reply || 'Xelora could not answer just now. Please try again.',
          });
          return;
        }
        updateAgentMessage(agentMsgId, {
          status: 'done', kind: 'chat', currentTask: undefined, response: quick.reply, sources: quick.sources ?? [],
        });
        if (quick.task_id) {
          // Saved to chat history: keep this conversation open so follow-ups continue it.
          if (currentTaskId !== quick.task_id) {
            setCurrentTaskId(quick.task_id);
            hydratedRouteRef.current = `chat:${quick.task_id}`;
            router.replace(`/dashboard/agent?chat=${quick.task_id}`);
          }
          refreshChatList();
        }
        return;
      }

      if (currentTaskId !== null) {
        try {
          await resumeTask(currentTaskId, instruction, true);
          updateAgentMessage(agentMsgId, { taskId: currentTaskId, status: 'running' });
          pollProgress(agentMsgId, currentTaskId);
        } catch (err) {
          if (err instanceof Error && err.message.includes('still processing')) {
            throw err;
          }
          toast.info('That earlier session had ended - continuing as a new conversation.');
          const res = await startTask(instruction, workbookHint, true);
          setCurrentTaskId(res.task_id);
          hydratedRouteRef.current = `chat:${res.task_id}`;
          router.replace(`/dashboard/agent?chat=${res.task_id}`);
          updateAgentMessage(agentMsgId, { taskId: res.task_id, status: 'running' });
          pollProgress(agentMsgId, res.task_id);
        }
      } else {
        const res = await startTask(instruction, workbookHint, true);
        setCurrentTaskId(res.task_id);
        hydratedRouteRef.current = `chat:${res.task_id}`;
        router.replace(`/dashboard/agent?chat=${res.task_id}`);
        updateAgentMessage(agentMsgId, { taskId: res.task_id, status: 'running' });
        pollProgress(agentMsgId, res.task_id);
      }
      refreshChatList();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not start the task.';
      updateAgentMessage(agentMsgId, { status: 'error', error: message, currentTask: undefined, retry });
    } finally {
      setIsSending(false);
    }
  };

  /** Drop a failed exchange and send the same message again. */
  const retryMessage = (msg: Extract<ChatMessage, { role: 'agent' }>) => {
    if (!msg.retry || isSending || conversationBusy) return;
    const { text, attachment } = msg.retry;
    setMessages((current) => {
      const index = current.findIndex((m) => m.id === msg.id);
      const before = index > 0 && current[index - 1].role === 'user' ? index - 1 : index;
      return index < 0 ? current : [...current.slice(0, before), ...current.slice(index + 1)];
    });
    void sendMessage(text, attachment ?? null);
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

  const hasMessages = messages.length > 0;
  const conversationBusy = messages.some(
    (message) => message.role === 'agent' && (message.status === 'running' || message.status === 'paused')
  );
  const firstUserText = messages.find((message) => message.role === 'user')?.text;
  const greetingName = user?.name?.split(' ')[0];

  const composer = (
    <div className="mx-auto w-full max-w-3xl">
      <div className="xelora-chat-composer rounded-2xl border border-xelora-border bg-xelora-surface shadow-sm transition-colors">
        {attachedFile && (
          <div className="px-3 pt-3">
            <span className="inline-flex items-center gap-2 rounded-lg border border-xelora-border bg-xelora-surface-2 px-2.5 py-1.5 text-xs text-xelora-text">
              <FileSpreadsheet className="h-3.5 w-3.5 text-xelora-green" />
              {attachedFile.name}
              <button onClick={() => setAttachedFile(null)} className="text-xelora-text-muted hover:text-xelora-text" aria-label="Remove attachment">
                <X className="h-3.5 w-3.5" />
              </button>
            </span>
          </div>
        )}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => { setInput(e.target.value); autoGrow(e.target); }}
          onKeyDown={handleKeyDown}
          placeholder={hasMessages ? 'Reply to Xelora…' : 'Ask a question or describe a spreadsheet task…'}
          rows={hasMessages ? 1 : 2}
          aria-label="Message Xelora"
          className="block max-h-[220px] w-full resize-none bg-transparent px-4 pt-3.5 text-[15px] leading-6 text-xelora-text outline-none placeholder:text-xelora-text-muted"
        />
        <div className="flex items-center justify-between px-2.5 pb-2.5 pt-1">
          <input ref={fileInputRef} type="file" className="hidden" accept=".xlsx,.xls,.csv,.ods,.tsv" onChange={handleFileSelected} />
          <button
            type="button"
            onClick={handleAttachClick}
            disabled={isAttaching}
            className="flex h-8 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2 hover:text-xelora-text disabled:opacity-50"
            aria-label="Attach a spreadsheet"
          >
            {isAttaching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
            <span className="hidden sm:inline">Attach file</span>
          </button>
          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={isSending || conversationBusy || !input.trim()}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-xelora-text text-xelora-surface transition-opacity hover:opacity-90 disabled:opacity-30"
            aria-label="Send message"
          >
            {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-xelora-text-muted">
        Xelora can make mistakes. Check important results.
      </p>
    </div>
  );

  const floatingModeButton = desktop && (
    <button
      onClick={() => void window.xeloraDesktop?.setFloatingMode(!isFloatingMode)}
      className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium text-xelora-text-secondary transition-colors hover:bg-xelora-surface-2 hover:text-xelora-text"
      title={isFloatingMode ? 'Return to the full window' : 'Keep Xelora in a small window on top of Excel'}
    >
      {isFloatingMode ? <Maximize2 className="h-3.5 w-3.5" /> : <PictureInPicture2 className="h-3.5 w-3.5" />}
      {isFloatingMode ? 'Full window' : 'Float over Excel'}
    </button>
  );
  const floatingWindowDragClass = isFloatingMode
    ? '[-webkit-app-region:drag] [&_a]:[-webkit-app-region:no-drag] [&_button]:[-webkit-app-region:no-drag] [&_input]:[-webkit-app-region:no-drag] [&_textarea]:[-webkit-app-region:no-drag] [&_select]:[-webkit-app-region:no-drag]'
    : '';

  const header = (
    <header className="flex h-12 flex-shrink-0 items-center gap-2 px-4">
      <button
        onClick={() => useUIStore.getState().toggleSidebar()}
        className="flex h-8 w-8 items-center justify-center rounded-lg text-xelora-text-secondary hover:bg-xelora-surface-2 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>
      <p className="min-w-0 truncate text-sm font-medium text-xelora-text">
        {firstUserText ? firstUserText : ''}
      </p>
      <div className="ml-auto flex items-center gap-1.5">
        {desktop ? <LocalAgentBadge /> : <DesktopConnection />}
        {floatingModeButton}
      </div>
    </header>
  );

  if (!hasMessages) {
    return (
      <div className={`flex h-full flex-col ${floatingWindowDragClass}`}>
        {header}
        <div className="flex flex-1 flex-col items-center justify-center px-4 pb-24">
          <div className="w-full max-w-3xl">
            <h1 className="mb-8 text-center text-3xl font-semibold tracking-tight text-xelora-text">
              {openingChatId !== null ? 'Opening conversation…' : `What can I help with${greetingName ? `, ${greetingName}` : ''}?`}
            </h1>
            {composer}
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.label}
                  onClick={() => { setInput(action.instruction); textareaRef.current?.focus(); }}
                  className="flex items-center gap-3 rounded-xl border border-xelora-border px-4 py-3 text-left text-sm text-xelora-text-secondary transition-colors hover:border-xelora-border-strong hover:bg-xelora-surface-2 hover:text-xelora-text"
                >
                  <action.icon className="h-4 w-4 shrink-0 text-xelora-text-muted" strokeWidth={1.75} />
                  {action.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex h-full flex-col ${floatingWindowDragClass}`}>
      {header}
      <div className="flex-1 overflow-y-auto px-4">
        <div className="mx-auto flex max-w-3xl flex-col gap-8 pb-10 pt-6">
          {messages.map((msg) =>
            msg.role === 'user' ? (
              <div key={msg.id} className="flex flex-col items-end gap-1.5">
                {msg.attachment && (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-xelora-border px-2.5 py-1 text-xs text-xelora-text-secondary">
                    <FileSpreadsheet className="h-3.5 w-3.5 text-xelora-green" /> {msg.attachment}
                  </span>
                )}
                <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl bg-xelora-surface-2 px-4 py-2.5 text-[15px] leading-7 text-xelora-text">
                  {msg.text}
                </div>
              </div>
            ) : (
              <AgentReply key={msg.id} msg={msg} onPauseResume={() => void handlePauseResume(msg)} onRetry={() => retryMessage(msg)} />
            )
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="px-4 pb-4">{composer}</div>
    </div>
  );
}

const STATUS_LINES: Record<string, { icon: typeof CircleCheck; text: string; tone: string }> = {
  completed: { icon: CircleCheck, text: 'Done and verified in Excel', tone: 'text-xelora-green' },
  completed_with_warnings: { icon: TriangleAlert, text: 'Done with warnings. Review the result before relying on it.', tone: 'text-xelora-warning' },
  awaiting_approval: { icon: ListChecks, text: 'Plan ready. Reply “Confirm” to apply it, or tell me what to change.', tone: 'text-xelora-text-secondary' },
  failed: { icon: CircleAlert, text: 'Not completed. Nothing unverified was marked as done.', tone: 'text-xelora-error' },
};

/** "Searching the web" -> "Searching the web…"; full sentences keep their punctuation. */
function liveText(text: string) {
  return /[.!?…:]$/.test(text) ? text : `${text}…`;
}

/** Seconds spent on the current step, shown once it is no longer instant. Remount (key) to restart. */
function Elapsed() {
  const [started] = useState(() => Date.now());
  const [now, setNow] = useState(started);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.floor((now - started) / 1000);
  if (seconds < 3) return null;
  return (
    <span className="shrink-0 tabular-nums text-xelora-text-muted">
      {seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`}
    </span>
  );
}

function AgentReply({ msg, onPauseResume, onRetry }: {
  msg: Extract<ChatMessage, { role: 'agent' }>;
  onPauseResume: () => void;
  onRetry: () => void;
}) {
  const desktop = useIsDesktop();
  const [stepsOpen, setStepsOpen] = useState(false);
  const running = msg.status === 'running';
  const hasSteps = msg.steps.length > 0;
  // Excel work gets the steps card; a quick answer (or a message not yet routed) a single status line.
  const excelWork = msg.kind !== 'chat' && (msg.kind === 'task' || msg.taskId > 0);
  const showCard = excelWork && (hasSteps || (running && Boolean(msg.currentTask)));
  // The notice below explains the wait; the card just names it.
  const cardStatus = msg.waitingForDesktop ? 'Waiting for Xelora Desktop' : msg.currentTask;
  const status = msg.status === 'done' && msg.kind !== 'chat' ? STATUS_LINES[msg.completionStatus ?? ''] : undefined;
  const limitError = msg.status === 'error' && /limit|plan|upgrade|quota/i.test(msg.error ?? '');

  return (
    <div className="flex gap-3">
      <XeloraLogo size="sm" showWordmark={false} className="mt-1 h-6 w-6 shrink-0" />
      <div className="min-w-0 flex-1 space-y-3">
        {msg.status === 'error' ? (
          <div className="flex items-start gap-2 rounded-xl border border-xelora-error/20 bg-xelora-error-bg px-4 py-3 text-sm text-xelora-text">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-xelora-error" />
            <div className="min-w-0 flex-1">
              <p>{msg.error}</p>
              {limitError && (
                <Link href="/dashboard/billing/plans" className="mt-1 inline-block text-xs font-medium text-xelora-green hover:underline">
                  View plans
                </Link>
              )}
              {msg.retry && !limitError && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="mt-2 flex h-7 items-center gap-1.5 rounded-lg border border-xelora-border bg-xelora-surface px-2.5 text-xs font-medium text-xelora-text-secondary hover:text-xelora-text"
                >
                  <RotateCw className="h-3 w-3" /> Try again
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {showCard && (
              <div className="rounded-xl border border-xelora-border">
                <button
                  type="button"
                  onClick={() => setStepsOpen((open) => !open)}
                  className="flex w-full items-center gap-2 px-3.5 py-2.5 text-left text-sm text-xelora-text-secondary"
                  aria-expanded={stepsOpen || running}
                >
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Table2 className="h-4 w-4" strokeWidth={1.75} />}
                  <span className="min-w-0 flex-1 truncate">
                    {running ? liveText(cardStatus || 'Working in Excel') : `Worked in Excel · ${msg.steps.length} ${msg.steps.length === 1 ? 'step' : 'steps'}`}
                  </span>
                  {running && <Elapsed key={cardStatus ?? ''} />}
                  {hasSteps && <ChevronDown className={`h-4 w-4 transition-transform ${stepsOpen || running ? 'rotate-180' : ''}`} />}
                </button>
                {hasSteps && (stepsOpen || running) && (
                  <ol className="space-y-1.5 border-t border-xelora-border px-3.5 py-3">
                    {msg.steps.map((step, index) => (
                      <li key={index} className="flex items-start gap-2 text-sm text-xelora-text-secondary">
                        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-xelora-green" /> {step}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
            {running && msg.waitingForDesktop && (
              <div className="flex items-start gap-2 rounded-xl border border-xelora-warning/30 bg-xelora-warning-bg px-3.5 py-3 text-sm text-xelora-text-secondary">
                <MonitorSmartphone className="mt-0.5 h-4 w-4 shrink-0 text-xelora-warning" />
                <div className="min-w-0">
                  <p>Excel work runs in Xelora Desktop on your Windows PC, and it isn’t connected right now. Open it and sign in; this task starts there automatically.</p>
                  {!desktop && (
                    <Link href="/download" className="mt-1 inline-block text-xs font-medium text-xelora-green hover:underline">
                      Get Xelora Desktop
                    </Link>
                  )}
                </div>
              </div>
            )}
            {running && !showCard && (
              <p className="flex items-center gap-2 text-sm text-xelora-text-muted">
                <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
                <span className="min-w-0 truncate">{liveText(msg.currentTask || 'Thinking')}</span>
                <Elapsed key={msg.currentTask ?? ''} />
              </p>
            )}
            {msg.status === 'done' && msg.response && <Markdown text={msg.response} sources={msg.sources ?? []} />}
            {msg.sources && msg.sources.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {msg.sources.map((source) => (
                  <a
                    key={source.n}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    title={source.url}
                    className="flex max-w-[260px] items-center gap-1.5 rounded-lg border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-text-secondary transition-colors hover:border-xelora-border-strong hover:text-xelora-text"
                  >
                    <span className="font-medium text-xelora-text-muted">{source.n}</span>
                    <span className="truncate">{source.title || new URL(source.url).hostname}</span>
                  </a>
                ))}
              </div>
            )}
            {status && (
              <p className={`flex items-center gap-1.5 text-xs font-medium ${status.tone}`}>
                <status.icon className="h-3.5 w-3.5" /> {status.text}
              </p>
            )}
            {msg.status === 'paused' && <p className="text-xs font-medium text-xelora-warning">Paused</p>}
          </>
        )}
        {msg.taskId > 0 && (msg.status === 'running' || msg.status === 'paused') && (
          <button
            type="button"
            onClick={onPauseResume}
            className="flex h-7 items-center gap-1.5 rounded-lg border border-xelora-border px-2.5 text-xs font-medium text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text"
          >
            {msg.status === 'running' ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
            {msg.status === 'running' ? 'Pause' : 'Resume'}
          </button>
        )}
      </div>
    </div>
  );
}

/** For the web app: whether Xelora Desktop is online to run Excel tasks. */
function DesktopConnection() {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    let cancelled = false;
    const check = () => fetch('/api/agent-link/status', { cache: 'no-store' })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => { if (!cancelled) setOnline(data ? Boolean(data.online) : null); })
      .catch(() => undefined);
    void check();
    const timer = window.setInterval(check, 30000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);
  if (online === null) return null;
  return online ? (
    <span className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs text-xelora-text-secondary" title="Excel tasks will run on your PC">
      <span className="h-1.5 w-1.5 rounded-full bg-xelora-green" /> Desktop connected
    </span>
  ) : (
    <Link
      href="/download"
      className="flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs text-xelora-text-secondary hover:bg-xelora-surface-2 hover:text-xelora-text"
      title="Excel tasks run in Xelora Desktop on your Windows PC"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-xelora-text-muted" /> Desktop offline
    </Link>
  );
}
