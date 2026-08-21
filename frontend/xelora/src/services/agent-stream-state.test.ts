import { afterEach, describe, expect, it, vi } from 'vitest';
import { applyTaskStreamEvent, type AgentStreamState } from './agent-stream-state';
import { streamTaskEvents, type TaskStreamEvent } from './agent';

const initial = (): AgentStreamState => ({ status: 'running', steps: [] });

describe('applyTaskStreamEvent', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('concatenates deltas into one assistant response and completes streaming', () => {
    let state = initial();
    state = applyTaskStreamEvent(state, { type: 'assistant_started', provider: 'gemini' });
    state = applyTaskStreamEvent(state, { type: 'assistant_delta', content: "I've " });
    state = applyTaskStreamEvent(state, { type: 'assistant_delta', content: 'inspected ' });
    state = applyTaskStreamEvent(state, { type: 'assistant_delta', content: 'your workbook.' });
    state = applyTaskStreamEvent(state, { type: 'assistant_completed', content: state.response ?? '' });
    expect(state.response).toBe("I've inspected your workbook.");
    expect(state.streaming).toBe(false);
  });

  it('preserves partial content when the stream fails', () => {
    let state = applyTaskStreamEvent(initial(), { type: 'assistant_delta', content: 'Partial answer' });
    state = applyTaskStreamEvent(state, { type: 'error', code: 'provider_timeout', message: 'Timed out.' });
    expect(state.response).toBe('Partial answer');
    expect(state.status).toBe('error');
  });

  it('updates structured action progress without adding chat bubbles', () => {
    let state = applyTaskStreamEvent(initial(), { type: 'action_started', skill: 'write_table', label: 'Writing table' });
    expect(state.currentTask).toBe('Writing table');
    state = applyTaskStreamEvent(state, { type: 'action_completed', skill: 'write_table', label: 'Writing table', success: true });
    expect(state.steps).toEqual(['Writing table']);
    expect(state.currentTask).toBeUndefined();
  });

  it('parses NDJSON incrementally even when a JSON line spans network chunks', async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('{"type":"assistant_delta","content":"Hello'));
        controller.enqueue(encoder.encode(' world"}\n{"type":"assistant_completed","content":"Hello world"}\n'));
        controller.close();
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })));
    const events: TaskStreamEvent[] = [];
    await streamTaskEvents(7, (event) => events.push(event));
    expect(events).toEqual([
      { type: 'assistant_delta', content: 'Hello world' },
      { type: 'assistant_completed', content: 'Hello world' },
    ]);
  });

  it('passes AbortController cancellation to the stream request', async () => {
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn((_url, init?: RequestInit) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    })));
    const pending = streamTaskEvents(8, () => undefined, controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  });
});
