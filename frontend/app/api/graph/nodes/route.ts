import { NextRequest, NextResponse } from 'next/server'

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

async function forward(path: string, body: unknown) {
  const response = await fetch(`${intelligenceUrl}${path}`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store',
  })
  const payload = await response.json().catch(() => ({ detail: 'Intelligence service returned an invalid response' }))
  return NextResponse.json(payload, { status: response.status })
}

export async function POST(request: Request) {
  const body = await request.json()
  if (!body?.label || !body?.type) return NextResponse.json({ error: 'label and type are required' }, { status: 400 })
  return forward('/evidence/manual-node', body)
}

export async function PUT(request: Request) {
  const body = await request.json()
  if (!body?.label || !body?.type) return NextResponse.json({ error: 'label and type are required' }, { status: 400 })
  return forward('/evidence/manual-node', body)
}

export async function DELETE(request: NextRequest) {
  const nodeId = request.nextUrl.searchParams.get('id')
  if (!nodeId) return NextResponse.json({ error: 'stable node UUID is required' }, { status: 400 })
  return forward('/evidence/manual-retire', { node_id: nodeId })
}
