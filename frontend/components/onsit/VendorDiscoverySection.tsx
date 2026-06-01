'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Search, Mail, Send, Loader2, CheckCircle2, AlertCircle, BrainCircuit } from 'lucide-react';
import { toast } from 'sonner';

interface Vendor {
    id?: number;
    domain: string;
    company_name?: string;
    dpo_email?: string;
    discovered_at?: string;
    gdpr_email_sent?: boolean;
}

export function VendorDiscoverySection() {
    const [domain, setDomain] = useState('');
    const [vendors, setVendors] = useState<Vendor[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [selectedVendors, setSelectedVendors] = useState<Set<number>>(new Set());
    const [isFindingDPO, setIsFindingDPO] = useState(false);
    const [isSendingEmails, setIsSendingEmails] = useState(false);

    const handleDomainSearch = async () => {
        if (!domain.trim()) {
            toast.error('Please enter a domain');
            return;
        }

        setIsSearching(true);
        try {
            const res = await fetch('/api/onsit/vendor-domain-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domain: domain.trim() }),
            });

            const data = await res.json();

            if (data.success && data.vendors) {
                setVendors(prev => [...prev, ...data.vendors]);
                toast.success(`Found ${data.vendors.length} related vendors`);
            } else {
                toast.error(data.error || 'Failed to search vendors');
            }
        } catch (error) {
            toast.error('Search failed');
        } finally {
            setIsSearching(false);
        }
    };

    const handleFindDPO = async () => {
        if (selectedVendors.size === 0) {
            toast.error('Please select vendors first');
            return;
        }

        setIsFindingDPO(true);
        const vendorIds = Array.from(selectedVendors);

        try {
            const res = await fetch('/api/onsit/vendor-dpo-discovery', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vendorIds }),
            });

            const data = await res.json();

            if (data.success) {
                // Update vendors with discovered DPO emails
                setVendors(prev => prev.map(v => {
                    const updated = data.updated.find((u: any) => u.id === v.id);
                    return updated ? { ...v, dpo_email: updated.dpo_email } : v;
                }));
                toast.success(`Found ${data.updated.length} DPO emails`);
            } else {
                toast.error(data.error || 'DPO discovery failed');
            }
        } catch (error) {
            toast.error('DPO discovery failed');
        } finally {
            setIsFindingDPO(false);
        }
    };

    const handleSendGDPREmails = async () => {
        if (selectedVendors.size === 0) {
            toast.error('Please select vendors first');
            return;
        }

        const vendorsToEmail = vendors.filter(v => selectedVendors.has(v.id!) && v.dpo_email);

        if (vendorsToEmail.length === 0) {
            toast.error('Selected vendors need DPO emails first');
            return;
        }

        setIsSendingEmails(true);

        try {
            const res = await fetch('/api/onsit/vendor-bulk-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ vendorIds: Array.from(selectedVendors) }),
            });

            const data = await res.json();

            if (data.success) {
                toast.success(`Sent ${data.emailsSent} GDPR requests`);
                setVendors(prev => prev.map(v =>
                    selectedVendors.has(v.id!) ? { ...v, gdpr_email_sent: true } : v
                ));
                setSelectedVendors(new Set());
            } else {
                toast.error(data.error || 'Failed to send emails');
            }
        } catch (error) {
            toast.error('Email sending failed');
        } finally {
            setIsSendingEmails(false);
        }
    };

    const toggleVendor = (id: number) => {
        setSelectedVendors(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    };

    return (
        <Card className="lg:col-span-2">
            <CardHeader>
                <div className="flex items-center gap-2">
                    <BrainCircuit className="h-5 w-5 text-indigo-500" />
                    <CardTitle>AI Vendor Discovery</CardTitle>
                </div>
                <CardDescription>
                    Use AI to discover vendor relationships, find DPO contacts, and send bulk GDPR requests
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* AI Domain Search */}
                <div className="space-y-3">
                    <Label>AI-Powered Domain Search</Label>
                    <div className="flex gap-2">
                        <Input
                            placeholder="Enter domain (e.g., google.com)"
                            value={domain}
                            onChange={(e) => setDomain(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleDomainSearch()}
                        />
                        <Button onClick={handleDomainSearch} disabled={isSearching}>
                            {isSearching ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <><Search className="mr-2 h-4 w-4" />Search</>
                            )}
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        AI agent will discover related vendors and third-party data processors
                    </p>
                </div>

                {/* Vendor List */}
                {vendors.length > 0 && (
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <Label>Discovered Vendors ({vendors.length})</Label>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleFindDPO}
                                    disabled={selectedVendors.size === 0 || isFindingDPO}
                                >
                                    {isFindingDPO ? (
                                        <><Loader2 className="mr-2 h-3 w-3 animate-spin" />Finding DPO...</>
                                    ) : (
                                        <><Mail className="mr-2 h-3 w-3" />Find DPO Emails</>
                                    )}
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleSendGDPREmails}
                                    disabled={selectedVendors.size === 0 || isSendingEmails}
                                >
                                    {isSendingEmails ? (
                                        <><Loader2 className="mr-2 h-3 w-3 animate-spin" />Sending...</>
                                    ) : (
                                        <><Send className="mr-2 h-3 w-3" />Send GDPR Requests</>
                                    )}
                                </Button>
                            </div>
                        </div>
                        <div className="border rounded-lg divide-y max-h-96 overflow-y-auto">
                            {vendors.map((vendor, idx) => (
                                <div key={idx} className="p-3 flex items-center gap-3 hover:bg-muted/50">
                                    <input
                                        type="checkbox"
                                        checked={selectedVendors.has(vendor.id!)}
                                        onChange={() => toggleVendor(vendor.id!)}
                                        className="h-4 w-4 rounded border-gray-300"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{vendor.company_name || vendor.domain}</p>
                                        <p className="text-xs text-muted-foreground truncate">{vendor.domain}</p>
                                        {vendor.dpo_email && (
                                            <p className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1 mt-1">
                                                <Mail className="h-3 w-3" />
                                                {vendor.dpo_email}
                                            </p>
                                        )}
                                    </div>
                                    <div className="flex gap-1">
                                        {vendor.dpo_email && (
                                            <Badge variant="secondary" className="text-xs gap-1">
                                                <CheckCircle2 className="h-3 w-3" />DPO Found
                                            </Badge>
                                        )}
                                        {vendor.gdpr_email_sent && (
                                            <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 text-xs gap-1">
                                                <Send className="h-3 w-3" />Sent
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Info */}
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                    <div className="flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5" />
                        <div>
                            <p className="text-sm font-medium text-blue-800 dark:text-blue-200">
                                AI-Powered Discovery
                            </p>
                            <p className="text-xs text-blue-600 dark:text-blue-300 mt-1">
                                The AI agent searches company websites and public sources to discover DPO contact information. Always verify emails before sending requests.
                            </p>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

