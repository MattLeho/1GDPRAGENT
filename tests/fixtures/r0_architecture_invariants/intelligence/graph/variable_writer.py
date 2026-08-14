async def unsafe_variable(neo4j_client):
    cypher = f"MATCH (n:GraphNode) SET n.compromised = {True} RETURN n"
    return await neo4j_client.execute(cypher)


async def unsafe_transaction(tx):
    query = "MATCH (n:GraphNode) DELETE n"
    return await tx.run(query)
