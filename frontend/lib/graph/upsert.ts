
import { runCypher } from '../graph'

type AccountData = Record<string, unknown>

/**
 * Smart Upserts an Account node and links it to extracted attributes.
 * 
 * Strategy:
 * 1. MERGE the Account node based on Persona + Platform + Main ID (username).
 * 2. SET simple properties on the Account node.
 * 3. EXTRACT specific keys (email, phone, ip, device) to create separate Nodes and link them.
 */
export async function upsertAccount(
    personaName: string,
    platform: string,
    data: AccountData
) {
    const reservedKeys = ['email', 'phone', 'ip', 'ip_address', 'device', 'device_id']

    // 1. Separate connection keys from simple properties
    const simpleProps: Record<string, unknown> = {
        updated_at: new Date().toISOString()
    }
    const linkableAttributes: Record<string, string> = {}
    const dynamicIdentifiers: Array<{ type: string, value: string }> = []

    for (const [key, value] of Object.entries(data)) {
        if (!value) continue;

        const lowerKey = key.toLowerCase()

        if (key === 'identifiers' && Array.isArray(value)) {
            // Handle Dynamic Identifiers Array
            dynamicIdentifiers.push(...value)
            continue
        }

        if (reservedKeys.includes(lowerKey)) {
            linkableAttributes[lowerKey] = String(value)
        } else if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
            simpleProps[key] = value
        }
    }

    // Ensure we have a username/identifier for the constraint
    const username = simpleProps['username'] || simpleProps['id'] || 'unknown_user'

    // 2. Construct Cypher Query
    let cypher = `
      MERGE (p:Persona { name: $personaName })
      MERGE (a:Account { platform: $platform, username: $username })
      MERGE (p)-[:OWNS_ACCOUNT]->(a)
      SET a += $simpleProps
    `

    // 3. Dynamic Linked Nodes
    if (linkableAttributes['email']) {
        cypher += `
          MERGE (e:Email { address: '${linkableAttributes['email']}' })
          MERGE (a)-[:REGISTERED_WITH]->(e)
          MERGE (p)-[:USES_EMAIL]->(e) 
        `
    }

    if (linkableAttributes['phone']) {
        cypher += `
          MERGE (ph:Phone { number: '${linkableAttributes['phone']}' })
          MERGE (a)-[:VERIFIED_BY]->(ph)
        `
    }

    // Handle dynamic identifiers as AccountProperties or Aliases
    // For now, let's treat them as properties on the Account node IF they are simple, 
    // or separate Identifier nodes if they are shared. 
    // Simplification: Create text properties for them on the Account node for now to ensure they are saved.
    // e.g. identifiers_username_0: "foo"
    // Better: Creating a JSON string property for them
    if (dynamicIdentifiers.length > 0) {
        cypher += ` SET a.identifiers_json = '${JSON.stringify(dynamicIdentifiers)}' `

        // Also create specific nodes for searchability if needed
        dynamicIdentifiers.forEach((id, idx) => {
            if (id.type === 'username' || id.type === 'handle') {
                cypher += `
                   MERGE (id${idx}:Identifier { value: '${id.value}', type: '${id.type}' })
                   MERGE (a)-[:HAS_IDENTIFIER]->(id${idx})
                 `
            }
        })
    }

    // IP/Device handling (unchanged)
    if (linkableAttributes['ip'] || linkableAttributes['ip_address']) {
        const ip = linkableAttributes['ip'] || linkableAttributes['ip_address']
        cypher += `
          MERGE (ip:IPAddress { value: '${ip}' })
          MERGE (a)-[:ACCESSED_FROM]->(ip)
        `
    }

    cypher += ` RETURN a`

    // Execute
    await runCypher(cypher, {
        personaName,
        platform,
        username,
        simpleProps
    })

    return { success: true, message: `Upserted ${platform} account for ${personaName}` }
}
