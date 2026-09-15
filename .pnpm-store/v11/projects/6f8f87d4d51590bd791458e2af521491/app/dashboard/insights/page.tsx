import { Suspense } from 'react';
import { PersonalInsightsDashboard } from '@/components/insights/PersonalInsightsDashboard';

export default function PersonalInsightsPage() {
    const initialNow = new Date().toISOString();
    return (
        <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading Personal Insights…</div>}>
            <PersonalInsightsDashboard initialNow={initialNow} />
        </Suspense>
    );
}
