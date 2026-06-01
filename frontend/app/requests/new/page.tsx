"use client"

import { useRequestStore } from "@/lib/stores/request-store"
import { UrlAnalyzer } from "@/components/wizard/UrlAnalyzer"
import { IdentityBuilder } from "@/components/wizard/IdentityBuilder"
import { ScopeSelector } from "@/components/wizard/ScopeSelector"
import { Check, ChevronLeft, X } from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function NewRequestPage() {
    const { currentStep } = useRequestStore()

    // Step Indicator Component
    const steps = [
        { number: 1, title: "Analyze Policy" },
        { number: 2, title: "Identity Builder" },
        { number: 3, title: "Review & Submit" }
    ]

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-zinc-950 pb-20">

            {/* Header / Progress Bar */}
            <div className="bg-white dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800 sticky top-0 z-10 px-4 py-4 md:px-8">
                <div className="max-w-4xl mx-auto">

                    {/* Top Controls */}
                    <div className="flex items-center justify-between mb-6">
                        <Link href="/dashboard/home">
                            <Button variant="ghost" size="sm" className="text-slate-500 dark:text-zinc-400 hover:text-slate-900 dark:hover:text-zinc-100 -ml-2">
                                <ChevronLeft className="mr-1 h-4 w-4" />
                                Back to Dashboard
                            </Button>
                        </Link>
                        <Link href="/dashboard/home">
                            <Button variant="ghost" size="icon" className="text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-zinc-300">
                                <X className="h-5 w-5" />
                            </Button>
                        </Link>
                    </div>

                    <div className="flex items-center justify-between mb-2">
                        <h1 className="text-xl font-bold text-slate-800 dark:text-zinc-100">New Privacy Request</h1>
                        <span className="text-sm text-slate-500">Step {currentStep} of 3</span>
                    </div>

                    <div className="flex items-center gap-2">
                        {steps.map((step, idx) => {
                            const isActive = currentStep === step.number
                            const isCompleted = currentStep > step.number

                            return (
                                <div key={step.number} className="flex items-center flex-1">
                                    <div className={cn(
                                        "flex flex-col flex-1 relative",
                                        idx !== 0 && "pl-2"
                                    )}>
                                        <div className={cn(
                                            "h-2 w-full rounded-full transition-all duration-300",
                                            isActive ? "bg-blue-600" : isCompleted ? "bg-green-500" : "bg-slate-200"
                                        )} />
                                        <span className={cn(
                                            "text-xs font-medium mt-2 transition-colors",
                                            isActive ? "text-blue-600" : isCompleted ? "text-green-600" : "text-slate-400"
                                        )}>
                                            {step.title}
                                        </span>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>

            {/* Main Content Area */}
            <main className="max-w-4xl mx-auto px-4 py-8 md:py-12 animate-in fade-in slide-in-from-bottom-4 duration-500">

                {currentStep === 1 && <UrlAnalyzer />}

                {currentStep === 2 && <IdentityBuilder />}

                {currentStep === 3 && <ScopeSelector />}

            </main>
        </div>
    )
}
