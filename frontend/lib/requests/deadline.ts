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
    request_type?: string;
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
    extension_reason?: string | null;
    /** ISO calendar dates confirmed as public holidays for the relevant UK jurisdiction. */
    publicHolidays?: readonly string[];
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

const UK_TIME_ZONE = 'Europe/London';

function ukDateParts(date: Date): { year: number; month: number; day: number } {
    const parts = new Intl.DateTimeFormat('en-GB', {timeZone:UK_TIME_ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
    const value = Object.fromEntries(parts.map(part=>[part.type,part.value]));
    return {year:Number(value.year),month:Number(value.month)-1,day:Number(value.day)};
}

function ukOffsetMilliseconds(date: Date): number {
    const name = new Intl.DateTimeFormat('en-GB',{timeZone:UK_TIME_ZONE,timeZoneName:'longOffset'}).formatToParts(date)
        .find(part=>part.type==='timeZoneName')?.value ?? 'GMT';
    const match = name.match(/GMT([+-])(\d{2}):(\d{2})/);
    if (!match) return 0;
    const minutes = Number(match[2])*60+Number(match[3]);
    return (match[1]==='-'?-1:1)*minutes*60_000;
}

function ukEndOfDate(year:number,month:number,day:number):Date {
    const nextNoonUtc=new Date(Date.UTC(year,month,day+1,12));
    const nextMidnightAsUtc=Date.UTC(year,month,day+1,0);
    return new Date(nextMidnightAsUtc-ukOffsetMilliseconds(nextNoonUtc)-1);
}

function addCalendarMonthsClampedEndOfDay(date: Date, months: number): Date {
    const local = ukDateParts(date);
    const year = local.year;
    const month = local.month;
    const day = local.day;
    const targetMonthStart = new Date(Date.UTC(year, month + months, 1));
    const targetYear = targetMonthStart.getUTCFullYear();
    const targetMonth = targetMonthStart.getUTCMonth();
    const lastTargetDay = new Date(Date.UTC(targetYear, targetMonth + 1, 0)).getUTCDate();

    return ukEndOfDate(targetYear,targetMonth,Math.min(day,lastTargetDay));
}

function addUkCalendarDays(date:Date,days:number):Date {
    const local=ukDateParts(date);
    const shifted=new Date(Date.UTC(local.year,local.month,local.day+days));
    return ukEndOfDate(shifted.getUTCFullYear(),shifted.getUTCMonth(),shifted.getUTCDate());
}

function calendarDate(date: Date): string {
    const local=ukDateParts(date);
    return `${local.year}-${String(local.month+1).padStart(2,'0')}-${String(local.day).padStart(2,'0')}`;
}

function nextWorkingDay(date: Date, publicHolidays: ReadonlySet<string>): Date {
    const adjusted = new Date(date);
    let local=ukDateParts(adjusted);
    while (true) {
        const weekday=new Date(Date.UTC(local.year,local.month,local.day)).getUTCDay();
        const key=`${local.year}-${String(local.month+1).padStart(2,'0')}-${String(local.day).padStart(2,'0')}`;
        if (weekday!==0&&weekday!==6&&!publicHolidays.has(key)) return ukEndOfDate(local.year,local.month,local.day);
        const next=new Date(Date.UTC(local.year,local.month,local.day+1));
        local={year:next.getUTCFullYear(),month:next.getUTCMonth(),day:next.getUTCDate()};
    }
}

function easterSunday(year:number):Date {
    const a=year%19,b=Math.floor(year/100),c=year%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3);
    const h=(19*a+b-d-g+15)%30,i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451);
    const month=Math.floor((h+l-7*m+114)/31)-1,day=((h+l-7*m+114)%31)+1;
    return new Date(Date.UTC(year,month,day));
}

const ONE_OFF_ENGLAND_WALES_BANK_HOLIDAYS = new Set([
    '2022-06-02', // Platinum Jubilee spring bank holiday
    '2022-06-03', // Platinum Jubilee bank holiday
    '2022-09-19', // State Funeral of Queen Elizabeth II
    '2023-05-08', // Coronation of King Charles III
]);

function englandWalesBankHolidays(year:number):string[] {
    const dates=new Set<string>();
    const add=(date:Date)=>dates.add(date.toISOString().slice(0,10));
    const weekdayOnOrAfter=(month:number,day:number,weekday:number)=>{const d=new Date(Date.UTC(year,month,day));d.setUTCDate(day+(weekday-d.getUTCDay()+7)%7);return d;};
    const lastWeekday=(month:number,weekday:number)=>{const d=new Date(Date.UTC(year,month+1,0));d.setUTCDate(d.getUTCDate()-(d.getUTCDay()-weekday+7)%7);return d;};
    const newYear=new Date(Date.UTC(year,0,1)); if(newYear.getUTCDay()===0)newYear.setUTCDate(2);else if(newYear.getUTCDay()===6)newYear.setUTCDate(3);add(newYear);
    const easter=easterSunday(year); const goodFriday=new Date(easter);goodFriday.setUTCDate(easter.getUTCDate()-2);add(goodFriday);const easterMonday=new Date(easter);easterMonday.setUTCDate(easter.getUTCDate()+1);add(easterMonday);
    add(weekdayOnOrAfter(4,1,1));
    if(year!==2022) add(lastWeekday(4,1)); // moved to 2 June for the Platinum Jubilee
    add(lastWeekday(7,1));
    const christmas=new Date(Date.UTC(year,11,25)),boxing=new Date(Date.UTC(year,11,26));
    if(christmas.getUTCDay()===6){add(new Date(Date.UTC(year,11,27)));add(new Date(Date.UTC(year,11,28)));}
    else if(christmas.getUTCDay()===0){add(new Date(Date.UTC(year,11,27)));add(boxing);}
    else {add(christmas); if(boxing.getUTCDay()===6)add(new Date(Date.UTC(year,11,28)));else if(boxing.getUTCDay()===0)add(new Date(Date.UTC(year,11,28)));else add(boxing);}
    for(const date of ONE_OFF_ENGLAND_WALES_BANK_HOLIDAYS) if(date.startsWith(`${year}-`)) dates.add(date);
    return [...dates];
}

function defaultPublicHolidays(dates:ParsedDates):string[] {
    const years=new Set<number>();
    for(const value of Object.values(dates)) if(value){const year=ukDateParts(value).year;years.add(year);years.add(year+1);}
    return [...years].flatMap(englandWalesBankHolidays);
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

    const decisiveFields: DeadlineInputField[] = [
        'controller_received_at', 'sent_at', 'identity_requested_at', 'identity_verified_at',
        'clarification_requested_at', 'clarification_resolved_at', 'response_received_at',
        'extension_notified_at', 'extension_deadline_at',
    ];
    if (disputes.some(field => decisiveFields.includes(field))) {
        humanReview = true;
        return result('unknown', null, 'A core lifecycle date is disputed, so no definitive deadline screening result is produced.');
    }

    const publicHolidays = new Set(input.publicHolidays ?? defaultPublicHolidays(dates));

    let base = dates.controller_received_at;
    let estimated = false;
    let basis = 'Ordinary deadline ends on the corresponding calendar date one month after controller_received_at.';

    if (!base && dates.sent_at) {
        base = dates.sent_at;
        estimated = true;
        humanReview = true;
        basis = 'Estimated ordinary deadline ends on the corresponding calendar date one month after sent_at because receipt evidence is absent.';
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

    if (dates.identity_requested_at && dates.identity_verified_at && dates.identity_verified_at.getTime() > base.getTime()) {
        base = dates.identity_verified_at;
        basis = 'Identity evidence was required, so the ordinary deadline starts when identity_verified_at was recorded.';
    }

    let pauseDays = 0;
    if (dates.clarification_requested_at && dates.clarification_resolved_at) {
        const isAccessRequest = (input.request_type ?? 'access').toLowerCase().includes('access');
        if (!isAccessRequest) {
            uncertainties.push('A clarification interval was recorded for a non-access request; it was not applied automatically.');
            humanReview = true;
        } else if (dates.clarification_resolved_at.getTime() >= dates.clarification_requested_at.getTime()) {
            const requested=ukDateParts(dates.clarification_requested_at);
            const resolved=ukDateParts(dates.clarification_resolved_at);
            pauseDays=Math.round((Date.UTC(resolved.year,resolved.month,resolved.day)-Date.UTC(requested.year,requested.month,requested.day))/86_400_000);
            basis += ' The access-request clarification interval was added as stopped-clock time.';
        } else {
            uncertainties.push('clarification_resolved_at precedes clarification_requested_at; the interval was not applied.');
            humanReview = true;
        }
    }

    const ordinaryDeadline = nextWorkingDay(
        addUkCalendarDays(addCalendarMonthsClampedEndOfDay(base, 1), pauseDays),
        publicHolidays,
    );
    const hasExtensionNotice = dates.extension_notified_at !== null;
    const hasExtensionDeadline = dates.extension_deadline_at !== null;
    const extensionReason = input.extension_reason?.trim() ?? '';
    const maximumExtendedDeadline = nextWorkingDay(
        addUkCalendarDays(addCalendarMonthsClampedEndOfDay(base, 3), pauseDays),
        publicHolidays,
    );
    const validExtension = hasExtensionNotice && hasExtensionDeadline && extensionReason.length > 0
        && (dates.extension_notified_at as Date).getTime() <= ordinaryDeadline.getTime()
        && (dates.extension_deadline_at as Date).getTime() >= ordinaryDeadline.getTime()
        && (dates.extension_deadline_at as Date).getTime() <= maximumExtendedDeadline.getTime();
    let applicableDeadline = ordinaryDeadline;

    if (validExtension) {
        applicableDeadline = nextWorkingDay(dates.extension_deadline_at as Date, publicHolidays);
        basis += ' A reasoned extension notified within the ordinary period and no later than the three-month maximum is applicable.';
    } else if (hasExtensionNotice || hasExtensionDeadline) {
        uncertainties.push('Extension evidence is incomplete or invalid: notice, reason, timing, and the three-month maximum must all be supported; the ordinary deadline was retained.');
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
