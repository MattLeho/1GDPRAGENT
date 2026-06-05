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
            useLLM = true  // Optionally call N8N, but direct Neo4j upsert always runs
        } = body;

        if (!personaName) {
            return NextResponse.json(
                { error: 'Persona name is required' },
                { status: 400 }
            );
        }

        let llmSucceeded = false;
        let llmPersonaId: string | undefined;

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
            } else {
                llmSucceeded = true;
                llmPersonaId = result.data?.personaId;
            }
        }

        const directResult = await directUpsertIdentityData({
            personaName, emails, phones, names, usernames
        });

        return NextResponse.json({
            success: true,
            personaId: llmPersonaId || directResult.personaId,
            entitiesCreated: directResult.entitiesCreated,
            method: llmSucceeded ? 'llm+direct' : 'direct',
        });

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
async function directUpsertIdentityData(data: {
    personaName: string;
    emails: string[];
    phones: string[];
    names: { firstName?: string; lastName?: string }[];
    usernames: string[];
}): Promise<{ personaId: string; entitiesCreated: number }> {
    const { personaName, emails, phones, names, usernames } = data;
    let entitiesCreated = 0;

    try {
        // Create/merge persona node
        await runCypher(`
            MERGE (u:User {uid: 'root'})
            SET u.name = coalesce(u.name, 'MainUser'), u.updatedAt = datetime()
            MERGE (p:Persona {name: $personaName})
            SET p.label = $personaName, p.source = 'manual', p.updatedAt = datetime()
            MERGE (u)-[:HAS_PERSONA]->(p)
        `, { personaName });
        entitiesCreated++;

        // Link names
        for (const name of names) {
            const fullName = [name?.firstName, name?.lastName].filter(Boolean).join(' ').trim();
            if (fullName) {
                await runCypher(`
                    MATCH (p:Persona {name: $personaName})
                    MERGE (n:Name {value: $fullName})
                    SET n.source = 'manual', n.updatedAt = datetime()
                    MERGE (p)-[:HAS_NAME]->(n)
                `, { personaName, fullName });
                entitiesCreated++;
            }
        }

        // Link emails
        for (const email of emails) {
            if (email && email.trim()) {
                await runCypher(`
                    MATCH (p:Persona {name: $personaName})
                    MERGE (e:Email {address: $email})
                    SET e.source = 'manual', e.updatedAt = datetime()
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
                    SET ph.source = 'manual', ph.updatedAt = datetime()
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
                    SET id.source = 'manual', id.updatedAt = datetime()
                    MERGE (p)-[:HAS_IDENTIFIER]->(id)
                `, { personaName, username: username.trim() });
                entitiesCreated++;
            }
        }

        return {
            personaId: personaName.toLowerCase().replace(/\s+/g, '_'),
            entitiesCreated,
        };

    } catch (error) {
        console.error('Direct Cypher upsert failed:', error);
        throw new Error('Failed to update knowledge graph');
    }
}
