# PLAN_05 — Validation Framework, Failure Modes, Deliverables & Execution Checklist
## El-Bagawat task2

---

## 1. Validation Framework

There is no ground-truth excavated path network. Validation must come from triangulation
across orthogonal evidence types. Build confidence from triangulation, not from a single check.

### 1.1 Internal Consistency Tests

**Entrance coverage:**
Every chapel entrance in entrances.geojson must be within <= 3 pixels (3 * pixel_size_m) of
a segment in path_network.geojson. Report the fraction of entrances within this tolerance.
Target: 100%. Anything below 95% requires investigation.

**No-go violations:**
Zero network segments should pass through any cell where building_mask = 1.
This is a hard binary check, not a score. Any violation = bug in cost surface construction.

**Crosswalk completeness:**
Report the fraction of 342 Excel records with a matched footprint_id.
Target: > 90% matched; remainder documented with explicit reason.

### 1.2 Cross-Method Agreement Analysis

For each pair of method streams (A-E), compute Spearman correlation on overlapping pixels:

```python
from scipy.stats import spearmanr
import numpy as np

def cross_method_correlations(rasters):
    """
    rasters: dict {"fete": array, "circuit": array, "spi": array,
                   "syntax": array, "prox": array}
    All arrays must be co-registered and same shape.
    """
    pairs = [
        ("fete", "circuit"),
        ("fete", "spi"),
        ("fete", "syntax"),
        ("circuit", "spi"),
        ("circuit", "syntax"),
        ("spi", "syntax"),
        ("spi", "prox"),
        ("fete", "prox"),
    ]
    
    results = {}
    for a, b in pairs:
        if a not in rasters or b not in rasters:
            continue
        r, p = spearmanr(rasters[a].ravel(), rasters[b].ravel())
        results[f"{a} vs {b}"] = {"spearman_r": round(r, 3), "p_value": float(p)}
        print(f"{a} vs {b}: r={r:.3f}, p={p:.2e}")
    
    return results
```

IMPORTANT INTERPRETATION NOTE:
- Methods A (FETE) and B (Circuit) are both derived from the same cost surface. Their
  agreement is expected and NOT independently informative. A high correlation between them
  confirms implementation consistency but does not validate the underlying route hypothesis.
- **Agreement between C (SPI, spectral) and any of A/B/D/E IS genuinely informative** because
  SPI is the only stream that does not use terrain modelling as a prior. If SPI aligns with
  the modelled corridors, there is real physical evidence for those routes.

### 1.3 Spectral Correlation Test (AUC)

```python
from sklearn.metrics import roc_auc_score

def spectral_correlation_test(network_skeleton, spi):
    """
    Test whether network segments correlate with spectral path anomalies.
    
    network_skeleton: binary raster (1 = network segment pixel)
    spi: Spectral Path Indicator raster (float, 0-1)
    
    AUC > 0.6: non-trivial agreement between spectral and modelled evidence
    AUC > 0.7: strong agreement — consider upweighting SPI in ensemble
    AUC < 0.55: no meaningful agreement — SPI may not contain path signal at this site
    """
    segment_mask = (network_skeleton > 0).ravel().astype(int)
    spi_scores = spi.ravel()
    
    auc = roc_auc_score(segment_mask, spi_scores)
    print(f"SPI AUC for network segments: {auc:.3f}")
    
    if auc > 0.70:
        print("  -> Strong spectral agreement. Consider upweighting SPI in ensemble.")
    elif auc > 0.60:
        print("  -> Moderate spectral agreement. Current weights appropriate.")
    else:
        print("  -> Weak spectral agreement. SPI may not contain clear path signal.")
    
    return auc
```

### 1.4 Graph Topology Sanity Checks

Real settlement path networks have characteristic topological properties:

```python
import networkx as nx
import numpy as np
from scipy.stats import entropy

def graph_topology_checks(G):
    """
    G: networkx Graph representing the final path network.
    Expected properties of a real necropolis street network:
    - Mostly degree-2 nodes (corridor segments)
    - Some degree-3 (junctions), rare degree-4+ (major intersections)
    - Few degree-1 nodes (dead-end spurs — acceptable for isolated chapel access)
    - Nearly planar (real streets don't cross over each other)
    - Betweenness distribution: power-law-ish with a few high-betweenness trunk routes
    """
    print("=== Graph Topology Report ===")
    
    # Degree distribution
    degrees = [d for _, d in G.degree()]
    deg_counts = {}
    for d in degrees:
        deg_counts[d] = deg_counts.get(d, 0) + 1
    
    print("\nDegree distribution:")
    for d in sorted(deg_counts.keys()):
        pct = 100 * deg_counts[d] / len(degrees)
        print(f"  Degree {d}: {deg_counts[d]} nodes ({pct:.1f}%)")
    
    deg_hist = np.array([deg_counts.get(d, 0) for d in range(1, max(degrees) + 2)])
    deg_entropy = entropy(deg_hist + 1e-10)
    print(f"  Degree entropy: {deg_entropy:.3f} (moderate = street-like)")
    
    # Connectivity
    n_components = nx.number_connected_components(G)
    print(f"\nConnected components: {n_components}")
    if n_components > 1:
        sizes = sorted([len(c) for c in nx.connected_components(G)], reverse=True)
        print(f"  Component sizes: {sizes[:5]}...")
    
    # Planarity
    is_planar, _ = nx.check_planarity(G)
    print(f"\nNetwork is planar: {is_planar}")
    if not is_planar:
        print("  -> Non-planar network: crossings detected. "
              "Real street networks are nearly planar. Consider simplifying.")
    
    # Betweenness centrality
    bc = nx.betweenness_centrality(G, normalized=True)
    bc_vals = sorted(bc.values(), reverse=True)
    print(f"\nBetweenness centrality:")
    print(f"  Max: {bc_vals[0]:.4f}")
    print(f"  Top-5 mean: {np.mean(bc_vals[:5]):.4f}")
    print(f"  Median: {np.median(bc_vals):.4f}")
    
    # High-betweenness nodes are candidates for main street junctions
    top_bc_nodes = sorted(bc.items(), key=lambda x: x[1], reverse=True)[:5]
    print("  Top-5 high-betweenness nodes (probable main junctions):")
    for node, centrality in top_bc_nodes:
        print(f"    Pixel {node}: betweenness = {centrality:.4f}")
    
    return {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "n_components": n_components,
        "is_planar": is_planar,
        "degree_entropy": deg_entropy,
        "max_betweenness": bc_vals[0] if bc_vals else 0,
    }
```

### 1.5 Literature Anchor Point Test

Chapel 180 (central church, principal building), Chapel 25 (Peace Chapel), and Chapel 80
(Exodus Chapel) should be on or very near high-confidence segments.

```python
def anchor_chapel_test(network_gdf, entrances_gdf, anchor_chapels=None):
    """
    Check that named anchor chapels are on or near high-confidence segments.
    
    anchor_chapels: dict {chapel_id: name}. Defaults to the three known anchors.
    """
    if anchor_chapels is None:
        anchor_chapels = {
            "25": "Peace Chapel",
            "80": "Exodus Chapel",
            "180": "Central Church (Chapel 180)"
        }
    
    results = []
    for chapel_id, name in anchor_chapels.items():
        chapel_entrances = entrances_gdf[
            entrances_gdf["chapel_id"].astype(str) == str(chapel_id)]
        
        if chapel_entrances.empty:
            print(f"Chapel {chapel_id} ({name}): NOT FOUND in entrance set")
            continue
        
        entrance_pt = chapel_entrances.iloc[0].geometry
        dists = network_gdf.geometry.distance(entrance_pt)
        nearest_idx = dists.idxmin()
        nearest_dist = dists.min()
        nearest_seg = network_gdf.iloc[nearest_idx]
        
        conf = nearest_seg.get("confidence_ensemble", 0)
        agreement = nearest_seg.get("method_agreement", 0)
        
        print(f"Chapel {chapel_id} ({name}):")
        print(f"  Nearest segment: {nearest_dist:.1f} m away")
        print(f"  Segment confidence: {conf:.2f}, method agreement: {agreement}/4")
        
        results.append({
            "chapel_id": chapel_id,
            "name": name,
            "nearest_segment_dist_m": nearest_dist,
            "segment_confidence": conf,
            "method_agreement": agreement,
        })
    
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv("outputs/anchor_chapel_check.csv", index=False)
    return df
```

---

## 2. Known Failure Modes and Mitigations

| Failure | Cause | Mitigation |
|---|---|---|
| Blue pen marks not isolatable | Ink hue overlaps with print colour, shadows, or paper tone | Tune HSV parameters against 5+ DXF-confirmed marks before running site-wide. Keep a manual fallback path open. |
| OCR label mis-reads | Typeset numerals small; scan noise | Validate every OCR match against spatial join result; flag mismatches for human review |
| CRS mismatch between WV-2 and shapefile | WV-2 delivered as WGS84/UTM; shapefile may be local | Reproject everything to Buildings_Mask.shp CRS; document in docs/decisions.md |
| WV-2 multi-temporal misalignment | Slight registration error between passes | Coregister with phase_cross_correlation to sub-pixel accuracy BEFORE computing SPI |
| DEM too coarse for local-scale alleys | DEM 1.5 m grid; some alleys may be narrower | Use DEM for macro-scale route corridors; use SPI/circuit for fine-scale within-cluster routing |
| FETE produces diffuse density with no clear threshold | Cost surface too flat (desert terrain, few elevation changes) | Upweight building obstruction term and SPI term; or use circuit model (produces sharper current bands) |
| High SPI in areas with no paths | Compacted building interiors also show temporal stability | ALWAYS mask SPI inside building footprints before using as evidence stream |
| Steiner tree too sparse | Approximation ratio leaves isolated subgraphs | Use as lower-bound reference only; do not substitute for FETE density as primary output |
| DWG/DXF file fails to open with ezdxf | R2018+ format incompatibility | Try LibreDWG: dwg2dxf "SITE CAD WORKING.dwg" -o working_converted.dxf |
| Proximity graph connects distant chapels across barriers | Gabriel/beta-skeleton is purely geometric | Run remove_barrier_crossing_edges() to filter edges crossing cells above 95th percentile cost |
| LGMRES solver fails to converge | Poorly conditioned conductance matrix (infinite-cost building cells) | Add a small epsilon to all conductance values; or use spsolve for smaller subgraphs |
| PDF too large to rasterize in memory | bagawat print.pdf is 1.4 GB | Process page-by-page with fitz; rasterize at 200 DPI first to check coverage; use tiling if needed |

---

## 3. Deliverables

### Primary Outputs

| File | Description |
|---|---|
| outputs/path_network.geojson | Final confidence-scored vector network. Per-segment fields: confidence_fete, confidence_circuit, confidence_spi, confidence_syntax, confidence_ensemble, method_agreement, flag_review |
| outputs/movement_potential.tif | FETE movement density raster (normalized 0-1) |
| outputs/spectral_path_indicator.tif | Multi-temporal WV-2 SPI raster (normalized 0-1) |
| outputs/confidence_report.md | Auto-generated summary: per-segment method agreement, entrance coverage, flagged items |
| data/crosswalk/building_id_crosswalk.csv | Versioned footprint <-> chapel ID crosswalk |

### Secondary Outputs

| File | Description |
|---|---|
| outputs/figures/fete_overlay.png | FETE density overlaid on orthoimage |
| outputs/figures/circuit_overlay.png | Circuit current density overlaid on orthoimage |
| outputs/figures/spi_overlay.png | SPI overlaid on orthoimage |
| outputs/figures/ensemble_heatmap.png | Ensemble confidence heatmap overlaid on orthoimage |
| outputs/figures/network_on_plan.png | Final network overlaid on the annotated site plan PDF |
| outputs/flagged_segments.geojson | Segments with method_agreement <= 2 for manual review |
| outputs/anchor_chapel_check.csv | Anchor chapel proximity and confidence scores |
| docs/decisions.md | Running log of parameter choices, dead ends, and revisions |

---

## 4. Execution Checklist

Complete these in order. Do not advance to a later phase without completing all items in the
current phase. Document every significant decision in docs/decisions.md.

### Phase 0 — Data Audit

- [ ] Open SITE CAD WORKING.dwg / converted DXF; print all layer names
- [ ] Search layer names for: ROUTE, PATH, ROAD, STREET, ALLEY, WAY, CIRCULATION
- [ ] If path layer found: extract geometry immediately; document in docs/decisions.md
- [ ] Read all three .shp.points GCP files; compare; select authoritative set
- [ ] Extract DXF entrance entities for buildings 1, 23, 24, 25, 26, 175, 210
- [ ] Print all DXF layer names for each building; document which contain entrance geometry
- [ ] Run CRS audit: confirm Buildings_Mask.shp CRS; check all rasters match
- [ ] Open Excel Bagawat Data From Excavation Report.xlsx; print all column names
- [ ] Confirm entrance direction column name; print value distribution
- [ ] Verify WV-2 P001/P002/P003 tile files open with rasterio; check band counts
- [ ] Check DEM in Generated_DEMs/Current_DEM/ opens and has expected resolution

### Phase 1 — Coordinate Reconciliation

- [ ] Establish WORKING_CRS from Buildings_Mask.shp; document EPSG/proj4 string
- [ ] Rasterize bagawat print.pdf at 400 DPI using fitz
- [ ] Fit PDF homography from QGIS GCPs; compute RMSE
- [ ] RMSE <= 5 map units (approximately 1 building width)? If not, remove outlier GCPs and re-fit
- [ ] Merge WV-2 tiles for P001, P002, P003 separately
- [ ] Reproject merged WV-2 rasters to working CRS
- [ ] Coregister P002 and P003 to P001 using phase_cross_correlation
- [ ] Reproject DEM to working CRS if needed
- [ ] Verify all rasters share same transform, shape, and CRS in working CRS
- [ ] Document final CRS and any reprojection steps in docs/decisions.md

### Phase 2 — ID Crosswalk

- [ ] Extract attribute table from Buildings_Mask.shp; note exact ID field name
- [ ] Extract chapel numbers from Database Full sheet; note exact column name
- [ ] Run OCR on rasterized PDF to extract plan labels; validate > 80% match rate
- [ ] Run exact string match (Pass 1); count matches
- [ ] Run spatial join match (Pass 2); count additional matches
- [ ] Run DXF filename match (Pass 3); count additional matches
- [ ] Generate crosswalk_manual_review.csv for unmatched records
- [ ] Complete manual review to target > 90% footprint match rate
- [ ] Build final building_id_crosswalk.csv with 1-to-many schema
- [ ] Confirm 1-to-many instances are documented with correct multi-chapel IDs

### Phase 3 — Entrance Extraction

- [ ] Verify DXF coordinate system by overlaying DXF geometry against shapefile
- [ ] Extract DXF entrance geometry for all 7 buildings (calibration set)
- [ ] Tune blue-mark HSV parameters using DXF-confirmed buildings 23-26
- [ ] Run PDF mark extraction site-wide on bagawat print.pdf
- [ ] Spot-check 10 random extracted marks visually against the PDF
- [ ] Run attribute-derived entrance computation for all 342 Excel records
- [ ] Run agreement analysis; generate entrance_qa_review.csv
- [ ] Complete manual review for disagreements > 2 m
- [ ] Merge all sources with priority order: dxf > pdf_mark > attribute_derived > centroid
- [ ] Output data/processed/entrances.geojson with all required fields
- [ ] Verify entrances.geojson contains records for at least 330/342 chapels

### Phase 4 — Cost Surface

- [ ] Compute slope from DEM using central differences; visually inspect for artifacts
- [ ] Implement Tobler cost function; spot-check output range
- [ ] Implement Llobera-Sluckin cost function; spot-check output range
- [ ] Rasterize building footprints as hard no-go mask; verify no gap at building edges
- [ ] Build composite cost surface with named, logged weights for both cost functions
- [ ] Save cost_surface_tobler.tif and cost_surface_llobera.tif
- [ ] Run quick 20-point FETE on Tobler cost; visually inspect density output

### Phase 5 — WV-2 Spectral Analysis

- [ ] Parse .IMD files for P001, P002, P003; extract absCalFactor and effectiveBandwidth
- [ ] Convert all WV-2 tiles DN -> radiance for all 8 bands, all 3 passes
- [ ] Apply DOS1 atmospheric correction per band per pass
- [ ] Coregister P002 and P003 to P001 (already done in Phase 1; verify sub-pixel accuracy)
- [ ] Compute CV per band and SPI composite; save to data/interim/spi.tif
- [ ] Visually inspect SPI: does it show linear features? are buildings masked?
- [ ] Compute IOR, SAVI, NDRE, ALB indices from P001; save to data/interim/
- [ ] Pan-sharpen P001 MUL to 0.46 m resolution using Gram-Schmidt method
- [ ] Apply Frangi vesselness to pan-sharpened image (both bright and dark variants)
- [ ] Mask SPI and vesselness outputs inside building footprints
- [ ] Combine SPI + IOR + vesselness into combined spectral evidence raster
- [ ] Run spectral_correlation_test() to check AUC (document result in decisions.md)

### Phase 6 — FETE Network

- [ ] Project all entrance points to raster pixel coordinates
- [ ] Confirm all entrance pixels are within raster bounds; report out-of-bounds
- [ ] Run FETE over Tobler cost surface; save fete_density_tobler.tif
- [ ] Run FETE over Llobera-Sluckin cost surface; save fete_density_llobera.tif
- [ ] Compute correlation between the two density maps; document in decisions.md
- [ ] Create combined density (average of both)
- [ ] Threshold at 0.15, skeletonize, prune spurs
- [ ] Vectorize skeleton to GeoDataFrame; verify segment geometries are in working CRS
- [ ] Verify no segment crosses building mask cells

### Phase 7 — Circuit Model

- [ ] Build conductance matrix from composite cost surface (8-connectivity)
- [ ] Run super-node current flow computation; save circuit_current.tif
- [ ] If LGMRES fails to converge: add epsilon to conductance; try spsolve on subset
- [ ] Compare current density map to FETE density: note agreements and disagreements
- [ ] Document correlation between FETE and circuit in decisions.md

### Phase 8 — Space Syntax

- [ ] Generate free-space mask from building footprints (erode by 1 pixel)
- [ ] Compute medial axis / skeleton of free space
- [ ] Build axial graph from skeleton
- [ ] Compute connectivity and global integration for each axial line
- [ ] Rasterize integration to raster for ensemble computation
- [ ] Visually inspect integration map: high-integration lines should be in open corridors

### Phase 9 — Proximity Graphs

- [ ] Extract entrance point coordinates as (N, 2) array
- [ ] Compute Gabriel graph (beta=1.0)
- [ ] Compute beta-skeleton for beta in {1.0, 1.2, 1.5, 2.0}
- [ ] Run remove_barrier_crossing_edges() for each graph
- [ ] Identify which beta best aligns with FETE high-density corridors; document choice
- [ ] Compute proximity_graph_to_edge_density() for use in ensemble
- [ ] Compute Steiner tree as parsimonious lower-bound reference
- [ ] Save gabriel_graph.geojson and beta_skeleton_{b}.geojson for each b

### Phase 10 — Ensemble

- [ ] Normalize all 5 evidence rasters to [0, 1]
- [ ] Compute weighted ensemble with default weights (0.30, 0.25, 0.25, 0.10, 0.10)
- [ ] Run weight sensitivity analysis; document if results are sensitive to weight choice
- [ ] Run spectral correlation AUC test; adjust SPI weight if AUC > 0.7
- [ ] Generate final path_network.geojson with all confidence fields
- [ ] Run graph_topology_checks() on the final network graph; document results
- [ ] Run anchor_chapel_test() for chapels 25, 80, 180; document results
- [ ] Run entrance_coverage_report(); target >= 95% coverage
- [ ] Confirm 0 no-go violations (segments crossing building mask)
- [ ] Generate confidence_report.md

### Phase 11 — Final Outputs and Visualization

- [ ] Generate overlay figures: FETE, circuit, SPI, ensemble on orthoimage
- [ ] Generate network overlay on bagawat print.pdf (annotated plan)
- [ ] Save all deliverables listed in Section 3 above
- [ ] Save flagged_segments.geojson (method_agreement <= 2)
- [ ] Review docs/decisions.md for completeness; add any undocumented choices
- [ ] Cross-reference network with Building Assignments sheet to prioritize which
      chapel modelling/texturing work should be sequenced near high-confidence routes
