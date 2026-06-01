# IDENTITY MAP ARCHITECTURE (Neo4j)

## 1. The Vision
To move beyond simple "lists" of accounts and create a living **Knowledge Graph** of the user's digital footprint. This allows us to query:
- "Which accounts use my old university email?"
- "Which identities are linked to my 'Gamer' username?"
- "Show me all data points (IPs, Addresses) Amazon holds on me."

## 2. The Tech Stack
- **Database:** Neo4j Community Edition (Dockerized).
- **Driver:** `neo4j-driver` (Node.js).
- **Visualization:** `react-force-graph` (for the interactive whiteboard).

## 3. The Graph Schema (Nodes & Relationships)

### Nodes (The Entities)
1.  `(:Person {name: 'Main User'})` (The Root)
2.  `(:Persona {label: 'Gamer', type: 'context'})` (e.g., Professional, Gamer, Anon)
3.  `(:Identity {value: 'John Doe', type: 'name'})` (Variations of names)
4.  `(:Email {address: 'john@gmail.com'})`
5.  `(:Phone {number: '+44...'})`
6.  `(:Account {username: 'johndoe123', platform: 'Twitter'})`
7.  `(:DataPoint {value: '192.168.1.1', type: 'ip_address'})` (Extracted from GDPR returns)

### Relationships (The Links)
- `(:Person)-[:HAS_PERSONA]->(:Persona)`
- `(:Persona)-[:USES_NAME]->(:Identity)`
- `(:Persona)-[:USES_EMAIL]->(:Email)`
- `(:Account)-[:BELONGS_TO_PERSONA]->(:Persona)`
- `(:Account)-[:REGISTERED_WITH]->(:Email)`
- `(:Account)-[:REVEALED_DATA]->(:DataPoint)`

## 4. Example Query (Cypher)
*Find all accounts linked to my 'Gamer' persona:*
```cypher
MATCH (p:Persona {label: 'Gamer'})-[:USES_EMAIL]->(e:Email)<-[:REGISTERED_WITH]-(a:Account)
RETURN a.platform, a.username