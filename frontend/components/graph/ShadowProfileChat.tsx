'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Loader2, MessageCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import type { PrivacyQueryResult } from '@/lib/privacy/types';

const tools = [
    ['Current evidence profile', 'get_current_profile'],
    ['Controller assignments', 'list_controller_assignments'],
    ['Capability exposure', 'list_capability_exposure'],
    ['Open uncertainties', 'list_open_privacy_hypotheses'],
] as const;

export function ShadowProfileChat() {
    const [result, setResult] = useState<PrivacyQueryResult | null>(null);
    const [loading, setLoading] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [question,setQuestion]=useState('');

    async function run(tool: string) {
        setLoading(tool); setError(null);
        try {
            const response = await fetch('/api/graph/chat', {
                method: 'POST', headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ tool, arguments: {} }),
            });
            const body = await response.json();
            if (!response.ok) throw new Error(body.detail || 'Privacy query failed');
            setResult(body as PrivacyQueryResult);
        } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
        finally { setLoading(null); }
    }
    async function ask(){const value=question.trim();if(!value)return;setLoading('question');setError(null);
        try{const response=await fetch('/api/graph/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question:value})});
            const body=await response.json();if(!response.ok)throw new Error(body.detail||'Privacy question failed');setResult(body);setQuestion('');
        }catch(reason){setError(reason instanceof Error?reason.message:String(reason))}finally{setLoading(null)}}

    const items = result && Array.isArray(result.data.items) ? result.data.items : [];
    return <Card className="border-t rounded-none bg-white dark:bg-zinc-900 p-4 space-y-3">
        <p className="text-xs text-muted-foreground flex items-center gap-1">
            <MessageCircle className="h-3 w-3" /> Evidence-backed privacy queries
        </p>
        <div className="flex flex-wrap gap-2">
            {tools.map(([label, tool]) => <Button key={tool} variant="outline" size="sm" onClick={() => run(tool)} disabled={!!loading}>
                {loading === tool && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}{label}
            </Button>)}
        </div>
        <div className="flex gap-2"><Input value={question} onChange={event=>setQuestion(event.target.value)}
            onKeyDown={event=>event.key==='Enter'&&void ask()} placeholder="Ask an evidence-backed privacy question" disabled={!!loading}/>
            <Button onClick={()=>void ask()} disabled={!!loading||!question.trim()}>{loading==='question'&&<Loader2 className="h-3 w-3 mr-1 animate-spin"/>}Ask</Button></div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {result && <div className="rounded-md border p-3 text-sm space-y-2">
            <p>{items.length} evidence item{items.length === 1 ? '' : 's'} · {result.citations.length} cited assertion{result.citations.length === 1 ? '' : 's'}</p>
            {result.explanation && <p className="whitespace-pre-wrap">{result.explanation}</p>}
            {result.unknowns.map(value => <p key={value} className="text-amber-700 dark:text-amber-300">Unknown: {value}</p>)}
            <details><summary className="cursor-pointer">Inspect typed result</summary>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(result.data, null, 2)}</pre>
            </details>
            {result.citations.length > 0 && <details><summary className="cursor-pointer">Evidence citations</summary>
                <ul className="mt-2 space-y-1 text-xs">{result.citations.map(c => <li key={c.assertion_id}>
                    Assertion {c.assertion_id} · locator {c.evidence_locator_ids.join(', ')} · artifact {c.source_artifact_ids.join(', ')}
                </li>)}</ul>
            </details>}
        </div>}
    </Card>;
}
