import { pool } from '@/lib/db';

export type DataArtifactType =
    | 'table'
    | 'chart_spec'
    | 'geo_points'
    | 'timeline_events'
    | 'document_outline'
    | 'json_schema'
    | 'html_preview'
    | 'metric'
    | 'risk_signal';

export interface DataArtifact {
    id?: string;
    request_id: string;
    file_id: string;
    artifact_type: DataArtifactType;
    title: string;
    payload: Record<string, unknown>;
    confidence?: number;
    source_span?: string | null;
}

export interface ArtifactSourceFile {
    id: string;
    request_id: string;
    file_name: string;
    file_size_mb?: number | string | null;
    file_type?: string | null;
    category?: string | null;
    ai_summary?: string | null;
    entities_extracted?: unknown;
    extracted_entities?: unknown;
    date_received?: string | Date | null;
}

const MAX_TABLE_ROWS = 250;
const MAX_TEXT_LENGTH = 120_000;
const coordinatePattern = /(-?\d{1,2}\.\d{3,})\s*[,;]\s*(-?\d{1,3}\.\d{3,})/g;
const isoDatePattern = /\b(\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z?)?)\b/g;
const commonDatePattern = /\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b/g;
const emailPattern = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const ipPattern = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;

export async function ensureDataArtifactsTable() {
    await pool.query(`
        CREATE TABLE IF NOT EXISTS data_artifacts (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
            file_id UUID REFERENCES received_data(id) ON DELETE CASCADE,
            artifact_type TEXT NOT NULL,
            title TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence NUMERIC DEFAULT 1.0,
            source_span TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    `);

    await pool.query(`CREATE INDEX IF NOT EXISTS idx_data_artifacts_request_id ON data_artifacts(request_id)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_data_artifacts_file_id ON data_artifacts(file_id)`);
    await pool.query(`CREATE INDEX IF NOT EXISTS idx_data_artifacts_type ON data_artifacts(artifact_type)`);
}

export async function replaceArtifactsForFile(file: ArtifactSourceFile, content: string): Promise<DataArtifact[]> {
    if (!file.request_id || !file.id) {
        return [];
    }

    await ensureDataArtifactsTable();
    const artifacts = generateArtifacts(file, content);

    await pool.query('DELETE FROM data_artifacts WHERE file_id = $1', [file.id]);

    for (const artifact of artifacts) {
        await pool.query(
            `INSERT INTO data_artifacts
             (request_id, file_id, artifact_type, title, payload, confidence, source_span, updated_at)
             VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, NOW())`,
            [
                artifact.request_id,
                artifact.file_id,
                artifact.artifact_type,
                artifact.title,
                JSON.stringify(artifact.payload),
                artifact.confidence ?? 1,
                artifact.source_span || null,
            ],
        );
    }

    return artifacts;
}

export async function getArtifactsForRequest(requestId: string): Promise<DataArtifact[]> {
    await ensureDataArtifactsTable();
    const result = await pool.query(
        `SELECT id, request_id, file_id, artifact_type, title, payload, confidence, source_span
         FROM data_artifacts
         WHERE request_id = $1
         ORDER BY created_at ASC`,
        [requestId],
    );

    return result.rows.map(row => ({
        ...row,
        payload: typeof row.payload === 'string' ? JSON.parse(row.payload) : row.payload,
        confidence: Number(row.confidence ?? 1),
    }));
}

export function generateArtifacts(file: ArtifactSourceFile, rawContent: string): DataArtifact[] {
    const content = rawContent.slice(0, MAX_TEXT_LENGTH);
    const artifacts: DataArtifact[] = [];
    const base = {
        request_id: file.request_id,
        file_id: file.id,
    };

    artifacts.push({
        ...base,
        artifact_type: 'metric',
        title: 'File Processing Summary',
        payload: {
            fileName: file.file_name,
            fileType: file.file_type || 'unknown',
            category: file.category || 'other',
            sizeMb: Number(file.file_size_mb || 0),
            characters: content.length,
            words: content.split(/\s+/).filter(Boolean).length,
            receivedAt: file.date_received || null,
            summary: file.ai_summary || null,
        },
    });

    const jsonValue = tryParseJson(content);
    if (jsonValue !== null) {
        const rows = flattenJsonToRows(jsonValue).slice(0, MAX_TABLE_ROWS);
        artifacts.push({
            ...base,
            artifact_type: 'json_schema',
            title: 'JSON Structure',
            payload: inferJsonSchema(jsonValue),
        });

        if (rows.length > 0) {
            artifacts.push(tableArtifact(base, 'JSON Table', rows));
            artifacts.push(chartSpecArtifact(base, 'JSON Field Coverage', rows));
        }
    }

    const delimitedRows = parseDelimitedRows(content);
    if (delimitedRows.length > 1) {
        const [headers, ...bodyRows] = delimitedRows;
        const rows = bodyRows.slice(0, MAX_TABLE_ROWS).map(row =>
            Object.fromEntries(headers.map((header, index) => [header || `Column ${index + 1}`, row[index] || ''])));
        artifacts.push(tableArtifact(base, 'Parsed Table', rows));
        artifacts.push(chartSpecArtifact(base, 'Table Field Coverage', rows));
    }

    if (looksLikeHtml(content)) {
        artifacts.push({
            ...base,
            artifact_type: 'html_preview',
            title: 'HTML Preview',
            payload: {
                text: stripHtml(content).slice(0, 8000),
                headings: extractHeadings(content),
            },
            confidence: 0.9,
        });
    }

    const outline = extractDocumentOutline(content);
    if (outline.length > 0) {
        artifacts.push({
            ...base,
            artifact_type: 'document_outline',
            title: 'Document Outline',
            payload: { headings: outline },
            confidence: 0.85,
        });
    }

    const geoPoints = extractGeoPoints(content);
    if (geoPoints.length > 0) {
        artifacts.push({
            ...base,
            artifact_type: 'geo_points',
            title: 'Location Points',
            payload: { points: geoPoints.slice(0, 1000), localFirst: true },
            confidence: 0.78,
        });
    }

    const timelineEvents = extractTimelineEvents(content);
    if (timelineEvents.length > 0) {
        artifacts.push({
            ...base,
            artifact_type: 'timeline_events',
            title: 'Timeline Events',
            payload: { events: timelineEvents.slice(0, 1000) },
            confidence: 0.75,
        });
    }

    const riskSignals = extractRiskSignals(content, file);
    for (const signal of riskSignals) {
        artifacts.push({
            ...base,
            artifact_type: 'risk_signal',
            title: signal.title,
            payload: signal,
            confidence: signal.confidence,
            source_span: signal.source,
        });
    }

    return artifacts;
}

function tableArtifact(
    base: Pick<DataArtifact, 'request_id' | 'file_id'>,
    title: string,
    rows: Record<string, unknown>[],
): DataArtifact {
    const columns = Array.from(new Set(rows.flatMap(row => Object.keys(row)))).slice(0, 50);
    return {
        ...base,
        artifact_type: 'table',
        title,
        payload: { columns, rows },
        confidence: 0.9,
    };
}

function chartSpecArtifact(
    base: Pick<DataArtifact, 'request_id' | 'file_id'>,
    title: string,
    rows: Record<string, unknown>[],
): DataArtifact {
    const counts = Object.entries(
        rows.reduce<Record<string, number>>((acc, row) => {
            for (const [key, value] of Object.entries(row)) {
                if (value !== null && value !== undefined && String(value).trim()) {
                    acc[key] = (acc[key] || 0) + 1;
                }
            }
            return acc;
        }, {}),
    )
        .sort((a, b) => b[1] - a[1])
        .slice(0, 12);

    return {
        ...base,
        artifact_type: 'chart_spec',
        title,
        payload: {
            kind: 'bar',
            x: counts.map(([key]) => key),
            y: counts.map(([, value]) => value),
        },
        confidence: 0.82,
    };
}

function tryParseJson(content: string): unknown | null {
    const trimmed = content.trim();
    if (!trimmed || (!trimmed.startsWith('{') && !trimmed.startsWith('['))) {
        return null;
    }

    try {
        return JSON.parse(trimmed);
    } catch {
        return null;
    }
}

function flattenJsonToRows(value: unknown): Record<string, unknown>[] {
    if (Array.isArray(value)) {
        return value
            .filter(item => item && typeof item === 'object')
            .map(item => flattenObject(item as Record<string, unknown>));
    }

    if (value && typeof value === 'object') {
        const objectValue = value as Record<string, unknown>;
        const arrayEntry = Object.values(objectValue).find(item => Array.isArray(item)) as unknown[] | undefined;
        if (arrayEntry) {
            return flattenJsonToRows(arrayEntry);
        }
        return [flattenObject(objectValue)];
    }

    return [];
}

function flattenObject(value: Record<string, unknown>, prefix = ''): Record<string, unknown> {
    const row: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
        const nextKey = prefix ? `${prefix}.${key}` : key;
        if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
            Object.assign(row, flattenObject(entry as Record<string, unknown>, nextKey));
        } else if (Array.isArray(entry)) {
            row[nextKey] = entry.length;
        } else {
            row[nextKey] = entry;
        }
    }
    return row;
}

function inferJsonSchema(value: unknown): Record<string, unknown> {
    if (Array.isArray(value)) {
        return {
            type: 'array',
            count: value.length,
            item: value.length > 0 ? inferJsonSchema(value[0]) : { type: 'unknown' },
        };
    }

    if (value && typeof value === 'object') {
        return {
            type: 'object',
            fields: Object.fromEntries(
                Object.entries(value as Record<string, unknown>).map(([key, entry]) => [key, inferJsonSchema(entry)]),
            ),
        };
    }

    return { type: value === null ? 'null' : typeof value };
}

function parseDelimitedRows(content: string): string[][] {
    const lines = content.split(/\r?\n/).map(line => line.trim()).filter(Boolean).slice(0, MAX_TABLE_ROWS + 1);
    if (lines.length < 2) {
        return [];
    }

    const delimiter = [',', '\t', ';'].find(candidate => lines[0].split(candidate).length > 1);
    if (!delimiter) {
        return [];
    }

    return lines.map(line => line.split(delimiter).map(cell => cell.trim().replace(/^"|"$/g, '')));
}

function looksLikeHtml(content: string): boolean {
    return /<\/?[a-z][\s\S]*>/i.test(content) && /<\/(html|body|div|table|p|section|article|script)>/i.test(content);
}

function stripHtml(content: string): string {
    return content
        .replace(/<script[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function extractHeadings(content: string): string[] {
    return Array.from(content.matchAll(/<h[1-6][^>]*>([\s\S]*?)<\/h[1-6]>/gi))
        .map(match => stripHtml(match[1] || '').trim())
        .filter(Boolean)
        .slice(0, 50);
}

function extractDocumentOutline(content: string): Array<{ level: number; text: string }> {
    const markdownHeadings = Array.from(content.matchAll(/^(#{1,6})\s+(.+)$/gm))
        .map(match => ({ level: (match[1] || '').length, text: (match[2] || '').trim() }))
        .filter(heading => heading.text);

    if (markdownHeadings.length > 0) {
        return markdownHeadings.slice(0, 80);
    }

    return content
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => /^[A-Z][A-Za-z0-9\s,&:/()-]{4,80}$/.test(line))
        .slice(0, 40)
        .map(text => ({ level: 2, text }));
}

function extractGeoPoints(content: string): Array<{ lat: number; lon: number; label: string }> {
    const points: Array<{ lat: number; lon: number; label: string }> = [];
    for (const match of content.matchAll(coordinatePattern)) {
        const lat = Number(match[1]);
        const lon = Number(match[2]);
        if (Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
            points.push({ lat, lon, label: `${lat.toFixed(5)}, ${lon.toFixed(5)}` });
        }
    }
    return points;
}

function extractTimelineEvents(content: string): Array<{ date: string; label: string }> {
    const events = new Map<string, string>();
    for (const match of [...content.matchAll(isoDatePattern), ...content.matchAll(commonDatePattern)]) {
        const value = match[1];
        if (!value || events.has(value)) {
            continue;
        }
        const index = match.index || 0;
        const context = content.slice(Math.max(0, index - 80), Math.min(content.length, index + 140)).replace(/\s+/g, ' ');
        events.set(value, context);
    }

    return Array.from(events.entries()).map(([date, label]) => ({ date, label }));
}

function extractRiskSignals(content: string, file: ArtifactSourceFile): Array<{
    title: string;
    kind: string;
    count: number;
    confidence: number;
    source: string;
}> {
    const signals = [];
    const emailCount = new Set(content.match(emailPattern) || []).size;
    const ipCount = new Set(content.match(ipPattern) || []).size;
    const sensitiveTerms = ['health', 'medical', 'biometric', 'precise location', 'gps', 'financial', 'passport', 'national insurance'];
    const matchedSensitiveTerms = sensitiveTerms.filter(term => content.toLowerCase().includes(term));

    if (emailCount > 0) {
        signals.push({ title: 'Email Addresses Found', kind: 'email', count: emailCount, confidence: 0.9, source: file.file_name });
    }

    if (ipCount > 0) {
        signals.push({ title: 'IP Addresses Found', kind: 'ip', count: ipCount, confidence: 0.85, source: file.file_name });
    }

    if (matchedSensitiveTerms.length > 0) {
        signals.push({
            title: 'Sensitive Data Terms Found',
            kind: 'sensitive_terms',
            count: matchedSensitiveTerms.length,
            confidence: 0.7,
            source: matchedSensitiveTerms.join(', '),
        });
    }

    return signals;
}
