# El-Bagawat Necropolis — Full-Site Pedestrian Path Reconstruction
## Technical Research Plan & Implementation Reference (`task2`)

**Site:** El-Bagawat Christian Necropolis, Kharga Oasis, Egypt (est. 3rd–7th c. CE)  
**Goal:** Reconstruct the most probable historical street and alley network connecting all 260+ chapel buildings, moving from the 3-node pilot (`task1`) to a full 342-chapel network inference pipeline  
**Key constraint:** Zero excavated path segments exist as ground truth; no analogous annotated site exists from which to transfer learning  
**Acquisition dates of WV-2 imagery:** 2018-03-22, 2018-06-01, 2018-06-14  

---

## Table of Contents

1. [Research Framing](#1-research-framing)
2. [Full Data Inventory](#2-full-data-inventory)
3. [Why MaxEnt IRL Cannot Scale Here](#3-why-maxent-irl-cannot-scale-here)
4. [Mathematical Foundations](#4-mathematical-foundations)
5. [Repository Structure](#5-repository-structure)
6. [Phase-by-Phase Implementation Plan](#6-phase-by-phase-implementation-plan)
7. [Code Reference](#7-code-reference)
8. [Validation Framework](#8-validation-framework)
9. [Known Failure Modes & Mitigations](#9-known-failure-modes--mitigations)
10. [Environment Specification](#10-environment-specification)
11. [Glossary](#11-glossary)
12. [References](#12-references)
13. [Execution Checklist](#13-execution-checklist)

---

## 1. Research Framing

### 1.1 What the task1 pilot actually showed

The `task1.ipynb` pilot applied MaxEnt IRL to three hand-picked building entrances (M0, M1, M2) over a terrain-derived cost surface. The three output panels — SAR composite, DEM hillshade, orthoimage with footprints — all show the same learned route in blue. That result is a **model artifact**, not a discovered path. The pilot demonstrates that the IRL machinery works on the geometry and cost surface, but the route itself is a 3-node spanning tree trivially determined by the terrain between those three specific points. It is not evidence that the method generalizes, and it cannot be used as a training demonstration for the full site without circularity.

### 1.2 The actual research question

> Given terrain, building obstruction, recorded chapel entrance orientations, three acquisition dates of 8-band WorldView-2 satellite imagery, site-wide CAD geometry, and 342 chapel records with typological attributes — what is the most probable historical network of streets and alleyways that connected the El-Bagawat necropolis, and how should confidence be assigned to each hypothesized segment?

This is a recognized problem class in landscape archaeology: **movement network reconstruction from passive evidence**. The correct methodological family is cost-surface accumulation / FETE analysis (White & Barber 2012), complemented by spectral archaeology on the WV-2 imagery and by network-theoretic graph inference. None of these require demonstration trajectories.

### 1.3 What "done" looks like

1. A **confidence-scored vector network** (`outputs/path_network.geojson`) — every segment tagged with a per-method evidence score and an ensemble confidence value.
2. A **movement potential raster** (`outputs/movement_potential.tif`) — the continuous density-of-crossing heatmap that the network was thresholded from.
3. A **spectral anomaly raster** (`outputs/spectral_path_indicator.tif`) — independent physical evidence from multi-temporal WV-2 analysis.
4. A **crosswalk table** (`data/crosswalk/building_id_crosswalk.csv`) — reconciling shapefile IDs, Excel chapel numbers, plan labels, and DXF filenames. Without this, nothing downstream is trustworthy.
5. A **confidence report** (`outputs/confidence_report.md`) — per-segment: which methods agree, which disagree, which segments are flagged for manual verification.

---

## 2. Full Data Inventory

### 2.1 Region of Interest layers (`100_Data/110_GISRegionOfInterest/`)

| File | Notes |
|---|---|
| `Bagawat_ROI.shp` | Full site ROI polygon |
| `BagawatROI_Smaller.shp` | Tighter ROI matching the pilot's red-box extent — use for comparability with task1 |

Both have accompanying `.prj` files defining the working CRS. Read these first in Phase 1; they define the local coordinate frame everything else must align to.

### 2.2 Site report and CAD (`100_Data/120_SiteReport/`)

| File | Format | Critical notes |
|---|---|---|
| `2026 El Bagawat Database Draft 1.xlsx` | Excel, 3 sheets | Primary chapel attribute database: 342 records, entrance directions, typology, condition |
| `bagawat print.pdf` | PDF | The hand-annotated site plan with light-blue entrance ticks. The primary human-labelled data source. |
| `SiteReport_missing9-12.pdf` | PDF | Supplementary report pages; inspect for additional entrance or path annotation |
| `BaseSiteCAD/Building1.dxf` | DXF | Individual building CAD; contains precise geometry layers for building 1 |
| `BaseSiteCAD/Building23–26.dxf` | DXF | Buildings 23, 24, 25, 26 — these include the Peace Chapel (25) cluster |
| `BaseSiteCAD/Building175.dxf` | DXF | Individual CAD for building 175 |
| `BaseSiteCAD/Building210.dxf` | DXF | Individual CAD for chapel 210 — a priority modeling target |
| `BaseSiteCAD/scan557.tif` | GeoTIFF | Scanned survey document — potentially Fakhry's original 1951 plan; inspect for any path markings |
| `BaseSiteCAD/SITE CAD BUILDINGS ONLY.dwg` | DWG | Site-wide CAD with building geometries only |
| `BaseSiteCAD/SITE CAD WORKING.dwg` | DWG | **Highest-value underexplored source.** May contain distinct CAD layers for roads, paths, or survey annotations. Inspect all layer names before coding anything else. |

**DXF strategy:** Parse with `ezdxf`. For each DXF, list all layer names (`doc.layers`). Common archaeological DXF conventions use layers named `DOOR`, `ENTRANCE`, `OPENING`, `ARCH_FEATURE`, or similar. If found, extract those entity geometries directly — they give sub-centimetre precision entrance locations for 7 buildings including the Peace Chapel cluster (23–26) and a high-priority modelling target (210). These 7 precisely known entrances are your **calibration set** for every other entrance-extraction method.

**DWG strategy:** Convert `SITE CAD WORKING.dwg` to DXF using `ezdxf`'s ODA converter wrapper or the open-source `LibreDWG`/`dwg2dxf` tool, then parse as above. If a layer named anything like `ROUTE`, `PATH`, `ROAD`, `STREET`, `ALLEY`, `WAY`, or `CIRCULATION` exists, it may represent the archaeologists' own hypothesis about the path network — treat that as a high-authority annotation, not just another data layer.

### 2.3 Building footprints (`100_Data/130_BuildingFootprintsVectorData/`)

| File | Notes |
|---|---|
| `BuildingTracesCurrent/Buildings_Mask.shp` | **Primary footprint layer.** 260+ polygon features. Use this exclusively; ignore the OLD layer. |
| `BuildingTracesCurrent/Buildings_Mask.shp.points` | QGIS Ground Control Points file — **plain-text GCPs** used when this shapefile was georeferenced. Contains source pixel ↔ target CRS coordinate pairs. These are your control points for registering `bagawat print.pdf`. Read before Phase 1. |
| `BuildingTracesCurrent/Buildings_Mask.shp.points1.points` | Alternate/previous GCP set — compare with `.points` for CRS consistency |
| `BuildingTracesCurrent/Buildings_Mask.shp.points2.points` | Third GCP set — may reflect a different registration attempt |
| `BuildingTraces-OLD/building_masks.shp` | Old version — archive only, do not use in analysis |

The `.points` files are tab-delimited text in QGIS format:
```
mapX,mapY,pixelX,pixelY,enable
```
Read them with `pandas.read_csv` and treat them as the authoritative tie between pixel space and CRS.

### 2.4 WorldView-2 Satellite Imagery (`100_Data/140_SAR_Imagery/DigitalGlobe_2018/MONO/`)

Three distinct acquisition dates provide **multi-temporal coverage** — this is the single most underexploited asset in the dataset.

| Pass | Date | Bands | Tile grid | Files per band |
|---|---|---|---|---|
| P001 | 2018-06-14 | 8-band MUL + PAN | 8 rows × 3 cols = 24 | 24 MUL + 24 PAN |
| P002 | 2018-06-01 | 8-band MUL + PAN | 2 rows × 3 cols = 6 | 6 MUL + 6 PAN |
| P003 | 2018-03-22 | 8-band MUL + PAN | 8 rows × 3 cols = 24 | 24 MUL + 24 PAN |

**Band assignments** (WorldView-2 M2AS product):

| Band | Name | Wavelength (nm) | Path-detection relevance |
|---|---|---|---|
| 1 | Coastal | 400–450 | Aerosol correction reference; low SNR |
| 2 | Blue | 450–510 | Bright compacted surfaces |
| 3 | Green | 510–580 | Baseline vegetation / soil albedo |
| 4 | Yellow | 585–625 | Iron-oxide sensitivity |
| 5 | Red | 630–690 | Chlorophyll / ferric iron |
| 6 | Red Edge | 705–745 | Vegetation stress, surface texture |
| 7 | NIR1 | 770–895 | Strong vegetation separation |
| 8 | NIR2 | 860–1040 | Equivalent to Landsat Band 4; atmospheric window |
| PAN | — | 450–800 | 0.46 m GSD — 4× finer than MUL |

**Radiometric notes:** The `.IMD` metadata file for each pass records:
- `absCalFactor` and `effectiveBandwidth` per band — needed to convert DN → radiance
- `firstLineTime` — exact acquisition UTC
- Sun elevation and azimuth — for shadow-correction and terrain illumination modelling

**The `.RPB` file** is an RPC (Rational Polynomial Coefficient) camera model — enables orthorectification without a full photogrammetric bundle if you don't already trust the delivered orthorectified products.

---

## 3. Why MaxEnt IRL Cannot Scale Here

This section is a hard break from the `task1` approach. Understanding why matters before choosing replacements.

### 3.1 What MaxEnt IRL actually requires

Ziebart et al. (2008) MaxEnt IRL recovers a linear reward function `r(s) = θᵀφ(s)` such that the probability of a trajectory `τ = (s₀, a₀, s₁, ...)` is:

```
P(τ | θ) ∝ exp( Σₜ r(sₜ) ) = exp( θᵀ Σₜ φ(sₜ) )
```

The parameter vector `θ` is found by maximizing the likelihood of a set of **expert demonstrations** D = {τ₁, ..., τₙ}. Concretely, gradient descent on the log-likelihood gives:

```
∇_θ L = Σ_τ∈D φ(τ)/|D|  −  E_τ~P(τ|θ)[φ(τ)]
```

The second term requires computing the **expected state-visitation frequency** under the current policy, which is done via a forward-backward pass on the MDP. This term vanishes — `θ` is completely unidentified — when `|D| = 0`.

### 3.2 Why the task1 output cannot serve as demonstrations

Three problems make circular use of the task1 result inadmissible:

**Problem A — Circular inference.** The task1 route is the output of an IRL run over three points and a terrain cost surface. Using it as a demonstration for a second IRL run means: learning weights that reconstruct the path that was itself generated by assumed weights. The result is that the second IRL converges on weights that perfectly reproduce the first path, regardless of what the true historical paths were. You learn nothing.

**Problem B — Underdetermination at scale.** Three demonstration points generate at most 3 pairwise paths = 3 independent route segments. The feature vector `φ` over a raster with k features has k free parameters. With k >> 3 (terrain, SAR bands, spectral indices, distance-to-buildings — easily 10–20 features), the IRL is underdetermined by more than an order of magnitude even if the demonstrations were valid.

**Problem C — No analogous annotated site.** Cross-site transfer learning would require a necropolis of similar layout, density, and terrain type where the historical paths have been excavated or reliably documented. No such dataset exists in the public literature for a desert Roman-period necropolis of this morphology. Pompeii's street network is excavated but its geometry, density, and terrain context are entirely different. Amarna is a flat city plan, not a hillside necropolis. Transfer is not justified.

### 3.3 The correct replacement strategy

Replace IRL with a **5-stream evidence ensemble**, each stream producing its own independent path-hypothesis raster, then combine:

| Stream | Method family | Needs demonstrations? | Evidence type |
|---|---|---|---|
| A | Terrain-informed FETE | No | Indirect (movement mechanics) |
| B | Electrical circuit model | No | Indirect (random walk theory) |
| C | WorldView-2 multi-temporal spectral analysis | No | **Direct** (physical surface evidence) |
| D | Space syntax / axial analysis | No | Indirect (perceptual/social logic) |
| E | Proximity graphs (Gabriel, β-skeleton) | No | Structural (geometric necessity) |

These are described mathematically in §4 and implemented in Phases 4–9.

---

## 4. Mathematical Foundations

### 4.1 Anisotropic Cost Surface

Movement cost through a raster cell is **direction-dependent** (traversing a slope costs less going downhill than uphill). This requires an anisotropic formulation.

**Tobler's hiking function** (Tobler 1993):

```
W(s) = 6 · exp(-3.5 · |s + 0.05|)    [km/h]
```

where `s = Δz / Δd` is slope (signed: positive = uphill, negative = downhill).

Asymmetric travel cost per metre:

```
C_tobler(s, d) = d / W(s)    [seconds]
```

**Llobera–Sluckin energy cost** (Llobera & Sluckin 2007), derived from biomechanical first principles:

```
E(θ) = a · (1 + b·sin²θ + c·θ²)    [J kg⁻¹ m⁻¹]
```

where `θ = arctan(s)`, `a ≈ 1.5`, `b ≈ 5.9`, `c ≈ 0.17`. Shown to outperform Tobler in reconstructing real Roman roads (Verhagen 2013). Implement both; compare outputs.

**Multi-band composite cost function:**

```
C(i,j) = w₁·C_terrain(i,j) + w₂·C_obs(i,j) + w₃·C_spec(i,j) + w₄·C_sar(i,j)
```

where:
- `C_terrain` = Tobler or Llobera–Sluckin cost derived from DEM slope
- `C_obs` = ∞ inside building footprint mask (hard no-go), 0 elsewhere
- `C_spec` = derived from WV-2 spectral path indicator (§4.4) — low where spectral evidence of paths is high
- `C_sar` = derived from SAR backscatter; low in low-backscatter (smooth) linear zones

Weights `w₁–w₄` are named parameters, not magic numbers. Document them. Sensitivity analysis over a grid of weight combinations validates robustness.

**48-neighbourhood kernel** (Harris 2000): For a move from `(i,j)` to neighbour `(i+di, j+dj)`, the diagonal correction factor is `√(di²+dj²)`, keeping path-length distortion below 1.4% versus the true optimum (compared to ~8% for an 8-connected grid). `skimage.graph.MCP_Geometric` handles this automatically with `fully_connected=True`.

### 4.2 FETE and Movement Potential

Let `E = {e₁, ..., eₙ}` be the set of n entrance points (n ≤ 342).

**Least-cost path:** For source `eₖ`, the accumulated cost surface `ACC_k(i,j)` is computed by multi-source Dijkstra from `eₖ` over `C(i,j)`. The least-cost path from `eₖ` to `eₗ` is the traceback through `ACC_k` from `eₗ`.

**Movement potential** (Llobera 2000):

```
MP(i,j) = Σₖ Σₗ≠ₖ  𝟏[ (i,j) ∈ LCP(eₖ, eₗ) ]
```

Every pair of entrances contributes 1 to each cell it passes through. High-MP cells are "where corridors converge" and are the best candidates for real paths.

**Computational complexity:** For n entrance nodes over a raster of V cells with E edges:
- One multi-source Dijkstra: O(V log V) using a binary heap
- For n entrances: n runs = O(n · V log V)  
- For n=342, V≈10⁶ (1000×1000 grid): ~342 × 10⁶ × 20 ≈ 7 × 10⁹ operations. At ~10⁸ ops/sec for Python, that's ~70 seconds — feasible. With `skimage.graph.MCP_Geometric` (C-backed): under 5 minutes.

**Traceback complexity:** Separate from Dijkstra. For each of n(n-1)/2 pairs, traceback costs O(path_length). Batching all tracebacks from one source together amortizes this.

**Important:** Do not run pairwise search n(n-1)/2 times. Run n Dijkstra passes (one per source), then extract all tracebacks from each accumulated surface. This is the FETE architecture.

### 4.3 Electrical Circuit Model

Random walk theory establishes a formal equivalence between electrical networks and stochastic movement (Doyle & Snell 1984; McRae et al. 2008):

**Resistance network construction:**
- Each raster cell `(i,j)` has conductance `G(i,j) = 1 / C(i,j)`
- Edge between adjacent cells: conductance = harmonic mean of cell conductances

**Kirchhoff equations:** For a source node `s` injecting current `I=1` and sink node `t`, the voltage vector `V` satisfies:

```
K · V = b
```

where K is the (sparse) conductance matrix (graph Laplacian) and `b` is the current injection vector (b[s]=1, b[t]=-1, 0 elsewhere).

**Current flow density:**

```
I(i,j) = G(i,j) · |V(i,j) - V(neighbor)|
```

Accumulated over all source-sink pairs (or using `multi-source` formulation), `I(i,j)` gives a probability-theoretic movement density. Key advantages over FETE:

1. **Flows through all paths simultaneously**, weighted by conductance. FETE picks only the single least-cost path per pair; the circuit model distributes current proportionally through all paths. This naturally represents uncertainty about which specific route was used.
2. **Resistance distance** (the effective resistance between two nodes) is formally the commute time of a random walk (McRae et al. 2008, Theorem 1). This grounds the path probability interpretation in proven Markov chain theory, not just heuristics.
3. **No threshold decisions** are needed at the inference stage — current is continuous.

**Solvers:** `scipy.sparse.linalg.spsolve` (direct, for small grids) or `scipy.sparse.linalg.minres`/`lgmres` with ILU preconditioner (iterative, for large grids). For V=10⁶ cells, the conductance matrix K has ~8×10⁶ non-zero entries; LGMRES converges in seconds.

**Multi-pair aggregation:** Rather than summing over all n(n-1)/2 pairs independently (expensive), use the **super-node** formulation: connect all entrance nodes to a meta-source and all non-entrance nodes to a meta-sink with a small conductance; solve once. This gives the joint movement potential in O(1) linear system solve rather than O(n²) solves. See McRae et al. (2008, §3.3).

### 4.4 Proximity Graphs

Proximity graphs provide a **geometry-first baseline**: given only entrance point locations (no terrain, no imagery), what edges are structurally necessary to connect them?

**Gabriel Graph (GG):** Edge `(u,v)` exists if and only if the diametric circle on `uv` contains no other point:

```
(u,v) ∈ GG   ⟺   ∀w ≠ u,v :  d(u,w)² + d(v,w)² > d(u,v)²
```

The Gabriel graph is a subset of the Delaunay triangulation. It has been used to model spatial network skeletons in archaeology (Nakoinz 2014) and urban morphology (Masucci et al. 2009).

**β-skeleton:** A one-parameter family generalizing GG (β=1) toward RNG (β=2). For `β ∈ (0,2]`:

- For β ≥ 1: Edge `(u,v)` iff no point `w` lies in the intersection of two circles of radius `β·d(u,v)/2` centered at `u` and `v`.
- For β < 1: Broader exclusion zone (denser graph).

For archaeological settlement networks, β ≈ 1.0–1.5 typically gives the right connectivity. Run a sweep over β ∈ {1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 2.0} and overlay with the FETE density map to find which β aligns best with high-density corridors.

**Steiner Tree:** Given terminal nodes T ⊆ V (the entrance set), the Steiner tree is the minimum-cost tree spanning all terminals, allowing Steiner points (intermediate nodes) anywhere in the graph. The Steiner problem is NP-hard in general but well-approximated:
- `networkx` provides `steiner_tree` (Kou et al. approximation, ratio ≤ 2)
- Better: Zelikovsky's algorithm (ratio ≤ 11/6) for terminal-heavy instances

The Steiner tree gives the **minimum necessary network** — a parsimonious lower bound on the required path infrastructure. Real necropolis streets are more than the minimum (they have redundant routes, loops, dead-end spurs), but the Steiner tree identifies which connections are structurally unavoidable.

### 4.5 WorldView-2 Spectral Path Indicators

**Physics of desert compacted paths:** Foot traffic over centuries consolidates loose surface sediment, removing fine-fraction material, reducing micro-roughness, and slightly altering soil mineralogy through iron oxidation and carbonate exposure. In arid environments (low biological activity), this signal is often persistent over centuries.

**Observable signatures in WV-2:**

**(a) Iron Oxide Ratio (IOR):**
```
IOR = Band5 / Band3
```
Disturbed/compacted soils often show elevated IOR due to ferric iron exposure. Ancient paths in arid zones have been detected via IOR in multiple remote sensing studies (Bewley & Donoghue 2011).

**(b) Soil-Adjusted Vegetation Index (SAVI):**
```
SAVI = (Band7 - Band5) / (Band7 + Band5 + L) · (1 + L),   L = 0.5
```
Paths have even lower SAVI than surrounding desert because they lack even micro-level lichen/moss. Low SAVI in linear patterns = candidate path evidence.

**(c) Red Edge / Vegetation Stress (NDRE):**
```
NDRE = (Band7 - Band6) / (Band7 + Band6)
```

**(d) Albedo / Surface Brightness:**
```
ALB = (Band2 + Band3 + Band4 + Band5) / 4
```
Compacted surfaces may have slightly elevated albedo (smoother = higher reflectance at low sun angle). Pan-sharpened imagery (0.46 m GSD) gives maximum sensitivity.

**Multi-temporal stability index (the most powerful indicator):**

Across the three acquisition dates (March 22, June 1, June 14, 2018), most desert surfaces show subtle seasonal variation: shifting sand, micro-vegetation flush from spring rains, moisture-driven albedo changes. Compacted paths are **temporally stable** — they show the same spectral signature regardless of season.

For each pixel `(i,j)` and band `b`:
```
μ_b(i,j) = mean( B_b_P001(i,j), B_b_P002(i,j), B_b_P003(i,j) )
σ_b(i,j) = std( B_b_P001(i,j), B_b_P002(i,j), B_b_P003(i,j) )
CV_b(i,j) = σ_b(i,j) / μ_b(i,j)   [coefficient of variation]
```

A **low CV composite** across all bands:
```
SPI(i,j) = 1 - mean_b( CV_b(i,j) )    [Spectral Path Indicator]
```

High SPI = temporally stable = candidate path zone. This is a direct physical evidence channel, entirely independent of all modelled cost surfaces.

**Pre-processing pipeline for multi-temporal alignment:**

1. Convert DN → top-of-atmosphere radiance: `L = absCalFactor × DN / effectiveBandwidth` (coefficients from `.IMD` files)
2. Atmospheric correction: apply DOS (Dark Object Subtraction) as a minimum — for quantitative multi-temporal comparison, QUAC or FLAASH is preferable if you have a trusted atmospheric model for Kharga
3. Reproject all tiles to the working CRS (`rasterio.merge` then `rasterio.reproject`)
4. Coregister the three dates: use phase correlation or feature-matching (`cv2.findTransformECC`) to sub-pixel align P001/P002/P003

**Pan-sharpening to 0.46 m:**

Use Gram-Schmidt Adaptive (GSA) pan-sharpening — preserves spectral fidelity better than Brovey (which distorts colour) and is faster than wavelet methods:

```python
from sklearn.linear_model import LinearRegression
# Project each MUL band onto PAN using linear regression over training pixels
# Inject high-frequency PAN detail into each band
# Result: 8-band image at PAN resolution (0.46 m)
```

At 0.46 m GSD, a 2-metre-wide path spans ~4 pixels — at the detection limit of the Frangi vesselness filter.

**Frangi vesselness filter** for linear feature detection (Frangi et al. 1998):

Compute the 2D Hessian of the smoothed image at scale `σ`:
```
H_σ = I * G_σ''(x,y)    [convolution with second-derivative-of-Gaussian]
```

Eigenvalues `λ₁ ≤ λ₂` of H_σ. For a bright line on dark background: `λ₁ ≈ 0`, `λ₂ << 0`.

Vesselness response:
```
V₀(σ) = 0                                    if λ₂ > 0
       = exp(-R_B²/2β²) · (1-exp(-S²/2c²))  otherwise

R_B = |λ₁/λ₂|,   S = sqrt(λ₁²+λ₂²)
β = 0.5 (line-blob discrimination), c = half of max(S)
```

Final scale-space maximum: `V(x,y) = max_σ V₀(σ)` over `σ ∈ {1, 2, 4, 8}` pixels.

For faint desert paths: also apply to the **dark-on-bright** variant (paths may be slightly darker than surroundings due to compaction removing bright top-layer dust). Apply to `-image` and take max.

### 4.6 Space Syntax

Space syntax (Hillier & Hanson 1984) quantifies how well-connected each space is to all others — capturing the **social and perceptual logic** of movement that terrain-cost models miss entirely. In a settlement-like necropolis, routes that maximise accessibility (not just minimise effort) are plausible candidates for primary streets.

**Axial lines:** The longest straight lines covering all convex spaces in the free space (complement of the building footprint union). At full-site scale, generate algorithmically:
1. Compute the binary free-space mask: erode `BuildingFootprints` union by a small buffer (representing a human body width ~0.5 m)
2. Extract the medial axis / skeleton of free space
3. For each skeleton branch, fit the longest possible line contained within free space
4. Prune: remove lines whose angular deviation from the skeleton axis exceeds 15°

**Connectivity:** `CN(i) = ` number of axial lines intersecting line `i`

**Integration (global):**
```
MD(i) = Σⱼ d(i,j) / (n-1)          [mean topological depth]
RA(i) = 2·(MD(i)-1) / (n-2)        [relative asymmetry]
RRA(i) = RA(i) / D_n                [normalized — diamond baseline]
Integration(i) = 1 / RRA(i)
```

High Integration = most accessible = candidate primary route. Penn et al. (1998) demonstrated that integration predicts pedestrian movement rates in urban environments with R² ≈ 0.5–0.8. In a necropolis with attested "streets and alleyways," similar structure is expected.

**Implementation:** `momepy` library provides space syntax metrics on `networkx` graphs. Build the axial graph, then run `momepy.Integration`, `momepy.Connectivity`, `momepy.Betweenness`.

---

## 5. Repository Structure

```
bagawat-paths/
├── README.md                          ← this file
├── environment.yml                    ← exact dependency versions (§10)
├── data/
│   ├── raw/                           ← untouched originals — READ ONLY after copy
│   │   ├── 110_GIS/
│   │   ├── 120_SiteReport/            ← xlsx, pdfs, dxf, dwg
│   │   ├── 130_Footprints/
│   │   └── 140_WV2/                   ← all P001/P002/P003 tile directories
│   ├── interim/
│   │   ├── wv2_merged_p001.tif        ← per-pass merged & atmospherically corrected
│   │   ├── wv2_merged_p002.tif
│   │   ├── wv2_merged_p003.tif
│   │   ├── wv2_pansharp_p001.tif      ← Gram-Schmidt pan-sharpened, 0.46 m
│   │   ├── wv2_multitemporal_cv.tif   ← coefficient-of-variation stack
│   │   ├── spi.tif                    ← Spectral Path Indicator
│   │   ├── dem_slope.tif
│   │   ├── cost_surface_tobler.tif
│   │   ├── cost_surface_llobera.tif
│   │   └── building_mask.tif          ← rasterized footprint no-go layer
│   ├── processed/
│   │   ├── entrances.geojson          ← n=342, with source & confidence fields
│   │   ├── cost_composite.tif         ← weighted multi-band cost
│   │   ├── fete_density.tif           ← movement potential raster
│   │   ├── circuit_current.tif        ← electrical current density
│   │   ├── space_syntax_integration.tif
│   │   ├── gabriel_graph.geojson
│   │   └── beta_skeleton_{b}.geojson  ← for b in 1.0, 1.2, 1.5, 2.0
│   └── crosswalk/
│       ├── building_id_crosswalk.csv  ← footprint_id | chapel_id | plan_label | ...
│       └── crosswalk_audit.md
├── notebooks/
│   ├── 00_data_audit.ipynb
│   ├── 01_coordinate_alignment.ipynb
│   ├── 02_id_crosswalk.ipynb
│   ├── 03_entrance_extraction.ipynb
│   ├── 04_cost_surface.ipynb
│   ├── 05_wv2_spectral.ipynb
│   ├── 06_fete_network.ipynb
│   ├── 07_circuit_model.ipynb
│   ├── 08_space_syntax.ipynb
│   ├── 09_proximity_graphs.ipynb
│   ├── 10_ensemble.ipynb
│   ├── 11_validation.ipynb
│   └── 12_final_outputs.ipynb
├── src/
│   ├── align.py                       ← CRS reconciliation, GCP reading, PDF homography
│   ├── crosswalk.py                   ← ID reconciliation logic
│   ├── entrances.py                   ← PDF color-threshold + attribute-driven extraction
│   ├── cost.py                        ← Tobler, Llobera–Sluckin, composite cost
│   ├── fete.py                        ← FETE engine, multi-source Dijkstra
│   ├── circuit.py                     ← Kirchhoff solver, conductance matrix
│   ├── spectral.py                    ← WV-2 preprocessing, SPI, Frangi
│   ├── syntax.py                      ← axial line generation, integration
│   ├── graphs.py                      ← Gabriel, beta-skeleton, Steiner
│   ├── ensemble.py                    ← evidence fusion, confidence scoring
│   └── viz.py                         ← all visualization helpers
├── outputs/
│   ├── path_network.geojson           ← final network, confidence-scored per segment
│   ├── movement_potential.tif
│   ├── spectral_path_indicator.tif
│   ├── confidence_report.md
│   └── figures/
│       ├── fete_overlay.png
│       ├── circuit_overlay.png
│       ├── spi_overlay.png
│       ├── ensemble_heatmap.png
│       └── network_on_ortho.png
└── docs/
    └── decisions.md                   ← running log of parameter choices, dead ends
```

---

## 6. Phase-by-Phase Implementation Plan

### Phase 0 — Data audit and environment (do this before touching any analysis)

**Step 0a — Inspect the DWG:**

```bash
ezdxf browse "100_Data/120_SiteReport/BaseSiteCAD/SITE CAD WORKING.dwg"
```

List all layer names. If any layer contains path/road geometry, extract it immediately — this becomes your highest-authority annotation layer, superseding everything else. Document in `docs/decisions.md`.

**Step 0b — Read the QGIS GCP files:**

```python
import pandas as pd
gcps = pd.read_csv("Buildings_Mask.shp.points", skiprows=1,
                   names=["mapX","mapY","pixelX","pixelY","enable"])
# mapX/mapY are in working CRS; pixelX/pixelY are in image coordinates
```

These GCPs are exactly what you need for PDF georeferencing in Phase 1. Read all three `.points` files and compare — if they agree, use the union; if they disagree, the later-numbered file is likely a revised registration.

**Step 0c — CRS audit:**

```python
import rasterio, geopandas as gpd
layers = {
    "footprints": gpd.read_file("Buildings_Mask.shp"),
    "roi":        gpd.read_file("Bagawat_ROI.shp"),
    "dem":        rasterio.open("DEM_Subset-Original.tif"),
    "ortho":      rasterio.open("OrthoImage_Subset.tif"),
    "sar":        rasterio.open("SAR-MS.tif"),
    "wv2_p001":   rasterio.open("18JUN14090738-M2AS_R1C1-058239078010_01_P001.TIF"),
}
for name, layer in layers.items():
    crs = layer.crs if hasattr(layer,'crs') else layer.meta['crs']
    print(f"{name}: {crs}")
```

All layers must land in the same CRS, or be explicitly reprojected. The working CRS is whichever the `Buildings_Mask.shp` uses. Every other layer must be warped/reprojected to match — document what was done.

**Step 0d — Parse individual DXF files:**

```python
import ezdxf
for bld_num in [1, 23, 24, 25, 26, 175, 210]:
    doc = ezdxf.readfile(f"Building{bld_num}.dxf")
    layers = [layer.dxf.name for layer in doc.layers]
    print(f"Building {bld_num} layers: {layers}")
    # Look for: DOOR, ENTRANCE, OPENING, FEATURE, ACCESS, THRESHOLD
```

Extract entities from entrance-relevant layers as `shapely.geometry.LineString` or `Point` objects. Transform to working CRS using the site-wide DXF coordinate system (verify by overlaying one DXF footprint against the `Buildings_Mask.shp` for the same building — they should coincide).

---

### Phase 1 — Coordinate Reconciliation

**Goal:** one consistent local CRS that every layer can be read into.

The `Buildings_Mask.shp.points` GCPs give you everything for registering the PDF:

```python
import cv2, numpy as np, fitz

def rasterize_pdf(pdf_path, dpi=400):
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:,:,:3]

def fit_pdf_to_crs(gcps_df):
    """
    gcps_df has columns: mapX, mapY (CRS), pixelX, pixelY (PDF pixel coords at chosen DPI)
    Returns 3x3 homography H such that CRS_point = H @ [px, py, 1]^T
    """
    src = gcps_df[["pixelX","pixelY"]].values.astype(np.float64)
    dst = gcps_df[["mapX","mapY"]].values.astype(np.float64)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    inliers = mask.ravel().sum()
    print(f"Homography fit: {inliers}/{len(src)} GCPs used as inliers")
    return H

def pdf_px_to_crs(px, py, H):
    pt = np.array([[px, py, 1.0]], dtype=np.float64)
    mapped = (H @ pt.T).T
    return mapped[0,:2] / mapped[0,2]
```

**Reprojection residuals:** After fitting the homography, compute RMSE over all GCPs:
```python
predicted = np.array([pdf_px_to_crs(r.pixelX, r.pixelY, H) for _, r in gcps.iterrows()])
actual = gcps[["mapX","mapY"]].values
rmse = np.sqrt(np.mean(np.sum((predicted - actual)**2, axis=1)))
print(f"Registration RMSE: {rmse:.3f} map units")
```

Target RMSE ≤ 1 building width (roughly 3–5 m in local coordinates). If RMSE is higher, identify outlier GCPs (highest residuals) and either flag them or remove and re-fit.

**WV-2 tile merging:**

```python
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling
import glob

def merge_wv2_pass(tile_dir, pass_id, out_path):
    tifs = sorted(glob.glob(f"{tile_dir}/*{pass_id}*.TIF"))
    src_files = [rasterio.open(f) for f in tifs]
    mosaic, transform = merge(src_files)
    # Reproject to working CRS
    dst_crs = target_crs  # from Buildings_Mask.shp
    transform_new, w, h = calculate_default_transform(
        src_files[0].crs, dst_crs, mosaic.shape[-1], mosaic.shape[-2], *src_files[0].bounds)
    with rasterio.open(out_path, 'w', driver='GTiff', count=mosaic.shape[0],
                       dtype=mosaic.dtype, crs=dst_crs, transform=transform_new, width=w, height=h) as dst:
        for band_idx in range(mosaic.shape[0]):
            reproject(mosaic[band_idx], dst.read(band_idx+1), src_transform=transform,
                      src_crs=src_files[0].crs, dst_transform=transform_new, dst_crs=dst_crs,
                      resampling=Resampling.bilinear)
```

---

### Phase 2 — Building ID Crosswalk

**Goal:** a versioned table mapping shapefile polygon ID ↔ Excel chapel number ↔ PDF plan label ↔ DXF filename, with explicit 1-to-many support.

Critical schema decision made upfront:

```
footprint_id  | chapel_ids      | plan_labels    | dxf_file      | match_method  | confidence
--------------+-----------------+----------------+---------------+---------------+-----------
FP_023        | 23, 24          | "23", "24"     | Building23.dxf| spatial+exact | 0.95
FP_025        | 25              | "25"           | Building25.dxf| exact         | 1.00
FP_180        | 180             | "180"          | None          | spatial       | 0.85
```

**Join strategy in order:**

1. **Exact string match** between shapefile `ID` field and Excel `Chapel_No` field — no normalization, no fuzzy matching. This catches the easy cases without introducing false matches.
2. **Spatial join** (post Phase 1): project PDF plan label centroid positions (extracted via OCR in Step 2b) into working CRS. Assign each PDF label to the nearest footprint polygon within a 5 m tolerance.
3. **DXF filename matching**: `Building{N}.dxf` → chapel N. Verify by overlaying DXF geometry against shapefile polygon for building N. If they coincide spatially, the match is confirmed.
4. **Manual resolution** for remaining unmatched records.

**OCR for plan labels:**

```python
import pytesseract, cv2
from PIL import Image

def extract_plan_labels(img_rgb, building_mask):
    """
    img_rgb: the rasterized PDF
    building_mask: binary mask where buildings are 1
    Returns: list of (text, centroid_x, centroid_y) in PDF pixel coordinates
    """
    # Erode building regions slightly to find label areas
    kernel = np.ones((5,5), np.uint8)
    search_area = 1 - cv2.erode(building_mask, kernel, iterations=2)
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    # Apply threshold; typeset numbers tend to be dark on white
    thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)[1]
    thresh = thresh * search_area.astype(np.uint8)
    config = '--psm 6 -c tessedit_char_whitelist=0123456789'
    data = pytesseract.image_to_data(thresh, config=config, output_type=pytesseract.Output.DICT)
    results = []
    for i, text in enumerate(data['text']):
        if text.strip().isdigit() and int(data['conf'][i]) > 60:
            cx = data['left'][i] + data['width'][i]//2
            cy = data['top'][i] + data['height'][i]//2
            results.append((text.strip(), cx, cy))
    return results
```

**Forbidden external sources:** Do not import building numbers from Fakhry (1951), NASSCAL, or any Wikipedia/secondary source into the crosswalk. These use different numbering conventions from your own dataset's internal sources, and the conventions are internally inconsistent across secondary sources. Qualitative literature references (for narrative validation in Phase 11) are fine; numerical ID imports are not.

---

### Phase 3 — Entrance Point Extraction (Hybrid Three-Pass)

**3a. DXF-derived entrances (highest precision — use as calibration set):**

```python
import ezdxf
from shapely.geometry import Point, LineString
import numpy as np

ENTRANCE_LAYER_KEYWORDS = ['door','entrance','opening','threshold','access','portal','seuil']

def extract_dxf_entrances(dxf_path):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    entrance_geoms = []
    for entity in msp:
        layer = entity.dxf.layer.lower()
        if any(kw in layer for kw in ENTRANCE_LAYER_KEYWORDS):
            if entity.dxftype() == 'LINE':
                pts = [(entity.dxf.start.x, entity.dxf.start.y),
                       (entity.dxf.end.x, entity.dxf.end.y)]
                entrance_geoms.append(LineString(pts).centroid)
            elif entity.dxftype() in ('POINT', 'INSERT'):
                entrance_geoms.append(Point(entity.dxf.insert.x, entity.dxf.insert.y))
    return entrance_geoms  # in DXF coordinate space; transform to working CRS
```

**3b. PDF color-threshold extraction (hand marks — ground truth annotation):**

```python
def find_blue_marks(img_rgb, h_lo=90, h_hi=115, s_min=50, v_min=80):
    """
    Light-blue pen hue in OpenCV HSV: H ≈ 90–115, S ≥ 50, V ≥ 80
    These values must be tuned against known marks from 3a before running site-wide.
    Tune procedure:
      1. Manually identify 5 marks near buildings 23-26 (confirmed from DXF)
      2. Sample HSV values at those marks
      3. Set h_lo = min(H_samples)-5, h_hi = max(H_samples)+5
      4. Set s_min = min(S_samples)-10, v_min = min(V_samples)-10
    """
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv,
                       np.array([h_lo, s_min, v_min]),
                       np.array([h_hi, 255, 255]))
    # Morphological close to connect dashes; open to remove speckle
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    # Filter by size: marks are typically 50–2000 pixels at 400 DPI
    valid_idx = np.where((stats[1:, cv2.CC_STAT_AREA] > 50) &
                          (stats[1:, cv2.CC_STAT_AREA] < 2000))[0] + 1
    return centroids[valid_idx], stats[valid_idx]  # in PDF pixel coordinates
```

**3c. Attribute-driven entrance derivation (full 342-chapel coverage):**

For every chapel in `Database Full` with a recorded entrance direction, compute the entrance geometrically from the footprint polygon:

```python
from shapely.geometry import Point
import numpy as np

DIRECTION_VECTORS = {
    "N": np.array([0,  1]),
    "S": np.array([0, -1]),
    "E": np.array([1,  0]),
    "W": np.array([-1, 0]),
    "NE": np.array([1,  1]) / np.sqrt(2),
    "NW": np.array([-1, 1]) / np.sqrt(2),
    "SE": np.array([1, -1]) / np.sqrt(2),
    "SW": np.array([-1,-1]) / np.sqrt(2),
}

def entrance_from_direction(polygon, direction_str):
    """
    Pick the polygon edge whose outward normal best aligns with direction_str.
    For multi-direction strings like 'S/E', try both and return the better-scoring edge.
    """
    directions = [d.strip() for d in direction_str.replace('/', ' ').split()]
    centroid = np.array([polygon.centroid.x, polygon.centroid.y])
    coords = np.array(polygon.exterior.coords)
    best_pt, best_score = None, -np.inf

    for direction in directions:
        if direction not in DIRECTION_VECTORS:
            continue
        target = DIRECTION_VECTORS[direction]
        for a, b in zip(coords[:-1], coords[1:]):
            mid = (a + b) / 2
            normal = mid - centroid
            norm = np.linalg.norm(normal)
            if norm < 1e-9:
                continue
            score = np.dot(normal / norm, target)
            if score > best_score:
                best_score = score
                best_pt = mid

    if best_pt is None:
        return polygon.centroid  # fallback: centroid if direction unparseable
    return Point(best_pt)
```

**3d. Agreement analysis and QA:**

For buildings where both 3a/3b and 3c produce entrance candidates, compute agreement:

```python
def entrance_agreement(pt_manual, pt_derived, polygon):
    """
    Returns: distance (in map units), wall_agreement (bool: same polygon edge?),
             confidence (0–1 based on distance relative to polygon diameter)
    """
    dist = pt_manual.distance(pt_derived)
    bbox_diag = polygon.bounds  # (minx, miny, maxx, maxy)
    diag = np.sqrt((bbox_diag[2]-bbox_diag[0])**2 + (bbox_diag[3]-bbox_diag[1])**2)
    confidence = max(0.0, 1.0 - dist / diag)
    return dist, confidence
```

Generate a per-building QA image for every disagreement > 2 map units:

```python
def render_qa_crop(img_rgb, H, footprint_poly, pt_manual, pt_derived, padding=50):
    """Render a small crop of the PDF showing both candidate entrance points."""
    # Project polygon to PDF pixel space using inverse homography
    # Draw footprint outline in grey, pt_manual in blue, pt_derived in red
    ...
```

Output: `data/processed/entrances.geojson` with fields:
- `chapel_id`, `footprint_id`: from crosswalk
- `geometry`: entrance point
- `source`: `dxf | pdf_mark | attribute_derived | manual`
- `direction_recorded`: raw Excel field value
- `confidence`: 0.0–1.0
- `agreement_dist_m`: distance to closest alternative-source candidate

---

### Phase 4 — Cost Surface Construction

```python
import rasterio, numpy as np
from rasterio.features import rasterize as rio_rasterize
import geopandas as gpd

def slope_to_tobler_cost(slope_rise_run):
    """Vectorized Tobler cost (seconds per map unit)."""
    speed = 6.0 * np.exp(-3.5 * np.abs(slope_rise_run + 0.05))
    return 1.0 / np.maximum(speed, 1e-6)

def slope_to_llobera_cost(slope_rise_run, pixel_size_m=1.0):
    """Llobera-Sluckin energy cost (J/kg/m) normalized to same scale as Tobler."""
    theta = np.arctan(slope_rise_run)
    a, b, c = 1.5, 5.9, 0.17
    return a * (1 + b * np.sin(theta)**2 + c * theta**2)

def build_cost_surface(dem_path, footprints_gdf, spi_path, sar_path, weights, out_path):
    with rasterio.open(dem_path) as dem_src:
        dem = dem_src.read(1).astype(float)
        transform = dem_src.transform
        shape = dem.shape
        profile = dem_src.profile

    # Compute slope from DEM using central differences
    py, px = np.gradient(dem, transform[4], transform[0])  # dy, dx
    slope = np.sqrt(py**2 + px**2)

    # Terrain cost
    C_terrain = slope_to_tobler_cost(slope)

    # Building obstruction mask (infinite cost = 1e9 as surrogate)
    footprint_mask = rio_rasterize(
        [(geom, 1) for geom in footprints_gdf.geometry],
        out_shape=shape, transform=transform, fill=0, dtype=np.uint8)
    C_obs = np.where(footprint_mask == 1, 1e9, 0.0)

    # Spectral path indicator → lower cost where SPI is high
    with rasterio.open(spi_path) as spi_src:
        spi = spi_src.read(1).astype(float)
    C_spec = 1.0 - np.clip(spi, 0, 1)  # invert: high SPI = low cost

    # SAR: low backscatter zones = candidate paths = lower cost
    with rasterio.open(sar_path) as sar_src:
        sar = sar_src.read(1).astype(float)
    sar_norm = (sar - sar.min()) / (sar.max() - sar.min() + 1e-9)
    C_sar = sar_norm  # low backscatter = 0 = low cost

    w1, w2, w3, w4 = weights['terrain'], weights['obs'], weights['spec'], weights['sar']
    C_composite = w1*C_terrain + w2*C_obs + w3*C_spec + w4*C_sar

    with rasterio.open(out_path, 'w', **{**profile, 'count': 1, 'dtype': 'float32'}) as dst:
        dst.write(C_composite.astype(np.float32), 1)
```

---

### Phase 5 — WorldView-2 Spectral Analysis

**Atmospheric correction (DOS1):**

```python
def dos1_correction(band_dn, nodata=0):
    """
    Dark Object Subtraction atmospheric correction.
    Assumes the darkest 0.1% of pixels is atmospheric haze.
    """
    valid = band_dn[band_dn != nodata]
    dark_val = np.percentile(valid, 0.1)
    return np.maximum(band_dn.astype(float) - dark_val, 0)
```

**Multi-temporal SPI computation:**

```python
def compute_spi(p001_bands, p002_bands, p003_bands, exclude_coastal=True):
    """
    p00N_bands: dict {band_idx: np.array} for pass N, atmospherically corrected
    Returns: SPI raster (float32, same shape as input bands)
    """
    band_ids = [2,3,4,5,6,7,8] if exclude_coastal else [1,2,3,4,5,6,7,8]
    cv_stack = []
    for b in band_ids:
        stack = np.stack([p001_bands[b], p002_bands[b], p003_bands[b]], axis=0)
        mu = stack.mean(axis=0)
        sigma = stack.std(axis=0)
        cv = sigma / (mu + 1e-6)
        cv_stack.append(cv)
    mean_cv = np.mean(cv_stack, axis=0)
    spi = 1.0 - np.clip(mean_cv, 0, 1)
    return spi.astype(np.float32)
```

**Iron Oxide Ratio:**

```python
def iron_oxide_ratio(red_band, green_band):
    return np.where(green_band > 0, red_band / (green_band + 1e-6), 0)
```

**Frangi vesselness on pan-sharpened image:**

```python
from skimage.filters import frangi

def detect_path_candidates(pan_img, sigmas=(1, 2, 4, 8)):
    """
    pan_img: 2D float array (pan-sharpened image, normalized 0-1)
    Returns: vesselness response as float32 raster
    """
    # Detect bright linear features
    v_bright = frangi(pan_img, sigmas=sigmas, black_ridges=False)
    # Detect dark linear features (paths may be darker than surroundings)
    v_dark = frangi(1.0 - pan_img, sigmas=sigmas, black_ridges=False)
    return np.maximum(v_bright, v_dark).astype(np.float32)
```

---

### Phase 6 — FETE Network Generation

```python
from skimage.graph import MCP_Geometric
import numpy as np

def run_fete(cost_raster, entrance_pixels, n_traceback_pairs='all'):
    """
    cost_raster: 2D float array
    entrance_pixels: list of (row, col) entrance coordinates in raster space
    n_traceback_pairs: 'all' for all pairs, or int for random subsample
    """
    n = len(entrance_pixels)
    density = np.zeros(cost_raster.shape, dtype=np.float32)

    if n_traceback_pairs == 'all':
        pairs = [(i, j) for i in range(n) for j in range(i+1, n)]
    else:
        import random
        all_pairs = [(i, j) for i in range(n) for j in range(i+1, n)]
        pairs = random.sample(all_pairs, min(n_traceback_pairs, len(all_pairs)))

    for src_idx, src in enumerate(entrance_pixels):
        mcp = MCP_Geometric(cost_raster, fully_connected=True)
        _, _ = mcp.find_costs([src])

        for tgt_idx, tgt in enumerate(entrance_pixels):
            if tgt_idx <= src_idx:
                continue
            if (src_idx, tgt_idx) not in [(p[0],p[1]) for p in pairs]:
                continue
            try:
                path = mcp.traceback(tgt)
                for (r, c) in path:
                    density[r, c] += 1
            except Exception:
                pass  # no path found (disconnected)

        if src_idx % 20 == 0:
            print(f"FETE: completed {src_idx+1}/{n} source nodes")

    return density / density.max()  # normalize to [0,1]
```

**Skeletonize and vectorize:**

```python
from skimage.morphology import skeletonize
from skimage.measure import label as sk_label
import networkx as nx

def density_to_network(density, threshold=0.15, min_segment_length=3):
    binary = (density > threshold).astype(np.uint8)
    skel = skeletonize(binary)

    G = nx.Graph()
    rows, cols = np.where(skel)
    coord_set = set(zip(rows.tolist(), cols.tolist()))

    for (r, c) in coord_set:
        neighbors = [(r+dr, c+dc)
                     for dr in (-1,0,1) for dc in (-1,0,1)
                     if (dr,dc) != (0,0) and (r+dr,c+dc) in coord_set]
        for nb in neighbors:
            dist = np.sqrt((nb[0]-r)**2 + (nb[1]-c)**2)
            G.add_edge((r,c), nb, weight=dist,
                       density=float(density[r,c]))

    # Prune short spurs (degree-1 nodes connected by short chains)
    changed = True
    while changed:
        changed = False
        for node in list(G.nodes()):
            if G.degree(node) == 1:
                path_len = 0
                curr = node
                prev = None
                while G.degree(curr) == 1:
                    nbrs = list(G.neighbors(curr))
                    nxt = [n for n in nbrs if n != prev]
                    if not nxt:
                        break
                    path_len += G[curr][nxt[0]]['weight']
                    prev, curr = curr, nxt[0]
                    if path_len > min_segment_length:
                        break
                if path_len <= min_segment_length:
                    G.remove_node(node)
                    changed = True

    return G
```

---

### Phase 7 — Electrical Circuit Model

```python
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import lgmres, LinearOperator

def build_conductance_matrix(cost_raster, connectivity=8):
    """Build sparse conductance (Laplacian) matrix from cost raster."""
    rows, cols = cost_raster.shape
    N = rows * cols
    conductance = 1.0 / (cost_raster + 1e-9)  # G = 1/R
    conductance = conductance.ravel()

    row_idx, col_idx, values = [], [], []
    diagonal = np.zeros(N)

    def flat(r, c):
        return r * cols + c

    offsets = [(-1,0),(1,0),(0,-1),(0,1)]
    if connectivity == 8:
        offsets += [(-1,-1),(-1,1),(1,-1),(1,1)]

    for r in range(rows):
        for c in range(cols):
            i = flat(r, c)
            for dr, dc in offsets:
                nr, nc = r+dr, c+dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    j = flat(nr, nc)
                    edge_cond = np.sqrt(conductance[i] * conductance[j])  # geometric mean
                    row_idx.append(i); col_idx.append(j); values.append(-edge_cond)
                    diagonal[i] += edge_cond

    K = sp.csr_matrix((values + list(diagonal),
                       (row_idx + list(range(N)), col_idx + list(range(N)))), shape=(N, N))
    return K, conductance.reshape(rows, cols)

def compute_current_density(K, conductance, src_nodes, tgt_nodes, shape):
    """
    src_nodes, tgt_nodes: lists of flat indices for source and target nodes
    Injects unit current at each src, extracts at each tgt.
    """
    rows, cols = shape
    N = rows * cols
    current_accumulator = np.zeros(N)

    for src, tgt in zip(src_nodes, tgt_nodes):
        b = np.zeros(N)
        b[src] = 1.0
        b[tgt] = -1.0
        # Ground one node to make system non-singular
        K_mod = K.tolil()
        K_mod[tgt, :] = 0
        K_mod[tgt, tgt] = 1.0
        K_csr = K_mod.tocsr()
        b[tgt] = 0.0
        v, info = lgmres(K_csr, b, maxiter=1000, tol=1e-8)
        if info != 0:
            continue
        # Compute current on each edge
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
            r_src = np.arange(rows * cols) // cols
            c_src = np.arange(rows * cols) % cols
            valid = ((r_src + dr >= 0) & (r_src + dr < rows) &
                     (c_src + dc >= 0) & (c_src + dc < cols))
            j_idx = np.where(valid)[0]
            edge_cond = np.sqrt(conductance.ravel()[j_idx] *
                                conductance.ravel()[(r_src[j_idx]+dr)*cols + c_src[j_idx]+dc])
            i_edge = np.abs(v[j_idx] - v[(r_src[j_idx]+dr)*cols + c_src[j_idx]+dc]) * edge_cond
            current_accumulator[j_idx] += i_edge

    return current_accumulator.reshape(rows, cols)
```

---

### Phase 8 — Space Syntax

```python
import numpy as np
import networkx as nx
from skimage.morphology import skeletonize, medial_axis
import geopandas as gpd
from shapely.geometry import LineString
import momepy

def generate_axial_lines(building_footprints_gdf, roi_bounds, resolution=0.5):
    """
    Compute the medial axis of free space, then fit long line segments.
    building_footprints_gdf: GeoDataFrame with Polygon geometries
    roi_bounds: (minx, miny, maxx, maxy)
    resolution: map units per pixel for the analysis grid
    """
    from rasterio.features import rasterize as rio_rasterize
    from rasterio.transform import from_bounds

    minx, miny, maxx, maxy = roi_bounds
    width = int((maxx - minx) / resolution)
    height = int((maxy - miny) / resolution)
    transform = from_bounds(minx, miny, maxx, maxy, width, height)

    footprint_mask = rio_rasterize(
        [(geom, 1) for geom in building_footprints_gdf.geometry],
        out_shape=(height, width), transform=transform, dtype=np.uint8)

    free_space = 1 - footprint_mask
    # Buffer buildings by ~0.5m (1 pixel) to represent wall thickness
    kernel = np.ones((3,3), np.uint8)
    import cv2
    free_space_eroded = cv2.erode(free_space, kernel, iterations=1)

    skel = skeletonize(free_space_eroded.astype(bool))
    return skel, transform

def compute_integration(axial_graph):
    """Compute space syntax integration from axial graph using momepy."""
    gdf = gpd.GeoDataFrame(geometry=[LineString([u, v])
                                      for u, v in axial_graph.edges()])
    gdf['node_id'] = range(len(gdf))
    queen = momepy.Queen.from_dataframe(gdf)
    gdf['integration'] = momepy.Integration(gdf, queen).series
    return gdf
```

---

### Phase 9 — Proximity Graphs

```python
import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import LineString
import networkx as nx

def gabriel_graph(points):
    """
    points: (N, 2) array of entrance coordinates
    Returns: networkx.Graph with edges in Gabriel graph
    """
    n = len(points)
    tri = Delaunay(points)
    candidate_edges = set()
    for simplex in tri.simplices:
        for i in range(3):
            for j in range(i+1, 3):
                candidate_edges.add((min(simplex[i], simplex[j]),
                                     max(simplex[i], simplex[j])))

    G = nx.Graph()
    G.add_nodes_from(range(n))

    for (u, v) in candidate_edges:
        mid = (points[u] + points[v]) / 2
        radius_sq = np.sum((points[u] - points[v])**2) / 4
        in_circle = np.sum((points - mid)**2, axis=1) < radius_sq - 1e-10
        in_circle[[u, v]] = False
        if not np.any(in_circle):
            G.add_edge(u, v,
                       geometry=LineString([points[u], points[v]]),
                       length=np.linalg.norm(points[u]-points[v]))

    return G

def beta_skeleton(points, beta=1.5):
    """
    Generalized β-skeleton (Gabriel = β=1, RNG = β=2).
    """
    n = len(points)
    G = nx.Graph()
    G.add_nodes_from(range(n))

    for u in range(n):
        for v in range(u+1, n):
            d_uv = np.linalg.norm(points[u] - points[v])
            r = beta * d_uv / 2
            center1 = points[u] + beta/2 * (points[v] - points[u])
            center2 = points[v] + beta/2 * (points[u] - points[v])
            blocked = False
            for w in range(n):
                if w == u or w == v:
                    continue
                if (np.linalg.norm(points[w]-center1) < r - 1e-10 or
                        np.linalg.norm(points[w]-center2) < r - 1e-10):
                    blocked = True
                    break
            if not blocked:
                G.add_edge(u, v, length=d_uv)
    return G
```

---

### Phase 10 — Ensemble and Confidence Scoring

**Five evidence streams produce five rasters, each normalized to [0,1]:**

| Stream | Raster | Interpretation |
|---|---|---|
| A | `fete_density_norm` | High = many LCPs converge here |
| B | `circuit_current_norm` | High = strong random-walk flow |
| C | `spi` | High = temporally stable surface |
| D | `space_syntax_integration_norm` | High = topologically central |
| E | `proximity_edge_density` | High = many graph edges pass through |

**Ensemble confidence:**

```python
def compute_ensemble(fete, circuit, spi, syntax, prox,
                     weights=(0.30, 0.25, 0.25, 0.10, 0.10)):
    """
    Weighted linear combination. Weights tunable; defaults reflect
    expected evidence quality:
      - FETE and Circuit: both terrain-based, but methodologically independent
      - SPI: only direct physical evidence stream; upweighted relative to model-only streams
      - Syntax: captures different evidence dimension
      - Prox: geometric constraint, less sensitive to terrain
    """
    w_fete, w_circ, w_spi, w_syn, w_prox = weights
    ensemble = (w_fete * fete + w_circ * circuit + w_spi * spi +
                w_syn * syntax + w_prox * prox)
    return ensemble.clip(0, 1)
```

**Per-segment confidence tag (after vectorization):**

For each segment in the final network GeoJSON:
- `confidence_fete`: mean FETE density along segment
- `confidence_circuit`: mean circuit current along segment
- `confidence_spi`: mean SPI along segment (the only direct-evidence field)
- `confidence_syntax`: mean syntax integration along segment
- `confidence_ensemble`: weighted combination
- `method_agreement`: count of streams with score > 0.5 (1–5)
- `flag_review`: True if `method_agreement ≤ 2` (flagged for manual verification)

---

## 7. Validation Framework

There is no ground-truth excavated path network. Validation must come from triangulation across orthogonal evidence types.

### 7.1 Internal consistency tests

**Entrance coverage:** Every chapel entrance in `entrances.geojson` must be within ≤ 3 pixels of a segment in `path_network.geojson`. Report the fraction of entrances within this tolerance.

**No-go violations:** Zero network segments should pass through any cell where `building_mask = 1`. This is a hard binary check, not a score.

**Crosswalk completeness:** Report the fraction of 342 Excel records with a matched `footprint_id`. Target: > 90% matched; remainder documented with reason.

### 7.2 Cross-method agreement analysis

For each pair of method streams (A–E), compute Pearson correlation on overlapping pixels:

```python
from scipy.stats import pearsonr, spearmanr
pairs = [('fete','circuit'),('fete','spi'),('circuit','spi'),
         ('fete','syntax'),('spi','syntax')]
for a, b in pairs:
    r, p = spearmanr(rasters[a].ravel(), rasters[b].ravel())
    print(f"{a} vs {b}: r={r:.3f}, p={p:.2e}")
```

Methods A and B (FETE and circuit) are not independent — both derive from the cost surface — so their agreement is expected and not informative by itself. **Agreement between C (SPI, spectral) and any of A/B/D/E is genuinely informative** because C is the only stream that does not use terrain modelling as a prior.

### 7.3 Spectral correlation test

Test whether high-confidence network segments correlate with spectral anomalies:

```python
from sklearn.metrics import roc_auc_score
# Binary: segment pixel = 1, non-segment = 0
segment_mask = (vectorized_network_raster > 0).ravel()
spi_scores = spi.ravel()
auc = roc_auc_score(segment_mask, spi_scores)
print(f"SPI AUC for network segments: {auc:.3f}")
# AUC > 0.6: non-trivial agreement between spectral and modelled evidence
# AUC > 0.7: strong agreement — consider upweighting SPI in ensemble
# AUC < 0.55: no meaningful agreement — SPI may not contain path signal
```

### 7.4 Graph topology sanity checks

Real settlement path networks have characteristic topological properties. Check:

```python
G = final_network_graph  # networkx Graph

# Degree distribution
degrees = [d for _, d in G.degree()]
# Expect: mostly degree 2 (path corridors), some degree 3 (junctions),
#         rare degree 4+ (major intersections), few degree 1 (dead ends)
from scipy.stats import entropy
deg_hist, _ = np.histogram(degrees, bins=range(1, max(degrees)+2))
print(f"Degree entropy: {entropy(deg_hist):.3f}")  # moderate = good

# Betweenness distribution
bc = nx.betweenness_centrality(G, normalized=True)
bc_vals = list(bc.values())
# Expect: power-law-ish; a few high-betweenness trunk routes
import scipy.stats as stats
slope, intercept, r, p, se = stats.linregress(
    np.log(sorted(bc_vals, reverse=True)+[1e-10]),
    np.log(np.arange(1, len(bc_vals)+1)))
print(f"Betweenness power-law fit: slope={slope:.2f}, R²={r**2:.3f}")

# Planarity (real street networks are nearly planar)
is_planar, _ = nx.check_planarity(G)
print(f"Network is planar: {is_planar}")
```

### 7.5 Literature anchor point test

Chapel 180 (central church, attested in multiple sources as the principal building) should have high betweenness centrality. The Peace (25) and Exodus (80) chapels should be on or very near high-confidence segments. These are not precise tests but provide a qualitative sanity check:

```python
anchor_chapels = {25: "Peace", 80: "Exodus", 180: "Central Church"}
for chapel_id, name in anchor_chapels.items():
    entrance_pt = entrances[entrances.chapel_id == chapel_id].geometry.iloc[0]
    nearest_seg_dist = path_network.distance(entrance_pt).min()
    seg_confidence = path_network.iloc[path_network.distance(entrance_pt).argmin()].confidence_ensemble
    print(f"Chapel {chapel_id} ({name}): nearest segment {nearest_seg_dist:.1f}m, confidence {seg_confidence:.2f}")
```

---

## 8. Known Failure Modes & Mitigations

| Failure | Cause | Mitigation |
|---|---|---|
| Blue pen marks not isolatable | Ink hue overlaps with print colour, shadows, or paper tone | Tune on 5+ confirmed marks (from 3a DXF) before running site-wide. Keep a manual-digitization fallback. |
| OCR label mis-reads | Typeset numerals in PDF are small; scan noise | Validate every OCR match against spatial join result; flag mismatches |
| CRS mismatch between WV-2 and shapefile | WV-2 delivered as WGS84/UTM; shapefile may be local | Reproject everything to the shapefile's CRS; document explicitly in `docs/decisions.md` |
| WV-2 multi-temporal misalignment | Slight registration error between passes | Coregister with phase correlation (`skimage.registration.phase_cross_correlation`) to sub-pixel accuracy before computing SPI |
| DEM too coarse for local-scale alleys | DEM pixel size may exceed alley width | Use DEM for macro-scale route corridors; use SPI/circuit for fine-scale within-cluster routing |
| FETE produces diffuse density with no clear threshold | Cost surface is too flat (desert terrain, few elevation changes) | Upweight building obstruction term and SPI term in composite cost; or use circuit model (produces sharper current bands) |
| High SPI in areas with no paths | Compacted building interiors also show temporal stability | Mask SPI inside building footprints before using as evidence stream |
| Steiner tree is too sparse | Approximation ratio may leave some isolated subgraphs | Use as lower-bound reference only; do not substitute for FETE density as primary output |
| DWG/DXF file fails to open with ezdxf | R2018+ format incompatibility | Try LibreDWG: `dwg2dxf "SITE CAD WORKING.dwg" -o working_converted.dxf` |
| Proximity graph connects distant chapels across physical barriers | Gabriel/β-skeleton is purely geometric | Intersect proximity edges with cost surface; remove edges crossing cells with cost > 95th percentile |

---

## 9. ID System Warning (Critical)

Four incompatible numbering systems exist. This is not an edge case — it directly affects whether your analysis is internally valid.

| Source | ID type | Known conflicts |
|---|---|---|
| `Buildings_Mask.shp` attribute table | Shapefile polygon ID (format TBD — inspect first) | May use sequential integers, not archaeological numbers |
| `Database Full` (Excel) | `Chapel_No` field | 342 records, some multi-chamber buildings counted separately |
| `bagawat print.pdf` | Typeset labels on plan | Physical position on plan; must be geocoded |
| External literature (Fakhry, NASSCAL) | Fakhry 1951 numbering | Confirmed to conflict with internal numbering — do not import |

The 1-to-many issue: your Excel database has 342 chapel records but the footprint layer has ~260 polygons. This is because many buildings contain multiple chapels (e.g., a building with a domed chamber and an apse room = 2 chapels, 1 footprint polygon). The crosswalk schema must support this from day one.

Do not allow any code downstream of Phase 2 to perform a 1-to-1 join on chapel number unless it has been explicitly confirmed for that specific building.

---

## 10. Environment Specification

```yaml
name: bagawat-paths
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - geopandas=0.14
  - rasterio=1.3
  - shapely=2.0
  - fiona=1.9
  - pyproj=3.6
  - numpy=1.26
  - scipy=1.11
  - scikit-image=0.22
  - networkx=3.2
  - opencv=4.8
  - matplotlib=3.8
  - pandas=2.1
  - openpyxl=3.1
  - pytesseract=0.3
  - momepy=0.7
  - ezdxf=1.1
  - pip:
    - PyMuPDF==1.23
    - pdf2image==1.17
    - scikit-learn==1.3
```

Install:
```bash
conda env create -f environment.yml
conda activate bagawat-paths
# For DWG conversion if needed:
# sudo apt-get install libredwg-utils   (Linux)
# or: oda_converter from ODA (requires free registration)
```

Additional system dependency for `pytesseract`:
```bash
sudo apt-get install tesseract-ocr   # or brew install tesseract on macOS
```

---

## 11. Glossary

- **β-skeleton:** A parameterized proximity graph family; at β=1 equals the Gabriel graph, at β=2 equals the relative neighborhood graph.
- **Commute time:** In a random walk, the expected number of steps to go from node u to v and back to u. Equal to effective electrical resistance × total graph conductance (McRae et al. 2008).
- **Cost surface / friction surface:** A raster where each cell's value represents the cost of traversing that cell. The fundamental substrate of all path-finding methods here.
- **Effective resistance:** The electrical resistance between two nodes in a resistor network; formally equivalent to commute time in random walk theory.
- **FETE (From-Everywhere-To-Everywhere):** Run least-cost paths between all pairs of points and accumulate crossing frequency; high-frequency cells = likely corridors.
- **Frangi vesselness:** A scale-space filter detecting curvilinear structures (blood vessels in medical imaging; paths in remote sensing) via Hessian eigenvalue analysis.
- **Gabriel graph:** A planar subgraph of the Delaunay triangulation where an edge (u,v) exists only if no other point lies inside the diametric circle on uv.
- **Gram-Schmidt pan-sharpening:** A spectral-fidelity-preserving method for fusing high-resolution panchromatic imagery with lower-resolution multispectral bands.
- **MaxEnt IRL:** Maximum Entropy Inverse Reinforcement Learning — recovers a reward function from expert demonstrations. Inapplicable here due to absence of valid demonstrations.
- **MCP_Geometric:** `skimage.graph.MCP_Geometric` — a C-backed, distance-corrected least-cost path implementation supporting 48-connected neighborhoods.
- **Movement potential:** Accumulated count of how many least-cost paths pass through each raster cell across a large set of origin-destination pairs.
- **SPI (Spectral Path Indicator):** A multi-temporal spectral index derived from coefficient-of-variation across three WV-2 acquisition dates; low temporal variation = candidate path surface.
- **Space syntax / integration:** A topological measure of how accessible a spatial element (axial line) is to all others in the network; predicts movement rates in empirical studies.
- **Steiner tree:** The minimum-cost tree connecting a required set of terminal nodes, allowing additional Steiner nodes anywhere in the graph.
- **WV-2 (WorldView-2):** DigitalGlobe satellite; 8 multispectral bands at 1.84 m GSD + panchromatic at 0.46 m GSD.

---

## 12. References

- Bewley, R., & Donoghue, D. (2011). Aerial and Satellite Archaeology of the Middle East. In *Remote Sensing for Archaeological Heritage Management* (pp. 99–113). — remote sensing methods for archaeological site detection.
- Doyle, P. G., & Snell, J. L. (1984). *Random Walks and Electric Networks.* MAA. — formal equivalence between random walks and electrical circuits.
- Fakhry, A. (1951). *The Necropolis of El-Bagawat in Kharga Oasis.* Government Press, Cairo. — canonical 263-chapel survey; calibration reference for building count.
- Frangi, A. F., Niessen, W. J., Vincken, K. L., & Viergever, M. A. (1998). Multiscale vessel enhancement filtering. *MICCAI 1998*, LNCS 1496, 130–137. — Frangi vesselness filter.
- Harris, M. (2000). Quantifying movement on cost surfaces: archaeological applications. *Internet Archaeology* 9. — 48-neighbourhood kernel advantage over 8-connected grid.
- Hillier, B., & Hanson, J. (1984). *The Social Logic of Space.* Cambridge University Press. — space syntax original formulation.
- Llobera, M. (2000). Understanding movement: a pilot model towards the sociology of movement. In *Beyond the Map.* IOS Press, 65–84. — movement potential concept.
- Llobera, M., & Sluckin, T. J. (2007). Zigzagging: Theoretical insights on climbing strategies. *Journal of Theoretical Biology* 249, 206–217. — biomechanical energy cost function.
- Masucci, A. P., Smith, D., Johansson, A., & Batty, M. (2009). Random planar graphs and the London street network. *European Physical Journal B* 71, 259–271. — proximity graphs in street network analysis.
- McRae, B. H., Dickson, B. G., Keitt, T. H., & Shah, V. B. (2008). Using circuit theory to model connectivity in ecology, evolution, and conservation. *Ecology* 89, 2712–2724. — electrical circuit model for movement ecology; random walk equivalence theorem.
- Momepy (Fleischmann 2019). `momepy`: Urban Morphology Measuring Toolkit. *JOSS* 4(43). — space syntax integration in Python.
- Nakoinz, O. (2014). Modelling human behaviour in landscapes using GIS and graph theory. *Internet Archaeology* 36. — proximity graph applications in archaeology.
- Penn, A., Hillier, B., Banister, D., & Xu, J. (1998). Configurational modelling of urban movement networks. *Environment and Planning B* 25, 59–84. — empirical validation of integration as movement predictor.
- Tobler, W. (1993). Three presentations on geographical analysis and modeling. *National Center for Geographic Information and Analysis Technical Report* 93-1. — hiking function.
- Verhagen, P. (2013). Least cost path modelling and the study of long distance movement. In *Computational Approaches to Archaeological Spaces* (pp. 11–43). Left Coast Press. — independent FETE formulation, review of limitations.
- White, D. A., & Barber, S. B. (2012). Geospatial modeling of pedestrian transportation networks: a case study from precolumbian Oaxaca, Mexico. *Journal of Archaeological Science* 39, 2684–2696. — FETE method, validated against known historical corridors.
- Ziebart, B. D., Maas, A., Bagnell, J. A., & Dey, A. K. (2008). Maximum entropy inverse reinforcement learning. *AAAI 2008*, 1433–1438. — cited for completeness; inapplicable here (see §3).

---

## 13. Execution Checklist

**Phase 0 — Audit**
- [ ] List all DWG layer names; document any path/road layers in `docs/decisions.md`
- [ ] Read all three `.shp.points` GCP files; compare and select authoritative set
- [ ] Extract DXF entrance entities for buildings 1, 23, 24, 25, 26, 175, 210
- [ ] Confirm CRS of Buildings_Mask.shp and document as "working CRS"
- [ ] Verify WV-2 P001/P002/P003 all open correctly with rasterio

**Phase 1 — Coordinate Reconciliation**
- [ ] Fit PDF homography from GCPs; RMSE ≤ 5 map units
- [ ] Merge and reproject WV-2 tiles to working CRS for each of 3 passes
- [ ] Verify all rasters share same transform and shape in working CRS
- [ ] Document CRS EPSG code and any local/custom proj4 string

**Phase 2 — Crosswalk**
- [ ] Extract attribute table from Buildings_Mask.shp; note exact ID field name
- [ ] OCR typeset labels from PDF; validate > 80% match against spatial join
- [ ] Build crosswalk CSV with 1-to-many schema; document unresolved records
- [ ] Confirm DXF buildings match crosswalk entries by spatial overlay

**Phase 3 — Entrances**
- [ ] Extract DXF entrances and transform to working CRS (calibration set)
- [ ] Tune blue-mark HSV parameters against DXF-confirmed buildings
- [ ] Run PDF mark extraction site-wide
- [ ] Run attribute-derived entrance computation for all 342 chapels
- [ ] Generate per-chapel agreement analysis and QA contact sheet
- [ ] Output `data/processed/entrances.geojson` with all required fields

**Phase 4 — Cost Surface**
- [ ] Compute slope from DEM_Subset-Original.tif
- [ ] Implement and compare Tobler and Llobera–Sluckin cost outputs
- [ ] Rasterize building footprints as hard no-go mask
- [ ] Assemble composite cost with named, logged weights

**Phase 5 — WV-2 Spectral**
- [ ] Convert all WV-2 tiles DN → radiance using absCalFactor from .IMD files
- [ ] Apply DOS1 atmospheric correction per band per pass
- [ ] Coregister P001/P002/P003 to sub-pixel accuracy
- [ ] Compute CV per band and SPI composite; inspect visually for linear features
- [ ] Compute IOR and NDRE indices; overlay on orthoimage for QA
- [ ] Pan-sharpen at least P001 (highest tile count) to 0.46 m
- [ ] Run Frangi vesselness on pan-sharpened image

**Phase 6 — FETE**
- [ ] Project entrance points to raster pixel coordinates
- [ ] Run FETE over Tobler cost surface; generate movement potential raster
- [ ] Run FETE over Llobera–Sluckin cost surface for comparison
- [ ] Threshold, skeletonize, and vectorize to draft network

**Phase 7 — Circuit Model**
- [ ] Build conductance matrix from composite cost surface
- [ ] Run circuit solver (LGMRES with ILU preconditioner)
- [ ] Compare current density map to FETE density; note agreements/disagreements

**Phase 8 — Space Syntax**
- [ ] Generate free-space mask from building footprints
- [ ] Extract medial axis and fit axial lines
- [ ] Compute connectivity and integration using momepy
- [ ] Output integration raster for ensemble

**Phase 9 — Proximity Graphs**
- [ ] Compute Gabriel graph from entrance points
- [ ] Compute β-skeleton for β ∈ {1.0, 1.2, 1.5, 2.0}
- [ ] Identify which β aligns best with high-FETE-density corridors
- [ ] Compute Steiner tree as parsimonious bound

**Phase 10 — Ensemble**
- [ ] Normalize all 5 evidence rasters to [0,1]
- [ ] Compute weighted ensemble with documented weights
- [ ] Run AUC test of SPI against modelled network
- [ ] Generate per-segment confidence fields in final GeoJSON

**Phase 11 — Validation**
- [ ] Entrance coverage: % of entrances within 3 pixels of a network segment
- [ ] No-go violations: 0 allowed
- [ ] Cross-method Spearman correlations: log all pairs
- [ ] Graph topology checks: degree distribution, betweenness, planarity
- [ ] Literature anchors: chapel 25, 80, 180 proximity to high-confidence segments

**Phase 12 — Final Outputs**
- [ ] `outputs/path_network.geojson` — confidence-scored vector network
- [ ] `outputs/movement_potential.tif` — FETE density raster
- [ ] `outputs/spectral_path_indicator.tif` — SPI raster
- [ ] `outputs/confidence_report.md` — auto-generated per-segment summary
- [ ] `outputs/figures/` — overlays on orthoimage and original annotated site plan PDF
- [ ] `docs/decisions.md` — complete log of parameter choices, dead ends, and revisions