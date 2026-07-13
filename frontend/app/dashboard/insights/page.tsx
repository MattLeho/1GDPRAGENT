import { Suspense } from 'react';
import { PersonalInsightsDashboard } from '@/components/insights/PersonalInsightsDashboard';

export default function PersonalInsightsPage() {
    return (
        <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading Personal Insights…</div>}>
            <PersonalInsightsDashboard />
        </Suspense>
    );
}
