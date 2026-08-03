'use client';

import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileArchive } from 'lucide-react';

interface ReceivedArtefactCompany {
    name: string;
    artefactCount: number;
    volumeGB: number;
}

interface ReceivedArtefactsByCompanyProps {
    data: ReceivedArtefactCompany[];
}

export function ReceivedArtefactsByCompany({ data }: ReceivedArtefactsByCompanyProps) {
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between gap-2">
                    Received artefacts by company
                    <Badge variant="outline" className="text-xs font-normal">{data.length} companies</Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {data.map((company) => (
                    <div key={company.name} className="flex items-center gap-3 rounded-lg p-2 -mx-2">
                        <Avatar className="h-9 w-9 border">
                            <AvatarFallback className="text-xs font-medium">
                                {company.name.substring(0, 2).toUpperCase()}
                            </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{company.name}</p>
                            <p className="text-xs text-muted-foreground">
                                {company.artefactCount} stored {company.artefactCount === 1 ? 'artefact' : 'artefacts'} · {company.volumeGB.toFixed(2)} GB
                            </p>
                        </div>
                        <FileArchive className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    </div>
                ))}
                {data.length === 0 && (
                    <p className="py-6 text-center text-sm text-muted-foreground">No received artefacts recorded yet.</p>
                )}
            </CardContent>
        </Card>
    );
}
