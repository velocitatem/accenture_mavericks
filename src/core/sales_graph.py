"""Visualize sale breakdown as directed graph showing seller->buyer relationships"""
import json
from typing import List, Dict
from pathlib import Path

try:
    import networkx as nx
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
except ImportError:
    raise ImportError("Install: pip install networkx matplotlib")

COLORS = {'seller': '#E57373', 'buyer': '#81C784', 'edge': '#78909C', 'bg': '#FAFAFA'}

def build_sales_graph(breakdowns: List[Dict], property_filter: str = None) -> nx.DiGraph:
    G = nx.DiGraph()
    for tx in breakdowns:
        if property_filter and tx.get('property_id') != property_filter:
            continue
        seller, buyer = tx.get('seller_nif', '?'), tx.get('buyer_nif', '?')
        pct = str(tx.get('percentage_sold', '?')).replace('%', '').replace(',', '.')
        amt = tx.get('amount')
        prop_id = tx.get('property_id', 'unknown')[:12]

        edge_data = {'pct': pct, 'amt': amt, 'prop': prop_id}
        if G.has_edge(seller, buyer):
            G[seller][buyer]['transactions'].append(edge_data)
        else:
            G.add_edge(seller, buyer, transactions=[edge_data])
        G.nodes[seller]['type'] = 'seller'
        G.nodes[buyer]['type'] = 'buyer'
    return G

def plot_sales_graph(G: nx.DiGraph, title: str = "Sales Transactions", output_path: str = None):
    if not G.nodes():
        print("Empty graph")
        return

    sellers = sorted([n for n, d in G.nodes(data=True) if d.get('type') == 'seller'])
    buyers = sorted([n for n, d in G.nodes(data=True) if d.get('type') == 'buyer'])

    fig, ax = plt.subplots(figsize=(14, max(7, len(G.nodes()) * 1.2)))
    ax.set_facecolor(COLORS['bg'])
    fig.patch.set_facecolor(COLORS['bg'])

    pos = {s: (0, -i * 2) for i, s in enumerate(sellers)}
    pos.update({b: (4, -i * 2 - (len(sellers) - len(buyers)) * 0.5) for i, b in enumerate(buyers)})

    # Draw edges with unique curves per edge to prevent overlap
    edges = list(G.edges(data=True))
    edge_counts = {}  # track edges between same nodes
    for i, (u, v, data) in enumerate(edges):
        key = (min(u, v), max(u, v))
        edge_counts[key] = edge_counts.get(key, 0) + 1

    edge_index = {}
    for i, (u, v, data) in enumerate(edges):
        key = (min(u, v), max(u, v))
        edge_index[(u, v)] = edge_index.get(key, -1) + 1
        idx = edge_index[(u, v)]

        # Spread curves: alternate positive/negative, increase magnitude
        rad = 0.2 * (idx + 1) * (1 if idx % 2 == 0 else -1)

        ax.annotate("", xy=pos[v], xytext=pos[u],
            arrowprops=dict(arrowstyle="-|>", color=COLORS['edge'], lw=2,
                connectionstyle=f"arc3,rad={rad}", shrinkA=30, shrinkB=30))

        # Position label along the curve - offset more aggressively based on curve direction
        mid_x = (pos[u][0] + pos[v][0]) / 2 + rad * 2.5
        mid_y = (pos[u][1] + pos[v][1]) / 2 + rad * 1.2 + i * 0.3
        txs = data['transactions']
        label = "\n".join([f"{tx['prop'][:8]}: {tx['pct']}%" + (f" ({tx['amt']})" if tx['amt'] else "") for tx in txs])
        ax.text(mid_x, mid_y, label, fontsize=8, ha='center', va='center', zorder=20,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#bbb', alpha=1.0, lw=1))

    # Draw nodes
    for n, (x, y) in pos.items():
        color = COLORS['seller'] if G.nodes[n].get('type') == 'seller' else COLORS['buyer']
        circle = plt.Circle((x, y), 0.35, color=color, ec='white', lw=3, zorder=10)
        ax.add_patch(circle)
        ax.text(x, y, n, fontsize=9, ha='center', va='center', fontweight='bold', zorder=11)

    # Legend
    ax.legend(handles=[
        mpatches.Patch(color=COLORS['seller'], label='Vendedores'),
        mpatches.Patch(color=COLORS['buyer'], label='Compradores')
    ], loc='upper right', framealpha=0.9)

    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_xlim(-1, 5)
    ax.set_ylim(min(p[1] for p in pos.values()) - 1, max(p[1] for p in pos.values()) + 1)
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
        print(f"Saved: {output_path}")
    else:
        plt.show()
    plt.close()

def visualize_from_files(escritura_path: str, modelo600_path: str, output_dir: str = None):
    """Load JSONs and create comparison graphs"""
    with open(escritura_path) as f:
        escritura = json.load(f)
    with open(modelo600_path) as f:
        modelo600 = json.load(f)

    out = Path(output_dir) if output_dir else Path(".")
    out.mkdir(exist_ok=True)

    G_esc = build_sales_graph(escritura.get('sale_breakdown', []))
    G_mod = build_sales_graph(modelo600.get('sale_breakdown', []))

    plot_sales_graph(G_esc, "Escritura Sales", str(out / "escritura_sales.png"))
    plot_sales_graph(G_mod, "Modelo600 Sales", str(out / "modelo600_sales.png"))

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        visualize_from_files(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        base = Path(__file__).parent.parent.parent
        visualize_from_files(base / "escritura_extracted.json", base / "modelo600_extracted.json")
