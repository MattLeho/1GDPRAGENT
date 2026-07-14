import { NextResponse, NextRequest } from 'next/server';
import neo4j from 'neo4j-driver';
import { getDriver } from '@/lib/graph';
import { getGraphNodeLabel, pickGraphNodeType } from '@/lib/graph/schema';
import { requireApiSession } from '@/lib/api-session';
import type { GraphEpistemicState, ProfileLayer } from '@/lib/privacy/types';

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
    assertionId: string;
    epistemicState: GraphEpistemicState;
    assertionStatus: string;
    evidenceLocatorIds: string[];
    sourceArtifactIds: string[];
    profileLayer: ProfileLayer;
    comparisonState?: 'added' | 'removed' | 'unchanged';
    confidence?: number|null; epistemicBasis?: string|null; dataClass?: string|null;
    validFrom?: string|null; validTo?: string|null; controllerObservedFrom?: string|null;
    controllerObservedTo?: string|null; exportedAt?: string|null; ingestedAt?: string|null;
    derivationMethod?: string|null; derivationVersion?: string|null;
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
    asOf: string | null;
    compareTo: string | null;
    profileLayer: ProfileLayer | null;
    epistemicBasis: string | null;
    assertionStatus: string | null;
    capabilityStatus: string | null;
    purpose: string | null;
    sourceArtifact: string | null;
    controller: string | null;
    dataDomain: string | null;
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
        asOf: searchParams.get('asOf'), compareTo: searchParams.get('compareTo'),
        profileLayer: searchParams.get('profileLayer') as ProfileLayer | null,
        epistemicBasis: searchParams.get('epistemicBasis'), assertionStatus: searchParams.get('assertionStatus'),
        capabilityStatus: searchParams.get('capabilityStatus'), purpose: searchParams.get('purpose'),
        sourceArtifact: searchParams.get('sourceArtifact'), controller: searchParams.get('controller'),
        dataDomain: searchParams.get('dataDomain'),
    };
}

function relationshipPredicate(alias: string, params: PaginationParams): string {
    const parts = [`${alias}.profile_id = $profileId`];
    if (!params.showInferences) parts.push(`coalesce(${alias}.edge_epistemic,'currently_observed')='currently_observed'`);
    if (params.asOf) parts.push(`(${alias}.valid_from IS NULL OR datetime(${alias}.valid_from)<=datetime($asOf)) AND (${alias}.valid_to IS NULL OR datetime(${alias}.valid_to)>datetime($asOf))`);
    if (params.epistemicBasis) parts.push(`(${alias}.edge_epistemic=$epistemicBasis OR ${alias}.epistemic_basis=$epistemicBasis)`);
    if (params.assertionStatus) parts.push(`${alias}.assertion_status=$assertionStatus`);
    if (params.capabilityStatus) parts.push(`${alias}.capability_status=$capabilityStatus`);
    if (params.sourceArtifact) parts.push(`$sourceArtifact IN coalesce(${alias}.source_artifact_ids,[])`);
    if (params.profileLayer === 'self_declared') parts.push(`${alias}.data_class='declared'`);
    if (params.profileLayer === 'observed_behaviour') parts.push(`${alias}.data_class='observed'`);
    if (params.profileLayer === 'controller_profile') parts.push(`${alias}.epistemic_basis='controller_assigned'`);
    if (params.profileLayer === 'system_hypotheses') parts.push(`coalesce(${alias}.edge_epistemic,'')='alleged_unverified'`);
    return parts.join(' AND ');
}

export async function GET(request: NextRequest) {
    const authority=await requireApiSession(request);
    if(authority instanceof NextResponse)return authority;
    const parsed = parsePaginationParams(request);
    const { limit, skip, layer, search, types, riskLevel, centerNodeId } = parsed;
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
                MATCH (center:GraphNode {node_id: $centerNodeId})-[scopeRel]-(neighbor:GraphNode)
                WHERE ${relationshipPredicate('scopeRel', parsed)}
                WITH [node IN collect(DISTINCT center) + collect(DISTINCT neighbor) WHERE node IS NOT NULL] as rawNodes
                UNWIND rawNodes as n
                RETURN DISTINCT n.node_id as id, labels(n) as labels, properties(n) as props
                ORDER BY n.node_id
                LIMIT $limit
            `, { centerNodeId, limit: neo4j.int(limit), profileId: authority.profileId, ...Object.fromEntries(request.nextUrl.searchParams) });

            const nodeIds = neighborResult.records.map(record => String(record.get('id')));
            const linksResult = nodeIds.length
                ? await session.run(`
                    MATCH (a)-[r]->(b)
                    WHERE a.node_id IN $nodeIds AND b.node_id IN $nodeIds AND ${relationshipPredicate('r', parsed)}
                    RETURN a.node_id as source, b.node_id as target, type(r) as type,
                           r.assertion_id as assertion_id,r.edge_epistemic as edge_epistemic,
                           r.assertion_status as assertion_status,r.evidence_locator_ids as evidence_locator_ids,
                           r.source_artifact_ids as source_artifact_ids,r.data_class as data_class,
                           r.epistemic_basis as epistemic_basis,r.valid_from as valid_from,r.valid_to as valid_to,
                           r.confidence as confidence,r.controller_observed_from as controller_observed_from,
                           r.controller_observed_to as controller_observed_to,r.exported_at as exported_at,
                           r.ingested_at as ingested_at,r.derivation_method as derivation_method,
                           r.derivation_version as derivation_version
                    LIMIT 2000
                `, { nodeIds, profileId: authority.profileId, ...Object.fromEntries(request.nextUrl.searchParams) })
                : { records: [] };

            return NextResponse.json({
                nodes: recordsToNodes(neighborResult.records),
                links: recordsToLinks(linksResult.records, parsed.asOf, parsed.compareTo),
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
            profileId: authority.profileId,
            ...Object.fromEntries(request.nextUrl.searchParams),
        };
        nodeFilters.push(`EXISTS { MATCH (n)-[scopeRel]-() WHERE ${relationshipPredicate('scopeRel', parsed)} }`);
        if (parsed.purpose) { nodeFilters.push(`(n:Purpose AND (n.node_id=$purpose OR n.canonical_key CONTAINS $purpose))`); }
        if (parsed.controller) { nodeFilters.push(`(n:ControllerProfile OR n:Organisation) AND (n.node_id=$controller OR toLower(n.canonical_key) CONTAINS toLower($controller))`); }
        if (parsed.dataDomain) { nodeFilters.push(`n:DataDomain AND (n.node_id=$dataDomain OR toLower(n.canonical_key) CONTAINS toLower($dataDomain))`); }

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
            WHERE a.node_id IN $nodeIds AND b.node_id IN $nodeIds AND ${relationshipPredicate('r', parsed)}
            RETURN a.node_id as source, b.node_id as target, type(r) as type,
                   r.assertion_id as assertion_id,r.edge_epistemic as edge_epistemic,
                   r.assertion_status as assertion_status,r.evidence_locator_ids as evidence_locator_ids,
                   r.source_artifact_ids as source_artifact_ids,r.data_class as data_class,
                   r.epistemic_basis as epistemic_basis,r.valid_from as valid_from,r.valid_to as valid_to,
                   r.confidence as confidence,r.controller_observed_from as controller_observed_from,
                   r.controller_observed_to as controller_observed_to,r.exported_at as exported_at,
                   r.ingested_at as ingested_at,r.derivation_method as derivation_method,
                   r.derivation_version as derivation_version
            LIMIT 2000
        `, { nodeIds, ...params });

        const nodes = recordsToNodes(nodeRecords);
        const links = recordsToLinks(linksResult.records, parsed.asOf, parsed.compareTo);

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
            filters: { asOf: parsed.asOf, compareTo: parsed.compareTo, profileLayer: parsed.profileLayer,
                epistemicBasis: parsed.epistemicBasis, assertionStatus: parsed.assertionStatus,
                capabilityStatus: parsed.capabilityStatus, purpose: parsed.purpose,
                sourceArtifact: parsed.sourceArtifact, controller: parsed.controller, dataDomain: parsed.dataDomain },
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

function recordsToLinks(records: Array<{ get: (key: string) => unknown }>, asOf: string | null, compareTo: string | null): GraphLink[] {
    return records.map((record) => ({
        source: record.get('source')!.toString(),
        target: record.get('target')!.toString(),
        type: record.get('type') as string,
        assertionId: String(record.get('assertion_id') || ''),
        epistemicState: (record.get('edge_epistemic') || 'currently_observed') as GraphEpistemicState,
        assertionStatus: String(record.get('assertion_status') || 'accepted'),
        evidenceLocatorIds: ((record.get('evidence_locator_ids') as unknown[]) || []).map(String),
        sourceArtifactIds: ((record.get('source_artifact_ids') as unknown[]) || []).map(String),
        profileLayer: record.get('epistemic_basis') === 'controller_assigned' ? 'controller_profile'
            : record.get('edge_epistemic') === 'alleged_unverified' ? 'system_hypotheses'
            : record.get('data_class') === 'declared' ? 'self_declared' : 'observed_behaviour',
        confidence: record.get('confidence') == null ? null : Number(record.get('confidence')),
        epistemicBasis: record.get('epistemic_basis') == null ? null : String(record.get('epistemic_basis')),
        dataClass: record.get('data_class') == null ? null : String(record.get('data_class')),
        validFrom: record.get('valid_from') == null ? null : String(record.get('valid_from')),
        validTo: record.get('valid_to') == null ? null : String(record.get('valid_to')),
        controllerObservedFrom: record.get('controller_observed_from') == null ? null : String(record.get('controller_observed_from')),
        controllerObservedTo: record.get('controller_observed_to') == null ? null : String(record.get('controller_observed_to')),
        exportedAt: record.get('exported_at') == null ? null : String(record.get('exported_at')),
        ingestedAt: record.get('ingested_at') == null ? null : String(record.get('ingested_at')),
        derivationMethod: record.get('derivation_method') == null ? null : String(record.get('derivation_method')),
        derivationVersion: record.get('derivation_version') == null ? null : String(record.get('derivation_version')),
        ...(asOf && compareTo ? { comparisonState: comparisonState(record.get('valid_from'), record.get('valid_to'), asOf, compareTo) } : {}),
    }));
}

function comparisonState(from: unknown, to: unknown, first: string, second: string): 'added' | 'removed' | 'unchanged' {
    const active = (point: string) => (!from || new Date(String(from)) <= new Date(point)) && (!to || new Date(String(to)) > new Date(point));
    const before = active(second), after = active(first);
    return before === after ? 'unchanged' : after ? 'added' : 'removed';
}

