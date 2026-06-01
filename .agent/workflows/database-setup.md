---
description: How to start and manage the GDPR app databases (PostgreSQL, Neo4j, N8N)
---

## Start All Services
// turbo-all
```powershell
cd d:\1GDPRAGENT
docker-compose up -d
```

## Verify Services Are Running
```powershell
docker ps --filter "name=gdpr_"
```

## Connection Details

### PostgreSQL
- **Host:** localhost:5432
- **Database:** gdpr_local
- **User:** admin
- **Password:** securepassword

### Neo4j
- **Bolt URI:** bolt://localhost:7687
- **Browser:** http://localhost:7474
- **User:** neo4j
- **Password:** password

### N8N
- **URL:** http://localhost:5678
- **User:** admin
- **Password:** admin

### Qdrant (Vector DB)
- **URL:** http://localhost:6333

## Run Database Migrations
```powershell
Get-Content "d:\1GDPRAGENT\02_DATABASE_SCHEMA.sql" | docker exec -i gdpr_postgres psql -U admin -d gdpr_local
```

## Seed Neo4j Graph
```powershell
docker exec gdpr_neo4j cypher-shell -u neo4j -p password "MATCH (n) RETURN count(n)"
```

## Stop All Services
```powershell
docker-compose down
```

## Restart Services
```powershell
docker-compose restart
```
