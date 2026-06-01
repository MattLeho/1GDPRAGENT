/**
 * RLM Agent — Tool Declarations
 *
 * Function tool schemas for Gemini native function calling.
 * Uses @google/genai Type enum for schema definitions.
 *
 * Architecture adapted from:
 * - RLM Paper: context as external environment, recursive decomposition
 * - RAG-Anything: hybrid vector-graph retrieval, entity extraction
 */

import { Type } from '@google/genai';

// ─────────────────────────────────────────────────────────────────────────────
// Tool: search_knowledge_graph
// Queries Neo4j for entities, relationships, and accounts
// ─────────────────────────────────────────────────────────────────────────────
export const searchKnowledgeGraphDeclaration = {
    name: 'search_knowledge_graph',
    description:
        'Search the Neo4j knowledge graph for entities, relationships, accounts, and personas ' +
        'related to this GDPR request. Use this when the user asks about people, organizations, ' +
        'data connections, or when you need structured relationship data. Returns nodes and ' +
        'relationships matching the query.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            query: {
                type: Type.STRING,
                description:
                    'Natural language query describing what to search for in the knowledge graph. ' +
                    'Examples: "email addresses linked to this persona", "accounts on social media platforms", ' +
                    '"data sharing relationships".',
            },
            entity_type: {
                type: Type.STRING,
                description:
                    'Optional. Specific entity label to filter: Persona, Account, Email, Phone, ' +
                    'IPAddress, Identifier, Document, Organization.',
            },
            relationship_type: {
                type: Type.STRING,
                description:
                    'Optional. Specific relationship type: OWNS_ACCOUNT, REGISTERED_WITH, ' +
                    'USES_EMAIL, VERIFIED_BY, ACCESSED_FROM, HAS_IDENTIFIER, MENTIONS, RELATES_TO.',
            },
        },
        required: ['query'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: search_documents
// Full-text search on received_data extracted text, summaries, transcripts
// ─────────────────────────────────────────────────────────────────────────────
export const searchDocumentsDeclaration = {
    name: 'search_documents',
    description:
        'Search uploaded documents for this request using full-text search. Searches across ' +
        'extracted text, AI summaries, and transcripts. Use this when the user asks about ' +
        'specific content in uploaded files, or when you need document evidence for an answer.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            query: {
                type: Type.STRING,
                description:
                    'Search terms to find in document content. Can be keywords, phrases, or ' +
                    'topic descriptions. Examples: "data retention policy", "consent form", "IP addresses".',
            },
            file_type: {
                type: Type.STRING,
                description:
                    'Optional. Filter by file type/category: document, spreadsheet, image, ' +
                    'audio, video, archive, other.',
            },
        },
        required: ['query'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: lookup_privacy_policy
// Fetches request details, policy analysis, and compliance status
// ─────────────────────────────────────────────────────────────────────────────
export const lookupPrivacyPolicyDeclaration = {
    name: 'lookup_privacy_policy',
    description:
        'Retrieve details about this GDPR request including the company information, request type, ' +
        'status, policy URL, and any existing policy analysis. Use this when the user asks about ' +
        'the request itself, the company, compliance status, or policy details.',
    parameters: {
        type: Type.OBJECT,
        properties: {},
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: get_gdpr_reference
// Returns relevant GDPR articles and regulations
// ─────────────────────────────────────────────────────────────────────────────
export const getGDPRReferenceDeclaration = {
    name: 'get_gdpr_reference',
    description:
        'Get relevant GDPR articles, regulations, and legal references for a specific topic. ' +
        'Use this when the user asks about their data rights, legal obligations, timelines, ' +
        'or when you need to cite specific GDPR provisions in your response.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            topic: {
                type: Type.STRING,
                description:
                    'The GDPR topic to look up. Examples: "right to erasure", "data portability", ' +
                    '"consent requirements", "data breach notification", "legitimate interest", ' +
                    '"right of access", "data processing agreement".',
            },
        },
        required: ['topic'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: decompose_query
// RLM recursive decomposition — breaks complex queries into sub-queries
// ─────────────────────────────────────────────────────────────────────────────
export const decomposeQueryDeclaration = {
    name: 'decompose_query',
    description:
        'Break down a complex user question into simpler sub-queries that can be answered ' +
        'individually and then combined. Use this when a question requires multiple types of ' +
        'information, spans different topics, or needs step-by-step reasoning. ' +
        'This is adapted from the RLM (Recursive Language Models) pattern for handling ' +
        'complex queries through programmatic decomposition.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            query: {
                type: Type.STRING,
                description: 'The complex query to decompose into simpler sub-queries.',
            },
            reason: {
                type: Type.STRING,
                description:
                    'Why this query needs decomposition — what makes it complex or multi-faceted.',
            },
        },
        required: ['query', 'reason'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: locate_file
// Names specific files with full metadata for the user
// ─────────────────────────────────────────────────────────────────────────────
export const locateFileDeclaration = {
    name: 'locate_file',
    description:
        'Look up a specific file by name or ID and return its full details including file name, ' +
        'size, type, processing status, whether it has been graph-ingested, and a download link. ' +
        'Use this when the user asks about a specific file, wants to find a particular document, ' +
        'or needs to know the status of a specific upload.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            file_name: {
                type: Type.STRING,
                description:
                    'Full or partial file name to search for. Examples: "privacy_policy.pdf", "consent", "invoice".',
            },
        },
        required: ['file_name'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: find_in_document
// Finds and highlights specific sections within a document
// ─────────────────────────────────────────────────────────────────────────────
export const findInDocumentDeclaration = {
    name: 'find_in_document',
    description:
        'Search within a specific document for a particular phrase, section, or topic. ' +
        'Returns matching excerpts with surrounding context so the user can locate exactly ' +
        'where information appears. Use this when the user wants to find a specific clause, ' +
        'paragraph, or piece of information within a known document.',
    parameters: {
        type: Type.OBJECT,
        properties: {
            file_name: {
                type: Type.STRING,
                description: 'The name (or partial name) of the file to search within.',
            },
            search_term: {
                type: Type.STRING,
                description:
                    'The text, phrase, or topic to find within the document. ' +
                    'Examples: "data retention period", "consent clause", "Article 15".',
            },
        },
        required: ['file_name', 'search_term'],
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// Tool: list_all_files
// Lists all files for the request with rich metadata
// ─────────────────────────────────────────────────────────────────────────────
export const listAllFilesDeclaration = {
    name: 'list_all_files',
    description:
        'List all files uploaded for this GDPR request with their full metadata: name, size, ' +
        'type, processing status, stage, whether they have been analyzed, and whether they ' +
        'have been ingested into the knowledge graph. Use this to give the user an overview ' +
        'of all available data or when they ask "what files do we have?".',
    parameters: {
        type: Type.OBJECT,
        properties: {},
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// All tool declarations for Gemini function calling config
// ─────────────────────────────────────────────────────────────────────────────
export const allToolDeclarations = [
    searchKnowledgeGraphDeclaration,
    searchDocumentsDeclaration,
    lookupPrivacyPolicyDeclaration,
    getGDPRReferenceDeclaration,
    decomposeQueryDeclaration,
    locateFileDeclaration,
    findInDocumentDeclaration,
    listAllFilesDeclaration,
];
