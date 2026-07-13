import type {
    AIConversationInsight, ChangeInsight, InsightSnapshot, InsightTrace,
    ObservedInterestState, PlaceInsight, SearchInsight, TemporalCorrelationCandidate,
} from './types';
import { serializeInsightSelection, type InsightTemporalSelection } from './query';

export type InsightModule = 'overview' | 'interests' | 'search' | 'ai-conversations' | 'places' | 'changes' | 'context';

export interface InsightModuleResponseMap {
    overview: InsightSnapshot['overview'];
    interests: ObservedInterestState[];
    search: SearchInsight;
    'ai-conversations': AIConversationInsight;
    places: PlaceInsight;
    changes: { changes: ChangeInsight[]; project_episodes: InsightSnapshot['project_episodes']; personal_eras: InsightSnapshot['personal_eras']; drift?: Record<string, Array<Record<string, unknown>>> };
    context: TemporalCorrelationCandidate[];
}

export async function fetchInsightModule<K extends InsightModule>(
    module: K,
    selection: InsightTemporalSelection,
    subjectId?: string,
    signal?: AbortSignal,
): Promise<InsightModuleResponseMap[K]> {
    const query = serializeInsightSelection(selection, subjectId);
    const response = await fetch(`/api/insights/${module}?${query}`, { signal, cache: 'no-store' });
    if (!response.ok) throw new Error(`Personal Insights ${module} returned ${response.status}`);
    return response.json() as Promise<InsightModuleResponseMap[K]>;
}

export async function fetchInsightTrace(insightId: string, signal?: AbortSignal): Promise<InsightTrace> {
    const response = await fetch(`/api/insights/evidence/${encodeURIComponent(insightId)}`, { signal, cache: 'no-store' });
    if (!response.ok) throw new Error(`Insight evidence returned ${response.status}`);
    return response.json() as Promise<InsightTrace>;
}
