import { NextResponse } from 'next/server';
import { runCypher } from '@/lib/graph';
import { getAICredential } from '@/lib/ai-credentials';
import { getWorkflowModelPreference } from '@/lib/model-preferences';

/**
 * Graph Chat API - Answers questions about the knowledge graph using Gemini
 */
export async function POST(request: Request) {
    try {
        const body = await request.json();
        const { query } = body;

        if (!query) {
            return NextResponse.json(
                { error: 'Query is required' },
                { status: 400 }
            );
        }

        // First, fetch relevant graph data based on query keywords
        const lowerQuery = query.toLowerCase();
        let cypherQuery = 'MATCH (n) RETURN n LIMIT 50';
        let cypherParams: Record<string, unknown> = {};

        // Use more specific queries based on what's being asked
        if (lowerQuery.includes('email')) {
            cypherQuery = `
                MATCH (p:Persona)-[r:USES_EMAIL]->(e:Email)
                OPTIONAL MATCH (a:Account)-[:REGISTERED_WITH]->(e)
                RETURN p, r, e, a LIMIT 50
            `;
        } else if (lowerQuery.includes('company') || lowerQuery.includes('companies')) {
            cypherQuery = `
                MATCH (c:Company)
                OPTIONAL MATCH (a:Account)-[:HELD_BY]->(c)
                RETURN c, a LIMIT 50
            `;
        } else if (lowerQuery.includes('amazon') || lowerQuery.includes('google') || lowerQuery.includes('facebook')) {
            const company = lowerQuery.includes('amazon') ? 'Amazon' :
                lowerQuery.includes('google') ? 'Google' : 'Facebook';
            cypherQuery = `
                MATCH (c:Company {name: $company})
                OPTIONAL MATCH (a:Account)-[:HELD_BY]->(c)
                OPTIONAL MATCH (a)-[:REGISTERED_WITH]->(e:Email)
                RETURN c, a, e LIMIT 50
            `;
            cypherParams = { company };
        } else if (lowerQuery.includes('phone')) {
            cypherQuery = `
                MATCH (p:Persona)-[r:HAS_PHONE]->(ph:Phone)
                OPTIONAL MATCH (a:Account)-[:VERIFIED_BY]->(ph)
                RETURN p, r, ph, a LIMIT 50
            `;
        } else if (lowerQuery.includes('account')) {
            cypherQuery = `
                MATCH (p:Persona)-[:OWNS_ACCOUNT]->(a:Account)
                OPTIONAL MATCH (a)-[:HELD_BY]->(c:Company)
                RETURN p, a, c LIMIT 50
            `;
        }

        // Execute the query
        const results = await runCypher(cypherQuery, cypherParams);

        // Build context from results
        const context = buildContextFromResults(results, lowerQuery);

        // Call Gemini to generate a natural language response
        const geminiResponse = await callGemini(query, context);

        return NextResponse.json({
            response: geminiResponse,
            graphData: context,
        });

    } catch (error) {
        console.error('Graph chat error:', error);
        return NextResponse.json(
            { error: 'Failed to process query' },
            { status: 500 }
        );
    }
}

function buildContextFromResults(results: unknown[], query: string): string {
    if (!results || results.length === 0) {
        return "The knowledge graph is empty or no relevant data was found.";
    }

    const nodes: Set<string> = new Set();
    const relationships: string[] = [];

    for (const record of results) {
        const rec = record as { keys: string[]; get: (key: string) => unknown };
        if (rec.keys) {
            for (const key of rec.keys) {
                const value = rec.get(key);
                if (value && typeof value === 'object') {
                    const node = value as { properties?: Record<string, unknown>; labels?: string[] };
                    if (node.properties) {
                        const props = node.properties;
                        const label = node.labels?.[0] || 'Node';
                        const name = props.name || props.value || props.address || props.username || 'unknown';
                        nodes.add(`${label}: ${name}`);
                    }
                }
            }
        }
    }

    let context = `Found ${nodes.size} relevant items in the graph:\n`;
    context += Array.from(nodes).join('\n');

    return context;
}

async function callGemini(query: string, context: string): Promise<string> {
    const preferences = await getWorkflowModelPreference('graph');
    const apiKey = await getAICredential('google') ||
        process.env.GEMINI_API_KEY ||
        process.env.GOOGLE_API_KEY;

    if (!apiKey) {
        // Fallback to simple response if no API key
        return generateSimpleResponse(query, context);
    }

    try {
        const { GoogleGenAI } = await import('@google/genai');
        const ai = new GoogleGenAI({ apiKey });
        const model = preferences.provider === 'google'
            ? preferences.model
            : process.env.GEMINI_MODEL_GRAPH || process.env.GEMINI_MODEL_FLASH || 'gemini-3.1-flash';

        const response = await ai.models.generateContent({
            model,
            contents: `You are a privacy analyst helping a user understand their data footprint. 
                            
The user asked: "${query}"

Based on their knowledge graph, here's what we found:
${context}

Provide a helpful, concise response (2-3 sentences max) that answers their question based on this data. 
If the data is limited, acknowledge that and suggest how they can expand their graph.
Focus on privacy implications and data connections.`,
            config: {
                temperature: 0.7,
                maxOutputTokens: 200,
            },
        });

        return response.text || generateSimpleResponse(query, context);
    } catch (error) {
        console.error('Gemini call failed:', error);
        return generateSimpleResponse(query, context);
    }
}

function generateSimpleResponse(query: string, context: string): string {
    const lowerQuery = query.toLowerCase();

    if (context.includes('empty')) {
        return "Your knowledge graph is empty. Start by creating GDPR requests and adding identities to build your data map.";
    }

    const itemCount = (context.match(/\n/g) || []).length;

    if (lowerQuery.includes('email')) {
        return `Based on your graph, I found ${itemCount} email-related entries. These create traceable connections across different services and companies.`;
    }

    if (lowerQuery.includes('compan')) {
        return `Your graph contains company data. Each company may share your information with partners and third parties.`;
    }

    return `Found ${itemCount} relevant items in your graph. ${context.substring(0, 200)}`;
}
