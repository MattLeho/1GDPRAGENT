'use client';

/**
 * N8NWebhooksSection Component
 * 
 * Settings section for managing N8N workflow webhook URLs.
 * Allows users to configure webhook endpoints without modifying .env files.
 * 
 * Falls back to environment variables if not configured in-app.
 */

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import {
    Workflow,
    Save,
    Loader2,
    CheckCircle2,
    Eye,
    EyeOff,
    ExternalLink,
    Server,
    FileText,
    ScanSearch,
    Search,
    BrainCircuit,
    RefreshCw,
} from 'lucide-react';

// =============================================================================
// Schema
// =============================================================================

const n8nWebhooksSchema = z.object({
    policyAnalyzer: z.string().url().optional().or(z.literal('')),
    requestDrafter: z.string().url().optional().or(z.literal('')),
    kgIngestor: z.string().url().optional().or(z.literal('')),
    hybridRag: z.string().url().optional().or(z.literal('')),
    transcription: z.string().url().optional().or(z.literal('')),
    vendorOcr: z.string().url().optional().or(z.literal('')),
    policyScanner: z.string().url().optional().or(z.literal('')),
});

type N8NWebhooksForm = z.infer<typeof n8nWebhooksSchema>;

// =============================================================================
// Webhook Configuration
// =============================================================================

interface WebhookConfig {
    id: keyof N8NWebhooksForm;
    name: string;
    description: string;
    envVar: string;
    icon: React.ElementType;
}

const webhookConfigs: WebhookConfig[] = [
    {
        id: 'policyAnalyzer',
        name: 'Policy Analyzer',
        description: 'Uses Python intelligence agents for policy analysis and data categorization',
        envVar: 'N8N_WEBHOOK_POLICY_ANALYZER',
        icon: FileText,
    },
    {
        id: 'requestDrafter',
        name: 'Request Drafter',
        description: 'Python RLM agent for drafting requests, N8N handles email forwarding',
        envVar: 'N8N_WEBHOOK_REQUEST_DRAFTER',
        icon: FileText,
    },
    {
        id: 'kgIngestor',
        name: 'Knowledge Graph Ingestor',
        description: 'Uses Python intelligence agents to process and ingest data into Neo4j',
        envVar: 'N8N_WEBHOOK_INGEST_DATA',
        icon: BrainCircuit,
    },
    {
        id: 'hybridRag',
        name: 'Hybrid RAG',
        description: 'Hybrid Python/N8N implementation for vector + graph retrieval',
        envVar: 'N8N_WEBHOOK_ENHANCED_RAG',
        icon: Search,
    },
    {
        id: 'transcription',
        name: 'File Transcription',
        description: 'Audio/video transcription with Gemini',
        envVar: 'N8N_WEBHOOK_TRANSCRIPTION',
        icon: FileText,
    },
    {
        id: 'vendorOcr',
        name: 'Vendor OCR Extractor',
        description: 'Python-based OCR extraction for vendor discovery from screenshots',
        envVar: 'N8N_WEBHOOK_VENDOR_OCR',
        icon: ScanSearch,
    },
    {
        id: 'policyScanner',
        name: 'Privacy Policy Scanner',
        description: 'UK GDPR compliance analysis',
        envVar: 'N8N_WEBHOOK_POLICY_SCANNER',
        icon: ScanSearch,
    },
];

// =============================================================================
// Component
// =============================================================================

export function N8NWebhooksSection() {
    const [isLoading, setIsLoading] = useState(false);
    const [savedUrls, setSavedUrls] = useState<Record<string, boolean>>({});
    const [showUrls, setShowUrls] = useState<Record<string, boolean>>({});
    const [envUrls, setEnvUrls] = useState<Record<string, boolean>>({});
    const [isTestingAll, setIsTestingAll] = useState(false);

    const form = useForm<N8NWebhooksForm>({
        resolver: zodResolver(n8nWebhooksSchema),
        defaultValues: {
            policyAnalyzer: '',
            requestDrafter: '',
            kgIngestor: '',
            hybridRag: '',
            transcription: '',
            vendorOcr: '',
            policyScanner: '',
        },
    });

    // Load existing settings
    useEffect(() => {
        async function loadWebhooks() {
            try {
                const res = await fetch('/api/settings/n8n-webhooks');
                if (res.ok) {
                    const data = await res.json();
                    setSavedUrls(data.savedUrls || {});
                    setEnvUrls(data.envUrls || {});
                    // Populate form with current values
                    if (data.currentUrls) {
                        Object.entries(data.currentUrls).forEach(([key, value]) => {
                            if (value) {
                                form.setValue(key as keyof N8NWebhooksForm, value as string);
                            }
                        });
                    }
                }
            } catch (e) {
                console.error('Failed to load N8N webhooks', e);
            }
        }
        loadWebhooks();
    }, [form]);

    const handleSave = async (data: N8NWebhooksForm) => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/settings/n8n-webhooks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (res.ok) {
                const result = await res.json();
                setSavedUrls(result.savedUrls || {});
                toast.success('N8N webhooks saved successfully');
            } else {
                const error = await res.json();
                toast.error(error.message || 'Failed to save webhooks');
            }
        } catch {
            toast.error('Failed to save webhooks');
        } finally {
            setIsLoading(false);
        }
    };

    const handleTestAll = async () => {
        setIsTestingAll(true);
        try {
            const res = await fetch('/api/settings/n8n-webhooks/test', {
                method: 'POST',
            });
            const result = await res.json();

            if (result.allPassed) {
                toast.success('All webhooks are responding');
            } else {
                toast.warning(`${result.passed}/${result.total} webhooks responding`);
            }
        } catch {
            toast.error('Failed to test webhooks');
        } finally {
            setIsTestingAll(false);
        }
    };

    const toggleShowUrl = (urlId: string) => {
        setShowUrls(prev => ({ ...prev, [urlId]: !prev[urlId] }));
    };

    return (
        <Card className="lg:col-span-2">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Workflow className="h-5 w-5 text-purple-500" />
                        <CardTitle>N8N Workflow Webhooks</CardTitle>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleTestAll}
                        disabled={isTestingAll}
                    >
                        {isTestingAll ? (
                            <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                        ) : (
                            <RefreshCw className="mr-2 h-3 w-3" />
                        )}
                        Test All
                    </Button>
                </div>
                <CardDescription>
                    Configure N8N webhook URLs for workflow automation. URLs set here override
                    environment variables. Leave empty to use .env defaults.
                </CardDescription>
            </CardHeader>
            <form onSubmit={form.handleSubmit(handleSave)}>
                <CardContent className="space-y-3">
                    {webhookConfigs.map(webhook => {
                        const isSaved = savedUrls[webhook.id];
                        const hasEnv = envUrls[webhook.id];
                        const isShown = showUrls[webhook.id];
                        const Icon = webhook.icon;

                        return (
                            <div
                                key={webhook.id}
                                className="flex items-center gap-3 p-3 rounded-lg border bg-zinc-50/50 dark:bg-zinc-900/50"
                            >
                                <div className="p-1.5 rounded bg-white dark:bg-zinc-800 shadow-sm">
                                    <Icon className="h-4 w-4 text-purple-500" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2 mb-1">
                                        <Label htmlFor={webhook.id} className="text-sm font-medium">
                                            {webhook.name}
                                        </Label>
                                        {isSaved && (
                                            <Badge className="bg-green-100 text-green-700 text-xs py-0">
                                                <CheckCircle2 className="h-2.5 w-2.5 mr-1" />
                                                Custom
                                            </Badge>
                                        )}
                                        {hasEnv && !isSaved && (
                                            <Badge variant="secondary" className="text-xs py-0">
                                                .env
                                            </Badge>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <div className="relative flex-1">
                                            <Input
                                                id={webhook.id}
                                                type={isShown ? 'text' : 'password'}
                                                placeholder={`http://localhost:5678/webhook/...`}
                                                {...form.register(webhook.id)}
                                                className="h-8 text-xs font-mono"
                                            />
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6"
                                                onClick={() => toggleShowUrl(webhook.id)}
                                            >
                                                {isShown ? (
                                                    <EyeOff className="h-3 w-3" />
                                                ) : (
                                                    <Eye className="h-3 w-3" />
                                                )}
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* N8N Link */}
                    <div className="flex items-center justify-between p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                        <div className="flex items-center gap-2">
                            <Server className="h-4 w-4 text-purple-600" />
                            <span className="text-sm text-purple-800 dark:text-purple-200">
                                N8N Dashboard
                            </span>
                        </div>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            asChild
                        >
                            <a
                                href="http://localhost:5678"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="gap-1"
                            >
                                Open N8N
                                <ExternalLink className="h-3 w-3" />
                            </a>
                        </Button>
                    </div>
                </CardContent>
                <CardFooter className="justify-end">
                    <Button type="submit" disabled={isLoading}>
                        {isLoading ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save className="mr-2 h-4 w-4" />
                                Save Webhooks
                            </>
                        )}
                    </Button>
                </CardFooter>
            </form>
        </Card>
    );
}
