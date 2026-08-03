import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body = await request.json()
  const source = body?.sourceId || body?.source_node_id
  const target = body?.targetId || body?.target_node_id
  if (!source || !target) return NextResponse.json({ error: 'source and target stable node UUIDs are required' }, { status: 400 })
  const url = `${intelligenceUrl}/evidence/manual-merge`
  const encodedBody=JSON.stringify({ source_node_id: source, target_node_id: target })
  const response = await fetch(url, { method: 'POST', headers: intelligenceAuthorityHeaders(authority.profileId, url, 'POST','application/json',undefined,undefined,encodedBody), body: encodedBody, cache: 'no-store' })
  return NextResponse.json(await response.json(), { status: response.status })
}
