"use client";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  protectedFetch as fetch,
  shouldSuppressProtectedRequestError,
} from "@/lib/api-client";
interface Form {
  googleApiKey: string;
  openaiApiKey: string;
  openrouterApiKey: string;
  ollamaApiKey: string;
  huggingfaceApiKey: string;
  nvidiaApiKey: string;
}
const providers: Array<{
  id: keyof Form;
  name: string;
  description: string;
  optional?: boolean;
}> = [
  {
    id: "googleApiKey",
    name: "Google AI",
    description: "Optional external generation adapter",
  },
  {
    id: "openaiApiKey",
    name: "OpenAI",
    description: "Optional external generation adapter",
  },
  {
    id: "openrouterApiKey",
    name: "OpenRouter",
    description: "Optional multi-provider generation adapter",
  },
  {
    id: "ollamaApiKey",
    name: "Ollama",
    description: "Local Ollama endpoint; key is usually optional",
    optional: true,
  },
  {
    id: "huggingfaceApiKey",
    name: "Hugging Face",
    description: "Optional hosted inference adapter",
  },
  {
    id: "nvidiaApiKey",
    name: "NVIDIA",
    description: "Optional NIM generation adapter",
  },
];
export function AICredentialsSection() {
  const [configured, setConfigured] = useState<Record<string, boolean>>({}),
    [environment, setEnvironment] = useState<Record<string, boolean>>({}),
    [saving, setSaving] = useState(false);
  const form = useForm<Form>({
    defaultValues: Object.fromEntries(
      providers.map((p) => [p.id, ""]),
    ) as unknown as Form,
  });
  useEffect(() => {
    fetch("/api/settings/ai-credentials")
      .then((r) => r.json())
      .then((data) => {
        setConfigured(data.savedKeys || {});
        setEnvironment(data.envKeys || {});
      })
      .catch((error) => {
        if (!shouldSuppressProtectedRequestError(error)) {
          toast.error("Could not load provider credentials");
        }
      });
  }, []);
  const save = form.handleSubmit(async (values) => {
    setSaving(true);
    try {
      const response = await fetch("/api/settings/ai-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const data = await response.json();
      if (!response.ok) {
        toast.error(data.error || "Could not save provider credentials");
        return;
      }
      setConfigured(data.savedKeys || {});
      setEnvironment(data.envKeys || {});
      form.reset();
      toast.success("Provider credentials encrypted and saved");
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        toast.error("Could not save provider credentials");
      }
    } finally {
      setSaving(false);
    }
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Raw provider credentials</CardTitle>
        <CardDescription>
          Credentials enable adapters; they do not choose a model or route.
          Configure those per task under Processing & Models.
        </CardDescription>
      </CardHeader>
      <form onSubmit={save}>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {providers.map((provider) => (
            <div key={provider.id} className="rounded-lg border p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <Label htmlFor={provider.id}>{provider.name}</Label>
                  <p className="text-xs text-muted-foreground">
                    {provider.description}
                  </p>
                </div>
                {configured[provider.id] ? (
                  <Badge>Saved</Badge>
                ) : environment[provider.id] ? (
                  <Badge variant="secondary">Environment</Badge>
                ) : (
                  <Badge variant="outline">Not configured</Badge>
                )}
              </div>
              <Input
                id={provider.id}
                type="password"
                autoComplete="off"
                placeholder={
                  provider.optional ? "Optional" : "Enter to save or rotate"
                }
                {...form.register(provider.id)}
              />
            </div>
          ))}
        </CardContent>
        <CardFooter className="flex-col items-stretch gap-3">
          <p className="text-xs text-muted-foreground">
            Keys are encrypted server-side. A configured key alone is not shown
            as a healthy engine; use the task engine health check.
          </p>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save provider credentials"}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
