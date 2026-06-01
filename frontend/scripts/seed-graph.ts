
import { runCypher, closeDriver } from '../lib/graph'

async function seed() {
    console.log('🌱 Seeding Graph...')

    try {
        // 1. Clean Graph (Optional - be careful in prod!)
        // await runCypher('MATCH (n) DETACH DELETE n')

        // 2. Create Root User
        await runCypher(`
            MERGE (u:User { uid: 'ME' })
            SET u.name = 'Main User', u.created_at = datetime()
        `)

        // 3. Create Personas and Link to User
        const personas = ['Professional', 'Gamer', 'Anonymous']

        for (const name of personas) {
            await runCypher(`
                MATCH (u:User { uid: 'ME' })
                MERGE (p:Persona { name: $name })
                MERGE (u)-[:HAS_PERSONA]->(p)
            `, { name })
            console.log(`> Created Persona: ${name}`)
        }

        console.log('✅ Seeding Complete!')
    } catch (error) {
        console.error('❌ Seeding Failed:', error)
    } finally {
        await closeDriver()
    }
}

seed()
