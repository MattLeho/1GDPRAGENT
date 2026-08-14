query: str = "MERGE (n:GraphNode {node_id: $id})"
await tx.run(query)
