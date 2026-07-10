import { NextResponse } from 'next/server'

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

export async function POST(request: Request) {
  const body = await request.json()
  const source = body?.sourceId || body?.source_node_id
  const target = body?.targetId || body?.target_node_id
  if (!source || !target) return NextResponse.json({ error: 'source and target stable node UUIDs are required' }, { status: 400 })
  const response = await fetch(`${intelligenceUrl}/evidence/manual-merge`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ source_node_id: source, target_node_id: target }), cache: 'no-store' })
  return NextResponse.json(await response.json(), { status: response.status })
}
