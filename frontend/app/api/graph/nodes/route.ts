import { NextRequest, NextResponse } from 'next/server';
import { requireApiSession } from '@/lib/api-session';
import { intelligenceAuthorityHeaders } from '@/lib/api-session';

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

async function forward(path: string, body: unknown, profileId: string) {
  const target = `${intelligenceUrl}${path}`
  const encodedBody = JSON.stringify(body)
  const response = await fetch(target, {
    method: 'POST', headers: intelligenceAuthorityHeaders(profileId, target, 'POST','application/json',undefined,undefined,encodedBody), body: encodedBody, cache: 'no-store',
  })
  const payload = await response.json().catch(() => ({ detail: 'Intelligence service returned an invalid response' }))
  return NextResponse.json(payload, { status: response.status })
}

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body = await request.json()
  if (!body?.label || !body?.type) return NextResponse.json({ error: 'label and type are required' }, { status: 400 })
  return forward('/evidence/manual-node', body, authority.profileId)
}

export async function PUT(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body = await request.json()
  if (!body?.label || !body?.type) return NextResponse.json({ error: 'label and type are required' }, { status: 400 })
  return forward('/evidence/manual-node', body, authority.profileId)
}

export async function DELETE(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const nodeId = request.nextUrl.searchParams.get('id')
  if (!nodeId) return NextResponse.json({ error: 'stable node UUID is required' }, { status: 400 })
  return forward('/evidence/manual-retire', { node_id: nodeId }, authority.profileId)
}
