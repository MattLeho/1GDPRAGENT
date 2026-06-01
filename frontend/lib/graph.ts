
import neo4j, { Driver } from 'neo4j-driver'

// Use environment variables with fallback for local dev
const NEO4J_URI = process.env.NEO4J_URI || 'bolt://localhost:7687'
const NEO4J_USER = process.env.NEO4J_USER || 'neo4j'
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD

let driver: Driver | null = null

export function getDriver(): Driver {
    if (!NEO4J_PASSWORD) {
        throw new Error('NEO4J_PASSWORD must be set')
    }

    if (!driver) {
        driver = neo4j.driver(
            NEO4J_URI,
            neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD)
        )
    }
    return driver
}

export async function runCypher(query: string, params: Record<string, unknown> = {}) {
    const driver = getDriver()
    const session = driver.session()

    try {
        const result = await session.run(query, params)
        return result.records
    } catch (error) {
        console.error('Neo4j Query Failed:', error)
        throw error // Re-throw to handle in API
    } finally {
        await session.close()
    }
}

export async function closeDriver() {
    if (driver) {
        await driver.close()
        driver = null
    }
}
