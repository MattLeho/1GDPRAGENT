'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
    PlusCircle,
    Search,
    FileText,
    Share2,
    Sparkles
} from 'lucide-react';

const quickActions = [
    {
        title: 'New Request',
        description: 'Start a new GDPR data request',
        icon: PlusCircle,
        href: '/requests/new',
        color: 'bg-gradient-to-br from-indigo-500 to-purple-600',
        primary: true,
    },
    {
        title: 'Find Company',
        description: 'Search for a company',
        icon: Search,
        href: '/dashboard/requests?focus=search',
        color: 'bg-zinc-100 dark:bg-zinc-800',
    },
    {
        title: 'View Requests',
        description: 'See all your requests',
        icon: FileText,
        href: '/dashboard/requests',
        color: 'bg-zinc-100 dark:bg-zinc-800',
    },
    {
        title: 'Data Graph',
        description: 'Explore your data map',
        icon: Share2,
        href: '/dashboard/graph',
        color: 'bg-zinc-100 dark:bg-zinc-800',
    },
];

export function QuickActions() {
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
                {quickActions.map((action) => {
                    const Icon = action.icon;

                    return (
                        <Link key={action.title} href={action.href}>
                            <div
                                className={cn(
                                    'group relative rounded-xl border p-4 transition-all hover:-translate-y-0.5 hover:shadow-md',
                                    action.primary
                                        ? 'border-transparent bg-gradient-to-br from-indigo-500 to-purple-600 text-white'
                                        : 'bg-white hover:border-zinc-300 dark:bg-zinc-900 dark:hover:border-zinc-700'
                                )}
                            >
                                <Icon className={cn('mb-2 h-5 w-5', action.primary ? 'text-white' : 'text-muted-foreground group-hover:text-foreground')} />
                                <h4 className={cn('text-sm font-medium', action.primary && 'text-white')}>
                                    {action.title}
                                </h4>
                                <p className={cn('mt-0.5 text-xs', action.primary ? 'text-white/80' : 'text-muted-foreground')}>
                                    {action.description}
                                </p>

                                {action.primary && (
                                    <div className="absolute top-3 right-3">
                                        <Sparkles className="h-4 w-4 text-white/60" />
                                    </div>
                                )}
                            </div>
                        </Link>
                    );
                })}
            </CardContent>
        </Card>
    );
}
