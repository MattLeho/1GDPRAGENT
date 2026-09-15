'use client';

import { useEffect, useMemo, useState } from 'react';
import { protectedApi, shouldSuppressProtectedRequestError } from '@/lib/api-client';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';

interface Task {
  task_key: string;
  display_name: string;
  description: string;
  task_category: string;
}

interface Engine {
  engine_id: string;
  display_name: string;
  execution_location: 'local' | 'external';
  capabilities: string[];
}

interface Route {
  task_key: string;
  engine_id: string;
  provider: string | null;
  model: string | null;
  execution_location: string;
  fallback_chain: Array<{ engine_id: string }>;
  enabled: boolean;
  max_concurrency: number;
  batch_size: number;
  timeout_ms: number;
  configuration: Record<string, unknown>;
}

interface RoutePayload {
  tasks: Task[];
  engines: Engine[];
  routes: Route[];
}

interface HealthPayload {
  status: string;
  message: string;
}

const labels: Record<string, string> = {
  speech: 'Speech', images: 'Images', documents: 'Documents', schema: 'Documents',
  semantic: 'Semantic Analysis', temporal: 'Semantic Analysis', graph: 'Graph',
  policy_requests: 'Policy & Requests', email: 'Policy & Requests', media: 'Speech',
};

export function TaskRoutesSection() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [engines, setEngines] = useState<Engine[]>([]);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [savedRoutes, setSavedRoutes] = useState<Route[]>([]);
  const [advanced, setAdvanced] = useState(false);
  const [health, setHealth] = useState<Record<string, string>>({});
  const [checking, setChecking] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<Set<string>>(new Set());
  const [loadError, setLoadError] = useState('');
  const [operationStatus, setOperationStatus] = useState('');

  const applyPayload = (data: RoutePayload) => {
    setTasks(data.tasks || []);
    setEngines(data.engines || []);
    setRoutes(data.routes || []);
    setSavedRoutes(data.routes || []);
    setLoadError('');
  };

  useEffect(() => {
    let active = true;
    protectedApi<RoutePayload>('/api/settings/task-routes')
      .then((data) => {
        if (active) applyPayload(data);
      })
      .catch((error) => {
        if (!active || shouldSuppressProtectedRequestError(error)) return;
        setLoadError('Could not load task routes');
        toast.error('Could not load task routes');
      });
    return () => {
      active = false;
    };
  }, []);

  const groups = useMemo(
    () => tasks.reduce((map, item) => {
      const key = labels[item.task_category] || item.task_category;
      map.set(key, [...(map.get(key) || []), item]);
      return map;
    }, new Map<string, Task[]>()),
    [tasks],
  );

  const retry = async () => {
    setLoadError('');
    try {
      applyPayload(await protectedApi<RoutePayload>('/api/settings/task-routes'));
      setOperationStatus('Task routes loaded');
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        setLoadError('Could not load task routes');
        setOperationStatus('Task routes could not be loaded');
      }
    }
  };

  const edit = (taskKey: string, changes: Partial<Route>) => {
    setRoutes((current) => current.map((route) => (
      route.task_key === taskKey ? { ...route, ...changes } : route
    )));
  };

  const save = async (route: Route) => {
    setSaving((current) => new Set(current).add(route.task_key));
    setOperationStatus(`Saving ${route.task_key}`);
    try {
      const data = await protectedApi<{ route: Route }>('/api/settings/task-routes', {
        method: 'POST',
        body: JSON.stringify(route),
      });
      setRoutes((current) => current.map((item) => item.task_key === route.task_key ? data.route : item));
      setSavedRoutes((current) => current.map((item) => item.task_key === route.task_key ? data.route : item));
      setOperationStatus(`${route.task_key} saved`);
      toast.success('Task route saved');
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        setOperationStatus(`${route.task_key} changes not saved`);
        toast.error(error instanceof Error ? error.message : 'Could not save task route');
      }
    } finally {
      setSaving((current) => {
        const next = new Set(current);
        next.delete(route.task_key);
        return next;
      });
    }
  };

  const check = async (task: Task, engineId: string) => {
    setChecking((current) => new Set(current).add(engineId));
    setHealth((current) => ({ ...current, [engineId]: 'Checking…' }));
    try {
      const data = await protectedApi<HealthPayload>(`/api/settings/engine-health/${encodeURIComponent(engineId)}`);
      setHealth((current) => ({ ...current, [engineId]: `${data.status}: ${data.message}` }));
      setOperationStatus(`${task.display_name} health: ${data.status}`);
    } catch (error) {
      if (!shouldSuppressProtectedRequestError(error)) {
        setHealth((current) => ({ ...current, [engineId]: 'Health check unavailable' }));
        setOperationStatus(`${task.display_name} health check unavailable`);
      }
    } finally {
      setChecking((current) => {
        const next = new Set(current);
        next.delete(engineId);
        return next;
      });
    }
  };

  if (loadError) {
    return (
      <Card>
        <CardHeader><CardTitle>Task Execution Router</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <p role="alert" className="text-sm text-destructive">{loadError}</p>
          <Button className="min-h-11 sm:min-h-9" variant="outline" onClick={retry}>
            Retry task routes
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold">Task Execution Router</h3>
          <p className="text-sm text-muted-foreground">Choose and save an engine for each concrete processing task.</p>
        </div>
        <Button className="min-h-11 shrink-0 sm:min-h-9" variant="outline" onClick={() => setAdvanced((value) => !value)}>
          {advanced ? 'Hide advanced' : 'Advanced'}
        </Button>
      </div>
      {[...groups].map(([group, items]) => (
        <Card key={group}>
          <CardHeader>
            <CardTitle>{group}</CardTitle>
            <CardDescription>Task-specific routes; no global preferred model.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {items.map((task) => {
              const route = routes.find((item) => item.task_key === task.task_key);
              if (!route) return null;
              const engine = engines.find((item) => item.engine_id === route.engine_id);
              const compatible = engines.filter((item) => item.capabilities.includes(task.task_key));
              const saved = savedRoutes.find((item) => item.task_key === task.task_key);
              const dirty = !saved || JSON.stringify(saved) !== JSON.stringify(route);
              const engineControlId = `task-engine-${task.task_key.replaceAll('.', '-')}`;
              return (
                <div key={task.task_key} className="min-w-0 space-y-3 rounded-lg border p-3">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{task.display_name}</p>
                      <p className="text-xs text-muted-foreground">{task.description}</p>
                    </div>
                    <span className={`self-start rounded-full px-2 py-1 text-xs lg:self-center ${engine?.execution_location === 'external' ? 'bg-amber-100 text-amber-900' : 'bg-emerald-100 text-emerald-900'}`}>
                      {engine?.execution_location || 'unknown'}
                    </span>
                    <div className="min-w-0 space-y-1 lg:w-64">
                      <Label htmlFor={engineControlId} className="text-xs">Primary engine</Label>
                      <Select
                        value={route.engine_id}
                        onValueChange={(value) => {
                          const nextEngine = engines.find((item) => item.engine_id === value);
                          edit(route.task_key, {
                            engine_id: value,
                            provider: null,
                            execution_location: nextEngine?.execution_location || route.execution_location,
                          });
                        }}
                      >
                        <SelectTrigger id={engineControlId} className="min-h-11 w-full sm:min-h-9">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {compatible.map((item) => (
                            <SelectItem key={item.engine_id} value={item.engine_id}>{item.display_name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <p className="break-words text-xs text-muted-foreground" aria-live="polite">
                    Model: {route.model || 'Adapter default'} · Fallbacks:{' '}
                    {route.fallback_chain.map((item) => item.engine_id).join(' → ') || 'none'} ·{' '}
                    {health[route.engine_id] || 'health not checked'}
                  </p>
                  {advanced && (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
                      <Field label="Model" id={`model-${task.task_key}`}>
                        <Input id={`model-${task.task_key}`} value={route.model || ''} onChange={(event) => edit(route.task_key, { model: event.target.value || null })} />
                      </Field>
                      <Field label="Fallback engine" id={`fallback-${task.task_key}`}>
                        <Select value={route.fallback_chain[0]?.engine_id || 'none'} onValueChange={(value) => edit(route.task_key, { fallback_chain: value === 'none' ? [] : [{ engine_id: value }] })}>
                          <SelectTrigger id={`fallback-${task.task_key}`} className="min-h-11 sm:min-h-9"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">No fallback</SelectItem>
                            {compatible.filter((item) => item.engine_id !== route.engine_id).map((item) => (
                              <SelectItem key={item.engine_id} value={item.engine_id}>{item.display_name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </Field>
                      <NumberField label="Max concurrency" id={`concurrency-${task.task_key}`} value={route.max_concurrency} min={1} max={64} onChange={(value) => edit(route.task_key, { max_concurrency: value })} />
                      <NumberField label="Batch size" id={`batch-${task.task_key}`} value={route.batch_size} min={1} max={10000} onChange={(value) => edit(route.task_key, { batch_size: value })} />
                      <NumberField label="Timeout (ms)" id={`timeout-${task.task_key}`} value={route.timeout_ms} min={1000} max={3600000} onChange={(value) => edit(route.task_key, { timeout_ms: value })} />
                    </div>
                  )}
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <Button
                      className="min-h-11 sm:min-h-9"
                      size="sm"
                      variant="outline"
                      disabled={checking.has(route.engine_id)}
                      aria-label={`Check ${task.display_name} engine health`}
                      onClick={() => check(task, route.engine_id)}
                    >
                      {checking.has(route.engine_id) ? 'Checking…' : 'Health'}
                    </Button>
                    <Button
                      className="min-h-11 sm:min-h-9"
                      size="sm"
                      disabled={!dirty || saving.has(route.task_key)}
                      onClick={() => save(route)}
                    >
                      {saving.has(route.task_key) ? 'Saving…' : 'Save route'}
                    </Button>
                    <span className="text-xs text-muted-foreground">{dirty ? 'Unsaved changes' : 'Saved'}</span>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      ))}
      <p className="sr-only" aria-live="polite">{operationStatus}</p>
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return <div className="min-w-0 space-y-1"><Label htmlFor={id} className="text-xs">{label}</Label>{children}</div>;
}

function NumberField({ label, id, value, min, max, onChange }: { label: string; id: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <Field label={label} id={id}>
      <Input id={id} type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </Field>
  );
}
