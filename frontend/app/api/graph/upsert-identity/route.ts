import { NextResponse } from 'next/server';
import { ingestIdentity } from '@/lib/n8n-client';
import { runCypher } from '@/lib/graph';

/**
 * Ingest identity data into Knowledge Graph.
 * Uses Gemini via N8N to generate Cypher queries.
 */
export async function POST(request: Request) {
    try {
        const body = await request.json();
        const {
            personaName,
            emails = [],
            phones = [],
            names = [],
            usernames = [],
            notes,
            useLLM = true  // Use LLM for Cypher generation by default
        } = body;

        if (!personaName) {
            return NextResponse.json(
                { error: 'Persona name is required' },
                { status: 400 }
            );
        }

        if (useLLM) {
            // Use N8N agent with Gemini for intelligent Cypher generation
            const result = await ingestIdentity({
                personaName,
                emails,
                phones,
                names,
                usernames,
                notes,
            });

            if (!result.success) {
                console.error('N8N Identity Ingestor failed:', result.error);
                // Fall back to direct Cypher
                return await directUpsertIdentity({
                    personaName, emails, phones, names, usernames
                });
            }

            return NextResponse.json({
                success: true,
                personaId: result.data?.personaId,
                entitiesCreated: result.data?.entitiesCreated || 0,
                method: 'llm',
            });
        } else {
            // Direct Cypher without LLM
            return await directUpsertIdentity({
                personaName, emails, phones, names, usernames
            });
        }

    } catch (error) {
        console.error('Identity upsert endpoint error:', error);
        return NextResponse.json(
            { error: 'Internal server error' },
            { status: 500 }
        );
    }
}

/**
 * Direct Cypher upsert without LLM (fallback)
 */
async function directUpsertIdentity(data: {
    personaName: string;
    emails: string[];
    phones: string[];
    names: { firstName?: string; lastName?: string }[];
    usernames: string[];
}) {
    const { personaName, emails, phones, usernames } = data;
    let entitiesCreated = 0;

    try {
        // Create/merge persona node
        await runCypher(`
            MERGE (u:User {name: 'MainUser'})
            MERGE (p:Persona {name: $personaName})
            MERGE (u)-[:HAS_PERSONA]->(p)
        `, { personaName });
        entitiesCreated++;

        // Link emails
        for (const email of emails) {
            if (email && email.trim()) {
                await runCypher(`
                    MATCH (p:Persona {name: $personaName})
                    MERGE (e:Email {address: $email})
                    MERGE (p)-[:USES_EMAIL]->(e)
                `, { personaName, email: email.trim().toLowerCase() });
                entitiesCreated++;
            }
        }

        // Link phones
        for (const phone of phones) {
            if (phone && phone.trim()) {
                await runCypher(`
                    MATCH (p:Persona {name: $personaName})
                    MERGE (ph:Phone {number: $phone})
                    MERGE (p)-[:HAS_PHONE]->(ph)
                `, { personaName, phone: phone.trim() });
                entitiesCreated++;
            }
        }

        // Link usernames as Identifiers
        for (const username of usernames) {
            if (username && username.trim()) {
                await runCypher(`
                    MATCH (p:Persona {name: $personaName})
                    MERGE (id:Identifier {value: $username, type: 'username'})
                    MERGE (p)-[:HAS_IDENTIFIER]->(id)
                `, { personaName, username: username.trim() });
                entitiesCreated++;
            }
        }

        return NextResponse.json({
            success: true,
            personaId: personaName.toLowerCase().replace(/\s+/g, '_'),
            entitiesCreated,
            method: 'direct',
        });

    } catch (error) {
        console.error('Direct Cypher upsert failed:', error);
        return NextResponse.json(
            { error: 'Failed to update knowledge graph' },
            { status: 500 }
        );
    }
}
