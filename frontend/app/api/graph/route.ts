import { NextResponse, NextRequest } from 'next/server';
import neo4j from 'neo4j-driver';
import { getDriver } from '@/lib/graph';
import { getGraphNodeLabel, pickGraphNodeType } from '@/lib/graph/schema';

/**
 * Extended GraphNode type including all ONSIT entity types
 * @see https://github.com/reconurge/flowsint - Entity types
 */
export interface GraphNode {
    id: string;
    label: string;
    type: string; // Extended to support all ONSIT types
    properties: Record<string, unknown>;
    source?: 'onsit' | 'gdpr' | 'inference' | 'manual';
    riskLevel?: 'low' | 'medium' | 'high' | 'critical';
}

export interface GraphLink {
    source: string;
    target: string;
    type: string;
    isInferred?: boolean;
}

export interface GraphData {
    nodes: GraphNode[];
    links: GraphLink[];
    pagination?: {
        hasMore: boolean;
        nextCursor: string | null;
        total: number;
    };
}

interface PaginationParams {
    limit: number;
    skip: number;
    layer?: 'onsit' | 'gdpr' | 'all';
    showInferences: boolean;
    search: string;
    types: string[];
    riskLevel: 'all' | 'low' | 'medium' | 'high' | 'critical';
    centerNodeId: string | null;
}

function parseBoundedInteger(
    value: string | null,
    fallback: number,
    minimum: number,
    maximum: number
): number {
    if (value === null || value.trim() === '') return fallback;
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) return fallback;
    return Math.min(Math.max(parsed, minimum), maximum);
}

function parsePaginationParams(request: NextRequest): PaginationParams {
    const searchParams = request.nextUrl.searchParams;
    const riskLevel = searchParams.get('riskLevel') || 'all';

    return {
        limit: parseBoundedInteger(searchParams.get('limit'), 100, 1, 500),
        skip: parseBoundedInteger(searchParams.get('skip'), 0, 0, Number.MAX_SAFE_INTEGER),
        layer: (searchParams.get('layer') as 'onsit' | 'gdpr' | 'all') || 'all',
        showInferences: searchParams.get('showInferences') === 'true',
        search: (searchParams.get('search') || '').trim().toLowerCase(),
        types: (searchParams.get('types') || '')
            .split(',')
            .map(type => type.trim())
            .filter(Boolean),
        riskLevel: ['low', 'medium', 'high', 'critical'].includes(riskLevel)
            ? riskLevel as PaginationParams['riskLevel']
            : 'all',
        centerNodeId: searchParams.get('centerNodeId'),
    };
}

export async function GET(request: NextRequest) {
    const { limit, skip, layer, showInferences, search, types, riskLevel, centerNodeId } = parsePaginationParams(request);
    let session;

    try {
        const driver = getDriver();
        session = driver.session();

        if (centerNodeId) {
            if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(centerNodeId)) {
                return NextResponse.json(
                    { nodes: [], links: [], error: 'centerNodeId must be a stable node UUID' },
                    { status: 400 }
                );
            }

            const neighborResult = await session.run(`
                MATCH (center:GraphNode {node_id: $centerNodeId})
                OPTIONAL MATCH (center)-[outRel]->(outNode)
                OPTIONAL MATCH (inNode)-[inRel]->(center)
                WITH [node IN collect(DISTINCT center) + collect(DISTINCT outNode) + collect(DISTINCT inNode) WHERE node IS NOT NULL] as rawNodes
                UNWIND rawNodes as n
                RETURN DISTINCT n.node_id as id, labels(n) as labels, properties(n) as props
                ORDER BY n.node_id
                LIMIT $limit
            `, { centerNodeId, limit: neo4j.int(limit) });

            const nodeIds = neighborResult.records.map(record => String(record.get('id')));
            const linksResult = nodeIds.length
                ? await session.run(`
                    MATCH (a)-[r]->(b)
                    WHERE a.node_id IN $nodeIds AND b.node_id IN $nodeIds ${showInferences ? '' : "AND coalesce(r.epistemic_basis, '') <> 'model_hypothesis' AND (r.inferred IS NULL OR r.inferred = false)"}
                    RETURN a.node_id as source, b.node_id as target, type(r) as type, r.inferred as inferred
                    LIMIT 2000
                `, { nodeIds })
                : { records: [] };

            return NextResponse.json({
                nodes: recordsToNodes(neighborResult.records),
                links: recordsToLinks(linksResult.records),
                pagination: {
                    hasMore: false,
                    nextCursor: null,
                    total: neighborResult.records.length,
                },
                dbStatus: 'connected',
            });
        }

        // Build safe filter clauses. Values are parameterized; label filtering uses labels(n).
        const nodeFilters: string[] = [];
        nodeFilters.push(`coalesce(n.retired, false) = false`);
        const params: Record<string, unknown> = {
            skip: neo4j.int(skip),
            limit: neo4j.int(limit + 1),
        };

        if (layer === 'onsit') {
            nodeFilters.push(`(n.source = 'onsit' OR n:ONSITFinding OR n:Email OR n:Username OR n:Domain)`);
        } else if (layer === 'gdpr') {
            nodeFilters.push(`(n.source = 'gdpr' OR n:Subject OR n:ControllerProfile OR n:Organisation OR n:DataPoint)`);
        }

        if (types.length > 0) {
            nodeFilters.push(`ANY(label IN labels(n) WHERE label IN $types)`);
            params.types = types;
        }

        if (search) {
            nodeFilters.push(`ANY(key IN keys(n) WHERE n[key] IS NOT NULL AND toLower(toString(n[key])) CONTAINS $search)`);
            params.search = search;
        }

        if (riskLevel !== 'all') {
            nodeFilters.push(`(n.riskLevel = $riskLevel OR n.risk_level = toUpper($riskLevel))`);
            params.riskLevel = riskLevel;
        }

        const nodeFilter = nodeFilters.length > 0 ? `WHERE ${nodeFilters.join(' AND ')}` : '';

        // First get total count
        const countResult = await session.run(`
            MATCH (n:GraphNode) ${nodeFilter}
            RETURN count(n) as total
        `, params);
        const total = countResult.records[0]?.get('total')?.toNumber() || 0;

        // Fetch nodes with pagination
        const nodesResult = await session.run(`
            MATCH (n:GraphNode) ${nodeFilter}
            RETURN n.node_id as id, labels(n) as labels, properties(n) as props
            ORDER BY n.node_id
            SKIP $skip
            LIMIT $limit
        `, params); // +1 to check if there's more

        // Check if there are more results
        const hasMore = nodesResult.records.length > limit;
        const nodeRecords = hasMore ? nodesResult.records.slice(0, limit) : nodesResult.records;

        // Fetch relationships for the nodes
        const nodeIds = nodeRecords.map(r => String(r.get('id')));
        const linksResult = await session.run(`
            MATCH (a)-[r]->(b)
            WHERE a.node_id IN $nodeIds AND b.node_id IN $nodeIds ${showInferences ? '' : "AND coalesce(r.epistemic_basis, '') <> 'model_hypothesis' AND (r.inferred IS NULL OR r.inferred = false)"}
            RETURN a.node_id as source, b.node_id as target, type(r) as type, r.inferred as inferred
            LIMIT 2000
        `, { nodeIds });

        const nodes = recordsToNodes(nodeRecords);
        const links = recordsToLinks(linksResult.records);

        const nextCursor = hasMore ? String(skip + limit) : null;

        return NextResponse.json({
            nodes,
            links,
            pagination: {
                hasMore,
                nextCursor,
                total,
            },
            dbStatus: 'connected',
        });
    } catch (error) {
        console.error('Failed to fetch graph data:', error);

        const neo4jError = error as { code?: string; message?: string };
        const errorText = `${neo4jError.code || ''} ${neo4jError.message || ''}`;
        const disconnected = /ServiceUnavailable|SessionExpired|Security\.Unauthorized|ECONNREFUSED|connection/i.test(errorText);

        // Return an explicit unknown/error state. Never substitute synthetic graph data.
        return NextResponse.json({
            nodes: [],
            links: [],
            pagination: {
                hasMore: false,
                nextCursor: null,
                total: 0,
            },
            error: disconnected
                ? 'Could not connect to Neo4j. Check that the service and credentials are available.'
                : 'Neo4j was reached, but the graph query failed.',
            dbStatus: disconnected ? 'disconnected' : 'error',
        });
    } finally {
        await session?.close();
    }
}

function recordsToNodes(records: Array<{ get: (key: string) => unknown }>): GraphNode[] {
    return records.map((record) => {
        const id = record.get('id')!.toString();
        const labels = record.get('labels') as string[];
        const props = record.get('props') as Record<string, unknown>;
        const type = pickGraphNodeType(labels);

        return {
            id,
            label: getGraphNodeLabel(props, type),
            type: type as GraphNode['type'],
            properties: props,
            source: props.source as GraphNode['source'],
            riskLevel: (props.riskLevel || props.risk_level) as GraphNode['riskLevel'],
        };
    });
}

function recordsToLinks(records: Array<{ get: (key: string) => unknown }>): GraphLink[] {
    return records.map((record) => ({
        source: record.get('source')!.toString(),
        target: record.get('target')!.toString(),
        type: record.get('type') as string,
        isInferred: record.get('inferred') === true,
    }));
}

