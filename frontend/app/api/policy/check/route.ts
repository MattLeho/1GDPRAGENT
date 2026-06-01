
import { NextRequest, NextResponse } from 'next/server'
import { getPolicyAnalysis } from '@/lib/actions/policy'

export async function POST(req: NextRequest) {
    try {
        const body = await req.json()
        const { url } = body

        if (!url) {
            return NextResponse.json({ error: "URL is required" }, { status: 400 })
        }

        const analysis = await getPolicyAnalysis(url)

        if (analysis) {
            return NextResponse.json({ found: true, analysis })
        } else {
            return NextResponse.json({ found: false })
        }

    } catch (error) {
        console.error("API Policy Check Error:", error)
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 })
    }
}
