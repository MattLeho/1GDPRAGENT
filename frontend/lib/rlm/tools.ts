/**
 * RLM Agent — Tool Implementations
 *
 * Concrete functions that execute when Gemini calls each tool.
 * Bridges Gemini function calling to our hybrid retriever, PostgreSQL,
 * and Neo4j backends.
 */

import { pool } from '@/lib/db';
import { searchGraph, searchDocuments as searchDocs, hybridRetrieve } from './retriever';

// ─────────────────────────────────────────────────────────────────────────────
// Tool: search_knowledge_graph
// ─────────────────────────────────────────────────────────────────────────────

export async function searchKnowledgeGraph(
    requestId: string,
    args: { query: string; entity_type?: string; relationship_type?: string },
): Promise<string> {
    const results = await searchGraph(
        requestId,
        args.query,
        args.entity_type,
        args.relationship_type,
    );

    if (results.length === 0) {
        return 'No matching entities or relationships found in the knowledge graph for this request.';
    }

    const formatted = results.map((r, i) =>
        `${i + 1}. [${r.type}] "${r.title}"\n   ${r.content.substring(0, 300)}`
    ).join('\n\n');

    return `Found ${results.length} result(s) in knowledge graph:\n\n${formatted}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: search_documents
// ─────────────────────────────────────────────────────────────────────────────

export async function searchDocumentsImpl(
    requestId: string,
    args: { query: string; file_type?: string },
): Promise<string> {
    const results = await searchDocs(
        requestId,
        args.query,
        args.file_type,
    );

    if (results.length === 0) {
        return 'No matching content found in uploaded documents for this request.';
    }

    const formatted = results.map((r, i) =>
        `${i + 1}. [${r.type}] "${r.title}" (score: ${r.score.toFixed(2)})\n${r.content.substring(0, 600)}`
    ).join('\n\n---\n\n');

    return `Found ${results.length} matching document(s):\n\n${formatted}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: lookup_privacy_policy
// ─────────────────────────────────────────────────────────────────────────────

export async function lookupPrivacyPolicy(requestId: string): Promise<string> {
    try {
        // Fetch request details
        const { rows: reqRows } = await pool.query(
            `SELECT id, company_name, domain, request_type, status, 
                    policy_url, created_at, deadline
             FROM access_requests WHERE id = $1`,
            [requestId],
        );

        if (reqRows.length === 0) return 'Request not found.';
        const req = reqRows[0] as Record<string, unknown>;

        // Fetch analysis if available
        const { rows: analysisRows } = await pool.query(
            `SELECT * FROM policy_analyses WHERE request_id = $1 ORDER BY created_at DESC LIMIT 1`,
            [requestId],
        );

        // Fetch file count & status summary
        const { rows: fileStats } = await pool.query(
            `SELECT status, COUNT(*)::int as count 
             FROM received_data WHERE request_id = $1 GROUP BY status`,
            [requestId],
        );

        let output = `## Request Details\n`;
        output += `- **Company**: ${req.company_name}\n`;
        output += `- **Domain**: ${req.domain || 'N/A'}\n`;
        output += `- **Type**: ${req.request_type}\n`;
        output += `- **Status**: ${req.status}\n`;
        output += `- **Policy URL**: ${req.policy_url || 'Not set'}\n`;
        output += `- **Created**: ${req.created_at}\n`;
        output += `- **Deadline**: ${req.deadline || 'Not set'}\n\n`;

        if (fileStats.length > 0) {
            output += `## File Summary\n`;
            const stats = fileStats as { status: string; count: number }[];
            for (const s of stats) {
                output += `- ${s.status}: ${s.count} file(s)\n`;
            }
            output += '\n';
        }

        if (analysisRows.length > 0) {
            const analysis = analysisRows[0] as Record<string, unknown>;
            output += `## Policy Analysis\n`;
            if (analysis.summary) output += `**Summary**: ${analysis.summary}\n`;
            if (analysis.compliance_score !== null) output += `**Compliance Score**: ${analysis.compliance_score}%\n`;
            if (analysis.recommendations) output += `**Recommendations**: ${analysis.recommendations}\n`;
        } else {
            output += `## Policy Analysis\nNo policy analysis has been performed yet.\n`;
        }

        return output;
    } catch (err) {
        console.error('[Tools] lookupPrivacyPolicy failed:', err);
        return 'Failed to retrieve request details. The database may be unavailable.';
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: get_gdpr_reference
// ─────────────────────────────────────────────────────────────────────────────

const GDPR_REFERENCES: Record<string, { articles: string[]; summary: string; deadline?: string }> = {
    'right of access': {
        articles: ['Article 15 GDPR'],
        summary: 'Data subjects have the right to obtain confirmation as to whether personal data concerning them is being processed, and access to that data along with information about processing purposes, categories of data, recipients, retention period, and the existence of automated decision-making. Controllers must provide a copy of the data free of charge.',
        deadline: '1 month from receipt of request, extendable by 2 months for complex requests',
    },
    'right to erasure': {
        articles: ['Article 17 GDPR'],
        summary: 'Also known as the "right to be forgotten". Data subjects can request erasure when data is no longer necessary, consent is withdrawn, the subject objects to processing, data was unlawfully processed, or data must be erased for legal compliance. Exceptions include freedom of expression, legal obligations, public health, archiving, and legal claims.',
        deadline: '1 month, extendable by 2 months',
    },
    'data portability': {
        articles: ['Article 20 GDPR'],
        summary: 'Data subjects have the right to receive their personal data in a structured, commonly used, machine-readable format and to transmit that data to another controller. Applies when processing is based on consent or contract and carried out by automated means.',
        deadline: '1 month, extendable by 2 months',
    },
    'consent': {
        articles: ['Article 6(1)(a)', 'Article 7', 'Recital 32'],
        summary: 'Consent must be freely given, specific, informed, and unambiguous. The controller must be able to demonstrate that consent was given. Consent can be withdrawn at any time. Pre-ticked boxes or silence do not constitute consent. Consent must be clearly distinguishable from other matters.',
    },
    'data breach notification': {
        articles: ['Article 33', 'Article 34'],
        summary: 'Controllers must notify the supervisory authority within 72 hours of becoming aware of a personal data breach, unless unlikely to result in risk. If the breach is likely to result in high risk to individuals, they must also be notified directly without undue delay.',
        deadline: '72 hours to supervisory authority',
    },
    'legitimate interest': {
        articles: ['Article 6(1)(f)', 'Recital 47'],
        summary: 'Processing is lawful when necessary for the purposes of legitimate interests pursued by the controller or a third party, except where overridden by the interests, rights, or freedoms of the data subject. Requires a balancing test between controller interests and data subject rights.',
    },
    'rectification': {
        articles: ['Article 16 GDPR'],
        summary: 'Data subjects have the right to obtain rectification of inaccurate personal data without undue delay. They also have the right to have incomplete data completed, including by means of a supplementary statement.',
        deadline: '1 month, extendable by 2 months',
    },
    'restriction of processing': {
        articles: ['Article 18 GDPR'],
        summary: 'Data subjects can request restriction of processing when accuracy is contested, processing is unlawful, the controller no longer needs the data, or the subject has objected to processing. When restricted, data may only be stored and processed with consent or for legal claims.',
        deadline: '1 month, extendable by 2 months',
    },
    'right to object': {
        articles: ['Article 21 GDPR'],
        summary: 'Data subjects have the right to object to processing based on legitimate interests or public interest, including profiling. For direct marketing, the right to object is absolute. The controller must stop processing unless demonstrating compelling legitimate grounds.',
    },
    'data processing agreement': {
        articles: ['Article 28 GDPR'],
        summary: 'Processing by a processor must be governed by a contract that sets out the subject matter, duration, nature, purpose, type of personal data, categories of data subjects, and obligations of the controller. The processor must only act on documented instructions from the controller.',
    },
    'data protection officer': {
        articles: ['Article 37', 'Article 38', 'Article 39'],
        summary: 'A DPO must be designated when processing is carried out by a public authority, core activities require regular/systematic monitoring at large scale, or core activities involve large-scale processing of special categories. The DPO must be independent, directly report to management, and be accessible to data subjects.',
    },
    'automated decision making': {
        articles: ['Article 22 GDPR'],
        summary: 'Data subjects have the right not to be subject to decisions based solely on automated processing, including profiling, which produces legal effects or similarly significantly affects them. Exceptions exist for contracts, legal authorization, or explicit consent. Suitable safeguards must be implemented.',
    },
    'transfers': {
        articles: ['Article 44-49 GDPR'],
        summary: 'Transfers of personal data to third countries or international organisations are permitted only if the controller/processor complies with Chapter V conditions. This includes adequacy decisions, appropriate safeguards (such as standard contractual clauses), binding corporate rules, or specific derogations.',
    },
    'children': {
        articles: ['Article 8 GDPR', 'Recital 38'],
        summary: 'For information society services offered directly to a child, processing based on consent is lawful only if the child is at least 16 years old (member states may lower this to 13). Below that age, processing requires consent from the holder of parental responsibility.',
    },
};

export function getGDPRReference(args: { topic: string }): string {
    const topic = args.topic.toLowerCase();

    // Try exact match first, then fuzzy match
    let match = GDPR_REFERENCES[topic];

    if (!match) {
        // Fuzzy search: find the best matching key
        const keys = Object.keys(GDPR_REFERENCES);
        const scored = keys.map(k => ({
            key: k,
            score: topic.split(/\s+/).filter(w => k.includes(w)).length,
        })).filter(s => s.score > 0).sort((a, b) => b.score - a.score);

        if (scored.length > 0) {
            match = GDPR_REFERENCES[scored[0].key];
        }
    }

    if (!match) {
        // List available topics
        const available = Object.keys(GDPR_REFERENCES).join(', ');
        return `No specific GDPR reference found for "${args.topic}". Available topics: ${available}. ` +
            'You can also ask about general GDPR principles or specific article numbers.';
    }

    let output = `## GDPR Reference: ${args.topic}\n\n`;
    output += `**Relevant Articles**: ${match.articles.join(', ')}\n\n`;
    output += `**Summary**: ${match.summary}\n`;
    if (match.deadline) output += `\n**Response Deadline**: ${match.deadline}\n`;

    return output;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: decompose_query
// RLM recursive decomposition
// ─────────────────────────────────────────────────────────────────────────────

export function decomposeQuery(args: { query: string; reason: string }): string {
    return JSON.stringify({
        original_query: args.query,
        decomposition_reason: args.reason,
        instruction: 'You have decomposed this query. Now use the other available tools ' +
            '(search_knowledge_graph, search_documents, lookup_privacy_policy, get_gdpr_reference, ' +
            'locate_file, find_in_document, list_all_files) ' +
            'to answer each aspect of the original query, then synthesize a comprehensive response.',
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: locate_file
// ─────────────────────────────────────────────────────────────────────────────

export async function locateFile(
    requestId: string,
    args: { file_name: string },
): Promise<string> {
    try {
        const { rows } = await pool.query(
            `SELECT id, file_name, file_type, category, file_size, status, 
                    processing_stage, date_received, graph_synced,
                    ai_summary IS NOT NULL as has_summary,
                    extracted_text IS NOT NULL as has_text,
                    transcript IS NOT NULL as has_transcript
             FROM received_data 
             WHERE request_id = $1 AND LOWER(file_name) LIKE LOWER($2)
             ORDER BY date_received DESC`,
            [requestId, `%${args.file_name}%`],
        );

        if (rows.length === 0) {
            return `No file matching "${args.file_name}" found for this request. Use list_all_files to see all available files.`;
        }

        const formatted = rows.map((f: any, i: number) => {
            const size = f.file_size ? `${(f.file_size / 1024).toFixed(1)} KB` : 'Unknown size';
            let output = `### ${i + 1}. ${f.file_name}\n`;
            output += `- **File ID**: ${f.id}\n`;
            output += `- **Type**: ${f.file_type || 'unknown'} (${f.category || 'uncategorized'})\n`;
            output += `- **Size**: ${size}\n`;
            output += `- **Status**: ${f.status || 'pending'}\n`;
            if (f.processing_stage) output += `- **Processing Stage**: ${f.processing_stage}\n`;
            output += `- **Received**: ${f.date_received || 'Unknown'}\n`;
            output += `- **Graph Synced**: ${f.graph_synced ? 'Yes ✅' : 'No'}\n`;
            output += `- **Has Content**: `;
            const content = [];
            if (f.has_summary) content.push('AI Summary');
            if (f.has_text) content.push('Extracted Text');
            if (f.has_transcript) content.push('Transcript');
            output += content.length > 0 ? content.join(', ') : 'Not yet processed';
            return output;
        }).join('\n\n');

        return `Found ${rows.length} file(s) matching "${args.file_name}":\n\n${formatted}`;
    } catch (err) {
        console.error('[Tools] locateFile failed:', err);
        return 'Failed to look up file. The database may be unavailable.';
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: find_in_document
// ─────────────────────────────────────────────────────────────────────────────

export async function findInDocument(
    requestId: string,
    args: { file_name: string; search_term: string },
): Promise<string> {
    try {
        // Find the document first
        const { rows } = await pool.query(
            `SELECT id, file_name, extracted_text, ai_summary, transcript
             FROM received_data 
             WHERE request_id = $1 AND LOWER(file_name) LIKE LOWER($2)
             ORDER BY date_received DESC LIMIT 5`,
            [requestId, `%${args.file_name}%`],
        );

        if (rows.length === 0) {
            return `No file matching "${args.file_name}" found. Use list_all_files to see available documents.`;
        }

        const results: string[] = [];
        const searchLower = args.search_term.toLowerCase();

        for (const doc of rows) {
            const file = doc as any;
            const matches: { source: string; excerpts: string[] }[] = [];

            // Search in extracted text
            if (file.extracted_text) {
                const excerpts = findExcerpts(file.extracted_text, searchLower);
                if (excerpts.length > 0) matches.push({ source: 'Extracted Text', excerpts });
            }

            // Search in AI summary
            if (file.ai_summary) {
                const excerpts = findExcerpts(file.ai_summary, searchLower);
                if (excerpts.length > 0) matches.push({ source: 'AI Summary', excerpts });
            }

            // Search in transcript
            if (file.transcript) {
                const excerpts = findExcerpts(file.transcript, searchLower);
                if (excerpts.length > 0) matches.push({ source: 'Transcript', excerpts });
            }

            if (matches.length > 0) {
                let output = `### 📄 ${file.file_name}\n`;
                for (const m of matches) {
                    output += `\n**In ${m.source}:**\n`;
                    for (const excerpt of m.excerpts) {
                        output += `> ...${excerpt}...\n\n`;
                    }
                }
                results.push(output);
            } else {
                results.push(`### 📄 ${file.file_name}\nNo matches for "${args.search_term}" found in this document's content.`);
            }
        }

        return results.join('\n\n---\n\n');
    } catch (err) {
        console.error('[Tools] findInDocument failed:', err);
        return 'Failed to search within document. The database may be unavailable.';
    }
}

/** Find excerpts around search term occurrences, with surrounding context */
function findExcerpts(text: string, searchTerm: string, contextChars = 150, maxExcerpts = 5): string[] {
    const lowerText = text.toLowerCase();
    const excerpts: string[] = [];
    let startPos = 0;

    while (excerpts.length < maxExcerpts) {
        const idx = lowerText.indexOf(searchTerm, startPos);
        if (idx === -1) break;

        const excerptStart = Math.max(0, idx - contextChars);
        const excerptEnd = Math.min(text.length, idx + searchTerm.length + contextChars);
        let excerpt = text.substring(excerptStart, excerptEnd).trim();

        // Bold the matching term for highlighting
        const matchText = text.substring(idx, idx + searchTerm.length);
        excerpt = excerpt.replace(new RegExp(escapeRegex(matchText), 'gi'), `**${matchText}**`);

        excerpts.push(excerpt);
        startPos = idx + searchTerm.length;
    }

    return excerpts;
}

function escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool: list_all_files
// ─────────────────────────────────────────────────────────────────────────────

export async function listAllFiles(requestId: string): Promise<string> {
    try {
        const { rows } = await pool.query(
            `SELECT file_name, file_type, category, file_size, status, 
                    processing_stage, date_received, graph_synced,
                    ai_summary IS NOT NULL as has_summary,
                    extracted_text IS NOT NULL as has_text
             FROM received_data 
             WHERE request_id = $1
             ORDER BY date_received DESC`,
            [requestId],
        );

        if (rows.length === 0) {
            return 'No files have been uploaded for this request yet.';
        }

        // Summary stats
        const total = rows.length;
        const completed = rows.filter((r: any) => r.status === 'completed').length;
        const processing = rows.filter((r: any) => r.status === 'processing').length;
        const errors = rows.filter((r: any) => r.status === 'error').length;
        const graphSynced = rows.filter((r: any) => r.graph_synced).length;

        let output = `## Files Overview\n`;
        output += `- **Total**: ${total} file(s)\n`;
        output += `- **Completed**: ${completed} | **Processing**: ${processing} | **Errors**: ${errors}\n`;
        output += `- **Graph Synced**: ${graphSynced}/${total}\n\n`;

        // File-type breakdown
        const byCategory: Record<string, number> = {};
        for (const r of rows) {
            const cat = (r as any).category || 'other';
            byCategory[cat] = (byCategory[cat] || 0) + 1;
        }
        output += `**By Category**: ${Object.entries(byCategory).map(([k, v]) => `${k} (${v})`).join(', ')}\n\n`;

        // File list
        output += `| # | File Name | Type | Status | Analyzed |\n`;
        output += `|---|-----------|------|--------|----------|\n`;

        for (let i = 0; i < rows.length; i++) {
            const f = rows[i] as any;
            const status = f.status === 'completed' ? '✅' : f.status === 'processing' ? '⏳' : f.status === 'error' ? '❌' : '⏸️';
            const analyzed = f.has_summary || f.has_text ? '✅' : '—';
            const name = f.file_name.length > 40 ? f.file_name.substring(0, 37) + '...' : f.file_name;
            output += `| ${i + 1} | ${name} | ${f.category || '—'} | ${status} ${f.status || 'pending'} | ${analyzed} |\n`;
        }

        return output;
    } catch (err) {
        console.error('[Tools] listAllFiles failed:', err);
        return 'Failed to list files. The database may be unavailable.';
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool Executor — Routes function calls to implementations
// ─────────────────────────────────────────────────────────────────────────────

export async function executeTool(
    requestId: string,
    toolName: string,
    args: Record<string, unknown>,
): Promise<string> {
    console.log(`[RLM] Executing tool: ${toolName}`, args);

    switch (toolName) {
        case 'search_knowledge_graph':
            return searchKnowledgeGraph(requestId, args as { query: string; entity_type?: string; relationship_type?: string });

        case 'search_documents':
            return searchDocumentsImpl(requestId, args as { query: string; file_type?: string });

        case 'lookup_privacy_policy':
            return lookupPrivacyPolicy(requestId);

        case 'get_gdpr_reference':
            return getGDPRReference(args as { topic: string });

        case 'decompose_query':
            return decomposeQuery(args as { query: string; reason: string });

        case 'locate_file':
            return locateFile(requestId, args as { file_name: string });

        case 'find_in_document':
            return findInDocument(requestId, args as { file_name: string; search_term: string });

        case 'list_all_files':
            return listAllFiles(requestId);

        default:
            return `Unknown tool: ${toolName}`;
    }
}
