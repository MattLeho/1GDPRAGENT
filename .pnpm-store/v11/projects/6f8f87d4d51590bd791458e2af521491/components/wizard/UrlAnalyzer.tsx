"use client"

import { useState } from "react"
import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client'
import { useRequestStore, AnalysisResult } from "@/lib/stores/request-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Sparkles, Loader2, CheckCircle2 } from "lucide-react"
import { toast } from "sonner"

interface PolicyResponse {
    found?: boolean;
    error?: string;
    analysis?: {
        dpo_email?: string | null;
        company_address?: string | null;
        data_collected?: string[];
        retention_period?: string | null;
        third_party_sharing?: string[];
        summary?: string | null;
        risk_score?: number | null;
    };
}

function validPublicUrlInput(value: string): boolean {
    try {
        const parsed = new URL(value);
        return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password;
    } catch {
        return false;
    }
}

export function UrlAnalyzer() {
    const [url, setLocalUrl] = useState("")
    const [loading, setLoading] = useState(false)
    const { setTargetUrl, setAnalysisResult, nextStep } = useRequestStore()

    const handleAnalyze = async () => {
        const normalizedUrl = url.trim()
        if (!validPublicUrlInput(normalizedUrl)) {
            toast.error("Enter a valid public HTTP(S) URL without embedded credentials")
            return
        }

        setLoading(true)
        try {
            const response = await fetch('/api/n8n/analyze-policy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: normalizedUrl })
            })
            const data = await response.json() as PolicyResponse
            if (!response.ok || !data.found || !data.analysis) {
                throw new Error(data.error || 'Policy analysis failed')
            }

            const analysis: AnalysisResult = {
                dpo_email: data.analysis.dpo_email || '',
                address: data.analysis.company_address || '',
                data_collected: data.analysis.data_collected || [],
                retention_period: data.analysis.retention_period || undefined,
                third_party_sharing: data.analysis.third_party_sharing || [],
                summary: data.analysis.summary || undefined,
                risk_score: data.analysis.risk_score ?? undefined,
            }
            setTargetUrl(normalizedUrl)
            setAnalysisResult(analysis)
            toast.success("Policy analysis complete", {
                description: analysis.dpo_email
                    ? `Found DPO contact: ${analysis.dpo_email}`
                    : "No DPO email was returned; delivery may remain queued for review."
            })
            nextStep()
        } catch (error) {
            if (shouldSuppressProtectedRequestError(error)) return
            const message = error instanceof Error ? error.message : 'Unknown error'
            toast.error("Policy analysis failed", { description: message })
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card className="mx-auto w-full max-w-2xl border-slate-200 shadow-lg">
            <CardHeader className="text-center">
                <CardTitle className="text-2xl font-bold text-slate-800 dark:text-zinc-100">New GDPR Request</CardTitle>
                <CardDescription>
                    Enter a public company or privacy-policy URL. Analysis runs only when you press Analyze and remains transient until the request is created.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="flex flex-col gap-3 sm:flex-row">
                    <Input
                        type="url"
                        inputMode="url"
                        aria-label="Company or privacy-policy URL"
                        placeholder="e.g. https://spotify.com/privacy"
                        className="h-12 min-w-0 flex-1 text-base sm:text-lg"
                        value={url}
                        onChange={(event) => setLocalUrl(event.target.value)}
                        disabled={loading}
                    />
                    <Button size="lg" onClick={handleAnalyze} disabled={loading} className="h-12 min-w-[140px] px-8">
                        {loading ? (
                            <><Loader2 className="mr-2 h-5 w-5 animate-spin" />Analyzing</>
                        ) : (
                            <><Sparkles className="mr-2 h-5 w-5" />Analyze</>
                        )}
                    </Button>
                </div>

                <div className="grid grid-cols-1 gap-4 text-sm text-slate-500 sm:grid-cols-3">
                    <div className="flex items-center justify-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-500" /><span>Finds stated DPO details</span></div>
                    <div className="flex items-center justify-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-500" /><span>Extracts stated data types</span></div>
                    <div className="flex items-center justify-center gap-2"><CheckCircle2 className="h-4 w-4 text-green-500" /><span>Prepares request context</span></div>
                </div>
            </CardContent>
        </Card>
    )
}
