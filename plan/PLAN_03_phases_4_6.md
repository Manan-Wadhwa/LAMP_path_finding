# PLAN_03 — Phases 4-6: Cost Surface, WV-2 Spectral Analysis, FETE Network Generation
## El-Bagawat task2

---

## Phase 4 — Cost Surface Construction

**Goal:** A raster (or composite stack) expressing how expensive it is to move through each
cell — the substrate every path-finding method downstream depends on.

```python
import rasterio
import numpy as np
from rasterio.features import rasterize as rio_rasterize
import geopandas as gpd

def slope_to_tobler_cost(slope_rise_run):
    """
    Tobler's hiking function: convert slope (rise/run) to movement cost.
    Returns cost in seconds per map unit.
    slope_rise_run: numpy array of slope values
    """
    speed = 6.0 * np.exp(-3.5 * np.abs(slope_rise_run + 0.05))  # km/h
    return 1.0 / np.maximum(speed, 1e-6)  # cost = 1/speed

def slope_to_llobera_sluckin_cost(slope_rise_run):
    """
    Llobera-Sluckin (2007) biomechanical energy cost.
    Parameters: a=1.5, b=5.9, c=0.17 (from the paper).
    """
    theta = np.arctan(slope_rise_run)  # in radians
    a, b, c = 1.5, 5.9, 0.17
    energy = a * (1 + b * np.sin(theta)**2 + c * theta**2)
    # Normalize to same approximate scale as Tobler for comparison
    return energy / energy.mean() * slope_to_tobler_cost(slope_rise_run).mean()

def compute_slope_from_dem(dem_array, pixel_size_x, pixel_size_y):
    """
    Compute slope (rise/run) from DEM using central differences.
    Returns: slope magnitude as 2D array (unsigned, for isotropic cost)
    For anisotropic cost (direction-dependent), return (dy, dx) separately.
    """
    # Central difference gradient
    dy, dx = np.gradient(dem_array, pixel_size_y, pixel_size_x)
    slope_magnitude = np.sqrt(dy**2 + dx**2)
    return slope_magnitude, dy, dx

def build_building_obstruction_mask(footprints_gdf, dem_shape, dem_transform):
    """
    Rasterize building footprints as a hard no-go mask.
    Returns: binary mask (1 = building, 0 = traversable)
    """
    shapes = [(geom, 1) for geom in footprints_gdf.geometry if geom is not None]
    mask = rio_rasterize(
        shapes,
        out_shape=dem_shape,
        transform=dem_transform,
        fill=0,
        dtype=np.uint8
    )
    return mask

def build_cost_surface(
    dem_path,
    footprints_gdf,
    spi_path=None,
    weights=None,
    cost_function="tobler",
    out_path_tobler=None,
    out_path_llobera=None
):
    """
    Build the composite multi-band cost surface.
    
    weights: dict with keys "terrain", "obs", "spec"
             Default: {"terrain": 0.5, "obs": 1.0, "spec": 0.5}
             w_obs should be large (e.g., 1.0 means infinite effective cost via 1e9 multiplier)
    """
    if weights is None:
        weights = {"terrain": 0.5, "obs": 1.0, "spec": 0.5}
    
    with rasterio.open(dem_path) as dem_src:
        dem = dem_src.read(1).astype(float)
        transform = dem_src.transform
        shape = dem.shape
        profile = dem_src.profile.copy()
        pixel_size_x = abs(transform[0])
        pixel_size_y = abs(transform[4])
    
    # 1. Slope-based terrain cost
    slope, dy, dx = compute_slope_from_dem(dem, pixel_size_x, pixel_size_y)
    C_tobler = slope_to_tobler_cost(slope)
    C_llobera = slope_to_llobera_sluckin_cost(slope)
    
    # 2. Building obstruction mask (infinite cost inside buildings)
    obs_mask = build_building_obstruction_mask(footprints_gdf, shape, transform)
    C_obs = np.where(obs_mask == 1, 1e9, 0.0)  # 1e9 as surrogate for infinity
    
    # 3. Spectral path indicator (inverted: high SPI = low cost)
    C_spec = np.zeros(shape, dtype=float)
    if spi_path is not None:
        with rasterio.open(spi_path) as spi_src:
            spi = spi_src.read(1).astype(float)
            spi = np.clip(spi, 0, 1)
        C_spec = 1.0 - spi  # invert: high SPI = path candidate = low cost
        # Mask SPI inside buildings (building interiors also show temporal stability)
        C_spec[obs_mask == 1] = 0.0
    
    # 4. Composite cost (Tobler version)
    w_t, w_o, w_s = weights["terrain"], weights["obs"], weights["spec"]
    C_composite_tobler = w_t * C_tobler + w_o * C_obs + w_s * C_spec
    C_composite_llobera = w_t * C_llobera + w_o * C_obs + w_s * C_spec
    
    # Save outputs
    profile.update(dtype="float32", count=1)
    
    if out_path_tobler:
        with rasterio.open(out_path_tobler, "w", **profile) as dst:
            dst.write(C_composite_tobler.astype(np.float32), 1)
    
    if out_path_llobera:
        with rasterio.open(out_path_llobera, "w", **profile) as dst:
            dst.write(C_composite_llobera.astype(np.float32), 1)
    
    return C_composite_tobler, C_composite_llobera

# Example usage:
# C_tobler, C_llobera = build_cost_surface(
#     dem_path="data/interim/dem_working_crs.tif",
#     footprints_gdf=footprints,
#     spi_path="data/interim/spi.tif",
#     weights={"terrain": 0.5, "obs": 1.0, "spec": 0.3},
#     out_path_tobler="data/interim/cost_surface_tobler.tif",
#     out_path_llobera="data/interim/cost_surface_llobera.tif"
# )
```

### 4a — Sensitivity Analysis on Cost Weights

Run cost surface generation over a grid of weight combinations and compare resulting networks:

```python
import itertools

def weight_sensitivity_analysis(dem_path, footprints_gdf, entrances_gdf, spi_path):
    """
    Grid search over weight combinations; compute FETE density for each;
    record top-5 segments by density for comparison.
    """
    terrain_weights = [0.3, 0.5, 0.7, 1.0]
    spec_weights = [0.0, 0.2, 0.4, 0.6]
    
    results = []
    for w_t, w_s in itertools.product(terrain_weights, spec_weights):
        weights = {"terrain": w_t, "obs": 1.0, "spec": w_s}
        C, _ = build_cost_surface(dem_path, footprints_gdf, spi_path, weights)
        
        # Quick FETE on a 20-point random sample for speed
        import random
        entrance_pixels = get_entrance_pixels(entrances_gdf, C.shape, transform)
        sample = random.sample(entrance_pixels, min(20, len(entrance_pixels)))
        density = run_fete(C, sample, n_traceback_pairs=50)
        
        results.append({
            "w_terrain": w_t, "w_spec": w_s,
            "mean_density": density.mean(),
            "max_density": density.max(),
            "density_cv": density.std() / (density.mean() + 1e-9),
        })
    
    results_df = pd.DataFrame(results)
    print(results_df.sort_values("density_cv", ascending=False))
    return results_df
```

---

## Phase 5 — WorldView-2 Spectral Analysis

**Goal:** Compute the Spectral Path Indicator (SPI) from multi-temporal WV-2 imagery as direct
physical evidence of compacted ancient path surfaces.

### 5a — DN to Radiance Conversion

```python
def parse_imd_file(imd_path):
    """
    Parse WorldView-2 .IMD metadata file to extract calibration coefficients.
    Returns: dict mapping band_index -> (absCalFactor, effectiveBandwidth)
    """
    import re
    coeffs = {}
    current_band = None
    
    with open(imd_path, "r") as f:
        for line in f:
            line = line.strip()
            band_match = re.match(r'BEGIN_GROUP\s*=\s*BAND_(\w+)', line)
            if band_match:
                current_band = band_match.group(1)
            if current_band and "absCalFactor" in line:
                val = float(line.split("=")[1].strip().rstrip(";"))
                if current_band not in coeffs:
                    coeffs[current_band] = {}
                coeffs[current_band]["absCalFactor"] = val
            if current_band and "effectiveBandwidth" in line:
                val = float(line.split("=")[1].strip().rstrip(";"))
                if current_band not in coeffs:
                    coeffs[current_band] = {}
                coeffs[current_band]["effectiveBandwidth"] = val
    
    return coeffs

def dn_to_radiance(band_dn, abs_cal_factor, effective_bandwidth):
    """Convert WorldView-2 DN to top-of-atmosphere radiance (W/m^2/sr/um)."""
    return abs_cal_factor * band_dn.astype(float) / effective_bandwidth
```

### 5b — Atmospheric Correction (DOS1)

```python
def dos1_correction(band_dn, nodata=0):
    """
    Dark Object Subtraction (DOS1) atmospheric correction.
    Assumes the darkest 0.1% of valid pixels represents atmospheric haze.
    """
    valid = band_dn[band_dn != nodata]
    if len(valid) == 0:
        return band_dn.astype(float)
    dark_val = np.percentile(valid, 0.1)
    return np.maximum(band_dn.astype(float) - dark_val, 0)
```

### 5c — Multi-Temporal SPI Computation

```python
def compute_spi(p001_bands, p002_bands, p003_bands, exclude_coastal=True):
    """
    Compute Spectral Path Indicator from three acquisition passes.
    
    p00N_bands: dict {band_idx: np.array} for pass N, atmospherically corrected.
                Band indices: 1=Coastal, 2=Blue, 3=Green, 4=Yellow, 5=Red,
                              6=RedEdge, 7=NIR1, 8=NIR2
    exclude_coastal: skip Band 1 (low SNR, unreliable)
    
    Returns: SPI raster (float32, values 0-1), same shape as input bands
    """
    band_ids = [2, 3, 4, 5, 6, 7, 8] if exclude_coastal else [1, 2, 3, 4, 5, 6, 7, 8]
    cv_stack = []
    
    for b in band_ids:
        if b not in p001_bands or b not in p002_bands or b not in p003_bands:
            continue
        
        stack = np.stack([p001_bands[b], p002_bands[b], p003_bands[b]], axis=0)
        mu = stack.mean(axis=0)
        sigma = stack.std(axis=0)
        cv = sigma / (mu + 1e-6)  # coefficient of variation
        cv_stack.append(cv)
    
    if not cv_stack:
        raise ValueError("No valid bands found for SPI computation")
    
    mean_cv = np.mean(cv_stack, axis=0)
    spi = 1.0 - np.clip(mean_cv, 0, 1)  # High SPI = low temporal variation = candidate path
    
    return spi.astype(np.float32)

def compute_spectral_indices(bands_dict):
    """
    Compute spectral indices relevant to path detection.
    bands_dict: {1: array, 2: array, ..., 8: array}
    """
    b2 = bands_dict[2].astype(float)  # Blue
    b3 = bands_dict[3].astype(float)  # Green
    b4 = bands_dict[4].astype(float)  # Yellow
    b5 = bands_dict[5].astype(float)  # Red
    b6 = bands_dict[6].astype(float)  # Red Edge
    b7 = bands_dict[7].astype(float)  # NIR1
    b8 = bands_dict[8].astype(float)  # NIR2
    
    # Iron Oxide Ratio: elevated in disturbed/compacted desert soils
    ior = np.where(b3 > 0, b5 / (b3 + 1e-6), 0)
    
    # SAVI: paths have lower vegetation signal even than surrounding desert
    L = 0.5
    savi = ((b7 - b5) / (b7 + b5 + L + 1e-6)) * (1 + L)
    
    # NDRE: red-edge vegetation stress index
    ndre = (b7 - b6) / (b7 + b6 + 1e-6)
    
    # Surface brightness (albedo proxy)
    alb = (b2 + b3 + b4 + b5) / 4.0
    
    return {"ior": ior, "savi": savi, "ndre": ndre, "alb": alb}
```

### 5d — Pan-Sharpening (Gram-Schmidt Adaptive)

```python
from sklearn.linear_model import LinearRegression

def gram_schmidt_pansharpening(mul_bands, pan_band):
    """
    Gram-Schmidt Adaptive pan-sharpening.
    Preserves spectral fidelity better than Brovey; faster than wavelet methods.
    
    mul_bands: dict {band_idx: 2D array at MUL resolution (1.84 m)}
    pan_band: 2D array at PAN resolution (0.46 m) — must be upsampled to same grid first
    
    Returns: dict of pan-sharpened bands at PAN resolution
    """
    from skimage.transform import resize
    
    # Upsample all MUL bands to PAN resolution
    pan_shape = pan_band.shape
    mul_up = {}
    for idx, band in mul_bands.items():
        mul_up[idx] = resize(band, pan_shape, order=3,  # bicubic
                              anti_aliasing=True, preserve_range=True)
    
    # Simulate PAN band from MUL bands using linear regression
    X = np.column_stack([mul_up[b].ravel() for b in sorted(mul_up.keys())])
    y = pan_band.ravel()
    reg = LinearRegression().fit(X, y)
    pan_simulated = reg.predict(X).reshape(pan_shape)
    
    # Inject PAN detail into each MUL band
    pan_residual = pan_band - pan_simulated
    sharpened = {}
    for idx, band in mul_up.items():
        # Project residual onto this band's regression coefficient
        band_coeff = reg.coef_[list(sorted(mul_up.keys())).index(idx)]
        sharpened[idx] = band + band_coeff * pan_residual
    
    return sharpened
```

### 5e — Frangi Vesselness for Linear Feature Detection

```python
from skimage.filters import frangi

def detect_linear_path_features(pan_img_normalized, sigmas=(1, 2, 4, 8)):
    """
    Apply Frangi vesselness filter to detect thin linear features (paths).
    
    pan_img_normalized: 2D float array (pan-sharpened image, normalized 0-1)
    sigmas: scale range in pixels. At 0.46 m/pixel, sigma=4 detects ~1.8 m wide features.
    
    Returns: vesselness response as float32 raster (0-1)
    """
    # Detect bright linear features (paths may be slightly brighter than surroundings
    # due to compaction removing dark shadow-casting micro-roughness)
    v_bright = frangi(pan_img_normalized, sigmas=sigmas,
                      black_ridges=False, mode="reflect")
    
    # Detect dark linear features (paths may be slightly darker due to compaction
    # removing bright top-layer dust)
    v_dark = frangi(1.0 - pan_img_normalized, sigmas=sigmas,
                    black_ridges=False, mode="reflect")
    
    # Take element-wise maximum (detect either polarity)
    vesselness = np.maximum(v_bright, v_dark)
    
    # Mask building footprints (walls are linear features we must NOT detect as paths)
    # Apply the building mask after running Frangi, not before — masking first destroys
    # the edge context that Hessian analysis needs.
    
    return vesselness.astype(np.float32)

def combine_spectral_evidence(spi, ior, vesselness, building_mask, weights=None):
    """
    Combine all spectral evidence streams into a single path-probability raster.
    All inputs must be co-registered and same shape. All normalized to [0,1].
    """
    if weights is None:
        weights = {"spi": 0.50, "ior": 0.20, "vesselness": 0.30}
    
    # Mask building interiors in all spectral layers
    bm = (building_mask == 0).astype(float)
    
    spi_m = spi * bm
    ior_norm = np.clip((ior - np.nanpercentile(ior, 5)) /
                       (np.nanpercentile(ior, 95) - np.nanpercentile(ior, 5) + 1e-6), 0, 1) * bm
    ves_m = np.clip(vesselness / (np.nanpercentile(vesselness, 99) + 1e-9), 0, 1) * bm
    
    combined = (weights["spi"] * spi_m +
                weights["ior"] * ior_norm +
                weights["vesselness"] * ves_m)
    
    return combined.clip(0, 1).astype(np.float32)
```

---

## Phase 6 — FETE Network Generation

**Goal:** Generate the movement potential raster and vectorize it into a draft path network.

### 6a — Project Entrance Points to Raster Pixels

```python
def entrances_to_pixels(entrances_gdf, raster_transform, raster_shape):
    """
    Convert entrance point coordinates (working CRS) to raster pixel indices.
    
    Returns: list of (row, col) tuples, filtered to be within raster bounds
    """
    from rasterio.transform import rowcol
    
    rows, cols = rasterio.transform.rowcol(
        raster_transform,
        [pt.x for pt in entrances_gdf.geometry],
        [pt.y for pt in entrances_gdf.geometry]
    )
    
    valid_pixels = []
    valid_chapel_ids = []
    height, width = raster_shape
    
    for i, (r, c) in enumerate(zip(rows, cols)):
        if 0 <= r < height and 0 <= c < width:
            valid_pixels.append((r, c))
            valid_chapel_ids.append(entrances_gdf.iloc[i]["chapel_id"])
        else:
            print(f"Warning: entrance {entrances_gdf.iloc[i]['chapel_id']} "
                  f"out of raster bounds at ({r}, {c})")
    
    print(f"Projected {len(valid_pixels)}/{len(entrances_gdf)} entrances to raster pixels")
    return valid_pixels, valid_chapel_ids
```

### 6b — FETE Engine (Multi-Source Dijkstra)

```python
from skimage.graph import MCP_Geometric
import numpy as np

def run_fete(cost_raster, entrance_pixels, n_traceback_pairs="all", verbose=True):
    """
    From-Everywhere-To-Everywhere: compute movement potential raster.
    
    cost_raster: 2D float array — MUST have same shape as raster containing entrance_pixels
    entrance_pixels: list of (row, col) tuples — entrance locations in raster space
    n_traceback_pairs: "all" to compute all n*(n-1)/2 pairs, or int for random subsample
    
    Algorithm:
      For each source entrance, run one Dijkstra from that source (O(V log V)).
      From the resulting accumulated cost surface, traceback paths to all other entrances.
      Increment density[r, c] for each cell along each traceback path.
    
    Complexity: O(n * V log V) total — feasible for n=342, V~1M cells.
    """
    n = len(entrance_pixels)
    density = np.zeros(cost_raster.shape, dtype=np.float32)
    
    # Build the set of (src_idx, tgt_idx) pairs to compute
    if n_traceback_pairs == "all":
        pairs_per_src = {i: list(range(i + 1, n)) for i in range(n)}
    else:
        import random
        all_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
        sampled = set(map(tuple, random.sample(all_pairs,
                                               min(n_traceback_pairs, len(all_pairs)))))
        pairs_per_src = {}
        for i, j in sampled:
            pairs_per_src.setdefault(i, []).append(j)
    
    total_paths = sum(len(v) for v in pairs_per_src.values())
    paths_computed = 0
    
    for src_idx, src_pixel in enumerate(entrance_pixels):
        if src_idx not in pairs_per_src:
            continue
        
        targets = pairs_per_src[src_idx]
        
        # One Dijkstra from this source
        mcp = MCP_Geometric(cost_raster, fully_connected=True)
        mcp.find_costs([src_pixel])
        
        # Traceback to each target
        for tgt_idx in targets:
            tgt_pixel = entrance_pixels[tgt_idx]
            try:
                path = mcp.traceback(tgt_pixel)
                for (r, c) in path:
                    density[r, c] += 1
                paths_computed += 1
            except Exception:
                pass  # No path found (disconnected region)
        
        if verbose and src_idx % 20 == 0:
            print(f"FETE: source {src_idx + 1}/{n} "
                  f"({paths_computed}/{total_paths} paths computed)")
    
    # Normalize to [0, 1]
    if density.max() > 0:
        density = density / density.max()
    
    return density
```

### 6c — Skeletonize and Vectorize to Network

```python
from skimage.morphology import skeletonize
import networkx as nx
from shapely.geometry import LineString, Point
import geopandas as gpd

def density_to_network(density, raster_transform, threshold=0.15,
                        min_segment_length_px=3):
    """
    Threshold the movement potential raster, skeletonize it, and convert
    the skeleton to a networkx graph.
    
    threshold: fraction of max density above which to include a cell as a path.
               Start at 0.15 and adjust based on visual inspection.
    min_segment_length_px: prune dead-end spurs shorter than this (in pixels).
    """
    # Threshold
    binary = (density > threshold).astype(np.uint8)
    
    # Skeletonize to 1-pixel-wide centerlines
    skel = skeletonize(binary.astype(bool))
    
    # Build graph from skeleton
    G = nx.Graph()
    rows, cols = np.where(skel)
    coord_set = set(zip(rows.tolist(), cols.tolist()))
    
    for (r, c) in coord_set:
        neighbors = [
            (r + dr, c + dc)
            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
            if (dr, dc) != (0, 0) and (r + dr, c + dc) in coord_set
        ]
        for nb in neighbors:
            dist = np.sqrt((nb[0] - r)**2 + (nb[1] - c)**2)
            G.add_edge((r, c), nb,
                       weight=dist,
                       density=float(density[r, c]))
    
    # Prune short spurs (degree-1 chains shorter than min_segment_length_px)
    changed = True
    while changed:
        changed = False
        for node in list(G.nodes()):
            if G.degree(node) == 1:
                chain_len = 0
                curr = node
                prev = None
                while G.degree(curr) == 1:
                    nbrs = [n for n in G.neighbors(curr) if n != prev]
                    if not nbrs:
                        break
                    chain_len += G[curr][nbrs[0]]["weight"]
                    prev, curr = curr, nbrs[0]
                    if chain_len > min_segment_length_px:
                        break
                if chain_len <= min_segment_length_px:
                    G.remove_node(node)
                    changed = True
    
    return G, skel

def graph_to_geodataframe(G, raster_transform, crs):
    """
    Convert the skeleton networkx graph to a GeoDataFrame of LineString segments.
    Each edge becomes a segment; node coordinates are transformed from pixel space
    to working CRS.
    """
    from rasterio.transform import xy
    
    segments = []
    for u, v, data in G.edges(data=True):
        # Transform pixel coordinates to CRS
        u_x, u_y = xy(raster_transform, u[0], u[1])
        v_x, v_y = xy(raster_transform, v[0], v[1])
        
        segments.append({
            "geometry": LineString([(u_x, u_y), (v_x, v_y)]),
            "density_u": float(data.get("density", 0)),
            "length_m": LineString([(u_x, u_y), (v_x, v_y)]).length,
        })
    
    gdf = gpd.GeoDataFrame(segments, crs=crs)
    return gdf
```

### 6d — Run FETE for Both Cost Functions and Compare

```python
def run_dual_fete(cost_tobler, cost_llobera, entrance_pixels, raster_transform,
                  crs, out_dir="data/processed"):
    """
    Run FETE for both Tobler and Llobera-Sluckin cost functions.
    Compare the resulting networks; document agreement/disagreement.
    """
    import os
    os.makedirs(out_dir, exist_ok=True)
    
    print("Running FETE (Tobler cost)...")
    density_tobler = run_fete(cost_tobler, entrance_pixels)
    
    print("Running FETE (Llobera-Sluckin cost)...")
    density_llobera = run_fete(cost_llobera, entrance_pixels)
    
    # Pearson correlation between the two density maps
    from scipy.stats import pearsonr
    r, p = pearsonr(density_tobler.ravel(), density_llobera.ravel())
    print(f"Tobler vs Llobera correlation: r={r:.3f}, p={p:.2e}")
    
    # Combined density: average of the two
    density_combined = (density_tobler + density_llobera) / 2
    
    # Vectorize combined
    G, skel = density_to_network(density_combined, raster_transform)
    network_gdf = graph_to_geodataframe(G, raster_transform, crs)
    
    return density_tobler, density_llobera, density_combined, network_gdf

def add_confidence_fields(network_gdf, fete_density, circuit_current,
                           spi_raster, syntax_raster, raster_transform):
    """
    Sample all evidence rasters along each network segment and add confidence fields.
    """
    from rasterio.transform import rowcol
    
    def sample_raster_along_segment(geom, raster, transform, n_samples=10):
        """Sample raster values at n_samples points along a LineString."""
        coords = [geom.interpolate(t, normalized=True)
                  for t in np.linspace(0, 1, n_samples)]
        xs = [pt.x for pt in coords]
        ys = [pt.y for pt in coords]
        rows, cols = rowcol(transform, xs, ys)
        h, w = raster.shape
        values = []
        for r, c in zip(rows, cols):
            if 0 <= r < h and 0 <= c < w:
                values.append(float(raster[r, c]))
        return np.mean(values) if values else 0.0
    
    fete_scores, circuit_scores, spi_scores, syntax_scores = [], [], [], []
    
    for _, row in network_gdf.iterrows():
        geom = row.geometry
        fete_scores.append(sample_raster_along_segment(geom, fete_density, raster_transform))
        circuit_scores.append(sample_raster_along_segment(geom, circuit_current, raster_transform))
        spi_scores.append(sample_raster_along_segment(geom, spi_raster, raster_transform))
        syntax_scores.append(sample_raster_along_segment(geom, syntax_raster, raster_transform))
    
    network_gdf["confidence_fete"] = fete_scores
    network_gdf["confidence_circuit"] = circuit_scores
    network_gdf["confidence_spi"] = spi_scores
    network_gdf["confidence_syntax"] = syntax_scores
    
    # Method agreement (count of streams with score > 0.5)
    network_gdf["method_agreement"] = (
        (network_gdf["confidence_fete"] > 0.5).astype(int) +
        (network_gdf["confidence_circuit"] > 0.5).astype(int) +
        (network_gdf["confidence_spi"] > 0.5).astype(int) +
        (network_gdf["confidence_syntax"] > 0.5).astype(int)
    )
    
    # Ensemble confidence
    network_gdf["confidence_ensemble"] = (
        0.30 * network_gdf["confidence_fete"] +
        0.25 * network_gdf["confidence_circuit"] +
        0.25 * network_gdf["confidence_spi"] +
        0.10 * network_gdf["confidence_syntax"]
    )
    
    # Flag segments needing manual review
    network_gdf["flag_review"] = network_gdf["method_agreement"] <= 2
    
    return network_gdf
```
