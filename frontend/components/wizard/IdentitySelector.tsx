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
import { Textarea } from "@/components/ui/textarea"
import { Lock, Plus, Trash2, Shield, User, Save, Briefcase, Gamepad2, Ghost, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

// --- Schema ---
const identitySchema = z.object({
    firstName: z.string().min(2, "First Name is required"),
    lastName: z.string().min(2, "Last Name is required"),
    email: z.string().email("Invalid email address"),
    phone: z.string().optional(),
    persona: z.string(),

    // Request Specifics
    notes: z.string().optional(),
    dateFrom: z.string().optional(),
    dateTo: z.string().optional(),

    // Dynamic Identifiers
    identifiers: z.array(z.object({
        type: z.enum(["username", "account_id", "email_alias", "handle"]),
        value: z.string().min(1, "Value is required")
    })).optional()
})

type IdentityFormValues = z.infer<typeof identitySchema>

interface PersonaData {
    id: string;
    label: string;
    emails: string[];
}

// Static persona icons - can be extended
const PERSONA_ICONS: Record<string, { icon: React.ElementType; color: string }> = {
    professional: { icon: Briefcase, color: "bg-blue-100 text-blue-700 border-blue-200" },
    gamer: { icon: Gamepad2, color: "bg-purple-100 text-purple-700 border-purple-200" },
    anon: { icon: Ghost, color: "bg-slate-100 text-slate-700 border-slate-200" },
    default: { icon: User, color: "bg-zinc-100 text-zinc-700 border-zinc-200" },
}

export function IdentitySelector() {
    const { setIdentity, nextStep, prevStep, setNotes, setDateRange } = useRequestStore()
    const [selectedPersona, setSelectedPersona] = useState("")
    const [personas, setPersonas] = useState<PersonaData[]>([])
    const [loadingPersonas, setLoadingPersonas] = useState(true)

    // Fetch personas from Neo4j on mount
    useEffect(() => {
        async function fetchPersonas() {
            try {
                const res = await fetch('/api/identities')
                if (res.ok) {
                    const data = await res.json()
                    setPersonas(data)
                    if (data.length > 0) {
                        setSelectedPersona(data[0].id)
                    }
                }
            } catch (e) {
                console.error("Failed to fetch personas:", e)
                toast.error("Could not load personas from graph")
            } finally {
                setLoadingPersonas(false)
            }
        }
        fetchPersonas()
    }, [])

    // React Hook Form Setup
    const form = useForm<IdentityFormValues>({
        resolver: zodResolver(identitySchema),
        defaultValues: {
            persona: "",
            identifiers: [{ type: "username", value: "" }],
            firstName: "",
            lastName: "",
            email: "",
            phone: "",
            notes: "",
            dateFrom: "",
            dateTo: "",
        }
    })

    const { fields, append, remove } = useFieldArray({
        control: form.control,
        name: "identifiers"
    })

    // Effect to update form when persona is selected and has linked emails
    const handlePersonaChange = (personaId: string) => {
        setSelectedPersona(personaId)
        form.setValue("persona", personaId)

        // Find the persona and pre-fill email if available
        const persona = personas.find(p => p.id === personaId)
        if (persona && persona.emails.length > 0) {
            form.setValue("email", persona.emails[0])
            toast.info(`Loaded ${persona.label} profile from graph`)
        }
    }

    const onSubmit = async (data: IdentityFormValues) => {
        const encryptionKey = "user-session-key"
        const fullName = `${data.firstName} ${data.lastName}`
        const requestDetails = [
            { fieldKey: "full_name", encryptedValue: encryptData(fullName, encryptionKey) },
            { fieldKey: "email", encryptedValue: encryptData(data.email, encryptionKey) },
            ...(data.phone ? [{ fieldKey: "phone", encryptedValue: encryptData(data.phone, encryptionKey) }] : []),
            ...(data.identifiers || []).map((identifier, index) => ({
                fieldKey: `${identifier.type}_${index + 1}`,
                encryptedValue: encryptData(identifier.value, encryptionKey),
            })),
        ].filter(detail => detail.encryptedValue)

        // 1. Store Request Context
        if (data.notes) setNotes(data.notes)
        if (data.dateFrom || data.dateTo) {
            setDateRange({
                from: data.dateFrom ? new Date(data.dateFrom) : undefined,
                to: data.dateTo ? new Date(data.dateTo) : undefined
            })
        }

        // 2. Create client-side profile request
        const profile: Profile = {
            id: crypto.randomUUID(),
            identity_name: data.persona || selectedPersona,
            contactName: fullName,
            contactEmail: data.email,
            encrypted_name: encryptData(fullName, encryptionKey),
            encrypted_email: encryptData(data.email, encryptionKey),
            encrypted_address: encryptData("Address Placeholder", encryptionKey),
            requestDetails,
        }

        // 3. Sync with Neo4j Graph via LLM-based upsert
        try {
            const response = await fetch('/api/graph/upsert-identity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    personaName: data.persona || selectedPersona,
                    emails: [data.email],
                    phones: data.phone ? [data.phone] : [],
                    names: [{ firstName: data.firstName, lastName: data.lastName }],
                    usernames: data.identifiers?.map(id => id.value) || [],
                    notes: data.notes,
                })
            })

            const result = await response.json()
            if (result.success) {
                toast.success("Identity synced to Knowledge Graph", {
                    description: `Created ${result.entitiesCreated} entities`
                })
            } else {
                throw new Error(result.error)
            }
        } catch (e) {
            console.error("Graph Sync Failed", e)
            toast.error("Graph sync failed", { description: "Local profile saved, but graph update failed." })
        }

        setIdentity(profile)
        nextStep()
    }

    const getPersonaIcon = (personaId: string) => {
        const lookup = PERSONA_ICONS[personaId.toLowerCase()] || PERSONA_ICONS.default
        return lookup
    }

    return (
        <Card className="w-full max-w-4xl mx-auto shadow-xl border-slate-200">
            <CardHeader className="border-b bg-slate-50/50">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2 text-xl">
                            <Shield className="h-6 w-6 text-indigo-600" />
                            Identity Builder
                        </CardTitle>
                        <CardDescription>
                            Construct the identity used for this request.
                        </CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="p-8 space-y-8">
                <Form {...form}>
                    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">

                            {/* LEFT COLUMN: Persona & Dates */}
                            <div className="md:col-span-1 space-y-6">
                                <FormLabel className="text-sm font-semibold text-slate-500 uppercase tracking-widest">Base Persona</FormLabel>

                                {loadingPersonas ? (
                                    <div className="flex items-center justify-center p-4">
                                        <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                                    </div>
                                ) : personas.length === 0 ? (
                                    <div className="text-sm text-slate-500 p-4 bg-slate-50 rounded-lg">
                                        No personas found. Create one below.
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {personas.map((p) => {
                                            const { icon: Icon } = getPersonaIcon(p.id)
                                            const isSelected = selectedPersona === p.id
                                            return (
                                                <div
                                                    key={p.id}
                                                    onClick={() => handlePersonaChange(p.id)}
                                                    className={cn(
                                                        "flex items-center gap-3 p-3 rounded-lg cursor-pointer border transition-all",
                                                        isSelected ? cn("border-indigo-500 bg-indigo-50/50", "ring-1 ring-indigo-200") : "border-slate-200 hover:border-slate-300"
                                                    )}
                                                >
                                                    <Icon className={cn("h-5 w-5", isSelected ? "text-indigo-600" : "text-slate-400")} />
                                                    <div className="flex-1">
                                                        <span className={cn("text-sm font-medium block", isSelected ? "text-indigo-900" : "text-slate-600")}>{p.label}</span>
                                                        {p.emails.length > 0 && (
                                                            <span className="text-xs text-slate-400">{p.emails[0]}</span>
                                                        )}
                                                    </div>
                                                </div>
                                            )
                                        })}
                                    </div>
                                )}

                                <div className="pt-6 border-t border-slate-100">
                                    <FormLabel className="text-sm font-semibold text-slate-500 uppercase tracking-widest mb-4 block">Request Scope</FormLabel>
                                    <div className="space-y-4">
                                        <FormField
                                            control={form.control}
                                            name="dateFrom"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel className="text-xs">Date From</FormLabel>
                                                    <FormControl>
                                                        <input type="date" className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" {...field} />
                                                    </FormControl>
                                                </FormItem>
                                            )}
                                        />
                                        <FormField
                                            control={form.control}
                                            name="dateTo"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel className="text-xs">Date To</FormLabel>
                                                    <FormControl>
                                                        <input type="date" className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50" {...field} />
                                                    </FormControl>
                                                </FormItem>
                                            )}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* RIGHT COLUMN: Identity Details */}
                            <div className="md:col-span-3 space-y-6">
                                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm space-y-6">
                                    <h3 className="font-semibold flex items-center gap-2 text-slate-800">
                                        <User className="h-4 w-4" /> Personal Details
                                    </h3>

                                    <div className="grid grid-cols-2 gap-4">
                                        <FormField
                                            control={form.control}
                                            name="firstName"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel>First Name</FormLabel>
                                                    <FormControl><Input {...field} /></FormControl>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />
                                        <FormField
                                            control={form.control}
                                            name="lastName"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel>Last Name</FormLabel>
                                                    <FormControl><Input {...field} /></FormControl>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <FormField
                                            control={form.control}
                                            name="email"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel>Primary Email</FormLabel>
                                                    <FormControl><Input {...field} /></FormControl>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />
                                        <FormField
                                            control={form.control}
                                            name="phone"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel>Phone (Optional)</FormLabel>
                                                    <FormControl><Input {...field} /></FormControl>
                                                </FormItem>
                                            )}
                                        />
                                    </div>
                                </div>

                                {/* Dynamic Identifiers */}
                                <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 space-y-4">
                                    <div className="flex items-center justify-between">
                                        <h3 className="font-semibold flex items-center gap-2 text-slate-800">
                                            <Lock className="h-4 w-4" /> Linked Identifiers
                                        </h3>
                                        <Button type="button" variant="outline" size="sm" onClick={() => append({ type: "username", value: "" })}>
                                            <Plus className="h-3 w-3 mr-1" /> Add ID
                                        </Button>
                                    </div>

                                    <div className="space-y-3">
                                        {fields.map((field, index) => (
                                            <div key={field.id} className="flex gap-2 items-start">
                                                <FormField
                                                    control={form.control}
                                                    name={`identifiers.${index}.type`}
                                                    render={({ field }) => (
                                                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                                                            <FormControl>
                                                                <SelectTrigger className="w-[140px] bg-white">
                                                                    <SelectValue placeholder="Type" />
                                                                </SelectTrigger>
                                                            </FormControl>
                                                            <SelectContent>
                                                                <SelectItem value="username">Username</SelectItem>
                                                                <SelectItem value="account_id">Account ID</SelectItem>
                                                                <SelectItem value="email_alias">Email Alias</SelectItem>
                                                                <SelectItem value="handle">Handle</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                    )}
                                                />
                                                <FormField
                                                    control={form.control}
                                                    name={`identifiers.${index}.value`}
                                                    render={({ field }) => (
                                                        <FormItem className="flex-1">
                                                            <FormControl>
                                                                <Input {...field} placeholder="Value..." className="bg-white" />
                                                            </FormControl>
                                                            <FormMessage />
                                                        </FormItem>
                                                    )}
                                                />
                                                <Button type="button" variant="ghost" size="icon" onClick={() => remove(index)} className="text-slate-400 hover:text-red-500">
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        ))}
                                    </div>
                                    <p className="text-xs text-slate-500">Add any usernames, aliases, or IDs you use on this platform.</p>
                                </div>

                                {/* Notes */}
                                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                                    <FormField
                                        control={form.control}
                                        name="notes"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel>Request Notes / Context</FormLabel>
                                                <FormControl>
                                                    <Textarea
                                                        {...field}
                                                        placeholder="Any specific instructions for this request? e.g. 'Please focus on my search history from 2023'"
                                                        className="resize-none min-h-[80px]"
                                                    />
                                                </FormControl>
                                            </FormItem>
                                        )}
                                    />
                                </div>
                            </div>
                        </div>

                    </form>
                </Form>
            </CardContent>

            <CardFooter className="flex justify-between border-t p-6 bg-slate-50/50">
                <Button variant="ghost" onClick={prevStep}>Back</Button>
                <Button onClick={form.handleSubmit(onSubmit)} className="min-w-[150px] bg-indigo-600 hover:bg-indigo-700">
                    <Save className="mr-2 h-4 w-4" />
                    Confirm & Proceed
                </Button>
            </CardFooter>
        </Card>
    )
}
