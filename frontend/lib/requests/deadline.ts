export const DEADLINE_STATES = [
    'known',
    'estimated',
    'paused_identity',
    'paused_clarification',
    'extended',
    'overdue',
    'completed_on_time',
    'completed_late',
    'unknown',
] as const;

export type DeadlineState = (typeof DEADLINE_STATES)[number];

export type DeadlineDateInput = Date | string | null;

export type DeadlineInputField =
    | 'sent_at'
    | 'controller_received_at'
    | 'identity_requested_at'
    | 'identity_verified_at'
    | 'clarification_requested_at'
    | 'clarification_resolved_at'
    | 'response_received_at'
    | 'completed_at'
    | 'extension_notified_at'
    | 'extension_deadline_at'
    | 'evaluation_at';

export interface DeadlineScreeningInput {
    sent_at?: DeadlineDateInput;
    controller_received_at?: DeadlineDateInput;
    identity_requested_at?: DeadlineDateInput;
    identity_verified_at?: DeadlineDateInput;
    clarification_requested_at?: DeadlineDateInput;
    clarification_resolved_at?: DeadlineDateInput;
    response_received_at?: DeadlineDateInput;
    completed_at?: DeadlineDateInput;
    extension_notified_at?: DeadlineDateInput;
    extension_deadline_at?: DeadlineDateInput;
    evaluationAt: Date | string;
    disputedFields?: readonly DeadlineInputField[];
}

export interface DeadlineScreeningResult {
    deadline_state: DeadlineState;
    deadline_at: string | null;
    basis: string;
    input_dates: Record<DeadlineInputField, string | null>;
    uncertainties: string[];
    human_review_required: boolean;
}

const DATE_FIELDS = [
    'sent_at',
    'controller_received_at',
    'identity_requested_at',
    'identity_verified_at',
    'clarification_requested_at',
    'clarification_resolved_at',
    'response_received_at',
    'completed_at',
    'extension_notified_at',
    'extension_deadline_at',
] as const;

type LifecycleField = (typeof DATE_FIELDS)[number];
type ParsedDates = Record<DeadlineInputField, Date | null>;

function parseDate(
    value: DeadlineDateInput | undefined,
    field: DeadlineInputField,
    uncertainties: string[],
): Date | null {
    if (value === null || value === undefined || value === '') return null;

    const parsed = value instanceof Date ? new Date(value.getTime()) : new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        uncertainties.push(`Invalid date recorded for ${field}; it was not used.`);
        return null;
    }
    return parsed;
}

function addOneCalendarMonthClamped(date: Date): Date {
    const year = date.getUTCFullYear();
    const month = date.getUTCMonth();
    const day = date.getUTCDate();
    const targetMonthStart = new Date(Date.UTC(year, month + 1, 1));
    const targetYear = targetMonthStart.getUTCFullYear();
    const targetMonth = targetMonthStart.getUTCMonth();
    const lastTargetDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();

    return new Date(Date.UTC(
        targetYear,
        targetMonth,
        Math.min(day, lastTargetDay),
        date.getUTCHours(),
        date.getUTCMinutes(),
        date.getUTCSeconds(),
        date.getUTCMilliseconds(),
    ));
}

function latestDate(...dates: Array<Date | null>): Date | null {
    return dates.reduce<Date | null>((latest, candidate) => {
        if (!candidate) return latest;
        return !latest || candidate.getTime() > latest.getTime() ? candidate : latest;
    }, null);
}

function normaliseInputDates(dates: ParsedDates): Record<DeadlineInputField, string | null> {
    return Object.fromEntries(
        (Object.keys(dates) as DeadlineInputField[]).map(field => [field, dates[field]?.toISOString() ?? null]),
    ) as Record<DeadlineInputField, string | null>;
}

/**
 * Produces a deterministic evidence screening result. It is deliberately not a
 * legal-compliance conclusion: uncertain and disputed evidence remains visible.
 */
export function screenRequestDeadline(input: DeadlineScreeningInput): DeadlineScreeningResult {
    const uncertainties: string[] = [];
    const dates = {} as ParsedDates;

    for (const field of DATE_FIELDS) {
        dates[field] = parseDate(input[field as LifecycleField], field, uncertainties);
    }
    dates.evaluation_at = parseDate(input.evaluationAt, 'evaluation_at', uncertainties);

    const disputes = [...new Set(input.disputedFields ?? [])];
    for (const field of disputes) uncertainties.push(`Disputed date: ${field}.`);

    let humanReview = uncertainties.length > 0;
    const result = (
        deadline_state: DeadlineState,
        deadline: Date | null,
        basis: string,
    ): DeadlineScreeningResult => ({
        deadline_state,
        deadline_at: deadline?.toISOString() ?? null,
        basis,
        input_dates: normaliseInputDates(dates),
        uncertainties,
        human_review_required: humanReview,
    });

    let base = dates.controller_received_at;
    let estimated = false;
    let basis = 'Ordinary deadline screened as one calendar month from controller_received_at.';

    if (!base && dates.sent_at) {
        base = dates.sent_at;
        estimated = true;
        humanReview = true;
        basis = 'Estimated ordinary deadline screened as one calendar month from sent_at because receipt evidence is absent.';
        uncertainties.push('Controller receipt date is unknown; sent_at is used only for an estimated screening date.');
    }

    if (!base) {
        if (dates.completed_at && !dates.response_received_at) {
            uncertainties.push('completed_at is recorded without response_received_at; local completion does not establish timeliness.');
        }
        humanReview = true;
        return result('unknown', null, 'No controller receipt or sent evidence is available to screen a deadline.');
    }

    if (dates.identity_requested_at && !dates.identity_verified_at) {
        uncertainties.push('Identity verification pause is unresolved.');
        humanReview = true;
        return result('paused_identity', null, `${basis} No active deadline is concluded while identity verification remains unresolved.`);
    }

    if (dates.clarification_requested_at && !dates.clarification_resolved_at) {
        uncertainties.push('Clarification pause is unresolved.');
        humanReview = true;
        return result('paused_clarification', null, `${basis} No active deadline is concluded while clarification remains unresolved.`);
    }

    const resolvedPauseBase = latestDate(
        dates.identity_requested_at ? dates.identity_verified_at : null,
        dates.clarification_requested_at ? dates.clarification_resolved_at : null,
    );
    if (resolvedPauseBase && resolvedPauseBase.getTime() > base.getTime()) {
        base = resolvedPauseBase;
        humanReview = true;
        uncertainties.push('A resolved identity or clarification pause moved the screening base to the latest verified/resolved date; this is a conservative screening assumption.');
        basis += ' The base was conservatively moved to the latest applicable identity_verified_at or clarification_resolved_at.';
    }

    const ordinaryDeadline = addOneCalendarMonthClamped(base);
    const hasExtensionNotice = dates.extension_notified_at !== null;
    const hasExtensionDeadline = dates.extension_deadline_at !== null;
    const validExtension = hasExtensionNotice && hasExtensionDeadline;
    let applicableDeadline = ordinaryDeadline;

    if (validExtension) {
        applicableDeadline = dates.extension_deadline_at as Date;
        basis += ' A recorded extension_notified_at and extension_deadline_at make the extension deadline applicable.';
    } else if (hasExtensionNotice || hasExtensionDeadline) {
        uncertainties.push('Extension evidence is incomplete: both extension_notified_at and extension_deadline_at are required; the ordinary deadline was retained.');
        humanReview = true;
    }

    if (dates.completed_at && !dates.response_received_at) {
        uncertainties.push('completed_at is recorded without response_received_at; local completion does not establish timeliness.');
        humanReview = true;
    }

    if (dates.response_received_at) {
        const onTime = dates.response_received_at.getTime() <= applicableDeadline.getTime();
        const comparisonBasis = `${basis} Timeliness is screened using response_received_at, never completed_at or operational status.`;
        return result(onTime ? 'completed_on_time' : 'completed_late', applicableDeadline, comparisonBasis);
    }

    if (!dates.evaluation_at) {
        uncertainties.push('A valid evaluationAt is required to screen an open deadline.');
        humanReview = true;
        return result('unknown', applicableDeadline, `${basis} The open deadline could not be evaluated deterministically.`);
    }

    if (dates.evaluation_at.getTime() > applicableDeadline.getTime()) {
        return result('overdue', applicableDeadline, `${basis} evaluationAt is later than the applicable screening deadline.`);
    }

    if (validExtension) return result('extended', applicableDeadline, basis);
    return result(estimated ? 'estimated' : 'known', applicableDeadline, basis);
}

