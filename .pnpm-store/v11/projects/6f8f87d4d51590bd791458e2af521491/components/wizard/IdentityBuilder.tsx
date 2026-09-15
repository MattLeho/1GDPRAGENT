
"use client"

import { useState, useEffect } from "react"
import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client'
import { useForm, useFieldArray, useWatch } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { useRequestStore, Profile } from "@/lib/stores/request-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Plus, Trash2, Briefcase, Gamepad2, Ghost, Save, Network } from "lucide-react"
import { toast } from "sonner"
import { IdentityMiniMap } from "./IdentityMiniMap"
import { cn } from "@/lib/utils"

// --- Schema ---
const identityBuilderSchema = z.object({
    persona: z.string().min(1, "Select a persona context"),
    email: z.string().email("Invalid email address"),
    phone: z.string().optional(),

    // The "Flexible" Account details
    name: z.string().min(1, "Your name is required"),
    details: z.array(z.object({
        key: z.string().min(1, "Field name required"),
        value: z.string().min(1, "Value required")
    }))
})

type IdentityBuilderValues = z.infer<typeof identityBuilderSchema>

export function IdentityBuilder() {
    const { setIdentity, nextStep, prevStep, graphData, fetchGraphData } = useRequestStore()
    const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null)

    // Fetch Graph Data on Mount
    useEffect(() => {
        fetchGraphData()
    }, [fetchGraphData])

    // React Hook Form Setup
    const form = useForm<IdentityBuilderValues>({
        resolver: zodResolver(identityBuilderSchema),
        defaultValues: {
            persona: "",
            email: "",
            phone: "",
            name: "",
            details: []
        }
    })

    const { fields, append, remove } = useFieldArray({
        control: form.control,
        name: "details"
    })

    // Watch values for visualization
    const watched = useWatch({ control: form.control })

    // Handle Persona Selection
    const handlePersonaClick = (id: string) => {
        setSelectedPersonaId(id)
        form.setValue("persona", id)

        // Auto-select first email if available
        const personaData = graphData.find(p => p.id === id)
        if (personaData && personaData.emails.length > 0) {
            form.setValue("email", personaData.emails[0])
            toast.info(`Auto-selected email: ${personaData.emails[0]}`)
        } else {
            form.setValue("email", "")
        }
    }

    const onSubmit = async (data: IdentityBuilderValues) => {
        const attributes: Record<string, unknown> = {
            name: data.name,
            email: data.email,
        }
        if (data.phone) attributes.phone = data.phone

        // Add dynamic fields
        data.details.forEach(detail => {
            attributes[detail.key.toLowerCase()] = detail.value
        })

        const requestDetails = [
            { fieldKey: 'full_name', value: data.name },
            { fieldKey: 'email', value: data.email },
            ...(data.phone ? [{ fieldKey: 'phone', value: data.phone }] : []),
            ...data.details.map(detail => ({ fieldKey: detail.key, value: detail.value })),
        ]

        const profile: Profile = {
            id: crypto.randomUUID(),
            identity_name: data.persona,
            contactName: data.name,
            contactEmail: data.email,
            contactPhone: data.phone || undefined,
            requestDetails,
        }

        setIdentity(profile)
        const loadingToast = toast.loading("Linking identity context to the knowledge graph...")
        try {
            const response = await fetch('/api/identities/account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    persona: data.persona,
                    platform: "request-wizard",
                    attributes: attributes
                })
            })
            if (!response.ok) {
                const result = await response.json().catch(() => null)
                throw new Error(result?.error || result?.message || "The identity could not be linked")
            }
            toast.dismiss(loadingToast)
            toast.success("Identity is ready and the graph context was linked")
        } catch (e) {
            toast.dismiss(loadingToast)
            if (!shouldSuppressProtectedRequestError(e)) {
                console.error(e)
                toast.warning("Identity is ready, but graph linking is unavailable")
            }
        }
        nextStep()
    }

    // Helper to get Persona Icon
    const getIcon = (label: string) => {
        const l = label.toLowerCase()
        if (l.includes('game')) return Gamepad2
        if (l.includes('prof') || l.includes('work')) return Briefcase
        return Ghost
    }

    return (
        <Card className="w-full max-w-5xl mx-auto shadow-xl border-slate-200">
            <CardHeader className="border-b bg-slate-50/50">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Network className="h-6 w-6 text-indigo-600" />
                            Identity Builder
                        </CardTitle>
                        <CardDescription>
                            Choose the identity used in the request. Values are sent to the authenticated graph service and encrypted server-side when the request is created.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-8 p-4 sm:p-6 lg:p-8">
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">

                        {/* ROW 1: Persona Chips (From Graph) */}
                        <div className="space-y-3">
                            <label className="text-sm font-medium text-slate-700">1. Select Persona Context</label>
                            <div className="flex flex-wrap gap-4">
                                {graphData.length === 0 && (
                                    <div className="text-sm text-slate-400 italic">Loading graph data... (did you run seed?)</div>
                                )}
                                {graphData.map((p) => {
                                    const Icon = getIcon(p.label)
                                    const isSelected = selectedPersonaId === p.id
                                    return (
                                        <button
                                            type="button"
                                            key={p.id}
                                            onClick={() => handlePersonaClick(p.id)}
                                            className={cn(
                                                "flex items-center gap-2 px-6 py-3 rounded-full cursor-pointer border transition-all shadow-sm",
                                                isSelected
                                                    ? "bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-200"
                                                    : "bg-white text-slate-700 border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                                            )}
                                        >
                                            <Icon className="h-4 w-4" />
                                            <span className="font-semibold text-sm">{p.label}</span>
                                        </button>
                                    )
                                })}
                            </div>
                        </div>

                        {/* ROW 2: Shared Attributes (Graph Aware) */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 relative p-6 bg-slate-50 rounded-xl border border-slate-100">
                            {/* Connector Line Logic would go here visually */}

                            <FormField
                                control={form.control}
                                name="email"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Email used for this request</FormLabel>
                                        <FormControl>
                                            <Input type="email" autoComplete="email" placeholder="you@example.com" {...field} className="bg-white" />
                                        </FormControl>
                                        <FormMessage />
                                    </FormItem>
                                )}
                            />

                            <FormField
                                control={form.control}
                                name="phone"
                                render={({ field }) => (
                                    <FormItem>
                                        <FormLabel>Linked Phone (Optional)</FormLabel>
                                        <FormControl>
                                            <Input placeholder="+1..." {...field} className="bg-white" />
                                        </FormControl>
                                    </FormItem>
                                )}
                            />
                        </div>

                        {/* ROW 3: Flexible Account Details */}
                        <div className="space-y-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <label className="text-sm font-medium text-slate-700">3. Account Details (Key-Value Store)</label>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => append({ key: "", value: "" })}
                                >
                                    <Plus className="mr-2 h-4 w-4" />
                                    Add Detail
                                </Button>
                            </div>

                            <div className="space-y-3">
                                {/* Required request name */}
                                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                                    <div className="w-full pt-2 sm:w-[180px]">
                                        <span className="text-sm font-medium text-slate-500">Full name</span>
                                    </div>
                                    <FormField
                                        control={form.control}
                                        name="name"
                                        render={({ field }) => (
                                            <div className="flex-1">
                                                <Input placeholder="Name used in the GDPR request" {...field} />
                                            </div>
                                        )}
                                    />
                                    <div className="w-10"></div> {/* Spacer for delete button alignment */}
                                </div>

                                {/* Dynamic Fields */}
                                {fields.map((field, index) => (
                                    <div key={field.id} className="flex flex-col gap-3 animate-in fade-in slide-in-from-top-1 sm:flex-row sm:items-end">
                                        <FormField
                                            control={form.control}
                                            name={`details.${index}.key`}
                                            render={({ field }) => (
                                                <div className="w-full sm:w-[180px]">
                                                    <Input placeholder="Key (e.g. Clan Tag)" {...field} />
                                                </div>
                                            )}
                                        />
                                        <FormField
                                            control={form.control}
                                            name={`details.${index}.value`}
                                            render={({ field }) => (
                                                <div className="flex-1">
                                                    <Input placeholder="Value..." {...field} />
                                                </div>
                                            )}
                                        />
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            className="mb-0.5 text-red-500 hover:text-red-700 hover:bg-red-50"
                                            onClick={() => remove(index)}
                                            aria-label={`Remove detail ${index + 1}`}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </div>

                    </form>
                </Form>

                {/* VISUALIZATION */}
                <div className="mt-8 pt-6 border-t border-slate-100">
                    <IdentityMiniMap
                        persona={graphData.find(p => p.id === selectedPersonaId)?.label || "None"}
                        identityName={watched.name || ""}
                        email={watched.email || ""}
                        targetCompany="Target"
                    />
                </div>

            </CardContent>

            <CardFooter className="flex flex-col-reverse gap-3 border-t bg-slate-50/50 p-4 sm:flex-row sm:justify-between sm:p-6">
                <Button variant="ghost" onClick={prevStep}>Back</Button>
                <Button onClick={form.handleSubmit(onSubmit)} className="min-w-[150px] bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-200">
                    <Save className="mr-2 h-4 w-4" />
                    Continue
                </Button>
            </CardFooter>
        </Card>
    )
}
