import { NextRequest, NextResponse } from 'next/server';
import { backendFetch } from '@/lib/backend';
import { getSessionToken } from '@/lib/session';

export async function POST(req: NextRequest) {
  const token = await getSessionToken();
  if (!token) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 });

  const body = await req.json();
  const result = await backendFetch('/task', {
    method: 'POST',
    token,
    body: { instruction: body.instruction, workbook_name: body.workbookName ?? null },
  });

  if (!result.ok) {
    const detail =
      (result.data as { error?: string })?.error ||
      (result.data as { detail?: string })?.detail ||
      'Could not start the task.';
    return NextResponse.json({ error: detail }, { status: result.status || 500 });
  }
  return NextResponse.json(result.data);
}
