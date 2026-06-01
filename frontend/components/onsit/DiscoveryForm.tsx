'use client';

/**
 * DiscoveryForm Component
 * 
 * Form for initiating ONSIT (Open Source Network Intelligence Toolkit) discovery.
 * Collects identity information to search for across public sources.
 * 
 * Following Flowsint enricher input patterns and Photon crawler configuration.
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from '@/components/ui/form';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import {
    Mail,
    User,
    Phone,
    Globe,
    Search,
    AlertTriangle,
    Info,
    Loader2,
    Shield,
} from 'lucide-react';

// =============================================================================
// Schema
// =============================================================================

const discoveryFormSchema = z.object({
    email: z.string().email('Please enter a valid email address'),
    usernames: z.string().optional(),
    phone: z.string().optional().refine(
        val => !val || /^[+]?[\d\s\-()]+$/.test(val),
        'Please enter a valid phone number'
    ),
    domains: z.string().optional(),
    includeBreachCheck: z.boolean().default(true),
    includeSocialScan: z.boolean().default(true),
    depth: z.enum(['quick', 'standard', 'deep']).default('standard'),
});

// The actual form input type (before transforms)
type DiscoveryFormInput = z.infer<typeof discoveryFormSchema>;

// The data type after processing (what gets passed to onSubmit)
export interface DiscoveryFormData {
    email: string;
    usernames: string[];
    phone?: string;
    domains: string[];
    includeBreachCheck: boolean;
    includeSocialScan: boolean;
    depth: 'quick' | 'standard' | 'deep';
}

interface DiscoveryFormProps {
    onSubmit: (data: DiscoveryFormData) => Promise<void>;
    isSubmitting?: boolean;
}

// =============================================================================
// Depth Configuration
// =============================================================================

const depthOptions = [
    {
        value: 'quick' as const,
        label: 'Quick',
        description: 'Basic email and username check (~1 min)',
        platforms: '~50 platforms',
    },
    {
        value: 'standard' as const,
        label: 'Standard',
        description: 'Full platform scan + breaches (~3 min)',
        platforms: '~500 platforms',
    },
    {
        value: 'deep' as const,
        label: 'Deep',
        description: 'Extended search with domain intel (~10 min)',
        platforms: '~1000+ sources',
    },
];

// =============================================================================
// Component
// =============================================================================

// Form input interface - what the form fields contain
interface FormInput {
    email: string;
    usernames: string;
    phone: string;
    domains: string;
    includeBreachCheck: boolean;
    includeSocialScan: boolean;
    depth: 'quick' | 'standard' | 'deep';
}

export function DiscoveryForm({ onSubmit, isSubmitting = false }: DiscoveryFormProps) {
    const [selectedDepth, setSelectedDepth] = useState<'quick' | 'standard' | 'deep'>('standard');

    const form = useForm<FormInput>({
        defaultValues: {
            email: '',
            usernames: '',
            phone: '',
            domains: '',
            includeBreachCheck: true,
            includeSocialScan: true,
            depth: 'standard',
        },
    });

    const handleSubmit = async (data: FormInput) => {
        // Transform the data before passing to onSubmit
        const processedData: DiscoveryFormData = {
            email: data.email,
            usernames: data.usernames ? data.usernames.split(',').map(u => u.trim()).filter(Boolean) : [],
            phone: data.phone,
            domains: data.domains ? data.domains.split(',').map(d => d.trim()).filter(Boolean) : [],
            includeBreachCheck: data.includeBreachCheck,
            includeSocialScan: data.includeSocialScan,
            depth: selectedDepth,
        };
        await onSubmit(processedData);
    };

    return (
        <Card>
            <CardHeader>
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-orange-100">
                        <Search className="h-5 w-5 text-orange-600" />
                    </div>
                    <div>
                        <CardTitle>ONSIT Discovery</CardTitle>
                        <CardDescription>
                            Search for your digital footprint across public sources
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
                        {/* Email (Required) */}
                        <FormField
                            control={form.control}
                            name="email"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="flex items-center gap-2">
                                        <Mail className="h-4 w-4 text-muted-foreground" />
                                        Email Address
                                        <Badge variant="secondary" className="text-xs">Required</Badge>
                                    </FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="your.email@example.com"
                                            type="email"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Primary email to search - used to find accounts and breach records
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {/* Usernames (Optional) */}
                        <FormField
                            control={form.control}
                            name="usernames"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="flex items-center gap-2">
                                        <User className="h-4 w-4 text-muted-foreground" />
                                        Usernames
                                        <TooltipProvider>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    <p>Comma-separated list of usernames to search</p>
                                                </TooltipContent>
                                            </Tooltip>
                                        </TooltipProvider>
                                    </FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="johndoe, john_doe, jdoe123"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Searches 500+ platforms using Maigret engine
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {/* Phone (Optional) */}
                        <FormField
                            control={form.control}
                            name="phone"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="flex items-center gap-2">
                                        <Phone className="h-4 w-4 text-muted-foreground" />
                                        Phone Number
                                    </FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="+44 7700 900000"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Include country code for international search
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        {/* Domains (Optional) */}
                        <FormField
                            control={form.control}
                            name="domains"
                            render={({ field }) => (
                                <FormItem>
                                    <FormLabel className="flex items-center gap-2">
                                        <Globe className="h-4 w-4 text-muted-foreground" />
                                        Known Domains
                                    </FormLabel>
                                    <FormControl>
                                        <Input
                                            placeholder="example.com, myblog.co.uk"
                                            {...field}
                                        />
                                    </FormControl>
                                    <FormDescription>
                                        Personal domains or websites to analyze (comma-separated)
                                    </FormDescription>
                                    <FormMessage />
                                </FormItem>
                            )}
                        />

                        <Separator />

                        {/* Scan Depth Selection */}
                        <div className="space-y-3">
                            <Label className="text-sm font-medium">Scan Depth</Label>
                            <div className="grid grid-cols-3 gap-3">
                                {depthOptions.map(option => (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => setSelectedDepth(option.value)}
                                        className={`p-3 rounded-lg border text-left transition-all ${selectedDepth === option.value
                                            ? 'border-primary bg-primary/5 ring-2 ring-primary/20'
                                            : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700'
                                            }`}
                                    >
                                        <p className="font-medium text-sm">{option.label}</p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            {option.description}
                                        </p>
                                        <Badge variant="secondary" className="text-xs mt-2">
                                            {option.platforms}
                                        </Badge>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Privacy Notice */}
                        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                            <div className="flex items-start gap-3">
                                <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
                                <div>
                                    <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                                        Privacy Notice
                                    </p>
                                    <p className="text-xs text-blue-600 dark:text-blue-300 mt-1">
                                        This tool searches publicly available information only.
                                        Results are stored locally and never shared.
                                        You should only search for information about yourself.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Submit Button */}
                        <Button
                            type="submit"
                            className="w-full gap-2"
                            size="lg"
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Starting Discovery...
                                </>
                            ) : (
                                <>
                                    <Search className="h-4 w-4" />
                                    Start Discovery
                                </>
                            )}
                        </Button>
                    </form>
                </Form>
            </CardContent>
        </Card>
    );
}
