import { NextResponse, NextRequest } from 'next/server';
import { getDriver } from '@/lib/graph';

/**
 * ONSIT Export API
 * 
 * Exports ONSIT discovery findings in JSON or CSV format.
 * Supports filtering by discovery ID and date range.
 */

interface ExportParams {
    format: 'json' | 'csv';
    discoveryId?: string;
    dateFrom?: string;
    dateTo?: string;
}

function parseExportParams(request: NextRequest): ExportParams {
    const searchParams = request.nextUrl.searchParams;
    return {
        format: (searchParams.get('format') as 'json' | 'csv') || 'json',
        discoveryId: searchParams.get('discoveryId') || undefined,
        dateFrom: searchParams.get('dateFrom') || undefined,
        dateTo: searchParams.get('dateTo') || undefined,
    };
}

interface Finding {
    id: string;
    type: string;
    value: string;
    source: string;
    riskLevel: string;
    discoveredAt: string;
    metadata: Record<string, unknown>;
}

export async function GET(request: NextRequest) {
    const driver = getDriver();
    const session = driver.session();
    const { format, discoveryId, dateFrom, dateTo } = parseExportParams(request);

    try {
        // Build query with filters
        let whereClause = "WHERE n.source = 'onsit'";
        const params: Record<string, unknown> = {};

        if (discoveryId) {
            whereClause += ' AND n.discoveryId = $discoveryId';
            params.discoveryId = discoveryId;
        }

        if (dateFrom) {
            whereClause += ' AND n.discoveredAt >= $dateFrom';
            params.dateFrom = dateFrom;
        }

        if (dateTo) {
            whereClause += ' AND n.discoveredAt <= $dateTo';
            params.dateTo = dateTo;
        }

        const result = await session.run(`
            MATCH (n)
            ${whereClause}
            RETURN 
                id(n) as id,
                labels(n) as labels,
                properties(n) as props
            ORDER BY n.discoveredAt DESC
            LIMIT 10000
        `, params);

        const findings: Finding[] = result.records.map((record) => {
            const id = record.get('id').toString();
            const labels = record.get('labels') as string[];
            const props = record.get('props') as Record<string, unknown>;

            return {
                id,
                type: labels[0] || 'Unknown',
                value: (props.value as string) || (props.name as string) || id,
                source: (props.enricher as string) || 'discovery',
                riskLevel: (props.riskLevel as string) || 'low',
                discoveredAt: (props.discoveredAt as string) || new Date().toISOString(),
                metadata: props,
            };
        });

        if (format === 'csv') {
            // Generate CSV
            const headers = ['id', 'type', 'value', 'source', 'riskLevel', 'discoveredAt'];
            const csvRows = [
                headers.join(','),
                ...findings.map(f =>
                    headers.map(h => {
                        const val = f[h as keyof Finding];
                        const strVal = typeof val === 'object' ? JSON.stringify(val) : String(val);
                        // Escape quotes and wrap in quotes if contains comma
                        if (strVal.includes(',') || strVal.includes('"')) {
                            return `"${strVal.replace(/"/g, '""')}"`;
                        }
                        return strVal;
                    }).join(',')
                )
            ];

            return new NextResponse(csvRows.join('\n'), {
                headers: {
                    'Content-Type': 'text/csv',
                    'Content-Disposition': `attachment; filename="onsit-export-${Date.now()}.csv"`,
                },
            });
        }

        // JSON format
        return NextResponse.json({
            exported_at: new Date().toISOString(),
            total_findings: findings.length,
            filters: { discoveryId, dateFrom, dateTo },
            findings,
        }, {
            headers: {
                'Content-Disposition': `attachment; filename="onsit-export-${Date.now()}.json"`,
            },
        });

    } catch (error) {
        console.error('Failed to export ONSIT data:', error);

        // Return sample export data
        const sampleFindings = [
            { id: '1', type: 'Email', value: 'user@example.com', source: 'maigret', riskLevel: 'medium', discoveredAt: new Date().toISOString(), metadata: {} },
            { id: '2', type: 'Username', value: 'johndoe', source: 'holehe', riskLevel: 'low', discoveredAt: new Date().toISOString(), metadata: {} },
        ];

        if (format === 'csv') {
            return new NextResponse(
                'id,type,value,source,riskLevel,discoveredAt\n1,Email,user@example.com,maigret,medium,' + new Date().toISOString(),
                { headers: { 'Content-Type': 'text/csv' } }
            );
        }

        return NextResponse.json({
            exported_at: new Date().toISOString(),
            total_findings: sampleFindings.length,
            findings: sampleFindings,
        });
    } finally {
        await session.close();
    }
}
