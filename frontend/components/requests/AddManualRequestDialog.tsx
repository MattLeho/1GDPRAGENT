"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Plus, Loader2, FileText, Sparkles, Eye, Link, CheckCircle2 } from "lucide-react";
import { createManualRequest } from "@/lib/actions/requests";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface PolicyData {
    url: string;
    markdownContent: string;
    aiSummary: string;
    complianceScore?: number;
    dataCollected?: string[];
    dpoEmail?: string;
}

interface AddManualRequestDialogProps {
    onRequestCreated?: () => void;
}

export function AddManualRequestDialog({ onRequestCreated }: AddManualRequestDialogProps) {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);

    // Form state
    const [companyName, setCompanyName] = useState("");
    const [domain, setDomain] = useState("");
    const [status, setStatus] = useState<'draft' | 'scheduled' | 'processing' | 'action_required' | 'completed'>("processing");
    const [requestType, setRequestType] = useState("access");
    const [notes, setNotes] = useState("");
    const [dateStarted, setDateStarted] = useState("");
    const [policyUrl, setPolicyUrl] = useState("");
    const [policyData, setPolicyData] = useState<PolicyData | null>(null);
    const [scanningPolicy, setScanningPolicy] = useState(false);
    const [viewingPolicy, setViewingPolicy] = useState(false);

    const resetForm = () => {
        setCompanyName("");
        setDomain("");
        setStatus("processing");
        setRequestType("access");
        setNotes("");
        setDateStarted("");
        setPolicyUrl("");
        setPolicyData(null);
        setViewingPolicy(false);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!companyName.trim()) {
            toast.error("Company name is required");
            return;
        }

        setLoading(true);

        try {
            const result = await createManualRequest({
                company_name: companyName.trim(),
                domain: domain.trim() || undefined,
                status,
                request_type: requestType,
                notes: notes.trim() || undefined,
                date_started: dateStarted ? new Date(dateStarted) : undefined,
            });

            if (result.success) {
                toast.success(`Request for ${companyName} added successfully`);
                resetForm();
                setOpen(false);
                onRequestCreated?.();
            } else {
                toast.error(result.error || "Failed to create request");
            }
        } catch (error) {
            console.error("Failed to create manual request:", error);
            toast.error("An unexpected error occurred");
        } finally {
            setLoading(false);
        }
    };

    // Scan privacy policy
    const handleScanPolicy = async () => {
        if (!policyUrl.trim() && !domain.trim()) {
            toast.error("Please enter a domain or policy URL first");
            return;
        }

        setScanningPolicy(true);

        try {
            const urlToScan = policyUrl.trim() || `https://${domain.trim()}`;

            // Call Python GDPR agent to analyze policy
            const response = await fetch('/api/gdpr-agent/analyze-policy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: urlToScan,
                    company: companyName.trim() || 'Company'
                }),
            });

            const result = await response.json();

            if (result.success) {
                setPolicyData({
                    url: urlToScan,
                    markdownContent: result.markdownContent || '',
                    aiSummary: result.summary || '',
                    complianceScore: result.analysis?.complianceScore,
                    dataCollected: result.analysis?.dataCollected,
                    dpoEmail: result.analysis?.dpoEmail,
                });

                // Auto-fill DPO email if found
                if (result.analysis?.dpoEmail) {
                    toast.success(`Found DPO email: ${result.analysis.dpoEmail}`);
                }

                toast.success("Privacy policy analyzed successfully");
            } else {
                throw new Error(result.error || 'Failed to analyze policy');
            }
        } catch (error) {
            console.error('Policy scan failed:', error);
            toast.error("Failed to scan privacy policy");
        } finally {
            setScanningPolicy(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" className="gap-2">
                    <Plus className="h-4 w-4" />
                    Add Manual Request
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
                <form onSubmit={handleSubmit}>
                    <DialogHeader>
                        <DialogTitle>Add Manual Request</DialogTitle>
                        <DialogDescription>
                            Add a request that was initiated outside this app (e.g., sent via email already).
                        </DialogDescription>
                    </DialogHeader>

                    <div className="grid gap-4 py-4">
                        {/* Company Name */}
                        <div className="grid gap-2">
                            <Label htmlFor="companyName">Company Name *</Label>
                            <Input
                                id="companyName"
                                value={companyName}
                                onChange={(e) => setCompanyName(e.target.value)}
                                placeholder="e.g., TalkTalk"
                                required
                            />
                        </div>

                        {/* Domain (optional) */}
                        <div className="grid gap-2">
                            <Label htmlFor="domain">Domain (for logo)</Label>
                            <Input
                                id="domain"
                                value={domain}
                                onChange={(e) => setDomain(e.target.value)}
                                placeholder="e.g., talktalk.co.uk"
                            />
                        </div>

                        {/* Privacy Policy Scanner */}
                        <div className="grid gap-2">
                            <Label>Privacy Policy (Optional)</Label>
                            <div className="flex gap-2">
                                <Input
                                    value={policyUrl}
                                    onChange={(e) => setPolicyUrl(e.target.value)}
                                    placeholder="Or enter direct policy URL"
                                />
                                <Button
                                    type="button"
                                    variant="secondary"
                                    onClick={handleScanPolicy}
                                    disabled={scanningPolicy || (!policyUrl.trim() && !domain.trim())}
                                >
                                    {scanningPolicy ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <>
                                            <Sparkles className="h-4 w-4 mr-1" />
                                            Scan
                                        </>
                                    )}
                                </Button>
                            </div>
                            {policyData && (
                                <Alert className="mt-2">
                                    <CheckCircle2 className="h-4 w-4" />
                                    <AlertDescription className="flex items-center justify-between">
                                        <span className="text-xs">
                                            Policy analyzed: {policyData.aiSummary.slice(0, 60)}...
                                        </span>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => setViewingPolicy(true)}
                                        >
                                            <Eye className="h-3 w-3 mr-1" />
                                            View
                                        </Button>
                                    </AlertDescription>
                                </Alert>
                            )}
                        </div>

                        {/* Status & Request Type Row */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                                <Label>Status</Label>
                                <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="draft">Draft</SelectItem>
                                        <SelectItem value="scheduled">Scheduled</SelectItem>
                                        <SelectItem value="processing">Processing</SelectItem>
                                        <SelectItem value="action_required">Action Required</SelectItem>
                                        <SelectItem value="completed">Completed</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="grid gap-2">
                                <Label>Request Type</Label>
                                <Select value={requestType} onValueChange={setRequestType}>
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="access">Access</SelectItem>
                                        <SelectItem value="deletion">Deletion</SelectItem>
                                        <SelectItem value="access+deletion">Access + Deletion</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Date Started */}
                        <div className="grid gap-2">
                            <Label htmlFor="dateStarted">Date Started</Label>
                            <Input
                                id="dateStarted"
                                type="date"
                                value={dateStarted}
                                onChange={(e) => setDateStarted(e.target.value)}
                            />
                        </div>

                        {/* Notes */}
                        <div className="grid gap-2">
                            <Label htmlFor="notes">Notes</Label>
                            <Textarea
                                id="notes"
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="e.g., Data received via email on Dec 15"
                                rows={3}
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={loading}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={loading}>
                            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Add Request
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>

            {/* Policy Viewer Dialog */}
            {policyData && (
                <Dialog open={viewingPolicy} onOpenChange={setViewingPolicy}>
                    <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileText className="h-5 w-5 text-blue-500" />
                                Privacy Policy Analysis
                            </DialogTitle>
                            <DialogDescription className="flex items-center gap-2 text-sm">
                                <Link className="h-3.5 w-3.5" />
                                <a href={policyData.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline truncate">
                                    {policyData.url}
                                </a>
                            </DialogDescription>
                        </DialogHeader>

                        {/* AI Summary */}
                        <div className="bg-amber-50 dark:bg-amber-900/20 p-4 rounded-lg">
                            <div className="flex items-center gap-2 mb-2">
                                <Sparkles className="h-4 w-4 text-amber-600" />
                                <span className="font-semibold text-amber-900 dark:text-amber-100">AI Summary</span>
                            </div>
                            <p className="text-sm text-amber-800 dark:text-amber-200">
                                {policyData.aiSummary}
                            </p>
                            {policyData.complianceScore && (
                                <div className="flex items-center gap-2 mt-2">
                                    <span className="text-xs text-amber-700">GDPR Compliance Score:</span>
                                    <Badge variant={policyData.complianceScore > 75 ? "default" : "destructive"}>
                                        {policyData.complianceScore}/100
                                    </Badge>
                                </div>
                            )}
                            {policyData.dpoEmail && (
                                <div className="mt-2 text-xs text-amber-700">
                                    <strong>DPO Email:</strong> {policyData.dpoEmail}
                                </div>
                            )}
                        </div>

                        {/* Markdown Content */}
                        <ScrollArea className="flex-1 mt-4 border rounded-lg">
                            <div className="p-4 prose prose-sm dark:prose-invert max-w-none">
                                <div
                                    dangerouslySetInnerHTML={{
                                        __html: policyData.markdownContent
                                            .replace(/\n/g, '<br>')
                                            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                                            .replace(/\*(.+?)\*/g, '<em>$1</em>')
                                    }}
                                />
                            </div>
                        </ScrollArea>
                    </DialogContent>
                </Dialog>
            )}
        </Dialog>
    );
}
