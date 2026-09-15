'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ListTree } from 'lucide-react';

interface RequestStateCardProps {
    states: { state: string; count: number }[];
}

function stateLabel(state: string): string {
    return state.replaceAll('_', ' ');
}

export function RequestStateCard({ states }: RequestStateCardProps) {
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <ListTree className="h-4 w-4" aria-hidden="true" />
                    Requests by state
                </CardTitle>
            </CardHeader>
            <CardContent>
                <ul className="space-y-2" aria-label="Request state counts">
                    {states.map(({ state, count }) => (
                        <li key={state} className="flex items-center justify-between gap-3 text-sm">
                            <span className="capitalize text-muted-foreground">{stateLabel(state)}</span>
                            <Badge variant="secondary">{count}</Badge>
                        </li>
                    ))}
                </ul>
                {states.length === 0 && <p className="text-sm text-muted-foreground">No request records yet.</p>}
            </CardContent>
        </Card>
    );
}
