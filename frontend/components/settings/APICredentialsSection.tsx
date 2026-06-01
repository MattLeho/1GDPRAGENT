'use client';

/**
 * APICredentialsSection Component
 * 
 * Settings section for managing external API credentials used by ONSIT tools.
 * Includes credentials for breach checking, WHOIS lookups, and other services.
 * 
 * All credentials are encrypted before storage.
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
    Key,
    Save,
    Loader2,
    CheckCircle2,
    XCircle,
    ExternalLink,
    Eye,
    EyeOff,
    Globe,
    Shield,
    AlertTriangle,
} from 'lucide-react';

// =============================================================================
// Schema
// =============================================================================

const apiCredentialsSchema = z.object({
    hibpApiKey: z.string().optional(),
    hunterApiKey: z.string().optional(),
    shodanApiKey: z.string().optional(),
    whoisApiKey: z.string().optional(),
});

type APICredentialsForm = z.infer<typeof apiCredentialsSchema>;

// =============================================================================
// Service Configuration
// =============================================================================

interface APIService {
    id: keyof APICredentialsForm;
    name: string;
    description: string;
    docsUrl: string;
    required: boolean;
    icon: React.ElementType;
}

const apiServices: APIService[] = [
    {
        id: 'hibpApiKey',
        name: 'Have I Been Pwned',
        description: 'Check if emails appear in data breaches',
        docsUrl: 'https://haveibeenpwned.com/API/Key',
        required: true,
        icon: AlertTriangle,
    },
    {
        id: 'hunterApiKey',
        name: 'Hunter.io',
        description: 'Email verification and enrichment',
        docsUrl: 'https://hunter.io/api',
        required: false,
        icon: Globe,
    },
    {
        id: 'shodanApiKey',
        name: 'Shodan',
        description: 'IP and domain intelligence',
        docsUrl: 'https://developer.shodan.io/',
        required: false,
        icon: Shield,
    },
    {
        id: 'whoisApiKey',
        name: 'WHOIS API',
        description: 'Domain registration data lookup',
        docsUrl: 'https://www.whoisxmlapi.com/',
        required: false,
        icon: Globe,
    },
];

// =============================================================================
// Component
// =============================================================================

export function APICredentialsSection() {
    const [isLoading, setIsLoading] = useState(false);
    const [savedKeys, setSavedKeys] = useState<Record<string, boolean>>({});
    const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

    const form = useForm<APICredentialsForm>({
        resolver: zodResolver(apiCredentialsSchema),
        defaultValues: {
            hibpApiKey: '',
            hunterApiKey: '',
            shodanApiKey: '',
            whoisApiKey: '',
        },
    });

    // Load existing settings
    useEffect(() => {
        async function loadCredentials() {
            try {
                const res = await fetch('/api/settings/api-credentials');
                if (res.ok) {
                    const data = await res.json();
                    // Set which keys are saved (we don't get the actual keys back for security)
                    setSavedKeys(data.savedKeys || {});
                }
            } catch (e) {
                console.error('Failed to load API credentials', e);
            }
        }
        loadCredentials();
    }, []);

    const handleSave = async (data: APICredentialsForm) => {
        setIsLoading(true);
        try {
            const res = await fetch('/api/settings/api-credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });

            if (res.ok) {
                const result = await res.json();
                setSavedKeys(result.savedKeys || {});
                // Clear the form fields (we don't want to show the keys)
                form.reset();
                toast.success('API credentials saved successfully');
            } else {
                toast.error('Failed to save credentials');
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
                    <Key className="h-5 w-5 text-purple-500" />
                    <CardTitle>API Credentials</CardTitle>
                </div>
                <CardDescription>
                    Configure API keys for ONSIT discovery tools. These are used for breach checking,
                    domain intelligence, and other OSINT operations.
                </CardDescription>
            </CardHeader>
            <form onSubmit={form.handleSubmit(handleSave)}>
                <CardContent className="space-y-4">
                    {apiServices.map(service => {
                        const isSaved = savedKeys[service.id];
                        const isShown = showKeys[service.id];
                        const Icon = service.icon;

                        return (
                            <div
                                key={service.id}
                                className="flex items-start gap-4 p-4 rounded-lg border bg-zinc-50/50 dark:bg-zinc-900/50"
                            >
                                <div className="p-2 rounded-lg bg-white dark:bg-zinc-800 shadow-sm">
                                    <Icon className="h-5 w-5 text-purple-500" />
                                </div>
                                <div className="flex-1 space-y-2">
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Label htmlFor={service.id} className="font-medium">
                                            {service.name}
                                        </Label>
                                        {service.required && (
                                            <Badge variant="secondary" className="text-xs">
                                                Required for breaches
                                            </Badge>
                                        )}
                                        {isSaved && (
                                            <Badge className="bg-green-100 text-green-700 gap-1">
                                                <CheckCircle2 className="h-3 w-3" />
                                                Configured
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-sm text-muted-foreground">
                                        {service.description}
                                    </p>
                                    <div className="flex items-center gap-2">
                                        <div className="relative flex-1">
                                            <Input
                                                id={service.id}
                                                type={isShown ? 'text' : 'password'}
                                                placeholder={isSaved ? '••••••••••••••••' : 'Enter API key'}
                                                {...form.register(service.id)}
                                                className="pr-10"
                                            />
                                            <Button
                                                type="button"
                                                variant="ghost"
                                                size="icon"
                                                className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                                                onClick={() => toggleShowKey(service.id)}
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
                                                href={service.docsUrl}
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

                    {/* Security Notice */}
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <div className="flex items-start gap-3">
                            <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
                            <div>
                                <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                                    Security Notice
                                </p>
                                <p className="text-xs text-blue-600 dark:text-blue-300 mt-1">
                                    API keys are encrypted before storage and never transmitted in plain text.
                                    Keys are only used for ONSIT discovery operations and are never shared.
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
