'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Shield, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface PrivacyScoreCardProps {
    score: number;
    breakdown: {
        dataMinimization: number;
        companyCompliance: number;
        requestSuccess: number;
    };
}

export function PrivacyScoreCard({ score, breakdown }: PrivacyScoreCardProps) {
    const getScoreColor = (s: number) => {
        if (s >= 80) return 'text-green-500';
        if (s >= 60) return 'text-yellow-500';
        return 'text-red-500';
    };

    const getScoreGradient = (s: number) => {
        if (s >= 80) return 'from-green-500 to-emerald-600';
        if (s >= 60) return 'from-yellow-500 to-orange-500';
        return 'from-red-500 to-rose-600';
    };

    const getScoreLabel = (s: number) => {
        if (s >= 80) return 'Excellent';
        if (s >= 60) return 'Good';
        if (s >= 40) return 'Fair';
        return 'Needs Work';
    };

    const getTrend = (s: number) => {
        if (s >= 80) return { icon: TrendingUp, label: 'Excellent progress', color: 'text-green-500' };
        if (s >= 60) return { icon: TrendingUp, label: 'Good standing', color: 'text-green-500' };
        if (s >= 40) return { icon: Minus, label: 'Room for improvement', color: 'text-yellow-500' };
        return { icon: TrendingDown, label: 'Needs attention', color: 'text-red-500' };
    };

    const trend = getTrend(score);
    const TrendIcon = trend.icon;

    return (
        <Card className="relative overflow-hidden">
            {/* Gradient Background */}
            <div className={`absolute inset-0 bg-gradient-to-br ${getScoreGradient(score)} opacity-5`} />

            <CardContent className="p-6">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`p-3 rounded-xl bg-gradient-to-br ${getScoreGradient(score)} shadow-lg`}>
                            <Shield className="h-6 w-6 text-white" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-muted-foreground">Privacy Score</p>
                            <div className="flex items-baseline gap-2">
                                <span className={`text-4xl font-bold ${getScoreColor(score)}`}>{score}</span>
                                <span className="text-lg text-muted-foreground">/100</span>
                            </div>
                        </div>
                    </div>

                    <div className="text-right">
                        <Badge variant="outline" className={`${getScoreColor(score)} border-current`}>
                            {getScoreLabel(score)}
                        </Badge>
                        <div className={`flex items-center gap-1 mt-2 text-xs ${trend.color}`}>
                            <TrendIcon className="h-3 w-3" />
                            <span>{trend.label}</span>
                        </div>
                    </div>
                </div>

                {/* Score Breakdown */}
                <div className="mt-6 space-y-3">
                    <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Data Minimization</span>
                            <span className="font-medium">{breakdown.dataMinimization}%</span>
                        </div>
                        <Progress value={breakdown.dataMinimization} className="h-1.5" />
                    </div>
                    <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Company Compliance</span>
                            <span className="font-medium">{breakdown.companyCompliance}%</span>
                        </div>
                        <Progress value={breakdown.companyCompliance} className="h-1.5" />
                    </div>
                    <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Request Success Rate</span>
                            <span className="font-medium">{breakdown.requestSuccess}%</span>
                        </div>
                        <Progress value={breakdown.requestSuccess} className="h-1.5" />
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
