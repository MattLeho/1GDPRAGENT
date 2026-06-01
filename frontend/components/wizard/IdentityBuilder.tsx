
"use client"

import { useState, useEffect } from "react"
import { useForm, useFieldArray } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { useRequestStore, Profile } from "@/lib/stores/request-store"
import { encryptData } from "@/lib/crypto"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Plus, Trash2, Shield, Briefcase, Gamepad2, Ghost, Save, Network } from "lucide-react"
import { toast } from "sonner"
import { IdentityMiniMap } from "./IdentityMiniMap"
import { cn } from "@/lib/utils"

// --- Schema ---
const identityBuilderSchema = z.object({
    persona: z.string(),
    email: z.string().email("Invalid email address"),
    phone: z.string().optional(),

    // The "Flexible" Account details
    username: z.string().min(1, "Username is required"),
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
            username: "",
            details: []
        }
    })

    const { fields, append, remove } = useFieldArray({
        control: form.control,
        name: "details"
    })

    // Watch values for visualization
    const watched = form.watch()

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
        const encryptionKey = "user-session-key"

        // 1. Construct the flexible attributes object
        const attributes: Record<string, unknown> = {
            username: data.username,
            email: data.email,
        }
        if (data.phone) attributes.phone = data.phone

        // Add dynamic fields
        data.details.forEach(detail => {
            attributes[detail.key.toLowerCase()] = detail.value
        })

        // 2. Create Profile Store Object (Encrypted)
        const profile: Profile = {
            id: crypto.randomUUID(),
            identity_name: data.persona,
            encrypted_name: encryptData(data.username, encryptionKey), // Using username as name proxy
            encrypted_email: encryptData(data.email, encryptionKey),
            encrypted_address: encryptData("Address Placeholder", encryptionKey),
        }

        // 3. Sync with Neo4j Graph
        const loadingToast = toast.loading("Updating Knowledge Graph...")
        try {
            await fetch('/api/identities/account', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    persona: data.persona,
                    platform: "TargetSite", // In a real app, this comes from Step 1
                    attributes: attributes
                })
            })
            toast.dismiss(loadingToast)
            toast.success("Graph Updated & Link Created")

            // Move Next
            setIdentity(profile)
            nextStep()
        } catch (e) {
            console.error(e)
            toast.dismiss(loadingToast)
            toast.error("Failed to update graph")
        }
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
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Network className="h-6 w-6 text-indigo-600" />
                            Identity Builder
                        </CardTitle>
                        <CardDescription>
                            Link a Graph Persona to this request.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-8 space-y-8">
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
                                        <div
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
                                        </div>
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
                                        <FormLabel>Linked Email (From Graph)</FormLabel>
                                        <Select onValueChange={field.onChange} value={field.value}>
                                            <FormControl>
                                                <SelectTrigger className="bg-white">
                                                    <SelectValue placeholder="Select an email..." />
                                                </SelectTrigger>
                                            </FormControl>
                                            <SelectContent>
                                                {selectedPersonaId
                                                    ? graphData.find(p => p.id === selectedPersonaId)?.emails.map(e => (
                                                        <SelectItem key={e} value={e}>{e}</SelectItem>
                                                    ))
                                                    : <SelectItem value="none" disabled>Select a persona first</SelectItem>
                                                }
                                                <SelectItem value="new">+ Add New Email</SelectItem>
                                            </SelectContent>
                                        </Select>
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
                            <div className="flex items-center justify-between">
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
                                {/* Default Username Field */}
                                <div className="flex gap-3 items-end">
                                    <div className="w-[180px] pt-2">
                                        <span className="text-sm font-medium text-slate-500">Username</span>
                                    </div>
                                    <FormField
                                        control={form.control}
                                        name="username"
                                        render={({ field }) => (
                                            <div className="flex-1">
                                                <Input placeholder="Required Identifier..." {...field} />
                                            </div>
                                        )}
                                    />
                                    <div className="w-10"></div> {/* Spacer for delete button alignment */}
                                </div>

                                {/* Dynamic Fields */}
                                {fields.map((field, index) => (
                                    <div key={field.id} className="flex gap-3 items-end animate-in fade-in slide-in-from-top-1">
                                        <FormField
                                            control={form.control}
                                            name={`details.${index}.key`}
                                            render={({ field }) => (
                                                <div className="w-[180px]">
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
                        identityName={watched.username}
                        email={watched.email}
                        targetCompany="Target"
                    />
                </div>

            </CardContent>

            <CardFooter className="flex justify-between border-t p-6 bg-slate-50/50">
                <Button variant="ghost" onClick={prevStep}>Back</Button>
                <Button onClick={form.handleSubmit(onSubmit)} className="min-w-[150px] bg-indigo-600 hover:bg-indigo-700 shadow-lg shadow-indigo-200">
                    <Save className="mr-2 h-4 w-4" />
                    Save & Link
                </Button>
            </CardFooter>
        </Card>
    )
}
