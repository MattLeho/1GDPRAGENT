
import { NextResponse } from 'next/server'
import { runCypher } from '@/lib/graph'

export async function GET() {
    try {
        // Fetch all Personas and their linked Emails
        // Returns: { name: "Gamer", emails: ["...", "..."] }
        const query = `
      MATCH (p:Persona)
      OPTIONAL MATCH (p)-[:USES_EMAIL]->(e:Email)
      RETURN p.name as persona, collect(e.address) as emails
    `

        const records = await runCypher(query)

        const data = records.map(record => ({
            id: record.get('persona').toLowerCase(),
            label: record.get('persona'),
            emails: record.get('emails')
        }))

        return NextResponse.json(data)
    } catch (error: any) {
        console.error('Graph Fetch Error:', error)
        return NextResponse.json(
            { error: 'Failed to fetch identities', details: error.message },
            { status: 500 }
        )
    }
}
