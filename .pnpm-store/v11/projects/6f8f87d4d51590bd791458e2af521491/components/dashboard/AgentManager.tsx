'use client';

import Link from 'next/link';
import { ArrowRight, Bot, Database, FileSearch, FileUp, Mail, Shield } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const workflows = [
    {
        name: 'Policy Analyzer',
        description: 'Start a request with a public company or privacy-policy URL.',
        action: 'Start request',
        href: '/requests/new',
        icon: FileSearch,
    },
    {
        name: 'Inbox Monitor',
        description: 'Configure the email connector and inbox workflow before monitoring.',
        action: 'Configure',
        href: '/dashboard/settings',
        icon: Mail,
    },
    {
        name: 'Knowledge Graph',
        description: 'Explore evidence already projected into your privacy graph.',
        action: 'Open graph',
        href: '/dashboard/graph',
        icon: Database,
    },
    {
        name: 'Broker Discovery',
        description: 'Run a bounded discovery from identity seeds you provide.',
        action: 'Open discovery',
        href: '/dashboard/onsit',
        icon: Shield,
    },
    {
        name: 'Data Import',
        description: 'Upload a GDPR export for reviewable evidence processing.',
        action: 'Import data',
        href: '/dashboard/import',
        icon: FileUp,
    },
] as const;

export function AgentManager() {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <CardTitle className="flex items-center gap-2 text-sm font-medium">
                        <Bot className="h-4 w-4 text-indigo-500" />
                        Workflow shortcuts
                    </CardTitle>
                    <Badge variant="secondary" className="text-xs">Manual actions</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                    Open the workflow with the context it needs. Recurring execution is not configured from this panel.
                </p>
            </CardHeader>
            <CardContent className="space-y-2">
                {workflows.map((workflow) => {
                    const WorkflowIcon = workflow.icon;
                    return (
                        <div
                            key={workflow.name}
                            className="flex min-w-0 flex-col gap-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800 sm:flex-row sm:items-center sm:justify-between"
                        >
                            <div className="flex min-w-0 items-start gap-3">
                                <WorkflowIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                <div className="min-w-0">
                                    <p className="text-sm font-medium">{workflow.name}</p>
                                    <p className="text-xs leading-relaxed text-muted-foreground">{workflow.description}</p>
                                </div>
                            </div>
                            <Button asChild variant="outline" size="sm" className="min-h-11 w-full shrink-0 justify-between sm:min-h-9 sm:w-auto">
                                <Link href={workflow.href}>
                                    {workflow.action}
                                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                                </Link>
                            </Button>
                        </div>
                    );
                })}
            </CardContent>
        </Card>
    );
}
