
import { NextResponse } from 'next/server'
import { upsertAccount } from '@/lib/graph/upsert'

export async function POST(request: Request) {
    try {
        const body = await request.json()
        const { persona, platform, attributes } = body

        if (!persona || !platform || !attributes) {
            return NextResponse.json(
                { error: 'Missing required fields: persona, platform, attributes' },
                { status: 400 }
            )
        }

        const result = await upsertAccount(persona, platform, attributes)

        return NextResponse.json(result)
    } catch (error: unknown) {
        console.error('Graph API Error:', error)
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
        return NextResponse.json(
            { error: 'Failed to update graph', details: errorMessage },
            { status: 500 }
        )
    }
}
