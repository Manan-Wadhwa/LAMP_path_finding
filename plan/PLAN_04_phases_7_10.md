# PLAN_04 — Phases 7-10: Circuit Model, Space Syntax, Proximity Graphs, Ensemble
## El-Bagawat task2

---

## Phase 7 — Electrical Circuit Model

**Goal:** Compute movement density using random-walk / electrical-circuit equivalence (Stream B).
This captures all paths simultaneously — not just the single least-cost path per pair.

### 7a — Build Conductance Matrix

```python
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lgmres

def build_conductance_matrix(cost_raster, connectivity=8):
    """
    Build sparse conductance (Laplacian) matrix from cost raster.
    Each raster cell = a node. Adjacent cells = edges with conductance = 1/cost.
    
    connectivity: 4 (cardinal) or 8 (including diagonals). Use 8 for consistency with FETE.
    
    Returns: (K, G) where K is the NxN conductance matrix (graph Laplacian)
             and G is the conductance array for each cell.
    """
    rows, cols = cost_raster.shape
    N = rows * cols
    
    # Conductance per cell: G = 1/C, clamped to avoid division by zero
    conductance = 1.0 / (cost_raster.ravel() + 1e-9)
    
    offsets_4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    offsets_8 = offsets_4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    offsets = offsets_8 if connectivity == 8 else offsets_4
    
    row_idx, col_idx, values = [], [], []
    diagonal = np.zeros(N, dtype=float)
    
    def flat(r, c):
        return r * cols + c
    
    for r in range(rows):
        for c in range(cols):
            i = flat(r, c)
            for dr, dc in offsets:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    j = flat(nr, nc)
                    # Geometric mean conductance on edge (for diagonal: scale by sqrt(2))
                    dist_scale = 1.0 / np.sqrt(dr**2 + dc**2)  # correct for diagonal length
                    edge_cond = dist_scale * np.sqrt(conductance[i] * conductance[j])
                    row_idx.append(i)
                    col_idx.append(j)
                    values.append(-edge_cond)
                    diagonal[i] += edge_cond
    
    # Add diagonal entries (sum of outgoing conductances)
    row_idx.extend(range(N))
    col_idx.extend(range(N))
    values.extend(diagonal.tolist())
    
    K = sp.csr_matrix((values, (row_idx, col_idx)), shape=(N, N))
    return K, conductance.reshape(rows, cols)
```

### 7b — Super-Node Current Flow (Efficient Multi-Pair)

```python
def compute_supernode_current(cost_raster, entrance_pixels, shape):
    """
    Super-node formulation: connect all entrance nodes to a virtual meta-source
    and solve once to get joint movement potential.
    
    This is O(1) linear system solve vs O(n^2) per-pair solves.
    See McRae et al. (2008), section 3.3.
    
    entrance_pixels: list of (row, col) flat-indexed entrance locations
    """
    rows, cols = shape
    N = rows * cols
    
    K, G = build_conductance_matrix(cost_raster)
    
    # Current injection: inject +1 at each entrance, extract -1/n at all others
    # This is the "all-to-all" super-node current formulation
    b = np.full(N, -1.0 / N)
    entrance_flat = [r * cols + c for (r, c) in entrance_pixels]
    for idx in entrance_flat:
        b[idx] += 1.0  # source injection
    
    # Ground one node to make the system non-singular
    ground_node = 0
    K_mod = K.tolil()
    K_mod[ground_node, :] = 0
    K_mod[ground_node, ground_node] = 1.0
    b[ground_node] = 0.0
    K_csr = K_mod.tocsr()
    
    # Solve Kirchhoff equations: K*V = b
    from scipy.sparse.linalg import lgmres
    from scipy.sparse.linalg import LinearOperator
    
    V, info = lgmres(K_csr, b, maxiter=2000, tol=1e-8)
    if info != 0:
        print(f"Warning: LGMRES did not fully converge (info={info}). "
              f"Results may be approximate.")
    
    # Compute current density at each cell
    current = np.zeros(N, dtype=float)
    offsets = [(-1, 0), (1, 0), (0, -1), (0, 1),
               (-1, -1), (-1, 1), (1, -1), (1, 1)]
    
    r_idx = np.arange(N) // cols
    c_idx = np.arange(N) % cols
    
    for dr, dc in offsets:
        nr = r_idx + dr
        nc = c_idx + dc
        valid = ((nr >= 0) & (nr < rows) & (nc >= 0) & (nc < cols))
        j_idx = np.where(valid)[0]
        nb_flat = (nr[j_idx] * cols + nc[j_idx])
        
        g_edge = np.sqrt(G.ravel()[j_idx] * G.ravel()[nb_flat])
        dist_scale = 1.0 / np.sqrt(dr**2 + dc**2)
        i_edge = np.abs(V[j_idx] - V[nb_flat]) * g_edge * dist_scale
        current[j_idx] += i_edge
    
    current_map = current.reshape(rows, cols)
    
    # Normalize to [0, 1]
    if current_map.max() > 0:
        current_map = current_map / current_map.max()
    
    return current_map.astype(np.float32)
```

### 7c — Pairwise Current Flow (Higher Fidelity, More Expensive)

```python
def compute_pairwise_current(cost_raster, entrance_pixels, max_pairs=500):
    """
    Compute current density by solving Kirchhoff equations for individual
    source-sink pairs. More expensive than super-node but provides per-pair
    current maps useful for diagnosing specific corridor hypotheses.
    
    max_pairs: limit computation to a random sample of pairs for large n.
    """
    import random
    
    rows, cols = cost_raster.shape
    N = rows * cols
    K, G = build_conductance_matrix(cost_raster)
    
    n = len(entrance_pixels)
    all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if len(all_pairs) > max_pairs:
        pairs = random.sample(all_pairs, max_pairs)
        print(f"Random sample of {max_pairs}/{len(all_pairs)} pairs")
    else:
        pairs = all_pairs
    
    current_accumulator = np.zeros(N, dtype=float)
    
    for src_idx, tgt_idx in pairs:
        src_flat = entrance_pixels[src_idx][0] * cols + entrance_pixels[src_idx][1]
        tgt_flat = entrance_pixels[tgt_idx][0] * cols + entrance_pixels[tgt_idx][1]
        
        b = np.zeros(N)
        b[src_flat] = 1.0
        b[tgt_flat] = -1.0
        
        K_mod = K.tolil()
        K_mod[tgt_flat, :] = 0
        K_mod[tgt_flat, tgt_flat] = 1.0
        b[tgt_flat] = 0.0
        
        V, info = lgmres(K_mod.tocsr(), b, maxiter=1000, tol=1e-8)
        if info != 0:
            continue
        
        r_idx = np.arange(N) // cols
        c_idx = np.arange(N) % cols
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = r_idx + dr, c_idx + dc
            valid = (nr >= 0) & (nr < rows) & (nc >= 0) & (nc < cols)
            j_idx = np.where(valid)[0]
            nb_flat = nr[j_idx] * cols + nc[j_idx]
            g_edge = np.sqrt(G.ravel()[j_idx] * G.ravel()[nb_flat])
            i_edge = np.abs(V[j_idx] - V[nb_flat]) * g_edge
            current_accumulator[j_idx] += i_edge
    
    result = current_accumulator.reshape(rows, cols)
    if result.max() > 0:
        result /= result.max()
    return result.astype(np.float32)
```

---

## Phase 8 — Space Syntax

**Goal:** Compute axial line integration as Stream D — capturing the social/perceptual logic
of movement independent of terrain cost.

```python
import numpy as np
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString
from skimage.morphology import skeletonize
import cv2

def generate_free_space_skeleton(footprints_gdf, roi_bounds, resolution=0.5):
    """
    Compute the medial axis of the free space (complement of building footprints).
    
    footprints_gdf: GeoDataFrame with building footprint Polygons
    roi_bounds: (minx, miny, maxx, maxy) in working CRS
    resolution: map units per pixel for the analysis grid (default 0.5 m = 1 pixel/0.5m)
    
    Returns: (skeleton_binary, raster_transform)
    """
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.transform import from_bounds
    
    minx, miny, maxx, maxy = roi_bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    transform = from_bounds(minx, miny, maxx, maxy, width, height)
    
    # Rasterize building footprints
    shapes = [(geom, 1) for geom in footprints_gdf.geometry if geom is not None]
    footprint_raster = rio_rasterize(
        shapes, out_shape=(height, width), transform=transform,
        fill=0, dtype=np.uint8)
    
    # Free space = complement, eroded by ~0.5m to represent wall thickness
    free_space = 1 - footprint_raster
    kernel = np.ones((3, 3), np.uint8)  # 1 pixel = 0.5 m at resolution=0.5
    free_space_eroded = cv2.erode(free_space, kernel, iterations=1)
    
    # Skeletonize to medial axis
    skeleton = skeletonize(free_space_eroded.astype(bool))
    
    return skeleton.astype(np.uint8), transform

def skeleton_to_axial_graph(skeleton, raster_transform, crs):
    """
    Convert skeleton binary image to a networkx graph of axial lines.
    Each skeleton pixel = a node; connected pixels = edges.
    
    Returns: GeoDataFrame of axial line segments with space syntax metrics.
    """
    import rasterio.transform
    
    G = nx.Graph()
    rows_idx, cols_idx = np.where(skeleton)
    coord_set = set(zip(rows_idx.tolist(), cols_idx.tolist()))
    
    for (r, c) in coord_set:
        neighbors = [
            (r + dr, c + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if (dr, dc) != (0, 0) and (r + dr, c + dc) in coord_set
        ]
        for nb in neighbors:
            G.add_edge((r, c), nb)
    
    return G

def compute_space_syntax_integration(G, raster_transform, crs):
    """
    Compute global integration for each axial line (node in G).
    Integration = 1 / RRA, where RRA = normalized relative asymmetry.
    
    High integration = well-connected to all others = candidate primary street.
    """
    import rasterio.transform
    
    n = G.number_of_nodes()
    if n < 3:
        return gpd.GeoDataFrame()
    
    # Compute mean topological depth from each node via BFS
    node_list = list(G.nodes())
    integration_vals = {}
    
    # Diamond baseline D_n (from Hillier & Hanson formula)
    # For large n, D_n ≈ 2*(n+2)/3 * log2((n+2)/3) / (n-1)
    # Use simplified normalization
    D_n = 2.0 / (n - 2) if n > 2 else 1.0
    
    for node in node_list:
        lengths = nx.single_source_shortest_path_length(G, node)
        if len(lengths) < 2:
            integration_vals[node] = 0.0
            continue
        total_depth = sum(lengths.values())
        MD = total_depth / (len(lengths) - 1)  # mean depth excluding self
        RA = 2 * (MD - 1) / (n - 2) if n > 2 else 0
        RRA = RA / D_n if D_n > 0 else 0
        integration_vals[node] = 1.0 / RRA if RRA > 0 else 0.0
    
    # Normalize integration to [0, 1]
    int_vals = np.array(list(integration_vals.values()))
    if int_vals.max() > 0:
        int_vals_norm = int_vals / int_vals.max()
    else:
        int_vals_norm = int_vals
    
    # Build GeoDataFrame of segments
    segments = []
    for (u, v) in G.edges():
        ux, uy = rasterio.transform.xy(raster_transform, u[0], u[1])
        vx, vy = rasterio.transform.xy(raster_transform, v[0], v[1])
        int_u = integration_vals.get(u, 0)
        int_v = integration_vals.get(v, 0)
        segments.append({
            "geometry": LineString([(ux, uy), (vx, vy)]),
            "integration_mean": (int_u + int_v) / 2,
            "integration_u": int_u,
            "integration_v": int_v,
        })
    
    gdf = gpd.GeoDataFrame(segments, crs=crs)
    return gdf

def rasterize_integration(syntax_gdf, raster_shape, raster_transform):
    """
    Convert the vector axial line integration GeoDataFrame to a raster
    for use in the ensemble confidence computation.
    """
    from rasterio.features import rasterize as rio_rasterize
    from shapely.geometry import mapping
    
    # Normalize integration values to [0, 1] first
    vals = syntax_gdf["integration_mean"].values
    if vals.max() > 0:
        vals_norm = vals / vals.max()
    else:
        vals_norm = vals
    
    shapes = [(mapping(geom), float(val))
              for geom, val in zip(syntax_gdf.geometry, vals_norm)]
    
    integration_raster = rio_rasterize(
        shapes,
        out_shape=raster_shape,
        transform=raster_transform,
        fill=0.0,
        dtype=np.float32,
        merge_alg=rasterio.enums.MergeAlg.replace
    )
    
    return integration_raster
```

---

## Phase 9 — Proximity Graphs

**Goal:** Compute geometry-first structural graphs (Stream E) — what connections are
geometrically necessary given only entrance point locations?

```python
import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import LineString
import networkx as nx
import geopandas as gpd

def gabriel_graph(entrance_points_array, crs):
    """
    Compute the Gabriel Graph of entrance points.
    Edge (u,v) exists iff no other point w lies inside the diametric circle on uv:
        d(u,w)^2 + d(v,w)^2 > d(u,v)^2
    
    entrance_points_array: (N, 2) array of entrance coordinates
    Returns: networkx Graph with edges as Gabriel graph edges
    """
    points = entrance_points_array
    n = len(points)
    
    # Start from Delaunay triangulation (GG is a subset of it)
    tri = Delaunay(points)
    candidate_edges = set()
    for simplex in tri.simplices:
        for i in range(3):
            for j in range(i + 1, 3):
                candidate_edges.add((min(simplex[i], simplex[j]),
                                     max(simplex[i], simplex[j])))
    
    G = nx.Graph()
    G.add_nodes_from(range(n))
    
    for (u, v) in candidate_edges:
        mid = (points[u] + points[v]) / 2
        radius_sq = np.sum((points[u] - points[v])**2) / 4
        
        # Check if any other point is inside the diametric circle
        dists_sq = np.sum((points - mid)**2, axis=1)
        inside = dists_sq < radius_sq - 1e-10
        inside[u] = False
        inside[v] = False
        
        if not np.any(inside):
            G.add_edge(u, v,
                       geometry=LineString([points[u], points[v]]),
                       length=float(np.linalg.norm(points[u] - points[v])))
    
    return G

def beta_skeleton(entrance_points_array, beta=1.5):
    """
    Compute the beta-skeleton of entrance points.
    beta=1.0: Gabriel Graph
    beta=2.0: Relative Neighborhood Graph (RNG)
    
    For archaeological settlement networks, beta=1.0-1.5 recommended.
    Run for beta in {1.0, 1.2, 1.5, 2.0} and compare with FETE density.
    """
    points = entrance_points_array
    n = len(points)
    G = nx.Graph()
    G.add_nodes_from(range(n))
    
    for u in range(n):
        for v in range(u + 1, n):
            d_uv = np.linalg.norm(points[u] - points[v])
            r = beta * d_uv / 2
            
            # Two exclusion circles centered at u and v (for beta >= 1)
            center_u = points[u] + (beta / 2) * (points[v] - points[u])
            center_v = points[v] + (beta / 2) * (points[u] - points[v])
            
            blocked = False
            for w in range(n):
                if w == u or w == v:
                    continue
                if (np.linalg.norm(points[w] - center_u) < r - 1e-10 or
                        np.linalg.norm(points[w] - center_v) < r - 1e-10):
                    blocked = True
                    break
            
            if not blocked:
                G.add_edge(u, v, length=float(d_uv))
    
    return G

def remove_barrier_crossing_edges(proximity_graph, cost_raster, raster_transform,
                                   entrance_points_array, barrier_percentile=95):
    """
    Remove edges from a proximity graph that cross high-cost barriers
    (e.g., building walls, steep cliffs).
    
    barrier_percentile: edges crossing cells above this percentile cost are removed.
    """
    barrier_threshold = np.percentile(cost_raster[cost_raster < 1e8], barrier_percentile)
    
    edges_to_remove = []
    for u, v in proximity_graph.edges():
        pt_u = entrance_points_array[u]
        pt_v = entrance_points_array[v]
        
        # Sample cost raster along the straight-line edge
        n_samples = int(np.linalg.norm(pt_u - pt_v) / abs(raster_transform[0])) + 2
        xs = np.linspace(pt_u[0], pt_v[0], n_samples)
        ys = np.linspace(pt_u[1], pt_v[1], n_samples)
        
        import rasterio.transform
        rows, cols = rasterio.transform.rowcol(raster_transform, xs, ys)
        h, w = cost_raster.shape
        
        max_cost_on_edge = 0
        for r, c in zip(rows, cols):
            if 0 <= r < h and 0 <= c < w:
                max_cost_on_edge = max(max_cost_on_edge, cost_raster[r, c])
        
        if max_cost_on_edge > barrier_threshold:
            edges_to_remove.append((u, v))
    
    proximity_graph.remove_edges_from(edges_to_remove)
    print(f"Removed {len(edges_to_remove)} barrier-crossing edges")
    return proximity_graph

def steiner_tree_approximation(proximity_graph, entrance_indices, entrance_points_array):
    """
    Compute Steiner tree approximation spanning all entrance terminals.
    Uses networkx's 2-approximation (Kou et al.).
    
    entrance_indices: list of node indices corresponding to chapel entrances
    Returns: networkx Graph (Steiner tree)
    """
    # Add length as edge weight
    for u, v, data in proximity_graph.edges(data=True):
        if "length" not in data:
            proximity_graph[u][v]["length"] = np.linalg.norm(
                entrance_points_array[u] - entrance_points_array[v])
    
    try:
        steiner = nx.algorithms.approximation.steiner_tree(
            proximity_graph,
            terminal_nodes=entrance_indices,
            weight="length"
        )
        return steiner
    except Exception as e:
        print(f"Steiner tree computation failed: {e}")
        return None

def proximity_graph_to_edge_density(gabriel_graph, beta_graphs, entrance_points_array,
                                     raster_shape, raster_transform):
    """
    Convert proximity graph edges to a raster edge density map (Stream E).
    High density = many proximity graph edges pass through this area.
    """
    from rasterio.features import rasterize as rio_rasterize
    from shapely.geometry import mapping
    
    all_edge_geoms = []
    
    # Gabriel graph edges
    for u, v, data in gabriel_graph.edges(data=True):
        geom = data.get("geometry")
        if geom is None:
            geom = LineString([entrance_points_array[u], entrance_points_array[v]])
        all_edge_geoms.append((mapping(geom), 1))
    
    # Beta-skeleton edges (from multiple beta values)
    for beta_val, bg in beta_graphs.items():
        for u, v in bg.edges():
            geom = LineString([entrance_points_array[u], entrance_points_array[v]])
            all_edge_geoms.append((mapping(geom), 1))
    
    # Rasterize with burn-and-accumulate
    from rasterio.enums import MergeAlg
    density = rio_rasterize(
        all_edge_geoms,
        out_shape=raster_shape,
        transform=raster_transform,
        fill=0,
        dtype=np.float32,
        merge_alg=MergeAlg.add
    )
    
    # Normalize
    if density.max() > 0:
        density = density / density.max()
    
    return density
```

---

## Phase 10 — Ensemble Confidence Scoring

**Goal:** Combine all 5 evidence streams into a single confidence-scored network.

```python
import numpy as np
import geopandas as gpd

def compute_ensemble(fete_norm, circuit_norm, spi, syntax_norm, prox_norm,
                     weights=(0.30, 0.25, 0.25, 0.10, 0.10)):
    """
    Weighted linear combination of 5 evidence rasters (all normalized to [0,1]).
    
    Default weight rationale:
    - FETE (0.30): primary terrain-based path inference method
    - Circuit (0.25): independent terrain-based; distributes through all paths vs FETE's single path
    - SPI (0.25): ONLY direct physical evidence stream — upweighted relative to purely modelled
    - Syntax (0.10): captures perceptual/social logic, orthogonal to terrain cost
    - Proximity (0.10): geometric constraint only; lowest weight
    
    All arrays must be co-registered and same shape.
    """
    w_f, w_c, w_s, w_sy, w_p = weights
    
    ensemble = (w_f * fete_norm +
                w_c * circuit_norm +
                w_s * spi +
                w_sy * syntax_norm +
                w_p * prox_norm)
    
    return ensemble.clip(0, 1).astype(np.float32)

def run_weight_sensitivity(fete_norm, circuit_norm, spi, syntax_norm, prox_norm,
                            network_skeleton, output_dir="docs"):
    """
    Test multiple weight combinations; report how sensitive the high-confidence
    network segments are to weight choices.
    """
    import itertools, os
    
    weight_sets = [
        (0.30, 0.25, 0.25, 0.10, 0.10),  # Default
        (0.40, 0.30, 0.15, 0.10, 0.05),  # Terrain-heavy
        (0.20, 0.20, 0.50, 0.05, 0.05),  # SPI-heavy (physical evidence)
        (0.25, 0.20, 0.25, 0.20, 0.10),  # Balanced
    ]
    
    results = []
    for weights in weight_sets:
        ens = compute_ensemble(fete_norm, circuit_norm, spi, syntax_norm, prox_norm, weights)
        # Sample ensemble along the primary network skeleton
        skel_cells = np.where(network_skeleton)
        if len(skel_cells[0]) > 0:
            mean_conf = float(ens[skel_cells].mean())
        else:
            mean_conf = 0.0
        results.append({"weights": weights, "mean_confidence_on_skeleton": mean_conf})
    
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv(os.path.join(output_dir, "weight_sensitivity.csv"), index=False)
    print(df.to_string())
    return df

def generate_final_network(ensemble_raster, raster_transform, crs, entrances_gdf,
                            fete_density, circuit_current, spi, syntax_norm,
                            ensemble_threshold=0.25):
    """
    Threshold ensemble raster, skeletonize, vectorize, add all confidence fields,
    and produce the final GeoJSON output.
    
    ensemble_threshold: fraction of max ensemble score above which to include a cell.
                        Start at 0.25; adjust based on visual inspection.
    """
    from skimage.morphology import skeletonize
    
    binary = (ensemble_raster > ensemble_threshold).astype(np.uint8)
    skel = skeletonize(binary.astype(bool))
    
    G, _ = density_to_network(ensemble_raster, raster_transform, threshold=ensemble_threshold)
    network_gdf = graph_to_geodataframe(G, raster_transform, crs)
    
    # Add confidence fields from all streams
    network_gdf = add_confidence_fields(
        network_gdf, fete_density, circuit_current, spi, syntax_norm, raster_transform
    )
    
    # Verify: every entrance must be within 3 pixels of a segment
    entrance_coverage_report(network_gdf, entrances_gdf, raster_transform)
    
    # Verify: no segment crosses a building mask cell
    # (This should be guaranteed if cost surface was built correctly,
    #  but verify explicitly before publishing)
    
    return network_gdf, skel

def entrance_coverage_report(network_gdf, entrances_gdf, raster_transform):
    """
    Report what fraction of chapel entrances are within tolerance of a network segment.
    Every entrance should connect to the network.
    """
    pixel_size = abs(raster_transform[0])
    tolerance_m = 3 * pixel_size  # 3 pixels
    
    covered = 0
    uncovered_chapels = []
    
    for _, entrance in entrances_gdf.iterrows():
        dists = network_gdf.geometry.distance(entrance.geometry)
        min_dist = dists.min()
        if min_dist <= tolerance_m:
            covered += 1
        else:
            uncovered_chapels.append({
                "chapel_id": entrance.get("chapel_id", "?"),
                "min_dist_m": min_dist
            })
    
    pct = 100 * covered / len(entrances_gdf)
    print(f"Entrance coverage: {covered}/{len(entrances_gdf)} ({pct:.1f}%) within {tolerance_m:.1f} m")
    
    if uncovered_chapels:
        import pandas as pd
        unc_df = pd.DataFrame(uncovered_chapels).sort_values("min_dist_m", ascending=False)
        print(f"Uncovered chapels ({len(uncovered_chapels)}):")
        print(unc_df.head(10).to_string(index=False))
    
    return covered, uncovered_chapels

def generate_confidence_report(network_gdf, entrances_gdf, raster_correlations,
                                out_path="outputs/confidence_report.md"):
    """
    Auto-generate the human-readable confidence report.
    """
    lines = [
        "# El-Bagawat Path Network — Confidence Report",
        f"\nGenerated: {pd.Timestamp.now().isoformat()}",
        "\n## Summary Statistics\n",
        f"- Total network segments: {len(network_gdf)}",
        f"- High-confidence segments (ensemble > 0.7): "
        f"{(network_gdf.confidence_ensemble > 0.7).sum()}",
        f"- Segments flagged for review (method_agreement <= 2): "
        f"{network_gdf.flag_review.sum()}",
        f"- Chapel entrances covered (within 3 pixels): "
        f"{entrance_coverage_report(network_gdf, entrances_gdf, None)[0]}",
        "\n## Method Agreement Distribution\n",
    ]
    
    for k in range(1, 6):
        n = (network_gdf.method_agreement == k).sum()
        lines.append(f"- {k} methods agree: {n} segments ({100*n/len(network_gdf):.1f}%)")
    
    lines += [
        "\n## Cross-Method Correlations\n",
    ]
    for pair, r_val in raster_correlations.items():
        lines.append(f"- {pair}: Spearman r = {r_val:.3f}")
    
    lines += [
        "\n## Anchor Chapel Proximity\n",
        "Chapel 180 (Central Church), Chapel 25 (Peace), Chapel 80 (Exodus):",
        "See outputs/anchor_chapel_check.csv for per-chapel nearest-segment details.",
        "\n## Segments Flagged for Manual Review\n",
        "See outputs/flagged_segments.geojson for segments with method_agreement <= 2.",
    ]
    
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"Confidence report written to {out_path}")
```
