"use client"

import { useState, useEffect } from "react"
import { useRequestStore, AnalysisResult } from "@/lib/stores/request-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Sparkles, Loader2, CheckCircle2, AlertCircle } from "lucide-react"
import { toast } from "sonner"

/**
 * Extended local analysis result that may come from cache
 * The store's AnalysisResult is the subset we actually need
 */
interface CachedAnalysis extends Partial<AnalysisResult> {
    dpo_email?: string;
    company_address?: string;
    address?: string;
    data_collected?: string[];
    retention_period?: string;
    third_party_sharing?: string[];
    summary?: string;
    risk_score?: number;
    analyzed_at?: Date;
}

export function UrlAnalyzer() {
    const [url, setLocalUrl] = useState("")
    const [loading, setLoading] = useState(false)
    const [existingAnalysis, setExistingAnalysis] = useState<CachedAnalysis | null>(null)
    const [checkingCache, setCheckingCache] = useState(false)
    const { setTargetUrl, setAnalysisResult, nextStep } = useRequestStore()

    // Check for existing analysis when URL changes (debounced)
    useEffect(() => {
        const checkPolicy = async () => {
            if (!url || url.length < 5) {
                setExistingAnalysis(null)
                return
            }

            setCheckingCache(true)
            try {
                const res = await fetch('/api/n8n/analyze-policy', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url, forceNew: false })
                })
                const data = await res.json()

                if (data.found && data.cached && data.analysis) {
                    setExistingAnalysis(data.analysis)
                } else {
                    setExistingAnalysis(null)
                }
            } catch (e) {
                console.error("Policy check failed", e)
                setExistingAnalysis(null)
            } finally {
                setCheckingCache(false)
            }
        }

        const timer = setTimeout(checkPolicy, 1000)
        return () => clearTimeout(timer)
    }, [url])

    const handleAnalyze = async (forceNew = false) => {
        if (!url) {
            toast.error("Please enter a valid URL")
            return
        }

        // Use cached result if available and not forcing new
        if (existingAnalysis && !forceNew) {
            setTargetUrl(url)
            // Convert cached analysis to store format with required fields
            setAnalysisResult({
                dpo_email: existingAnalysis.dpo_email || '',
                address: existingAnalysis.address || existingAnalysis.company_address || '',
                data_collected: existingAnalysis.data_collected || [],
            })
            toast.success("Using cached policy analysis!")
            nextStep()
            return
        }

        setLoading(true)
        try {
            // Call real N8N Policy Analyzer via API route
            const response = await fetch('/api/n8n/analyze-policy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, forceNew: true })
            })

            const data = await response.json()

            if (!response.ok || !data.found) {
                throw new Error(data.error || 'Policy analysis failed')
            }

            const result = data.analysis

            setTargetUrl(url)
            setAnalysisResult(result)
            toast.success("Policy Analyzed!", {
                description: result.dpo_email
                    ? `Found DPO contact: ${result.dpo_email}`
                    : "Analysis complete. Review the details in the next step."
            })

            setTimeout(() => {
                nextStep()
            }, 1000)

        } catch (error) {
            console.error(error)
            const message = error instanceof Error ? error.message : 'Unknown error'
            toast.error("Analysis Failed", {
                description: message.includes('N8N')
                    ? "Could not connect to analysis service. Check if N8N is running."
                    : "Could not fetch privacy policy. Try manual entry."
            })
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card className="w-full max-w-2xl mx-auto shadow-lg border-slate-200">
            <CardHeader className="text-center">
                <CardTitle className="text-2xl font-bold text-slate-800">New GDPR Request</CardTitle>
                <CardDescription>
                    Enter the company's website URL. Our AI will analyze their privacy policy for you.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex-1 relative">
                        <Input
                            placeholder="e.g. https://spotify.com"
                            className="h-12 text-lg pr-10"
                            value={url}
                            onChange={(e) => setLocalUrl(e.target.value)}
                            disabled={loading}
                        />
                        {checkingCache && (
                            <Loader2 className="absolute right-3 top-3 h-5 w-5 animate-spin text-slate-400" />
                        )}
                    </div>
                    <Button
                        size="lg"
                        onClick={() => handleAnalyze(false)}
                        disabled={loading}
                        className="h-12 px-8 min-w-[140px]"
                    >
                        {loading ? (
                            <>
                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                Analyzing
                            </>
                        ) : (
                            <>
                                <Sparkles className="mr-2 h-5 w-5" />
                                Analyze
                            </>
                        )}
                    </Button>
                </div>

                {/* Existing Analysis Alert */}
                {existingAnalysis && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 animate-in fade-in slide-in-from-top-2">
                        <div className="flex items-start gap-3">
                            <Sparkles className="h-5 w-5 text-blue-600 mt-0.5" />
                            <div className="flex-1">
                                <h4 className="font-semibold text-blue-900">
                                    Analysis Found
                                    {existingAnalysis.analyzed_at && (
                                        <span className="font-normal text-blue-700">
                                            {' '}from {new Date(existingAnalysis.analyzed_at).toLocaleDateString()}
                                        </span>
                                    )}
                                </h4>
                                <p className="text-sm text-blue-700 mt-1">
                                    {existingAnalysis.summary ||
                                        `Found DPO: ${existingAnalysis.dpo_email || 'N/A'}, ` +
                                        `Data points: ${existingAnalysis.data_collected?.length || 0}`}
                                </p>
                                {existingAnalysis.risk_score !== undefined && (
                                    <div className="mt-2 flex items-center gap-2">
                                        <AlertCircle className={`h-4 w-4 ${existingAnalysis.risk_score > 70 ? 'text-red-500' :
                                            existingAnalysis.risk_score > 40 ? 'text-yellow-500' : 'text-green-500'
                                            }`} />
                                        <span className="text-sm font-medium">
                                            Risk Score: {existingAnalysis.risk_score}/100
                                        </span>
                                    </div>
                                )}
                                <div className="mt-3 flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="default"
                                        className="bg-blue-600 hover:bg-blue-700 text-white"
                                        onClick={() => handleAnalyze(false)}
                                    >
                                        Use This Analysis
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-blue-700 border-blue-300 hover:bg-blue-100"
                                        onClick={() => handleAnalyze(true)}
                                    >
                                        Re-Analyze
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* Benefits / Features List */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm text-slate-500 mt-6">
                    <div className="flex items-center justify-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span>Finds DPO Email</span>
                    </div>
                    <div className="flex items-center justify-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span>Identifies Data Types</span>
                    </div>
                    <div className="flex items-center justify-center gap-2">
                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                        <span>Generates Request</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
