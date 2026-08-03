import { NextResponse, NextRequest } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
  const body = await request.json()
  const nodes = Array.isArray(body?.nodes) ? body.nodes : []
  if (!nodes.length || nodes.length > 100) return NextResponse.json({ error: 'nodes must contain 1-100 items' }, { status: 400 })
  const target = `${intelligenceUrl}/evidence/manual-node`
  const results = await Promise.all(nodes.map(async (node: unknown) => {
    const body=JSON.stringify(node)
    const response = await fetch(target, { method: 'POST', headers: intelligenceAuthorityHeaders(authority.profileId, target, 'POST','application/json',undefined,undefined,body), body, cache: 'no-store' })
    return { status: response.status, body: await response.json() }
  }))
  const failed = results.filter(result => result.status >= 400)
  return NextResponse.json({ success: failed.length === 0, created: results.length - failed.length, failed })
}
