export type GraphSource = 'onsit' | 'gdpr' | 'manual' | 'inference' | 'file_upload'
export type GraphRiskLevel = 'low' | 'medium' | 'high' | 'critical'

const labelMap: Record<string, string> = {
    email: 'Email',
    username: 'Username',
    phone: 'Phone',
    domain: 'Domain',
    ip: 'IP',
    ipaddress: 'IPAddress',
    ip_address: 'IPAddress',
    identifier: 'Identifier',
    name: 'Name',
    social_profile: 'SocialProfile',
    socialprofile: 'SocialProfile',
    individual: 'Individual',
    organization: 'Organization',
    breach_record: 'BreachRecord',
    breachrecord: 'BreachRecord',
    credential: 'Credential',
    website: 'Website',
    document: 'PublicDocument',
    publicdocument: 'PublicDocument',
    cryptowallet: 'CryptoWallet',
    crypto_wallet: 'CryptoWallet',
    user: 'User',
    persona: 'Persona',
    company: 'Company',
    account: 'Account',
    attribute: 'Attribute',
    datapoint: 'DataPoint',
    data_point: 'DataPoint',
    entity: 'Entity',
    inference: 'Inference',
}

export const graphNodeTypeOrder = [
    'User',
    'Persona',
    'Company',
    'Account',
    'Attribute',
    'DataPoint',
    'Inference',
    'Entity',
    'Email',
    'Username',
    'Phone',
    'Name',
    'Identifier',
    'Domain',
    'IP',
    'IPAddress',
    'ASN',
    'CIDR',
    'SocialProfile',
    'Individual',
    'Organization',
    'Website',
    'BreachRecord',
    'Credential',
    'PublicDocument',
    'CryptoWallet',
    'Transaction',
    'NFT',
    'ONSITFinding',
]

export function sanitizeNeo4jLabel(label: string): string {
    const sanitized = label.replace(/[^A-Za-z0-9_]/g, '')
    if (!sanitized) return 'Entity'
    return /^[A-Za-z_]/.test(sanitized) ? sanitized : `Entity${sanitized}`
}

export function mapTypeToLabel(type: string = 'Entity'): string {
    return sanitizeNeo4jLabel(labelMap[type.toLowerCase()] || type)
}

export function sanitizeRelationshipType(type: string = 'RELATES_TO'): string {
    const sanitized = type.toUpperCase().replace(/[^A-Z0-9_]/g, '_')
    if (!sanitized || !/^[A-Z_]/.test(sanitized)) return 'RELATES_TO'
    return sanitized
}

export function sanitizeProperties(props: Record<string, unknown>): Record<string, unknown> {
    const sanitized: Record<string, unknown> = {}

    for (const [key, value] of Object.entries(props)) {
        if (value === null || value === undefined) continue

        if (typeof value === 'object' && !Array.isArray(value)) {
            sanitized[key] = JSON.stringify(value)
        } else if (Array.isArray(value)) {
            sanitized[key] = value.some(item => typeof item === 'object')
                ? JSON.stringify(value)
                : value
        } else {
            sanitized[key] = value
        }
    }

    return sanitized
}

export function normalizeRiskLevel(value: unknown): GraphRiskLevel {
    const riskLevel = String(value || 'low').toLowerCase()
    return ['low', 'medium', 'high', 'critical'].includes(riskLevel)
        ? riskLevel as GraphRiskLevel
        : 'low'
}

export function pickGraphNodeType(labels: string[]): string {
    return graphNodeTypeOrder.find(type => labels.includes(type)) || labels[0] || 'Unknown'
}

export function getGraphNodeLabel(props: Record<string, unknown>, type: string): string {
    return String(
        props.name ||
        props.value ||
        props.label ||
        props.address ||
        props.username ||
        props.number ||
        props.domain ||
        type
    )
}
