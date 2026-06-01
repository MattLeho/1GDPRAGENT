"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import {
    CheckCircle2,
    Mail,
    Shield,
    Server,
    Save,
    Loader2,
    XCircle,
    Upload,
    FileText,
    Trash2,
    Key,
    Database
} from "lucide-react";
import { saveEmailCredentials, getEmailSettings, testImapConnection } from "@/lib/actions/email-settings";
import { APICredentialsSection } from "@/components/settings/APICredentialsSection";
import { AICredentialsSection } from "@/components/settings/AICredentialsSection";
import { N8NWebhooksSection } from "@/components/settings/N8NWebhooksSection";
import { UserProfileSection } from "@/components/settings/UserProfileSection";
import { IDDocumentsSection } from "@/components/settings/IDDocumentsSection";

const emailSettingsSchema = z.object({
    email: z.string().email("Please enter a valid email address"),
    password: z.string().min(8, "App password must be at least 8 characters"),
    imapHost: z.string().min(1, "IMAP host is required"),
    imapPort: z.string().regex(/^\d+$/, "Port must be a number"),
});

type EmailSettingsForm = z.infer<typeof emailSettingsSchema>;

export default function SettingsPage() {
    const [isLoading, setIsLoading] = useState(false);
    const [isTesting, setIsTesting] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'idle' | 'success' | 'failed'>('idle');
    const [savedEmail, setSavedEmail] = useState<string | null>(null);

    const form = useForm<EmailSettingsForm>({
        resolver: zodResolver(emailSettingsSchema),
        defaultValues: {
            email: "",
            password: "",
            imapHost: "imap.gmail.com",
            imapPort: "993",
        },
    });

    // Load existing settings on mount
    useEffect(() => {
        async function loadSettings() {
            const settings = await getEmailSettings();
            if (settings) {
                form.setValue('email', settings.email);
                form.setValue('imapHost', settings.imap_host);
                form.setValue('imapPort', String(settings.imap_port));
                setSavedEmail(settings.email);
                if (settings.connection_verified) {
                    setConnectionStatus('success');
                }
            }
        }
        loadSettings();
    }, [form]);

    const handleSave = async (data: EmailSettingsForm) => {
        setIsLoading(true);
        setConnectionStatus('idle');

        try {
            // Encrypt password client-side before sending (simplified - use proper encryption in production)
            const result = await saveEmailCredentials({
                email: data.email,
                password_encrypted: btoa(data.password), // Base64 encode for demo
                imap_host: data.imapHost,
                imap_port: parseInt(data.imapPort, 10),
            });

            if (result.success) {
                setSavedEmail(data.email);
                toast.success("Email settings saved successfully!");

                // Now test connection
                setIsTesting(true);
                const testResult = await testImapConnection();
                setIsTesting(false);

                if (testResult.success) {
                    setConnectionStatus('success');
                    toast.success("Connection verified!");
                } else {
                    setConnectionStatus('failed');
                    toast.error(testResult.message);
                }
            } else {
                toast.error(result.message);
            }
        } catch (error) {
            toast.error("Failed to save settings");
        } finally {
            setIsLoading(false);
        }
    };

    const handleTestConnection = async () => {
        setIsTesting(true);
        const result = await testImapConnection();
        setIsTesting(false);

        if (result.success) {
            setConnectionStatus('success');
            toast.success("Connection verified!");
        } else {
            setConnectionStatus('failed');
            toast.error(result.message);
        }
    };

    return (
        <div className="flex-1 space-y-6 p-8 pt-6 max-w-5xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
                    <p className="text-muted-foreground">Configure your GDPR Agent preferences</p>
                </div>
            </div>
            <Separator />

            <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">

                {/* User Profile Section */}
                <UserProfileSection />

                {/* ID Documents Section */}
                <IDDocumentsSection />

                {/* Email Integration Card */}
                <Card className="lg:col-span-2">
                    <CardHeader>
                        <div className="flex items-center gap-2">
                            <Mail className="h-5 w-5 text-indigo-500" />
                            <CardTitle>Email Integration</CardTitle>
                        </div>
                        <CardDescription>
                            Connect your personal email to allow the agent to send GDPR requests and monitor responses.
                        </CardDescription>
                    </CardHeader>
                    <form onSubmit={form.handleSubmit(handleSave)}>
                        <CardContent className="space-y-4">
                            <div className="grid gap-4 md:grid-cols-2">
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email Address</Label>
                                    <Input
                                        id="email"
                                        placeholder="user@gmail.com"
                                        type="email"
                                        {...form.register('email')}
                                    />
                                    {form.formState.errors.email && (
                                        <p className="text-xs text-red-500">{form.formState.errors.email.message}</p>
                                    )}
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="password">App Password</Label>
                                    <div className="relative">
                                        <Key className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            id="password"
                                            type="password"
                                            placeholder="••••••••••••"
                                            className="pl-9"
                                            {...form.register('password')}
                                        />
                                    </div>
                                    <p className="text-[0.8rem] text-muted-foreground">
                                        Use an App Password for Gmail/Outlook. <a href="https://myaccount.google.com/apppasswords" target="_blank" className="underline text-blue-600">Get one here</a>
                                    </p>
                                    {form.formState.errors.password && (
                                        <p className="text-xs text-red-500">{form.formState.errors.password.message}</p>
                                    )}
                                </div>
                            </div>

                            <div className="grid gap-4 md:grid-cols-3">
                                <div className="space-y-2">
                                    <Label htmlFor="imap-host">IMAP Host</Label>
                                    <div className="relative">
                                        <Server className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            id="imap-host"
                                            className="pl-9"
                                            placeholder="imap.gmail.com"
                                            {...form.register('imapHost')}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="port">Port</Label>
                                    <Input
                                        id="port"
                                        placeholder="993"
                                        {...form.register('imapPort')}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="protocol">Security</Label>
                                    <Input id="protocol" placeholder="SSL/TLS" disabled defaultValue="SSL/TLS" />
                                </div>
                            </div>

                            {/* Connection Status */}
                            {connectionStatus === 'success' && (
                                <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded-md text-sm">
                                    <CheckCircle2 className="h-4 w-4" />
                                    Connection verified. The agent is ready to send emails.
                                </div>
                            )}
                            {connectionStatus === 'failed' && (
                                <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded-md text-sm">
                                    <XCircle className="h-4 w-4" />
                                    Connection failed. Please check your credentials and try again.
                                </div>
                            )}
                            {savedEmail && connectionStatus === 'idle' && (
                                <div className="flex items-center gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 rounded-md text-sm">
                                    <Database className="h-4 w-4" />
                                    Settings saved for {savedEmail}. Click "Test Connection" to verify.
                                </div>
                            )}
                        </CardContent>
                        <CardFooter className="justify-between">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleTestConnection}
                                disabled={isTesting || !savedEmail}
                            >
                                {isTesting ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Testing...
                                    </>
                                ) : (
                                    'Test Connection'
                                )}
                            </Button>
                            <Button type="submit" disabled={isLoading}>
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Saving...
                                    </>
                                ) : (
                                    <>
                                        <Save className="mr-2 h-4 w-4" />
                                        Save Settings
                                    </>
                                )}
                            </Button>
                        </CardFooter>
                    </form>
                </Card>

                {/* API Credentials Section - ONSIT Tools */}
                <APICredentialsSection />

                {/* AI Provider Credentials Section */}
                <AICredentialsSection />

                {/* N8N Webhooks Section */}
                <N8NWebhooksSection />



                {/* Data & Privacy Card */}
                <Card>
                    <CardHeader>
                        <div className="flex items-center gap-2">
                            <Database className="h-5 w-5 text-orange-500" />
                            <CardTitle>Data & Privacy</CardTitle>
                        </div>
                        <CardDescription>
                            Manage your local data and privacy settings.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center justify-between p-3 rounded-md border">
                            <div>
                                <p className="text-sm font-medium">Encryption Key</p>
                                <p className="text-xs text-muted-foreground">Used for encrypting sensitive data</p>
                            </div>
                            <Button variant="outline" size="sm">
                                <Key className="mr-2 h-4 w-4" />
                                Regenerate
                            </Button>
                        </div>
                        <div className="flex items-center justify-between p-3 rounded-md border">
                            <div>
                                <p className="text-sm font-medium">Delete All Data</p>
                                <p className="text-xs text-muted-foreground">Permanently remove all stored data</p>
                            </div>
                            <Button variant="destructive" size="sm">
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
