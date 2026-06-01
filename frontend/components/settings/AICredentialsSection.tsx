'use client';

/**
 * AICredentialsSection Component
 * 
 * Settings section for managing AI provider API credentials.
 * Separate from ONSIT tools - this handles AI model providers.
 * 
 * Providers: Google (Gemini), OpenAI, OpenRouter, Anthropic
 * 
 * All credentials are encrypted before storage.
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import {
    Sparkles,
    Save,
    Loader2,
    CheckCircle2,
    Eye,
    EyeOff,
    ExternalLink,
    Shield,
    Cpu,
    Zap,
    BrainCircuit,
} from 'lucide-react';

// =============================================================================
// Schema
// =============================================================================

const aiCredentialsSchema = z.object({
    googleApiKey: z.string().optional(),
    openaiApiKey: z.string().optional(),
    openrouterApiKey: z.string().optional(),
    anthropicApiKey: z.string().optional(),
    preferredGeminiModel: z.string().optional(),
});

type AICredentialsForm = z.infer<typeof aiCredentialsSchema>;

// =============================================================================
// AI Provider Configuration
// =============================================================================

interface AIProvider {
    id: keyof AICredentialsForm;
    name: string;
    description: string;
    docsUrl: string;
    models: string;
    icon: React.ElementType;
    color: string;
}

const aiProviders: AIProvider[] = [
    {
        id: 'googleApiKey',
        name: 'Google AI (Gemini)',
        description: 'Powers transcription, analysis, and knowledge extraction',
        docsUrl: 'https://aistudio.google.com/apikey',
        models: 'gemini-3-flash, gemini-3-pro',
        icon: Sparkles,
        color: 'text-blue-500',
    },
    {
        id: 'openaiApiKey',
        name: 'OpenAI',
        description: 'Alternative model provider for GPT-based tasks',
        docsUrl: 'https://platform.openai.com/api-keys',
        models: 'gpt-4o, gpt-4-turbo',
        icon: Cpu,
        color: 'text-emerald-500',
    },
    {
        id: 'openrouterApiKey',
        name: 'OpenRouter',
        description: 'Unified gateway for 300+ LLM providers',
        docsUrl: 'https://openrouter.ai/keys',
        models: 'Multi-provider access',
        icon: Zap,
        color: 'text-orange-500',
    },
    {
        id: 'anthropicApiKey',
        name: 'Anthropic',
        description: 'Claude models for complex reasoning tasks',
        docsUrl: 'https://console.anthropic.com/settings/keys',
        models: 'claude-3.5-sonnet',
        icon: BrainCircuit,
        color: 'text-violet-500',
    },
];

// =============================================================================
// Component
// =============================================================================

// Available Gemini 3 models
const geminiModels = [
    { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash (Fast)', description: 'Optimized for speed' },
    { value: 'gemini-3-flash-preview-8b', label: 'Gemini 3 Flash 8B', description: 'Lightweight model' },
    { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro (Powerful)', description: 'Best for complex tasks' },
    { value: 'gemini-3-flash-lite-preview', label: 'Gemini 3 Flash Lite', description: 'Minimal latency' },
];

export function AICredentialsSection() {
    const [isLoading, setIsLoading] = useState(false);
    const [savedKeys, setSavedKeys] = useState<Record<string, boolean>>({});
    const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
    const [envKeys, setEnvKeys] = useState<Record<string, boolean>>({});
    const [selectedModel, setSelectedModel] = useState('gemini-3-flash-preview');

    const form = useForm<AICredentialsForm>({
        resolver: zodResolver(aiCredentialsSchema),
        defaultValues: {
            googleApiKey: '',
            openaiApiKey: '',
            openrouterApiKey: '',
            anthropicApiKey: '',
            preferredGeminiModel: 'gemini-3-flash-preview',
        },
    });

    // Load existing settings
    useEffect(() => {
        async function loadCredentials() {
            try {
                const res = await fetch('/api/settings/ai-credentials');
                if (res.ok) {
                    const data = await res.json();
                    setSavedKeys(data.savedKeys || {});
                    setEnvKeys(data.envKeys || {});
                    if (data.preferredGeminiModel) {
                        setSelectedModel(data.preferredGeminiModel);
                        form.setValue('preferredGeminiModel', data.preferredGeminiModel);
                    }
                }
            } catch (e) {
                console.error('Failed to load AI credentials', e);
            }
        }
        loadCredentials();
    }, [form]);

    const handleSave = async (data: AICredentialsForm) => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/settings/ai-credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (res.ok) {
                const result = await res.json();
                setSavedKeys(result.savedKeys || {});
                form.reset();
                toast.success('AI credentials saved successfully');
            } else {
                const error = await res.json();
                toast.error(error.message || 'Failed to save credentials');
            }
        } catch (error) {
            toast.error('Failed to save credentials');
        } finally {
            setIsLoading(false);
        }
    };

    const toggleShowKey = (keyId: string) => {
        setShowKeys(prev => ({ ...prev, [keyId]: !prev[keyId] }));
    };

    return (
        <Card className="lg:col-span-2">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-blue-500" />
                    <CardTitle>AI Provider Credentials</CardTitle>
                </div>
                <CardDescription>
                    Configure API keys for AI model providers. These power transcription, analysis,
                    and GDPR request drafting. Keys configured here take precedence over .env files.
                </CardDescription>
            </CardHeader>
            <form onSubmit={form.handleSubmit(handleSave)}>
                <CardContent className="space-y-4">
                    {aiProviders.map(provider => {
                        const isSaved = savedKeys[provider.id];
                        const hasEnv = envKeys[provider.id];
                        const isShown = showKeys[provider.id];
                        const Icon = provider.icon;

                        return (
                            <div
                                key={provider.id}
                                className="flex items-start gap-4 p-4 rounded-lg border bg-zinc-50/50 dark:bg-zinc-900/50"
                            >
                                <div className="p-2 rounded-lg bg-white dark:bg-zinc-800 shadow-sm">
                                    <Icon className={`h-5 w-5 ${provider.color}`} />
                                </div>
                                <div className="flex-1 space-y-2">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Label htmlFor={provider.id} className="font-medium">
                                            {provider.name}
                                        </Label>
                                        {isSaved && (
                                            <Badge className="bg-green-100 text-green-700 gap-1">
                                                <CheckCircle2 className="h-3 w-3" />
                                                In-App
                                            </Badge>
                                        )}
                                        {hasEnv && !isSaved && (
                                            <Badge variant="secondary" className="text-xs">
                                                Using .env
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        {provider.description}
                                    </p>
                                    <p className="text-xs text-muted-foreground/70">
                                        Models: {provider.models}
                                    </p>
                                    <div className="flex items-center gap-2">
                                        <div className="relative flex-1">
                                            <Input
                                                id={provider.id}
                                                type={isShown ? 'text' : 'password'}
                                                placeholder={isSaved ? '••••••••••••••••' : hasEnv ? 'Override .env key...' : 'Enter API key'}
                                                {...form.register(provider.id)}
                                                className="pr-10"
                                            />
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                                                onClick={() => toggleShowKey(provider.id)}
                                            >
                                                {isShown ? (
                                                    <EyeOff className="h-4 w-4" />
                                                ) : (
                                                    <Eye className="h-4 w-4" />
                                                )}
                                            </Button>
                                        </div>
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            asChild
                                        >
                                            <a
                                                href={provider.docsUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="gap-1"
                                            >
                                                Get Key
                                                <ExternalLink className="h-3 w-3" />
                                            </a>
                                        </Button>
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* Gemini Model Selector */}
                    <div className="p-4 rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
                        <div className="flex items-start gap-3">
                            <Sparkles className="h-5 w-5 text-blue-600 mt-0.5" />
                            <div className="flex-1 space-y-3">
                                <div>
                                    <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                                        Preferred Gemini Model
                                    </p>
                                    <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                                        Select which Gemini 3 model to use for AI operations. This applies to all Python agents and N8N workflows.
                                    </p>
                                </div>
                                <Select
                                    value={selectedModel}
                                    onValueChange={(value) => {
                                        setSelectedModel(value);
                                        form.setValue('preferredGeminiModel', value);
                                    }}
                                >
                                    <SelectTrigger className="bg-white dark:bg-zinc-900">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {geminiModels.map(model => (
                                            <SelectItem key={model.value} value={model.value}>
                                                <div className="flex flex-col">
                                                    <span className="font-medium">{model.label}</span>
                                                    <span className="text-xs text-muted-foreground">{model.description}</span>
                                                </div>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>

                    {/* Info Notice */}
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <div className="flex items-start gap-3">
                            <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                                    Secure Storage
                                </p>
                                <p className="text-xs text-blue-600 dark:text-blue-300 mt-1">
                                    API keys are encrypted before storage. Keys set here override
                                    environment variables and are never transmitted in plain text.
                                </p>
                            </div>
                        </div>
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
                                Save Credentials
                            </>
                        )}
                    </Button>
                </CardFooter>
            </form>
        </Card>
    );
}
