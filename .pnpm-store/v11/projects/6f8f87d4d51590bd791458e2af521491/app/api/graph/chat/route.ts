import { NextRequest, NextResponse } from 'next/server';
import { intelligenceAuthorityHeaders, requireApiSession } from '@/lib/api-session';
import { executeTask } from '@/lib/execution/router';

const baseUrl = () => process.env.INTELLIGENCE_SERVICE_URL || process.env.INTELLIGENCE_URL || 'http://intelligence:8000';

/** Closed proxy for the typed PrivacyQueryService. No question, SQL or Cypher is accepted. */
export async function POST(request: NextRequest) {
    const authority = await requireApiSession(request);
    if (authority instanceof NextResponse) return authority;
    let body: unknown;
    try { body = await request.json(); }
    catch { return NextResponse.json({ detail: 'A typed privacy tool call is required.' }, { status: 400 }); }
    try {
        if (body && typeof body === 'object' && typeof (body as {question?:unknown}).question === 'string') {
            const question=(body as {question:string}).question.trim();
            if(!question)return NextResponse.json({detail:'Question is required'},{status:400});
            const selection=await executeTask({taskKey:'graph.explanation',workflowKey:'graph.query',input:{text:question},configuration:{systemPrompt:`Select exactly one privacy tool and its arguments. Return JSON only: {"tool":"...","arguments":{...}}. Allowed tools: get_current_profile, get_profile_at, compare_profile_periods, trace_assertion, get_assertion_evidence, find_identifier_links, get_identifier_centrality, simulate_identifier_removal, list_controller_assignments, compare_behavioural_and_controller_profile, list_capability_exposure, trace_capability_evidence, list_purpose_drift_candidates, trace_purpose_lineage, list_open_privacy_hypotheses, compare_export_snapshots, get_personal_drift, get_controller_drift, get_understanding_drift. Never return SQL or Cypher. If required IDs or dates are absent, select the closest no-argument tool and preserve uncertainty.`},profileId:authority.profileId});
            const selectedText=selection.ok?(selection.output as {text?:unknown}).text:null;
            if(typeof selectedText!=='string')return NextResponse.json({detail:'No typed tool selection was produced'},{status:422});
            const match=selectedText.match(/\{[\s\S]*\}/);if(!match)return NextResponse.json({detail:'Tool selector returned invalid JSON'},{status:422});
            try{body=JSON.parse(match[0]);}catch{return NextResponse.json({detail:'Tool selector returned invalid JSON'},{status:422});}
        }
        const queryUrl = `${baseUrl()}/query`;
        const encodedBody=JSON.stringify(body);
        const response = await fetch(queryUrl, {
            method: 'POST', body: encodedBody, cache: 'no-store',
            headers: intelligenceAuthorityHeaders(authority.profileId, queryUrl, 'POST','application/json',undefined,undefined,encodedBody), signal: AbortSignal.timeout(120_000),
        });
        const payload = await response.json().catch(() => ({ detail: `Privacy query service returned ${response.status}` }));
        if (!response.ok) return NextResponse.json(payload, { status: response.status });
        let explanation: string | null = null;
        if (payload.evidence_bearing === true && Array.isArray(payload.citations) && payload.citations.length > 0) {
            const explained = await executeTask({taskKey:'graph.explanation',workflowKey:'graph.query',input:{text:JSON.stringify(payload)},configuration:{systemPrompt:'Explain only the supplied typed privacy-tool result. Preserve unknowns and epistemic status. Every evidence-bearing sentence must cite an Assertion ID and EvidenceLocator from the supplied citations. Do not generate or execute graph queries.'},profileId:authority.profileId});
            const text = explained.ok ? (explained.output as {text?:unknown}).text : null;
            explanation = typeof text === 'string' ? text : null;
        }
        return NextResponse.json({ ...payload, explanation });
    } catch (error) {
        return NextResponse.json({ detail: 'Privacy query service is unavailable', error: error instanceof Error ? error.message : String(error) }, { status: 503 });
    }
}
