'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { AlertTriangle, CalendarClock, Clock3 } from 'lucide-react';

interface DeadlineEvidenceCardProps {
    knownUpcoming: number;
    unknown: number;
    responseDuration: {
        sampleCount: number;
        averageDays: number | null;
        fastestDays: number | null;
    };
}

export function DeadlineEvidenceCard({ knownUpcoming, unknown, responseDuration }: DeadlineEvidenceCardProps) {
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Deadline and response evidence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-900/20">
                        <CalendarClock className="h-4 w-4 text-blue-600" aria-hidden="true" />
                        <p className="mt-2 text-2xl font-bold">{knownUpcoming}</p>
                        <p className="text-xs text-muted-foreground">Known upcoming explicit deadlines</p>
                    </div>
                    <div className="rounded-lg bg-amber-50 p-3 dark:bg-amber-900/20">
                        <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                        <p className="mt-2 text-2xl font-bold">{unknown}</p>
                        <p className="text-xs text-muted-foreground">Active requests with unknown deadline</p>
                    </div>
                </div>
                <div className="rounded-lg border p-3">
                    <div className="flex items-center gap-2 text-sm font-medium">
                        <Clock3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                        Evidence-backed response-duration screening
                    </div>
                    {responseDuration.sampleCount > 0 ? (
                        <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
                            <div><p className="font-bold">{responseDuration.sampleCount}</p><p className="text-xs text-muted-foreground">paired dates</p></div>
                            <div><p className="font-bold">{responseDuration.averageDays} days</p><p className="text-xs text-muted-foreground">average</p></div>
                            <div><p className="font-bold">{responseDuration.fastestDays} days</p><p className="text-xs text-muted-foreground">fastest</p></div>
                        </div>
                    ) : (
                        <p className="mt-2 text-xs text-muted-foreground">
                            No requests have both controller receipt and response receipt dates.
                        </p>
                    )}
                    <p className="mt-3 text-xs text-muted-foreground">
                        Screening only; this does not determine legal timeliness.
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}
