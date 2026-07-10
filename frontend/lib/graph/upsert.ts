type AccountData = Record<string, unknown>

const intelligenceUrl = process.env.INTELLIGENCE_URL || 'http://localhost:8001'

async function createHumanConfirmedNode(payload: Record<string, unknown>) {
  const response = await fetch(`${intelligenceUrl}/evidence/manual-node`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload), cache: 'no-store',
  })
  if (!response.ok) throw new Error(`Canonical graph projection rejected manual node (${response.status})`)
  return response.json()
}

/** Compatibility adapter: manual account edits become human-confirmed assertions. */
export async function upsertAccount(personaName: string, platform: string, data: AccountData) {
  const username=String(data.username || data.id || 'unknown-account')
  const results=[await createHumanConfirmedNode({ type:'Account',label:username,properties:{...data,controller:platform},subject_ref:personaName })]
  for (const [kind,value] of [['email',data.email],['phone',data.phone],['ip',data.ip || data.ip_address]] as const) {
    if (value) results.push(await createHumanConfirmedNode({ type:'Identifier',label:String(value),properties:{controller:platform,identifier_type:kind},subject_ref:personaName }))
  }
  if (Array.isArray(data.identifiers)) {
    for (const item of data.identifiers) {
      if (item && typeof item==='object' && 'value' in item) {
        const identifier=item as {type?:unknown;value:unknown}
        results.push(await createHumanConfirmedNode({type:'Identifier',label:String(identifier.value),properties:{controller:platform,identifier_type:String(identifier.type || 'opaque')},subject_ref:personaName}))
      }
    }
  }
  return {success:true,message:`Recorded ${platform} account assertions for ${personaName}`,results}
}
