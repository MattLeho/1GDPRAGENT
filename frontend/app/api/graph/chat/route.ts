import { NextResponse } from 'next/server';
import { runCypher } from '@/lib/graph';
import { executeTask } from '@/lib/execution/router';

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
        let cypherQuery = "MATCH (n:GraphNode) WHERE coalesce(n.retired,false)=false AND coalesce(n.source,'')<>'inference' RETURN n LIMIT 50";
        let cypherParams: Record<string, unknown> = {};

        // Use more specific queries based on what's being asked
        if (lowerQuery.includes('email')) {
            cypherQuery = `
                MATCH (s:Subject)-[r]->(e:GraphNode)
                WHERE (e:Identifier OR e:Email) AND coalesce(r.epistemic_basis,'') <> 'model_hypothesis'
                RETURN s, r, e LIMIT 50
            `;
        } else if (lowerQuery.includes('company') || lowerQuery.includes('companies')) {
            cypherQuery = `
                MATCH (c:GraphNode)
                WHERE c:Organisation OR c:ControllerProfile
                OPTIONAL MATCH (a:Account)-[r:HELD_BY]->(c)
                WHERE r IS NULL OR coalesce(r.epistemic_basis,'') <> 'model_hypothesis'
                RETURN c, a, r LIMIT 50
            `;
        } else if (lowerQuery.includes('amazon') || lowerQuery.includes('google') || lowerQuery.includes('facebook')) {
            const company = lowerQuery.includes('amazon') ? 'Amazon' :
                lowerQuery.includes('google') ? 'Google' : 'Facebook';
            cypherQuery = `
                MATCH (c:GraphNode)
                WHERE (c:Organisation OR c:ControllerProfile) AND toLower(coalesce(c.value,c.canonical_key,'')) CONTAINS toLower($company)
                OPTIONAL MATCH (a:Account)-[r:HELD_BY]->(c)
                WHERE r IS NULL OR coalesce(r.epistemic_basis,'') <> 'model_hypothesis'
                RETURN c, a, r LIMIT 50
            `;
            cypherParams = { company };
        } else if (lowerQuery.includes('phone')) {
            cypherQuery = `
                MATCH (s:Subject)-[r]->(ph:GraphNode)
                WHERE (ph:Identifier OR ph:Phone) AND coalesce(r.epistemic_basis,'') <> 'model_hypothesis'
                RETURN s, r, ph LIMIT 50
            `;
        } else if (lowerQuery.includes('account')) {
            cypherQuery = `
                MATCH (s:Subject)-[r]->(a:Account)
                WHERE coalesce(r.epistemic_basis,'') <> 'model_hypothesis'
                OPTIONAL MATCH (a)-[held:HELD_BY]->(c:Organisation)
                RETURN s, r, a, held, c LIMIT 50
            `;
        }

        // Execute the query
        const results = await runCypher(cypherQuery, cypherParams);

        // Build context from results
        const context = buildContextFromResults(results);

        const geminiResponse = await explainGraph(query, context);

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

function buildContextFromResults(results: unknown[]): string {
    if (!results || results.length === 0) {
        return "The knowledge graph is empty or no relevant data was found.";
    }

    const nodes: Set<string> = new Set();
    const relationships: Set<string> = new Set();

    for (const record of results) {
        const rec = record as { keys: string[]; get: (key: string) => unknown };
        if (rec.keys) {
            for (const key of rec.keys) {
                const value = rec.get(key);
                if (value && typeof value === 'object') {
                    const node = value as { properties?: Record<string, unknown>; labels?: string[]; type?: string };
                    if (node.properties) {
                        const props = node.properties;
                        const label = node.labels?.[0] || 'Node';
                        const name = props.name || props.value || props.address || props.username || 'unknown';
                        nodes.add(`${label}: ${name}`);
                    } else if (node.type) {
                        relationships.add(node.type);
                    }
                }
            }
        }
    }

    let context = `Found ${nodes.size} relevant items in the graph:\n`;
    context += Array.from(nodes).join('\n');
    if (relationships.size) context += `\nRelationships: ${Array.from(relationships).join(', ')}`;

    return context;
}

async function explainGraph(query: string, context: string): Promise<string> {
    try {
        const result=await executeTask({taskKey:'graph.explanation',workflowKey:'graph.query',input:{text:`Question: ${query}\n\nGrounded graph results:\n${context}`},configuration:{systemPrompt:'Answer the question in two or three concise sentences using only the grounded graph results. State when evidence is limited and do not turn model hypotheses into facts.'}});
        return result.ok&&typeof (result.output as {text?:unknown}).text==='string'?(result.output as {text:string}).text:generateSimpleResponse(query,context);
    } catch (error) {
        console.error('Graph explanation task failed:', error);
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
