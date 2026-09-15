'use client';
import { useEffect,useState } from 'react';
import { protectedFetch as fetch, shouldSuppressProtectedRequestError } from '@/lib/api-client';
import type { PrivacyGraphFilters,PrivacyGraphMode,PrivacyQueryResult } from '@/lib/privacy/types';

async function invoke(tool:string,arguments_:Record<string,unknown>={}):Promise<PrivacyQueryResult>{
  const response=await fetch('/api/graph/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({tool,arguments:arguments_})});
  const body=await response.json();if(!response.ok)throw new Error(body.detail||'Privacy analysis failed');return body;
}

export function PrivacyModePanel({mode,filters}:{mode:PrivacyGraphMode;filters:PrivacyGraphFilters}){
  const [results,setResults]=useState<PrivacyQueryResult[]>([]);const [error,setError]=useState<string|null>(null);
  useEffect(()=>{let active=true;setError(null);
    const period=filters.asOf&&filters.compareTo?{from_at:filters.compareTo,to_at:filters.asOf}:null;
    const calls:Promise<PrivacyQueryResult>[] = mode==='compare'&&period
      ? ['get_personal_drift','get_controller_drift','get_understanding_drift'].map(tool=>invoke(tool,period))
      : mode==='capabilities'?[invoke('list_capability_exposure')]
      : mode==='purpose'?[invoke('list_purpose_drift_candidates')]
      : mode==='controller_profile'?[invoke('compare_behavioural_and_controller_profile')]
      : mode==='through_time'&&filters.asOf?[invoke('get_profile_at',{as_of:filters.asOf})]
      : mode==='access'?[invoke('list_controller_assignments')]
      : [];
    if(!calls.length){setResults([]);return()=>{active=false};}
    Promise.all(calls).then(value=>{if(active)setResults(value)}).catch(reason=>{if(active&&!shouldSuppressProtectedRequestError(reason))setError(reason instanceof Error?reason.message:String(reason))});
    return()=>{active=false};
  },[mode,filters.asOf,filters.compareTo]);
  if(!results.length&&!error)return null;
  return <div className="border-b p-3 text-xs space-y-2 bg-zinc-50 dark:bg-zinc-950">
    {error&&<p className="text-red-600">{error}</p>}
    {results.map(result=><div key={result.tool} className="rounded border bg-background p-2">
      <p className="font-semibold uppercase">{result.tool.replaceAll('_',' ')}</p>
      <p>{Array.isArray(result.data.items)?result.data.items.length:0} item(s) · {result.citations.length} cited assertion(s)</p>
      {result.unknowns.map(value=><p key={value} className="text-amber-700">Unknown: {value}</p>)}
    </div>)}
  </div>;
}
