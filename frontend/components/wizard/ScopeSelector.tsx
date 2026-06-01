"use client"

import { useRequestStore } from "@/lib/stores/request-store"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { submitRequest } from "@/lib/actions/requests/submit"
import { toast } from "sonner"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { CalendarIcon, Trash2, ArrowRight, Eye, Calendar } from "lucide-react"

export function ScopeSelector() {
    const {
        targetUrl,
        selectedIdentity,
        analysisResult,
        dateRange,
        setDateRange,
        additionalNotes,
        setNotes,
        prevStep,
        reset
    } = useRequestStore()

    const [isSubmitting, setIsSubmitting] = useState(false)
    const [wantAccess, setWantAccess] = useState(true)
    const [wantDeletion, setWantDeletion] = useState(false)
    const [allData, setAllData] = useState(true)
    const router = useRouter()

    const handleSubmit = async () => {
        if (!wantAccess && !wantDeletion) {
            toast.error("Please select at least one request type")
            return
        }

        setIsSubmitting(true)

        const requestTypes = []
        if (wantAccess) requestTypes.push('access')
        if (wantDeletion) requestTypes.push('deletion')

        const payload = {
            company: targetUrl,
            identity: selectedIdentity,
            scope: requestTypes.join('+'),
            dateRange: allData ? null : dateRange,
            notes: additionalNotes,
            analysis: analysisResult
        }

        const result = await submitRequest(payload)

        if (result.success) {
            toast.success("Request sent successfully!", {
                description: "We'll notify you when they respond."
            })
            reset()
            router.push('/dashboard/requests')
        } else {
            toast.error("Failed to send request", {
                description: result.message
            })
            setIsSubmitting(false)
        }
    }

    const handleFromChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setDateRange({ ...dateRange, from: e.target.valueAsDate || undefined })
    }

    const handleToChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setDateRange({ ...dateRange, to: e.target.valueAsDate || undefined })
    }

    return (
        <div className="space-y-6">
            {/* Summary Card */}
            <Card>
                <CardHeader>
                    <CardTitle>Review Request Scope</CardTitle>
                    <CardDescription>You are about to send a formal GDPR request.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-zinc-900 rounded-lg border border-slate-200 dark:border-zinc-800">
                        <div>
                            <p className="text-sm font-medium text-slate-500 dark:text-zinc-400">Target Company</p>
                            <p className="font-semibold text-slate-900 dark:text-zinc-100">{targetUrl || "Unknown Company"}</p>
                        </div>
                        <div className="text-right">
                            <p className="text-sm font-medium text-slate-500 dark:text-zinc-400">Identity</p>
                            <p className="font-semibold text-slate-900 dark:text-zinc-100">{selectedIdentity?.identity_name || "Anonymous"}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Date Range */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base flex items-center gap-2">
                            <Calendar className="h-4 w-4" /> Timeframe
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center gap-2 mb-4">
                            <Checkbox
                                id="all-data"
                                checked={allData}
                                onCheckedChange={(v) => setAllData(!!v)}
                            />
                            <label htmlFor="all-data" className="text-sm font-medium cursor-pointer">
                                All data since account creation
                            </label>
                        </div>

                        {!allData && (
                            <>
                                <div className="flex flex-col space-y-2">
                                    <Label htmlFor="from">From Date</Label>
                                    <input
                                        type="date"
                                        id="from"
                                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        onChange={handleFromChange}
                                    />
                                </div>
                                <div className="flex flex-col space-y-2">
                                    <Label htmlFor="to">To Date</Label>
                                    <input
                                        type="date"
                                        id="to"
                                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                        onChange={handleToChange}
                                    />
                                </div>
                            </>
                        )}
                    </CardContent>
                </Card>

                {/* Type of Request - Multi-select */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">What do you want?</CardTitle>
                        <CardDescription>Select one or both options</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div
                            className={`p-4 rounded-lg border cursor-pointer transition-all ${wantAccess
                                ? 'bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800 ring-2 ring-blue-500'
                                : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700 hover:border-slate-300 dark:hover:border-zinc-600'
                                }`}
                            onClick={() => setWantAccess(!wantAccess)}
                        >
                            <div className="flex items-center gap-3">
                                <Checkbox checked={wantAccess} onCheckedChange={(v) => setWantAccess(!!v)} />
                                <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-md text-blue-700 dark:text-blue-300">
                                    <Eye className="h-5 w-5" />
                                </div>
                                <div>
                                    <p className="font-semibold text-slate-900 dark:text-zinc-100">Access my data</p>
                                    <p className="text-sm text-slate-500 dark:text-zinc-400">I want to see what data they have (Article 15)</p>
                                </div>
                            </div>
                        </div>

                        <div
                            className={`p-4 rounded-lg border cursor-pointer transition-all ${wantDeletion
                                ? 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800 ring-2 ring-red-500'
                                : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-700 hover:border-slate-300 dark:hover:border-zinc-600'
                                }`}
                            onClick={() => setWantDeletion(!wantDeletion)}
                        >
                            <div className="flex items-center gap-3">
                                <Checkbox checked={wantDeletion} onCheckedChange={(v) => setWantDeletion(!!v)} />
                                <div className="p-2 bg-red-100 dark:bg-red-900 rounded-md text-red-700 dark:text-red-300">
                                    <Trash2 className="h-5 w-5" />
                                </div>
                                <div>
                                    <p className="font-semibold text-slate-900 dark:text-zinc-100">Delete my data</p>
                                    <p className="text-sm text-slate-500 dark:text-zinc-400">Right to be forgotten (Article 17)</p>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Additional Notes */}
            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Additional Context</CardTitle>
                    <CardDescription>Add details like Order IDs, old addresses, or specific requests. This will be used by our AI agent to tailor your request.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Textarea
                        placeholder="e.g. Please also check for accounts associated with my old phone number +44... I'm particularly interested in purchase history and profile data..."
                        value={additionalNotes}
                        onChange={(e) => setNotes(e.target.value)}
                        className="min-h-[100px]"
                    />
                </CardContent>
            </Card>

            {/* Actions */}
            <div className="flex justify-between pt-6 border-t border-slate-200 dark:border-zinc-800">
                <Button variant="outline" onClick={prevStep} disabled={isSubmitting}>
                    Back
                </Button>
                <Button
                    onClick={handleSubmit}
                    disabled={isSubmitting || (!wantAccess && !wantDeletion)}
                    className="px-8"
                >
                    {isSubmitting ? "Sending..." : (
                        <>Send Request <ArrowRight className="ml-2 h-4 w-4" /></>
                    )}
                </Button>
            </div>
        </div>
    )
}
