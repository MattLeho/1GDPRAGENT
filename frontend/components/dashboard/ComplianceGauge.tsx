'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

interface ComplianceGaugeProps {
    deadlinesMet: number;
    deadlinesMissed: number;
    avgResponseDays: number;
    fastestResponseDays: number;
}

export function ComplianceGauge({
    deadlinesMet,
    deadlinesMissed,
    avgResponseDays,
    fastestResponseDays
}: ComplianceGaugeProps) {
    const total = deadlinesMet + deadlinesMissed || 1;
    const complianceRate = (deadlinesMet / total) * 100;
    const gdprLimit = 30;
    const daysRemaining = gdprLimit - avgResponseDays;

    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                    GDPR Compliance
                    <Badge
                        variant="outline"
                        className={complianceRate === 100 ? 'text-green-600 border-green-200' : 'text-yellow-600 border-yellow-200'}
                    >
                        {complianceRate.toFixed(0)}% On Time
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Circular Progress Visual */}
                <div className="flex items-center justify-center py-4">
                    <div className="relative w-32 h-32">
                        {/* Background Circle */}
                        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                            <circle
                                cx="50"
                                cy="50"
                                r="40"
                                fill="transparent"
                                stroke="currentColor"
                                strokeWidth="8"
                                className="text-zinc-200 dark:text-zinc-800"
                            />
                            <circle
                                cx="50"
                                cy="50"
                                r="40"
                                fill="transparent"
                                stroke="currentColor"
                                strokeWidth="8"
                                strokeDasharray={`${complianceRate * 2.51} 251`}
                                strokeLinecap="round"
                                className={complianceRate >= 80 ? 'text-green-500' : complianceRate >= 50 ? 'text-yellow-500' : 'text-red-500'}
                            />
                        </svg>
                        {/* Center Text */}
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-3xl font-bold">{avgResponseDays}</span>
                            <span className="text-xs text-muted-foreground">avg days</span>
                        </div>
                    </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-green-50 dark:bg-green-900/20">
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                        <div>
                            <p className="text-lg font-bold text-green-600">{deadlinesMet}</p>
                            <p className="text-xs text-muted-foreground">Met Deadline</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20">
                        <AlertTriangle className="h-4 w-4 text-red-600" />
                        <div>
                            <p className="text-lg font-bold text-red-600">{deadlinesMissed}</p>
                            <p className="text-xs text-muted-foreground">Missed</p>
                        </div>
                    </div>
                </div>

                {/* GDPR Timer */}
                <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-900">
                    <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            <span>GDPR 30-day limit</span>
                        </div>
                        <span className="font-medium">{daysRemaining} days buffer</span>
                    </div>
                    <Progress value={(avgResponseDays / gdprLimit) * 100} className="h-2 mt-2" />
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                        <span>0 days</span>
                        <span>30 days (GDPR max)</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
