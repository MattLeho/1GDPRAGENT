'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/ui/avatar';
import { AlertTriangle, Shield, CheckCircle } from 'lucide-react';

interface DataHolder {
    name: string;
    dataPoints: number;
    riskLevel: 'low' | 'medium' | 'high';
}

interface TopDataHoldersProps {
    data: DataHolder[];
}

export function TopDataHolders({ data }: TopDataHoldersProps) {
    const getRiskStyles = (level: string) => {
        switch (level) {
            case 'high':
                return {
                    badge: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
                    icon: AlertTriangle,
                    iconColor: 'text-red-500',
                };
            case 'medium':
                return {
                    badge: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
                    icon: Shield,
                    iconColor: 'text-yellow-500',
                };
            default:
                return {
                    badge: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                    icon: CheckCircle,
                    iconColor: 'text-green-500',
                };
        }
    };

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                    Top Data Holders
                    <Badge variant="outline" className="text-xs font-normal">
                        {data.length} Companies
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                {data.map((company, idx) => {
                    const styles = getRiskStyles(company.riskLevel);
                    const Icon = styles.icon;

                    return (
                        <div
                            key={company.name}
                            className="flex items-center gap-3 p-2 -mx-2 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-colors cursor-pointer"
                        >
                            <div className="relative">
                                <Avatar className="h-9 w-9 border">
                                    <AvatarImage
                                        src={`https://logo.clearbit.com/${company.name.toLowerCase()}.com`}
                                        alt={company.name}
                                    />
                                    <AvatarFallback className="text-xs font-medium">
                                        {company.name.substring(0, 2).toUpperCase()}
                                    </AvatarFallback>
                                </Avatar>
                                <div className={`absolute -bottom-0.5 -right-0.5 rounded-full bg-white dark:bg-zinc-950 p-0.5`}>
                                    <Icon className={`h-3 w-3 ${styles.iconColor}`} />
                                </div>
                            </div>

                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{company.name}</p>
                                <p className="text-xs text-muted-foreground">
                                    {company.dataPoints} data {company.dataPoints === 1 ? 'point' : 'points'}
                                </p>
                            </div>

                            <Badge variant="secondary" className={`text-xs ${styles.badge}`}>
                                {company.riskLevel}
                            </Badge>
                        </div>
                    );
                })}

                {data.length === 0 && (
                    <div className="text-center py-6 text-muted-foreground text-sm">
                        No companies tracked yet
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
