'use client';

/**
 * AICredentialsSection Component
 * 
 * Settings section for managing AI provider API credentials.
 * Separate from ONSIT tools - this handles AI model providers.
 * 
 * Providers: Google (Gemini), OpenAI, Ollama, OpenRouter, Hugging Face, NVIDIA
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
import { GsapReveal } from '@/components/ui/animations';
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
    Search,
    Workflow,
} from 'lucide-react';

// =============================================================================
// Schema
// =============================================================================

const aiCredentialsSchema = z.object({
    googleApiKey: z.string().optional(),
    openaiApiKey: z.string().optional(),
    openrouterApiKey: z.string().optional(),
    ollamaApiKey: z.string().optional(),
    huggingfaceApiKey: z.string().optional(),
    nvidiaApiKey: z.string().optional(),
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
    keyOptional?: boolean;
}

const aiProviders: AIProvider[] = [
    {
        id: 'googleApiKey',
        name: 'Google AI (Gemini)',
        description: 'Powers transcription, analysis, and knowledge extraction',
        docsUrl: 'https://aistudio.google.com/apikey',
        models: 'Latest Flash Lite, Latest Flash, Gemini models',
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
        id: 'ollamaApiKey',
        name: 'Ollama',
        description: 'Local models from your own Ollama server',
        docsUrl: 'https://ollama.com',
        models: 'Local installed models',
        icon: BrainCircuit,
        color: 'text-violet-500',
        keyOptional: true,
    },
    {
        id: 'huggingfaceApiKey',
        name: 'Hugging Face',
        description: 'Specialized and fine-tuned open models',
        docsUrl: 'https://huggingface.co/settings/tokens',
        models: 'Text generation and specialist models',
        icon: BrainCircuit,
        color: 'text-pink-500',
    },
    {
        id: 'nvidiaApiKey',
        name: 'NVIDIA',
        description: 'Hosted open models via NVIDIA API',
        docsUrl: 'https://build.nvidia.com/explore/discover',
        models: 'Llama, Mistral, Nemotron, and more',
        icon: Cpu,
        color: 'text-green-500',
    },
];

// =============================================================================
// Component
// =============================================================================

const modelProviders = [
    { value: 'google', label: 'Google' },
    { value: 'openai', label: 'OpenAI' },
    { value: 'ollama', label: 'Ollama' },
    { value: 'openrouter', label: 'OpenRouter' },
    { value: 'huggingface', label: 'Hugging Face' },
    { value: 'nvidia', label: 'NVIDIA' },
];

const modelPurposes = [
    { value: 'default', label: 'Default / RLM Agent', description: 'General assistant and fallback built-in workflow model.' },
    { value: 'drafting', label: 'Request Drafting', description: 'GDPR email drafting and correspondence generation.' },
    { value: 'extraction', label: 'File Extraction', description: 'OCR, transcription, document parsing, and summaries.' },
    { value: 'graph', label: 'Knowledge Graph', description: 'Graph entity/relationship extraction and graph chat.' },
    { value: 'policy', label: 'Policy Analysis', description: 'Privacy policy and vendor analysis.' },
] as const;

type ModelPurpose = typeof modelPurposes[number]['value'];

interface WorkflowModelChoice {
    provider: string;
    model: string;
}

const defaultWorkflowModels: Record<ModelPurpose, WorkflowModelChoice> = {
    default: { provider: 'google', model: 'flash_latest' },
    drafting: { provider: 'google', model: 'flash_latest' },
    extraction: { provider: 'google', model: 'flash_lite_latest' },
    graph: { provider: 'google', model: 'flash_latest' },
    policy: { provider: 'google', model: 'flash_latest' },
};

interface ModelOption {
    id: string;
    name: string;
    provider: string;
    contextWindow?: number;
    priceLabel: string;
    description?: string;
}

export function AICredentialsSection() {
    const [isLoading, setIsLoading] = useState(false);
    const [savedKeys, setSavedKeys] = useState<Record<string, boolean>>({});
    const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
    const [envKeys, setEnvKeys] = useState<Record<string, boolean>>({});
    const [workflowBackend, setWorkflowBackend] = useState('built_in');
    const [activePurpose, setActivePurpose] = useState<ModelPurpose>('default');
    const [workflowModels, setWorkflowModels] = useState<Record<ModelPurpose, WorkflowModelChoice>>(defaultWorkflowModels);
    const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
    const [modelSearch, setModelSearch] = useState('');
    const [isFetchingModels, setIsFetchingModels] = useState(false);
    const [modelFetchError, setModelFetchError] = useState<string | null>(null);
    const [modelFetchWarning, setModelFetchWarning] = useState<string | null>(null);

    const form = useForm<AICredentialsForm>({
        resolver: zodResolver(aiCredentialsSchema),
        defaultValues: {
            googleApiKey: '',
            openaiApiKey: '',
            openrouterApiKey: '',
            ollamaApiKey: '',
            huggingfaceApiKey: '',
            nvidiaApiKey: '',
        },
    });

    const selectedProvider = workflowModels[activePurpose]?.provider || 'google';
    const selectedModel = workflowModels[activePurpose]?.model || defaultWorkflowModels[activePurpose].model;

    // Load existing settings
    useEffect(() => {
        async function loadCredentials() {
            try {
                const res = await fetch('/api/settings/ai-credentials');
                if (res.ok) {
                    const data = await res.json();
                    setSavedKeys(data.savedKeys || {});
                    setEnvKeys(data.envKeys || {});
                }
            } catch (e) {
                console.error('Failed to load AI credentials', e);
            }
        }
        loadCredentials();
    }, [form]);

    useEffect(() => {
        async function loadPreferences() {
            try {
                const res = await fetch('/api/settings/model-preferences');
                if (res.ok) {
                    const data = await res.json();
                    setWorkflowBackend(data.workflowBackend || 'built_in');
                    setWorkflowModels({
                        ...defaultWorkflowModels,
                        ...(data.workflowModels || {}),
                        default: {
                            provider: data.provider || data.workflowModels?.default?.provider || 'google',
                            model: data.model || data.workflowModels?.default?.model || 'flash_latest',
                        },
                    });
                }
            } catch (e) {
                console.error('Failed to load model preferences', e);
            }
        }
        loadPreferences();
    }, []);

    useEffect(() => {
        let isCurrentRequest = true;

        async function loadModels() {
            setIsFetchingModels(true);
            setModelFetchError(null);
            setModelFetchWarning(null);
            try {
                const res = await fetch(`/api/settings/ai-models?provider=${encodeURIComponent(selectedProvider)}`);
                const data = await res.json().catch(() => ({}));

                if (!res.ok) {
                    throw new Error(data.error || data.message || `Model fetch failed with ${res.status}`);
                }

                const models = data.models || [];
                if (isCurrentRequest) {
                    setModelOptions(models);
                    setModelFetchWarning(data.fallback ? data.message || 'Showing fallback models.' : null);
                    setWorkflowModels(current => {
                        const choice = current[activePurpose] || defaultWorkflowModels[activePurpose];
                        if (models.some((model: ModelOption) => model.id === choice.model)) {
                            return current;
                        }

                        return {
                            ...current,
                            [activePurpose]: {
                                ...choice,
                                model: models[0]?.id || choice.model,
                            },
                        };
                    });
                }
            } catch (e) {
                console.error('Failed to load models', e);
                if (isCurrentRequest) {
                    setModelFetchError(e instanceof Error
                        ? e.message
                        : 'Could not fetch models for this provider. Check credentials or local provider availability.');
                    setModelOptions([]);
                }
            } finally {
                if (isCurrentRequest) {
                    setIsFetchingModels(false);
                }
            }
        }
        loadModels();

        return () => {
            isCurrentRequest = false;
        };
    }, [activePurpose, selectedProvider]);

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
                await savePreferences();
                toast.success('AI settings saved successfully');
            } else {
                const error = await res.json();
                toast.error(error.message || error.error || 'Failed to save credentials');
            }
        } catch (error) {
            toast.error(error instanceof Error ? error.message : 'Failed to save credentials');
        } finally {
            setIsLoading(false);
        }
    };

    const toggleShowKey = (keyId: string) => {
        setShowKeys(prev => ({ ...prev, [keyId]: !prev[keyId] }));
    };

    const savePreferences = async () => {
        const defaultChoice = workflowModels.default;
        const res = await fetch('/api/settings/model-preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workflowBackend,
                provider: defaultChoice.provider,
                model: defaultChoice.model,
                workflowModels,
            }),
        });

        if (!res.ok) {
            throw new Error('Failed to save model preferences');
        }
    };

    const updateActiveModelChoice = (updates: Partial<WorkflowModelChoice>) => {
        setWorkflowModels(current => ({
            ...current,
            [activePurpose]: {
                ...(current[activePurpose] || defaultWorkflowModels[activePurpose]),
                ...updates,
            },
        }));
    };

    const filteredModels = modelOptions.filter(model => {
        const query = modelSearch.toLowerCase();
        return model.name.toLowerCase().includes(query) || model.id.toLowerCase().includes(query);
    });

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
                                className="grid gap-3 rounded-lg border bg-zinc-50/50 p-4 dark:bg-zinc-900/50 sm:grid-cols-[auto_1fr]"
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
                                        Models: {provider.models}{provider.keyOptional ? ' (API key optional)' : ''}
                                    </p>
                                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
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

                    {/* Workflow Backend Selector */}
                    <div className="p-4 rounded-lg border bg-zinc-50/50 dark:bg-zinc-900/50">
                        <div className="grid gap-3 sm:grid-cols-[auto_1fr]">
                            <Workflow className="h-5 w-5 text-purple-600 mt-0.5" />
                            <div className="flex-1 space-y-3">
                                <div>
                                    <p className="text-sm font-medium">Workflow Backend</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        Built-in workflows are the default. N8N can still be used for the original webhook automation.
                                    </p>
                                </div>
                                <Select value={workflowBackend} onValueChange={setWorkflowBackend}>
                                    <SelectTrigger className="bg-white dark:bg-zinc-900">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="built_in">Built-in workflows (default)</SelectItem>
                                        <SelectItem value="n8n">N8N workflows</SelectItem>
                                        <SelectItem value="hybrid">Hybrid: built-in first, N8N fallback</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>

                    {/* Model Selector */}
                    <div className="p-4 rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
                        <div className="grid gap-3 sm:grid-cols-[auto_1fr]">
                            <Sparkles className="h-5 w-5 text-blue-600 mt-0.5" />
                            <div className="flex-1 space-y-3">
                                <div>
                                    <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                                        Preferred Model
                                    </p>
                                    <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                                        Pick separate models for each workflow. Extraction defaults to Flash Lite because it is a low-reasoning, high-throughput task.
                                    </p>
                                </div>
                                <div className="grid gap-3 md:grid-cols-[220px_220px_1fr]">
                                    <Select
                                        value={activePurpose}
                                        onValueChange={(value) => {
                                            setActivePurpose(value as ModelPurpose);
                                            setModelSearch('');
                                        }}
                                    >
                                        <SelectTrigger className="bg-white dark:bg-zinc-900">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {modelPurposes.map(purpose => (
                                                <SelectItem key={purpose.value} value={purpose.value}>
                                                    {purpose.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={selectedProvider}
                                        onValueChange={(value) => {
                                            updateActiveModelChoice({ provider: value });
                                            setModelSearch('');
                                        }}
                                    >
                                        <SelectTrigger className="bg-white dark:bg-zinc-900">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {modelProviders.map(provider => (
                                                <SelectItem key={provider.value} value={provider.value}>
                                                    {provider.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative">
                                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            value={modelSearch}
                                            onChange={(event) => setModelSearch(event.target.value)}
                                            placeholder="Search models..."
                                            className="pl-9 bg-white dark:bg-zinc-900"
                                        />
                                    </div>
                                </div>
                                <GsapReveal key={selectedProvider} direction="up" distance={8}>
                                    <div className="space-y-2" aria-live="polite">
                                        <Select
                                            value={selectedModel}
                                            onValueChange={(model) => updateActiveModelChoice({ model })}
                                            disabled={isFetchingModels || filteredModels.length === 0}
                                        >
                                            <SelectTrigger
                                                className="bg-white dark:bg-zinc-900"
                                                aria-busy={isFetchingModels}
                                            >
                                                <SelectValue placeholder={isFetchingModels ? 'Loading models...' : 'Select a model'} />
                                            </SelectTrigger>
                                            <SelectContent className="max-h-80">
                                                {filteredModels.map(model => (
                                                    <SelectItem key={model.id} value={model.id}>
                                                        <div className="flex flex-col">
                                                            <span className="font-medium">{model.name}</span>
                                                            <span className="text-xs text-muted-foreground">
                                                                {model.priceLabel}
                                                                {model.contextWindow ? `, ${model.contextWindow.toLocaleString()} context` : ''}
                                                            </span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>

                                        {isFetchingModels && (
                                            <p className="flex items-center gap-2 text-xs text-blue-700 dark:text-blue-300" role="status">
                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                Fetching available models...
                                            </p>
                                        )}
                                        {!isFetchingModels && modelFetchError && (
                                            <p className="text-xs text-red-700 dark:text-red-300" role="alert">
                                                {modelFetchError}
                                            </p>
                                        )}
                                        {!isFetchingModels && modelFetchWarning && !modelFetchError && (
                                            <p className="text-xs text-amber-700 dark:text-amber-300" role="status">
                                                {modelFetchWarning}
                                            </p>
                                        )}
                                        {!isFetchingModels && !modelFetchError && filteredModels.length === 0 && (
                                            <p className="text-xs text-blue-700 dark:text-blue-300">
                                                No models match your search for this provider.
                                            </p>
                                        )}
                                        <p className="text-xs text-muted-foreground">
                                            {modelPurposes.find(purpose => purpose.value === activePurpose)?.description}
                                        </p>
                                    </div>
                                </GsapReveal>
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
                    <Button type="submit" disabled={isLoading || isFetchingModels}>
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
