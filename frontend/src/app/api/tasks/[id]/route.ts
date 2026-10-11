import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

interface RouteContext {
  params: Promise<{ id: string }>;
}

export interface ChatDetail {
  id: number;
  instruction: string;
  status: string;
  created_at: string | null;
  completed_at: string | null;
  transcript: { role: 'user' | 'assistant'; text: string; timestamp: string }[];
  resumable: boolean;
}

export async function GET(_req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch<ChatDetail>(`/tasks/${id}`, { token });

  if (!result.ok) {
    const detail =
      (result.data as { error?: string })?.error ||
      (result.data as { detail?: string })?.detail ||
      'Could not load this conversation.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function POST(req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  if (body.action !== 'mark-read') {
    return NextResponse.json({ error: 'Unsupported conversation action.' }, { status: 400 });
  }

  const result = await backendFetch(`/tasks/${id}/mark-read`, { method: 'POST', token });
  if (!result.ok) {
    const detail = (result.data as { error?: string; detail?: string }).error || (result.data as { detail?: string }).detail || 'Could not update this conversation.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}

export async function DELETE(_req: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const result = await backendFetch(`/tasks/${id}`, { method: 'DELETE', token });
  if (!result.ok) {
    const detail = (result.data as { error?: string; detail?: string }).error || (result.data as { detail?: string }).detail || 'Could not delete this conversation.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
