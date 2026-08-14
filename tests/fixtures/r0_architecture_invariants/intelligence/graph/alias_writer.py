async def unsafe_alias(graph_client):
    mutation = "MERGE (n:GraphNode {node_id: $node_id})"
    writer = graph_client.execute
    return await writer(mutation, {"node_id": "bad"})
