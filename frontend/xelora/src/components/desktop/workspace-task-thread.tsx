'use client';
import { useState, useRef, useEffect } from 'react';
import { Loader2, CheckCircle2, Circle, ChevronDown, ChevronRight, Pause, Square, ArrowRight, CheckCheck, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatRelativeTime } from '@/lib/utils';
import { toast } from 'sonner';
import type { DesktopTask, TaskMessage, TaskStep } from './types';

interface Props {
  task: DesktopTask;
  tasks: DesktopTask[];
  setTasks: React.Dispatch<React.SetStateAction<DesktopTask[]>>;
  setActiveTask: (t: DesktopTask | null) => void;
  onOpenSpreadsheet: (name: string) => void;
}

export function TaskThreadWorkspace({ task, tasks, setTasks, setActiveTask, onOpenSpreadsheet }: Props) {
  const [input, setInput] = useState('');
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [task.messages.length]);

  const updateTaskStatus = (status: DesktopTask['status']) => {
    setTasks(prev => prev.map(t => t.id === task.id ? { ...t, status } : t));
    setActiveTask({ ...task, status });
  };

  const toggleStep = (id: string) => {
    setExpandedSteps(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleApprove = () => {
    toast.success('Approved — Xelora will continue the workflow.');
    updateTaskStatus('running');
  };

  const handleSend = () => {
    if (!input.trim()) return;
    toast.info('Follow-up instruction noted. In a connected app, Xelora would continue the task.');
    setInput('');
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Thread header */}
      <div className="flex items-center justify-between border-b border-xelora-border px-5 py-3 shrink-0">
        <div>
          <p className="text-sm font-semibold text-xelora-text">{task.title}</p>
          <p className="text-xs text-xelora-text-muted">{task.workbook}</p>
        </div>
        <div className="flex gap-2">
          {task.status === 'running' && (
            <>
              <button onClick={() => { updateTaskStatus('paused'); toast.info('Workflow paused.'); }}
                className="flex items-center gap-1.5 rounded-md border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors">
                <Pause className="h-3.5 w-3.5" />Pause
              </button>
              <button onClick={() => { updateTaskStatus('cancelled'); toast.error('Workflow stopped.'); }}
                className="flex items-center gap-1.5 rounded-md border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-error hover:bg-xelora-error-bg transition-colors">
                <Square className="h-3.5 w-3.5" />Stop
              </button>
            </>
          )}
          <button onClick={() => onOpenSpreadsheet(task.workbook)}
            className="flex items-center gap-1.5 rounded-md border border-xelora-border px-2.5 py-1.5 text-xs text-xelora-text-secondary hover:bg-xelora-surface-2 transition-colors">
            View Workbook
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
        {task.messages.map(msg => (
          <MessageBubble
            key={msg.id}
            message={msg}
            expandedSteps={expandedSteps}
            onToggleStep={toggleStep}
            onApprove={handleApprove}
            onKeepAll={() => { updateTaskStatus('running'); toast.info('All rows kept — continuing.'); }}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-xelora-border px-4 py-3 shrink-0">
        <div className="flex gap-2 items-end">
          <div className="flex-1 rounded-lg border border-xelora-border bg-xelora-surface-2 px-3 py-2">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
              placeholder="Give Xelora a follow-up instruction…"
              rows={1}
              className="w-full resize-none bg-transparent text-sm text-xelora-text placeholder:text-xelora-text-muted focus:outline-none"
            />
          </div>
          <button onClick={handleSend} disabled={!input.trim()}
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-xelora-green text-white hover:bg-xelora-deep-green disabled:opacity-40 transition-colors">
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message, expandedSteps, onToggleStep, onApprove, onKeepAll }: {
  message: TaskMessage;
  expandedSteps: Set<string>;
  onToggleStep: (id: string) => void;
  onApprove: () => void;
  onKeepAll: () => void;
}) {
  const isUser = message.role === 'user';
  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('max-w-[85%] rounded-xl px-4 py-3', isUser ? 'bg-xelora-nav text-white' : 'bg-xelora-surface-2 text-xelora-text')}>
        {!isUser && <p className="text-[10px] font-semibold text-xelora-green mb-1 uppercase tracking-wider">Xelora AI</p>}
        <p className="text-sm leading-relaxed">{message.content}</p>
        <p className="text-[10px] mt-1 opacity-50">{formatRelativeTime(message.timestamp)}</p>

        {/* Workflow steps */}
        {message.steps && message.steps.length > 0 && (
          <div className="mt-4 space-y-1">
            <p className="text-xs font-semibold text-xelora-text-secondary mb-2">Workflow plan</p>
            {message.steps.map((step, i) => (
              <StepRow key={step.id} step={step} index={i} expanded={expandedSteps.has(step.id)} onToggle={() => onToggleStep(step.id)} />
            ))}
            {message.steps.some(s => s.status === 'pending') && (
              <div className="mt-3 flex gap-2">
                <button onClick={onApprove} className="flex items-center gap-1.5 rounded-md bg-xelora-green px-3 py-1.5 text-xs font-medium text-white hover:bg-xelora-deep-green transition-colors">
                  <CheckCheck className="h-3.5 w-3.5" />Run Workflow
                </button>
                <button onClick={() => toast.info('Step-by-step mode would run each step individually.')}
                  className="rounded-md border border-xelora-border px-3 py-1.5 text-xs text-xelora-text-secondary hover:bg-xelora-border transition-colors">
                  Run Step by Step
                </button>
              </div>
            )}
          </div>
        )}

        {/* Approval request */}
        {message.approvalRequest && (
          <ApprovalPanel req={message.approvalRequest} onApprove={onApprove} onKeepAll={onKeepAll} />
        )}

        {/* Result summary */}
        {message.resultSummary && (
          <div className="mt-3 rounded-lg border border-xelora-success bg-xelora-success-bg px-3 py-2">
            <p className="text-xs font-medium text-xelora-success flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />Completed
            </p>
            <p className="text-xs text-xelora-text-secondary mt-1">{message.resultSummary}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function StepRow({ step, index, expanded, onToggle }: { step: TaskStep; index: number; expanded: boolean; onToggle: () => void }) {
  const isDone = step.status === 'done';
  const isRunning = step.status === 'running';
  const isPending = step.status === 'pending';
  return (
    <div className="text-left">
      <button onClick={onToggle} className="flex w-full items-center gap-2 py-1 hover:opacity-80 transition-opacity text-left">
        {isDone ? <CheckCircle2 className="h-4 w-4 text-xelora-green shrink-0" />
          : isRunning ? <Loader2 className="h-4 w-4 text-xelora-info shrink-0 animate-spin" />
          : <Circle className="h-4 w-4 text-xelora-border shrink-0" />}
        <span className={cn('flex-1 text-xs', isDone ? 'text-xelora-text-secondary line-through' : isRunning ? 'text-xelora-text font-medium' : 'text-xelora-text-muted')}>
          {index + 1}. {step.name}
        </span>
        {step.requiresApproval && <span className="text-[10px] text-amber-500 font-medium">Approval</span>}
        {step.details && (expanded ? <ChevronDown className="h-3 w-3 text-xelora-text-muted" /> : <ChevronRight className="h-3 w-3 text-xelora-text-muted" />)}
      </button>
      {isRunning && step.progress && (
        <div className="ml-6 mt-1">
          <div className="flex justify-between text-[10px] text-xelora-text-muted mb-1">
            <span>{step.progress.label}</span>
            <span>{step.progress.current.toLocaleString()} of {step.progress.total.toLocaleString()}</span>
          </div>
          <div className="h-1 rounded-full bg-xelora-border overflow-hidden">
            <div className="h-full bg-xelora-green rounded-full transition-all duration-300" style={{ width: `${Math.round((step.progress.current / step.progress.total) * 100)}%` }} />
          </div>
        </div>
      )}
      {expanded && step.details && (
        <ul className="ml-6 mt-1 space-y-0.5">
          {step.details.map(d => (
            <li key={d} className="flex items-center gap-1.5 text-[10px] text-xelora-text-muted">
              <span className="h-1 w-1 rounded-full bg-xelora-border shrink-0" />
              {d}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ApprovalPanel({ req, onApprove, onKeepAll }: { req: NonNullable<TaskMessage['approvalRequest']>; onApprove: () => void; onKeepAll: () => void }) {
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 overflow-hidden">
      <div className="px-4 py-3 border-b border-amber-200">
        <p className="text-sm font-semibold text-amber-800">{req.heading}</p>
        <p className="text-xs text-amber-700 mt-0.5">Worksheet: {req.worksheet} · {req.affectedRows} rows affected</p>
      </div>
      <div className="px-4 py-3">
        <p className="text-xs text-amber-700 mb-2">{req.reason}</p>
        <div className="space-y-1.5 mb-3">
          {req.preview.map((p, i) => (
            <div key={i} className="grid grid-cols-2 gap-2 text-[10px]">
              <div className="rounded bg-amber-100 px-2 py-1 text-amber-800">{p.before}</div>
              <div className="rounded bg-xelora-success-bg px-2 py-1 text-xelora-success">{p.after}</div>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-amber-600 mb-3">{req.safetyNote}</p>
        <div className="flex gap-2">
          <button onClick={onApprove} className="flex items-center gap-1.5 rounded-md bg-xelora-green px-3 py-1.5 text-xs font-medium text-white hover:bg-xelora-deep-green transition-colors">
            <CheckCheck className="h-3.5 w-3.5" />Approve and Continue
          </button>
          <button onClick={onKeepAll} className="rounded-md border border-amber-300 px-3 py-1.5 text-xs text-amber-700 hover:bg-amber-100 transition-colors">Keep All Rows</button>
          <button onClick={() => toast.error('Workflow stopped.')} className="rounded-md border border-xelora-border px-3 py-1.5 text-xs text-xelora-error hover:bg-xelora-error-bg transition-colors">
            <X className="h-3 w-3 inline mr-1" />Stop
          </button>
        </div>
      </div>
    </div>
  );
}
