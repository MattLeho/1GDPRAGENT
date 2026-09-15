'use client';

import { useSyncExternalStore } from 'react';
import type { InsightTemporalSelection } from '@/lib/insights/query';
import type { PeriodGranularity, TemporalMode } from '@/lib/insights/types';

interface TemporalControlProps {
    selection: InsightTemporalSelection;
    onChange: (selection: InsightTemporalSelection) => void;
    disabled?: boolean;
}

const GRANULARITIES: Array<{ value: PeriodGranularity; label: string }> = [
    { value: 'month', label: 'Month' },
    { value: 'quarter', label: 'Quarter' },
    { value: 'year', label: 'Year' },
    { value: 'custom', label: 'Custom' },
];

const subscribeToClient = () => () => {};

export function TemporalControl({ selection, onChange, disabled }: TemporalControlProps) {
    const mounted = useSyncExternalStore(subscribeToClient, () => true, () => false);

    const setMode = (mode: TemporalMode) => {
        const now = new Date();
        if (mode === 'point_in_time') {
            onChange({ mode, granularity: selection.granularity, point: selection.point || selection.to || now.toISOString() });
            return;
        }
        const to = selection.to || now.toISOString();
        const from = selection.from || shifted(to, selection.granularity, -1);
        if (mode === 'compare') {
            const duration = new Date(to).valueOf() - new Date(from).valueOf();
            onChange({ mode, granularity: selection.granularity, from, to, compareFrom: new Date(new Date(from).valueOf() - duration).toISOString(), compareTo: from });
            return;
        }
        onChange({ mode, granularity: selection.granularity, from, to });
    };

    const setGranularity = (granularity: PeriodGranularity) => {
        if (selection.mode === 'point_in_time') return onChange({ ...selection, granularity });
        if (granularity === 'custom') return onChange({ ...selection, granularity });
        const to = selection.to || new Date().toISOString();
        const from = shifted(to, granularity, -1);
        if (selection.mode === 'compare') {
            onChange({ ...selection, granularity, from, to, compareFrom: shifted(from, granularity, -1), compareTo: from });
        } else onChange({ ...selection, granularity, from, to });
    };

    return (
        <section aria-label="Global Personal Insights time selection" className="rounded-2xl border border-border bg-card p-4 text-card-foreground shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
                <div className="grid w-full grid-cols-3 rounded-xl bg-muted p-1 sm:inline-grid sm:w-auto" role="group" aria-label="Temporal mode">
                    {([['point_in_time', 'Point in time'], ['period', 'Period'], ['compare', 'Compare']] as const).map(([mode, label]) => (
                        <button key={mode} type="button" disabled={disabled} aria-pressed={selection.mode === mode} onClick={() => setMode(mode)} className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-muted disabled:cursor-not-allowed disabled:opacity-50 ${selection.mode === mode ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-background/80 hover:text-foreground'}`}>{label}</button>
                    ))}
                </div>
                <label className="flex w-full items-center justify-between gap-2 text-sm text-muted-foreground sm:w-auto sm:justify-start">
                    View
                    <select disabled={disabled} value={selection.granularity} onChange={event => setGranularity(event.target.value as PeriodGranularity)} className="min-w-0 flex-1 rounded-lg border border-input bg-background px-3 py-2 text-foreground shadow-sm [color-scheme:light] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50 dark:[color-scheme:dark] sm:flex-none">
                        {GRANULARITIES.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                </label>
                <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2 xl:ml-auto xl:w-auto">
                    {selection.mode === 'point_in_time' ? (
                        <DateField label="At" value={selection.point} disabled={disabled} localize={mounted} onChange={point => onChange({ ...selection, point })} />
                    ) : (
                        <>
                            <DateField label="From" value={selection.from} disabled={disabled} localize={mounted} onChange={from => onChange({ ...selection, from })} />
                            <DateField label="To" value={selection.to} disabled={disabled} localize={mounted} onChange={to => onChange({ ...selection, to })} />
                            {selection.mode === 'compare' && <>
                                <DateField label="Compare from" value={selection.compareFrom} disabled={disabled} localize={mounted} onChange={compareFrom => onChange({ ...selection, compareFrom })} />
                                <DateField label="Compare to" value={selection.compareTo} disabled={disabled} localize={mounted} onChange={compareTo => onChange({ ...selection, compareTo })} />
                            </>}
                        </>
                    )}
                </div>
            </div>
        </section>
    );
}

function DateField({ label, value, onChange, disabled, localize }: { label: string; value?: string; onChange: (value: string) => void; disabled?: boolean; localize: boolean }) {
    return <label className="min-w-0 text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}<input type="datetime-local" disabled={disabled} value={toDateInput(value, localize)} onChange={event => event.target.value && onChange(new Date(event.target.value).toISOString())} className="mt-1 block w-full min-w-0 rounded-lg border border-input bg-background px-2 py-2 text-sm font-normal normal-case tracking-normal text-foreground shadow-sm [color-scheme:light] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-50 dark:[color-scheme:dark]" /></label>;
}

function toDateInput(value: string | undefined, localize: boolean) {
    if (!value) return '';
    const date = new Date(value);
    if (!localize) return date.toISOString().slice(0, 16);
    const local = new Date(date.valueOf() - date.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 16);
}

function shifted(value: string, granularity: PeriodGranularity, amount: number) {
    const date = new Date(value);
    if (granularity === 'year') date.setUTCFullYear(date.getUTCFullYear() + amount);
    else if (granularity === 'quarter') date.setUTCMonth(date.getUTCMonth() + amount * 3);
    else if (granularity === 'week') date.setUTCDate(date.getUTCDate() + amount * 7);
    else if (granularity === 'day') date.setUTCDate(date.getUTCDate() + amount);
    else date.setUTCMonth(date.getUTCMonth() + amount);
    return date.toISOString();
}
