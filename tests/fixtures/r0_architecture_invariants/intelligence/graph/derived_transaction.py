query = "MERGE (n:GraphNode {node_id: $id})"
transaction = session.begin_transaction()
await transaction.run(query)
