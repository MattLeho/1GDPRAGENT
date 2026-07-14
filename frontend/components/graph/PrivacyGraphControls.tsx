'use client';

import { Button } from '@/components/ui/button';
import type { PrivacyGraphFilters, PrivacyGraphMode, ProfileLayer } from '@/lib/privacy/types';

const modes: Array<[PrivacyGraphMode, string]> = [
    ['now','NOW'], ['through_time','THROUGH TIME'], ['compare','COMPARE'],
    ['controller_profile','CONTROLLER PROFILE'], ['capabilities','CAPABILITIES'],
    ['linkability','LINKABILITY'], ['purpose','PURPOSE'], ['access','ACCESS'],
];
const layers: Array<[ProfileLayer, string]> = [
    ['self_declared','WHO I SAY I AM'], ['observed_behaviour','WHAT MY ACTIVITY EVIDENCES'],
    ['controller_profile','WHAT THE CONTROLLER ASSIGNS'], ['system_hypotheses','WHAT THE SYSTEM HYPOTHESISES'],
];

export function PrivacyGraphControls({mode, filters, onMode, onFilters}:{
    mode:PrivacyGraphMode; filters:PrivacyGraphFilters;
    onMode:(mode:PrivacyGraphMode)=>void; onFilters:(filters:PrivacyGraphFilters)=>void;
}) {
    const timed = mode === 'through_time' || mode === 'compare';
    return <div className="border-b bg-white dark:bg-zinc-900 px-4 py-3 space-y-3">
        <div className="flex gap-1 overflow-x-auto">{modes.map(([value,label]) =>
            <Button key={value} size="sm" variant={mode===value?'default':'outline'} onClick={()=>onMode(value)}>{label}</Button>)}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
            <label>Profile layer <select className="ml-1 rounded border bg-background p-1" value={filters.profileLayer||''}
                onChange={event=>onFilters({...filters,profileLayer:event.target.value as ProfileLayer||undefined})}>
                <option value="">ALL LAYERS — KEPT SEPARATE</option>{layers.map(([value,label])=><option key={value} value={value}>{label}</option>)}
            </select></label>
            <label>Epistemic state <select className="ml-1 rounded border bg-background p-1" value={filters.epistemicBasis||''}
                onChange={event=>onFilters({...filters,epistemicBasis:event.target.value as PrivacyGraphFilters['epistemicBasis']||undefined})}>
                <option value="">ALL</option><option value="currently_observed">CURRENTLY OBSERVED</option>
                <option value="potentially_enabled">POTENTIALLY ENABLED</option><option value="alleged_unverified">ALLEGED / UNVERIFIED</option>
            </select></label>
            {timed && <label>As of <input aria-label="As of" type="datetime-local" className="ml-1 rounded border bg-background p-1"
                onChange={event=>onFilters({...filters,asOf:event.target.value?new Date(event.target.value).toISOString():undefined})}/></label>}
            {mode==='compare' && <label>Compare to <input aria-label="Compare to" type="datetime-local" className="ml-1 rounded border bg-background p-1"
                onChange={event=>onFilters({...filters,compareTo:event.target.value?new Date(event.target.value).toISOString():undefined})}/></label>}
        </div>
        {mode==='compare' && <p className="text-xs text-muted-foreground">Drift view labels edges as added, removed, or unchanged between the two selected observations.</p>}
    </div>;
}
