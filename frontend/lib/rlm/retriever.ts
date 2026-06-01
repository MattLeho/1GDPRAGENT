/**
 * RLM Agent — Hybrid Retriever
 *
 * Adapted from RAG-Anything's modality-aware retrieval architecture:
 * - Vector-Graph Fusion: combines Neo4j graph traversal with SQL text search
 * - Weighted Relationship Scoring: scores results by relevance type
 * - Context Window Management: truncates merged results for Gemini context
 *
 * Uses existing lib/graph.ts runCypher for Neo4j queries
 * Uses lib/db.ts pool for PostgreSQL queries
 */

import { runCypher } from '@/lib/graph';
import { pool } from '@/lib/db';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface RetrievalResult {
    source: 'graph' | 'document';
    type: string;           // entity label, file type, etc.
    title: string;          // node label, file name, etc.
    content: string;        // extracted text, properties, etc.
    score: number;          // relevance score 0-1
    metadata?: Record<string, unknown>;
}

export interface HybridRetrievalOptions {
    requestId: string;
    query: string;
    entityType?: string;
    relationshipType?: string;
    fileType?: string;
    maxResults?: number;
    maxContextChars?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Graph Retrieval — Neo4j Cypher queries
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Searches Neo4j knowledge graph for entities and relationships
 * matching the query. Supports filtering by entity type and relationship type.
 */
export async function searchGraph(
    requestId: string,
    query: string,
    entityType?: string,
    relationshipType?: string,
    maxResults = 20,
): Promise<RetrievalResult[]> {
    const results: RetrievalResult[] = [];

    try {
        // Strategy 1: Full-text search across node properties
        // First, check if full-text index exists; if not, fall back to CONTAINS
        const keywords = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);

        if (keywords.length === 0) return results;

        // Build a flexible search query that works across node types
        const labelFilter = entityType ? `:${entityType}` : '';
        const relFilter = relationshipType || '';

        // Search across all nodes with property matching
        const nodeSearchCypher = `
            MATCH (n${labelFilter})
            WHERE any(key IN keys(n) WHERE 
                key <> 'embedding' AND 
                toString(n[key]) IS NOT NULL AND
                toLower(toString(n[key])) CONTAINS $keyword
            )
            RETURN labels(n) AS labels, properties(n) AS props, n.name AS name, n.username AS username
            LIMIT $limit
        `;

        // Search each keyword and collect unique results
        const seenIds = new Set<string>();
        for (const keyword of keywords.slice(0, 3)) { // limit to first 3 keywords
            try {
                const records = await runCypher(nodeSearchCypher, {
                    keyword,
                    limit: maxResults,
                });

                for (const record of records) {
                    const labels = record.get('labels') as string[];
                    const props = record.get('props') as Record<string, unknown>;
                    const name = record.get('name') || record.get('username') || labels[0];
                    const id = `${labels.join('-')}-${name}-${JSON.stringify(props).substring(0, 50)}`;

                    if (seenIds.has(id)) continue;
                    seenIds.add(id);

                    // Filter out internal/system properties
                    const cleanProps = Object.fromEntries(
                        Object.entries(props).filter(([k]) =>
                            !['embedding', 'updated_at', 'created_at'].includes(k)
                        )
                    );

                    results.push({
                        source: 'graph',
                        type: labels.join(', '),
                        title: String(name),
                        content: JSON.stringify(cleanProps, null, 2),
                        score: keyword === query.toLowerCase() ? 1.0 : 0.7,
                        metadata: { labels, keyword },
                    });
                }
            } catch { /* skip failing keywords */ }
        }

        // Strategy 2: Relationship traversal — find connected nodes
        if (relFilter || results.length < 5) {
            const relCypher = relFilter
                ? `
                    MATCH (a)-[r:${relFilter}]->(b)
                    RETURN labels(a) AS aLabels, properties(a) AS aProps, 
                           type(r) AS relType, properties(r) AS rProps,
                           labels(b) AS bLabels, properties(b) AS bProps
                    LIMIT $limit
                `
                : `
                    MATCH (a)-[r]->(b)
                    WHERE any(key IN keys(a) WHERE 
                        key <> 'embedding' AND 
                        toString(a[key]) IS NOT NULL AND
                        toLower(toString(a[key])) CONTAINS $keyword
                    )
                    RETURN labels(a) AS aLabels, properties(a) AS aProps, 
                           type(r) AS relType, properties(r) AS rProps,
                           labels(b) AS bLabels, properties(b) AS bProps
                    LIMIT $limit
                `;

            try {
                const params: Record<string, unknown> = { limit: Math.min(maxResults, 10) };
                if (!relFilter) params.keyword = keywords[0] || query.toLowerCase();

                const relRecords = await runCypher(relCypher, params);

                for (const record of relRecords) {
                    const aLabels = record.get('aLabels') as string[];
                    const relType = record.get('relType') as string;
                    const bLabels = record.get('bLabels') as string[];
                    const aProps = record.get('aProps') as Record<string, unknown>;
                    const bProps = record.get('bProps') as Record<string, unknown>;

                    const aName = aProps.name || aProps.username || aLabels[0];
                    const bName = bProps.name || bProps.username || bProps.address || bProps.value || bLabels[0];

                    results.push({
                        source: 'graph',
                        type: 'Relationship',
                        title: `${aName} —[${relType}]→ ${bName}`,
                        content: `${aLabels.join(',')} (${JSON.stringify(aProps)}) -[${relType}]-> ${bLabels.join(',')} (${JSON.stringify(bProps)})`,
                        score: relFilter ? 0.9 : 0.5,
                        metadata: { relType, aLabels, bLabels },
                    });
                }
            } catch { /* graph may be empty */ }
        }
    } catch (err) {
        console.error('[HybridRetriever] Graph search failed:', err);
    }

    return results;
}

// ─────────────────────────────────────────────────────────────────────────────
// Document Retrieval — PostgreSQL search on received_data
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Searches uploaded documents using SQL ILIKE across extracted_text,
 * ai_summary, transcript, and entities columns.
 */
export async function searchDocuments(
    requestId: string,
    query: string,
    fileType?: string,
    maxResults = 10,
): Promise<RetrievalResult[]> {
    const results: RetrievalResult[] = [];

    try {
        const keywords = query.split(/\s+/).filter(w => w.length > 2);
        if (keywords.length === 0) return results;

        // Build WHERE clause with ILIKE for each keyword across content columns
        const likeConditions = keywords.map((_, i) =>
            `(COALESCE(extracted_text, '') ILIKE $${i + 2} OR ` +
            `COALESCE(ai_summary, '') ILIKE $${i + 2} OR ` +
            `COALESCE(transcript, '') ILIKE $${i + 2} OR ` +
            `COALESCE(entities::text, '') ILIKE $${i + 2})`
        ).join(' AND ');

        const typeCondition = fileType
            ? ` AND LOWER(category) = LOWER($${keywords.length + 2})`
            : '';

        const sql = `
            SELECT id, file_name, file_size_mb, category, status,
                   processing_stage, extracted_text, ai_summary, transcript, 
                   entities, graph_ingested, error_message
            FROM received_data
            WHERE request_id = $1
            AND (${likeConditions})${typeCondition}
            ORDER BY 
                CASE WHEN ai_summary IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN extracted_text IS NOT NULL THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT $${keywords.length + (fileType ? 3 : 2)}
        `;

        const params: (string | number)[] = [requestId];
        keywords.forEach(k => params.push(`%${k}%`));
        if (fileType) params.push(fileType);
        params.push(maxResults);

        const { rows } = await pool.query(sql, params);

        for (const row of rows) {
            // Build a content summary from available fields
            const contentParts: string[] = [];
            if (row.ai_summary) contentParts.push(`AI Summary: ${row.ai_summary}`);
            if (row.entities) {
                try {
                    const ents = typeof row.entities === 'string' ? JSON.parse(row.entities) : row.entities;
                    contentParts.push(`Entities: ${JSON.stringify(ents).substring(0, 500)}`);
                } catch { contentParts.push(`Entities: ${String(row.entities).substring(0, 500)}`); }
            }
            if (row.extracted_text) {
                // Find the most relevant excerpt
                const excerpt = findRelevantExcerpt(row.extracted_text, keywords, 500);
                contentParts.push(`Extracted Text: ...${excerpt}...`);
            }
            if (row.transcript) {
                const excerpt = findRelevantExcerpt(row.transcript, keywords, 500);
                contentParts.push(`Transcript: ...${excerpt}...`);
            }

            // Score based on how many content types matched
            const score = Math.min(1.0, 0.3 + (contentParts.length * 0.2));

            results.push({
                source: 'document',
                type: row.category || 'document',
                title: row.file_name,
                content: contentParts.join('\n\n') || 'No extracted content available.',
                score,
                metadata: {
                    fileId: row.id,
                    status: row.status,
                    graphIngested: row.graph_ingested,
                    errorMessage: row.error_message,
                },
            });
        }
    } catch (err) {
        console.error('[HybridRetriever] Document search failed:', err);
    }

    return results;
}

// ─────────────────────────────────────────────────────────────────────────────
// Hybrid Fusion — Merge and rank results from both sources
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Performs hybrid retrieval across both Neo4j and PostgreSQL,
 * merges results, deduplicates, scores by relevance, and truncates
 * to fit within Gemini's context window.
 *
 * Adapted from RAG-Anything's Vector-Graph Fusion approach.
 */
export async function hybridRetrieve(options: HybridRetrievalOptions): Promise<{
    results: RetrievalResult[];
    context: string;
    stats: { graphHits: number; docHits: number; totalChars: number };
}> {
    const {
        requestId,
        query,
        entityType,
        relationshipType,
        fileType,
        maxResults = 20,
        maxContextChars = 8000,
    } = options;

    // Run both search strategies in parallel (RAG-Anything: concurrent pipelines)
    const [graphResults, docResults] = await Promise.all([
        searchGraph(requestId, query, entityType, relationshipType, maxResults),
        searchDocuments(requestId, query, fileType, maxResults),
    ]);

    // Merge and sort by score (highest first)
    const allResults = [...graphResults, ...docResults]
        .sort((a, b) => b.score - a.score)
        .slice(0, maxResults);

    // Build context string for the LLM, respecting token budget
    let context = '';
    let charCount = 0;
    const usedResults: RetrievalResult[] = [];

    for (const result of allResults) {
        const entry = `[${result.source.toUpperCase()}: ${result.type}] ${result.title}\n${result.content}\n\n`;
        if (charCount + entry.length > maxContextChars) break;
        context += entry;
        charCount += entry.length;
        usedResults.push(result);
    }

    return {
        results: usedResults,
        context: context || 'No relevant results found in documents or knowledge graph.',
        stats: {
            graphHits: graphResults.length,
            docHits: docResults.length,
            totalChars: charCount,
        },
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Find the most relevant excerpt from a long text given search keywords.
 * Returns a window centered on the first keyword match.
 */
function findRelevantExcerpt(text: string, keywords: string[], maxLength: number): string {
    const lower = text.toLowerCase();
    let bestPos = 0;

    for (const keyword of keywords) {
        const pos = lower.indexOf(keyword.toLowerCase());
        if (pos !== -1) {
            bestPos = pos;
            break;
        }
    }

    const start = Math.max(0, bestPos - Math.floor(maxLength / 2));
    const end = Math.min(text.length, start + maxLength);
    return text.substring(start, end);
}
