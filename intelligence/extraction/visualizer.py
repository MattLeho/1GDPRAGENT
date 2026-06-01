"""
Graph Visualization Export

Generates interactive visualizations following AI-KG Phase 4 patterns:
- PyVis HTML graphs with community colors
- Node sizing by centrality metrics
- Solid vs dashed edges for original vs inferred
- Dark/light theme support

Source patterns: https://github.com/robert-mcdermott/ai-knowledge-graph
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from collections import defaultdict

from .schemas import SPOTriple


# =============================================================================
# Color Palettes
# =============================================================================

# Community colors (distinct, colorblind-friendly)
COMMUNITY_COLORS = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
    "#7f7f7f",  # Gray
    "#bcbd22",  # Olive
    "#17becf",  # Cyan
]

# Edge colors
EDGE_COLOR_ORIGINAL = "#666666"
EDGE_COLOR_INFERRED = "#999999"


# =============================================================================
# Graph Visualizer Class
# =============================================================================

class GraphVisualizer:
    """
    Generates interactive graph visualizations.
    
    Creates PyVis-based HTML visualizations with:
    - Community detection and color coding
    - Centrality-based node sizing
    - Inferred relationship styling
    
    Usage:
        visualizer = GraphVisualizer()
        path = visualizer.generate_pyvis(triples, output_path)
    """
    
    def __init__(
        self,
        theme: str = "light",  # "light" or "dark"
    ):
        self.theme = theme
    
    def generate_pyvis(
        self,
        triples: list[SPOTriple],
        output_path: Path,
        title: str = "Knowledge Graph",
    ) -> Path:
        """
        Generate PyVis HTML visualization.
        
        Args:
            triples: SPO triples to visualize
            output_path: Where to save HTML file
            title: Graph title
            
        Returns:
            Path to generated HTML file
        """
        try:
            from pyvis.network import Network
            import networkx as nx
        except ImportError:
            # Fall back to simple HTML
            return self._generate_simple_html(triples, output_path, title)
        
        # Build NetworkX graph for analysis
        G = nx.Graph()
        for triple in triples:
            G.add_edge(
                triple.subject,
                triple.object,
                label=triple.predicate,
                confidence=triple.confidence,
                inferred=triple.inferred,
            )
        
        # Calculate centrality metrics
        centrality = self._calculate_centrality(G)
        
        # Detect communities
        communities = self._detect_communities(G)
        
        # Assign colors
        node_colors = self._assign_colors(communities)
        
        # Calculate node sizes
        node_sizes = self._calculate_node_sizes(centrality)
        
        # Create PyVis network
        bg_color = "#1a1a2e" if self.theme == "dark" else "#ffffff"
        font_color = "#ffffff" if self.theme == "dark" else "#000000"
        
        net = Network(
            height="800px",
            width="100%",
            bgcolor=bg_color,
            font_color=font_color,
            directed=True,
        )
        
        # Add nodes
        for node in G.nodes():
            net.add_node(
                node,
                label=str(node)[:30],  # Truncate long labels
                title=f"{node} (centrality: {centrality.get(node, 0):.2f})",
                color=node_colors.get(node, COMMUNITY_COLORS[0]),
                size=node_sizes.get(node, 15),
            )
        
        # Add edges
        for u, v, data in G.edges(data=True):
            color = EDGE_COLOR_INFERRED if data.get("inferred") else EDGE_COLOR_ORIGINAL
            dashes = data.get("inferred", False)
            
            net.add_edge(
                u, v,
                title=data.get("label", ""),
                color=color,
                dashes=dashes,
                width=2,
            )
        
        # Configure physics
        net.set_options("""
        var options = {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -50,
              "springLength": 100,
              "springConstant": 0.08
            },
            "minVelocity": 0.75,
            "solver": "forceAtlas2Based"
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 200
          }
        }
        """)
        
        # Save HTML
        output_path = Path(output_path)
        net.save_graph(str(output_path))
        
        return output_path
    
    def _calculate_centrality(
        self,
        G,
    ) -> dict[str, float]:
        """
        Calculate combined centrality metrics.
        
        Uses weighted average of degree, betweenness, and eigenvector.
        """
        import networkx as nx
        
        try:
            degree_cent = nx.degree_centrality(G)
            betweenness_cent = nx.betweenness_centrality(G)
            
            try:
                eigenvector_cent = nx.eigenvector_centrality(G, max_iter=100)
            except nx.PowerIterationFailedConvergence:
                eigenvector_cent = {n: 0 for n in G.nodes()}
            
            # Combine with weights
            combined = {}
            for node in G.nodes():
                combined[node] = (
                    0.4 * degree_cent.get(node, 0) +
                    0.4 * betweenness_cent.get(node, 0) +
                    0.2 * eigenvector_cent.get(node, 0)
                )
            
            return combined
            
        except Exception:
            return {n: 1.0 for n in G.nodes()}
    
    def _detect_communities(
        self,
        G,
    ) -> dict[str, int]:
        """
        Detect communities using Louvain algorithm.
        
        Returns mapping of node to community index.
        """
        import networkx as nx
        
        try:
            from networkx.algorithms import community as nx_community
            communities = nx_community.louvain_communities(G)
            
            node_to_community = {}
            for i, community in enumerate(communities):
                for node in community:
                    node_to_community[node] = i
            
            return node_to_community
            
        except Exception:
            # Fall back to all same community
            return {n: 0 for n in G.nodes()}
    
    def _assign_colors(
        self,
        communities: dict[str, int],
    ) -> dict[str, str]:
        """
        Assign colors to nodes based on community.
        """
        colors = {}
        for node, community in communities.items():
            color_idx = community % len(COMMUNITY_COLORS)
            colors[node] = COMMUNITY_COLORS[color_idx]
        return colors
    
    def _calculate_node_sizes(
        self,
        centrality: dict[str, float],
        min_size: int = 10,
        max_size: int = 50,
    ) -> dict[str, int]:
        """
        Calculate node sizes based on centrality.
        """
        if not centrality:
            return {}
        
        max_cent = max(centrality.values()) or 1
        min_cent = min(centrality.values())
        range_cent = max_cent - min_cent or 1
        
        sizes = {}
        for node, cent in centrality.items():
            normalized = (cent - min_cent) / range_cent
            sizes[node] = int(min_size + normalized * (max_size - min_size))
        
        return sizes
    
    def _generate_simple_html(
        self,
        triples: list[SPOTriple],
        output_path: Path,
        title: str,
    ) -> Path:
        """
        Generate simple HTML fallback when PyVis not available.
        """
        # Build node and edge lists
        nodes = set()
        edges = []
        
        for triple in triples:
            nodes.add(triple.subject)
            nodes.add(triple.object)
            edges.append({
                "source": triple.subject,
                "target": triple.object,
                "label": triple.predicate,
                "inferred": triple.inferred,
            })
        
        # Generate HTML with D3.js-style layout
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .stats {{ margin: 20px 0; padding: 10px; background: #f5f5f5; border-radius: 5px; }}
        .legend {{ display: flex; gap: 20px; margin: 20px 0; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; }}
        .legend-line {{ width: 30px; height: 2px; }}
        .solid {{ background: {EDGE_COLOR_ORIGINAL}; }}
        .dashed {{ background: repeating-linear-gradient(90deg, {EDGE_COLOR_INFERRED} 0 5px, transparent 5px 10px); }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background: #f2f2f2; }}
        .inferred {{ color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="stats">
        <strong>Statistics:</strong>
        Nodes: {len(nodes)} | 
        Edges: {len(edges)} | 
        Inferred: {sum(1 for e in edges if e['inferred'])}
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-line solid"></div>
            <span>Original relationship</span>
        </div>
        <div class="legend-item">
            <div class="legend-line dashed"></div>
            <span>Inferred relationship</span>
        </div>
    </div>
    
    <h2>Relationships</h2>
    <table>
        <tr>
            <th>Subject</th>
            <th>Predicate</th>
            <th>Object</th>
            <th>Type</th>
        </tr>
"""
        
        for edge in edges[:200]:  # Limit to 200 rows
            row_class = 'inferred' if edge['inferred'] else ''
            type_text = 'Inferred' if edge['inferred'] else 'Original'
            html += f"""        <tr class="{row_class}">
            <td>{edge['source']}</td>
            <td>{edge['label']}</td>
            <td>{edge['target']}</td>
            <td>{type_text}</td>
        </tr>
"""
        
        html += """    </table>
</body>
</html>"""
        
        output_path = Path(output_path)
        output_path.write_text(html, encoding='utf-8')
        
        return output_path
    
    def generate_stats(
        self,
        triples: list[SPOTriple],
    ) -> dict:
        """
        Generate statistics about the graph.
        """
        nodes = set()
        predicates = defaultdict(int)
        inferred_count = 0
        
        for triple in triples:
            nodes.add(triple.subject)
            nodes.add(triple.object)
            predicates[triple.predicate] += 1
            if triple.inferred:
                inferred_count += 1
        
        return {
            "node_count": len(nodes),
            "edge_count": len(triples),
            "inferred_count": inferred_count,
            "original_count": len(triples) - inferred_count,
            "predicate_distribution": dict(predicates),
            "top_predicates": sorted(
                predicates.items(),
                key=lambda x: -x[1]
            )[:10],
        }


# =============================================================================
# Convenience Functions
# =============================================================================

def generate_graph_html(
    triples: list[SPOTriple],
    output_path: str | Path,
    title: str = "Knowledge Graph",
    theme: str = "light",
) -> Path:
    """
    Quick graph HTML generation.
    
    Args:
        triples: SPO triples to visualize
        output_path: Where to save HTML
        title: Graph title
        theme: "light" or "dark"
        
    Returns:
        Path to generated file
    """
    visualizer = GraphVisualizer(theme=theme)
    return visualizer.generate_pyvis(triples, Path(output_path), title)
