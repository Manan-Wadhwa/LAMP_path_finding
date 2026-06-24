# El-Bagawat Necropolis — Full-Site Movement & Path Reconstruction

**Project codename:** `task2` (successor to the 3-entrance pilot `task1`)
**Goal:** Computationally reconstruct the most plausible real pedestrian path/street network connecting all 260+ chapel buildings of the El-Bagawat necropolis, generalizing the `task1.ipynb` MaxEnt-IRL pilot from 3 hand-picked entrances to the full site.

---

## Table of Contents

1. [Project Brief](#1-project-brief)
2. [What You Actually Have](#2-what-you-actually-have-data-inventory)
3. [The Four Hard Problems](#3-the-four-hard-problems)
4. [Why This Is a Real, Solvable Question](#4-why-this-is-a-real-solvable-question-not-just-an-exercise)
5. [Proposed Repository Structure](#5-proposed-repository-structure)
6. [The Plan: Phase by Phase](#6-the-plan-phase-by-phase)
7. [Methodological Toolkit](#7-methodological-toolkit-the-different-techniques)
8. [Notebook / Script Map](#8-notebook--script-map)
9. [Code Skeletons (Appendix A)](#9-code-skeletons-appendix-a)
10. [Validation & Confidence Scoring](#10-validation--confidence-scoring)
11. [Risks, Assumptions, Open Questions](#11-risks-assumptions-open-questions)
12. [Glossary](#12-glossary)
13. [References](#13-references)
14. [Execution Checklist](#14-execution-checklist)

---

## 1. Project Brief

### 1.1 Where this started
`task1` worked with a tiny, clean slice of the site: 3 buildings, their entrances marked by hand, a DEM, and an orthoimage. The pilot used **Maximum Entropy Inverse Reinforcement Learning (MaxEnt IRL)** to learn an implicit "movement cost function" from terrain, then generated plausible connecting paths between the 3 marked entrances (M0, M1, M2). That is the result you have in the preliminary investigation screenshots — three panels (NDVI-like surface, slope/hillshade surface, orthoimage with footprints) all showing the same learned route.

### 1.2 What changed
You now have (or can get):
- The **full `BuildingFootprints` layer** for 260+ structures (not 3).
- A **hand-annotated `Site_Plan.pdf`**, marked in light-blue pen, with entrance ticks on most/all buildings.
- A **342-chapel relational database** (Excel, 3 sheets) with typology, facade style, orientation, and condition for every chapel — including a field that matters enormously: **recorded entrance direction** (N/S/E/W).
- No absolute geographic coordinates (no lat/long) — only locally consistent raster/vector layers.

### 1.3 The actual research question
Not "draw a line between two points." The real question is:

> **Given terrain, obstacles, and 260+ known building entrances, what is the most probable historical network of streets and alleyways connecting them — and how confident can we be in each segment?**

This is a known archaeological sub-field (GIS movement/accessibility modeling), not something being invented from scratch. Section 4 grounds this in the actual published literature on El-Bagawat and in the established "off-path reconstruction" methods used elsewhere in landscape archaeology. That matters: you're not just running an ML pilot at scale, you're doing a recognized class of analysis, which means there are established techniques, failure modes, and validation strategies you can borrow instead of reinventing.

### 1.4 Definition of "done"
A successful outcome is **not** a single deterministic line drawing. It is:

1. A **vector network** (GeoJSON/Shapefile) of hypothesized route segments connecting all entrances, each segment tagged with a **confidence score**.
2. A **movement-potential / path-density raster** showing where corridors converge (the byproduct of the FETE method, see §7) — visually, this is the "heat map" version of "the real paths."
3. A short **per-method comparison** (deterministic least-cost paths vs. IRL-learned vs. any direct trace detection) so disagreement between methods is visible, not hidden.
4. A **crosswalk table** reconciling building/footprint IDs across the shapefile, the Excel database, and the site-plan labels — this is a deliverable in its own right, because without it nothing else is trustworthy at scale.
5. A documented list of chapels/areas where the model is **not confident**, flagged for ground-truthing or manual review — not a system that pretends a a flat, "true" answer for everything.

---

## 2. What You Actually Have (Data Inventory)

### 2.1 Pilot dataset (from `original-tree.txt`)

| File | Format | Role | Notes |
|---|---|---|---|
| `BuildingFootprints.shp/.dbf/.shx/.prj/.cpg` | ESRI Shapefile | Building polygons (pilot subset) | `.prj` exists → it already has *a* CRS, even if you don't know the real-world lat/long. That's fine — see §3.1. |
| `DEM_Subset-Original.tif` (+`.aux.xml`) | GeoTIFF | Bare-earth elevation | Use for slope/aspect cost layer. |
| `DEM_Subset-WithBuildings.tif` (+`.aux.xml`) | GeoTIFF | Elevation *with* structures present | **Underused asset.** `WithBuildings − Original` gives you a building-height/obstruction mask almost for free — don't skip this. |
| `SAR-MS.tif` (+`.aux.xml`) | GeoTIFF, multi-band, 130 KB→ larger than other rasters | Synthetic Aperture Radar, multispectral | Candidate source of **direct physical evidence** of old paths (soil compaction/disturbance can show up in SAR backscatter). High-value, unexplored in the pilot. |
| `OrthoImage_Subset.tif` (+`.aux.xml`) | GeoTIFF | Visual base layer | Useful for QA, eyeballing, and possibly visible faint trail traces. |
| `Marks_Brief1.shp` (+ companions) | ESRI Shapefile, tiny (292 bytes shp) | The 3 hand-marked entrance points from the pilot | This is your **only existing ground-truth digitized entrance set** — treat it as a calibration/validation set for the full-site entrance-extraction pipeline (§6, Phase 3). |
| `Site_Map_With_ROI.png` | Raster image | Site overview with region-of-interest highlighted | Context image. |
| `Site_Plan.pdf` | PDF | Vector/scanned site plan | At full-site scale, **this is now hand-annotated** with light-blue entrance ticks (per your description and the screenshot). |
| `README.md` | text | Pilot's own documentation | Read this first — it should describe what CRS/units the pilot actually used, which the new pipeline must match or explicitly re-derive. |

### 2.2 New full-site data
- **Full `BuildingFootprints` layer**, 260+ polygons, presumably same schema/CRS family as the pilot subset (verify, don't assume).
- **`Site_Plan.pdf`, hand-marked**: light-blue pen ticks near most buildings, indicating entrance location/side. This is a *manual digitization task waiting to happen* — see Phase 3.
- **Excel workbook, 3 sheets:**
  - **`Sheet4`** — classification legends: 10 architectural types, 7 facade types, each with a text description. This is a **lookup/dimension table**, not building-level data.
  - **`Database Full`** — 342 chapel records. Per-chapel fields include: architectural type, facade type, chamber count, pilasters, burial pits, niches, light apertures, paintings/graffiti, preservation notes, and — critically — **entrance direction** (recorded as compass orientation, aggregated as South ~84–91, East ~60–62, West ~59–62 in your summaries).
  - **`Building Assignments`** — a project-management sheet (who is modeling/texturing which chapel), not spatial data, but useful for prioritization (§6, Phase 9) and as a secondary ID list to reconcile against.

### 2.3 What's missing / must be resolved, not assumed
- **No absolute lat/long.** Not actually a blocker (see §3.1) — but means you cannot just "drop pins on Google Earth" without an extra georeferencing step, and any output claiming WGS84 coordinates needs that step done first and flagged as approximate.
- **No common building ID across PDF labels / shapefile attributes / Excel chapel numbers**, *and published literature uses yet another numbering scheme* — confirmed independently: external sources (NASSCAL) cite the "Exodus Chapel" as chapel no. 30 and "Peace Chapel" as chapel no. 80, while your own summary lists chapel 25 as the Peace Chapel and chapel 80 as the Exodus Chapel. Two respected sources disagree on what "chapel 80" even is. **Conclusion: do not import any external numbering as ground truth. Build the crosswalk only from internal cross-references inside your own three sources** (shapefile attribute table ↔ Excel `Database Full` ↔ Site_Plan.pdf labels). See Phase 2.
- **260+ footprints vs. 342 database chapels.** These are not the same count for a structural reason, not an error: many buildings at El-Bagawat are multi-chamber (the Excel typology itself lists "two-chambered buildings with a dome in the first chamber and an apse in the second" as a defined type). Expect a **one-to-many relationship**: one footprint polygon ↔ multiple chapel/chamber records. Design the crosswalk schema for this from day one; don't force a 1:1 join and silently drop rows.
- **No demonstrated/observed paths at full-site scale** — the pilot's 3-point result was itself a *model output*, not an excavated ground truth. At 260+ buildings you have zero direct trail observations unless SAR or the orthoimage reveals something. Treat "real paths" as a confidence-scored hypothesis, not a retrievable fact (this shapes the validation philosophy in §10).

---

## 3. The Four Hard Problems

| # | Problem | Why it matters | Resolution strategy |
|---|---|---|---|
| 1 | **No absolute georeference** | You can't naively trust "lat/long" anywhere, and `Site_Plan.pdf` (a drawn/scanned plan) isn't natively in the same coordinate space as the GeoTIFFs/shapefile | Don't chase real-world coordinates. Define one **local working CRS** anchored to the existing shapefile `.prj`, and georeference everything else (especially the PDF) *into* that local frame using control points, not external geodesy. (Phase 1) |
| 2 | **Three incompatible ID systems** (+ a fourth from outside literature that you must ignore) | Without reconciled IDs, "chapel 25" in the Excel might not be polygon 25 in the shapefile or label "25" on the plan | Build an explicit, versioned **crosswalk table**, validated by spot-checks, supporting 1-to-many footprint↔chapel links. (Phase 2) |
| 3 | **Entrances are only hand-marked for some buildings (manually, on a PDF), not encoded for all 260+** | Manual digitization of 260+ marks is slow and error-prone; pure attribute-based inference might miss nuance the hand marks capture | **Hybrid pipeline**: color-threshold the hand marks where they exist (ground truth) + auto-derive a candidate entrance point for every chapel from footprint geometry × the Excel's recorded entrance-direction field (this gets you 100% coverage even where nobody drew a tick) + reconcile and flag disagreements for manual QA. (Phase 3) |
| 4 | **Scaling a 3-node pilot to 260+ nodes** | Pairwise route computation is *not* simply "run task1 N² times" — it's a different problem class (network inference, not point-to-point pathing) | Adopt the **From-Everywhere-To-Everywhere (FETE)** / cumulative cost-path family of methods from landscape archaeology, generalize MaxEnt IRL to learn feature weights rather than a single path, and use multi-source shortest-path algorithms so cost is computed once per node, not once per pair. (Phase 5–7) |

---

## 4. Why This Is a Real, Solvable Question (Not Just an Exercise)

A few things came back from background research that materially change how you should think about this project — worth knowing before you write a line of code:

- **The premise is archaeologically real, not invented.** El-Bagawat is consistently described in the literature as a settlement-like necropolis where chapels are arranged along **streets and interconnecting narrow alleyways** — it's informally called one of the earliest "cities of the dead." That means you're not hunting for *desire lines* that may or may not exist; you're trying to recover an attested but unmapped street plan. That reframes the project from "infer paths from terrain alone" to "infer paths from terrain **and the fact that this was a planned/organic settlement layout**" — clustering, hierarchy of routes (main streets vs. spurs to single chapels), and shared walls/alignment between adjacent chapels are all legitimate signals.
- **The canonical academic survey is Fakhry's 1951 monograph**, which counted 263 chapels — strikingly close to your "over 260 buildings" footprint count. Your 342-chapel database is larger, almost certainly because it counts at the chamber/chapel level rather than the footprint/building level (consistent with the one-to-many issue flagged in §2.3), or because later surveys identified additional structures. Either way, this is good external corroboration that your footprint layer is at the *building* granularity and your Excel database is at the *chapel/chamber* granularity — keep that distinction explicit in the schema.
- **Chapel 180 is independently documented as the large central courtyard building, frequently described in the literature as the necropolis's principal church**, occupying a commanding position in the middle of the site. This lines up with what's visible in your full-site overlay image (the large rectangular structure flagged inside the red ROI). This is a perfect **named anchor node** — in any "city of the dead" reading of the site, the main church and the site's main approach point are exactly the kind of high-betweenness nodes that real path networks converge on. Treat it (and any comparable large/central structure) as a priority anchor in the network analysis, not just one node among 260.
- **There is an established methodological family for exactly this problem** in landscape archaeology: cost-surface movement modeling, least-cost paths (LCP), and — most relevant to "scaling up" — **From-Everywhere-To-Everywhere (FETE)** analysis, independently developed under that name by White & Barber (2012) and as "cumulative cost path" modeling by Verhagen (2013), building on movement-potential work by Llobera (2000) and focal mobility networks by Llobera et al. (2011) / Fábrega-Álvarez (2006). White & Barber specifically validated FETE-derived corridors against **known** precolonial and colonial-era movement corridors in Oaxaca, Mexico, and found the method effective — this is the closest published analogue to what you're trying to do, and it's worth reading directly (full citation in §13). You are not improvising a method; you're applying a validated one.

This context should shape tone: the README below treats this as a serious (if compute-heavy) GIS/ML research pipeline, not a toy script.

---

## 5. Proposed Repository Structure

```
necropolis-paths/
├── README.md                      ← this file
├── environment.yml                ← conda env (see Phase 0)
├── data/
│   ├── raw/                       ← untouched originals (shp, tif, xlsx, pdf) — read-only
│   ├── interim/                   ← intermediate outputs (rasterized PDF, masks, etc.)
│   ├── processed/                 ← final, analysis-ready layers
│   └── crosswalk/
│       └── building_id_crosswalk.csv
├── notebooks/
│   ├── 00_data_audit.ipynb
│   ├── 01_coordinate_alignment.ipynb
│   ├── 02_id_crosswalk.ipynb
│   ├── 03_entrance_extraction.ipynb
│   ├── 04_cost_surface.ipynb
│   ├── 05_irl_reward_learning.ipynb
│   ├── 06_fete_network.ipynb
│   ├── 07_complementary_methods.ipynb
│   ├── 08_validation_and_confidence.ipynb
│   └── 09_final_outputs_and_maps.ipynb
├── src/
│   ├── geo.py                     ← CRS/alignment helpers
│   ├── crosswalk.py
│   ├── entrances.py               ← color-threshold + attribute-driven extraction
│   ├── cost_surface.py
│   ├── irl.py
│   ├── network.py                 ← FETE / cost-distance / skeletonization
│   └── viz.py
├── outputs/
│   ├── path_network.geojson
│   ├── movement_potential.tif
│   ├── confidence_report.md
│   └── figures/
└── docs/
    └── method_notes.md            ← running lab notebook of decisions, tuning, dead ends
```

This mirrors and extends the pilot's structure (it had its own `README.md`, a notebook, shapefiles, rasters) so the two repos stay legible side by side.

---

## 6. The Plan: Phase by Phase

### Phase 0 — Environment & Tooling
Set up once, use everywhere.

| Library | Purpose |
|---|---|
| `geopandas`, `shapely`, `fiona` | Vector handling (footprints, crosswalk, output network) |
| `rasterio`, `rasterio.mask` | Reading/writing/aligning GeoTIFFs |
| `numpy`, `scipy` | Numerical work, cost-distance via `scipy.sparse.csgraph` or grid Dijkstra |
| `scikit-image` (`skimage.graph.MCP_Geometric`, `skimage.morphology.skeletonize`) | Cost-distance shortest paths on rasters; network skeletonization |
| `networkx` | Graph construction, Steiner-tree-style pruning, centrality analysis |
| `opencv-python` (`cv2`) | Color thresholding on rasterized PDF, morphology, connected components |
| `PyMuPDF` (`fitz`) or `pdf2image` + Poppler | Rasterize `Site_Plan.pdf` at high DPI for digitization |
| `pandas`, `openpyxl` | Excel workbook ingestion |
| `matplotlib`, `plotly` | Visualization / QA maps |
| (optional) `torch` | Only if you go beyond classical MaxEnt IRL into a learned/neural reward model, or want a CNN trail-detector on SAR/Ortho (§7) |

Compute isn't the constraint here — correctness of the geometry and IDs is. Spend disproportionate time on Phases 1–2 before touching anything ML-flavored.

### Phase 1 — Coordinate Reconciliation
**Goal:** one consistent local coordinate system that every layer can be read into, even without true lat/long.

1. Inspect the existing `BuildingFootprints.prj` — it almost certainly already encodes *some* CRS (even if "fake"/local). Read it with `pyproj`/`rasterio.crs` rather than assuming.
2. Check whether `DEM_*.tif`, `SAR-MS.tif`, `OrthoImage_Subset.tif` share that CRS and a consistent pixel grid/transform. If they were exported together by the original survey team, they probably already align — verify with `rasterio`'s `.crs` and `.transform`, don't assume from filenames.
3. **`Site_Plan.pdf` is the odd one out** — it's a drawn/scanned plan, not a native geo-raster. Georeference it into the working CRS:
   - Identify ≥4 well-distributed **control points**: buildings whose footprint is unambiguous in both the PDF and the shapefile/orthoimage (corners of distinctive large structures, e.g. building 180, work well).
   - Fit an affine or low-order polynomial transform (`cv2.findHomography`, or QGIS Georeferencer if you prefer a GUI pass) from PDF pixel space → working CRS.
   - Apply it to every digitized point/mark extracted from the PDF in Phase 3.
4. Document the chosen CRS (even if it's "arbitrary local meters, origin = SW corner of BuildingFootprints bounding box") in `docs/method_notes.md`. Real-world lat/long can be back-derived later *if* a single trusted GPS tie-point ever turns up — don't block on it now.

### Phase 2 — Building ID Crosswalk
**Goal:** a single authoritative table mapping footprint ID ↔ chapel ID(s) ↔ plan label, with explicit support for one-to-many.

1. Extract the attribute table from `BuildingFootprints.shp` (`geopandas.read_file`) — note whatever ID field it uses.
2. Extract the chapel number column from `Database Full`.
3. OCR or manually transcribe the plan's printed building numbers from `Site_Plan.pdf` (the numbers are typeset, not hand-drawn, so OCR — e.g. `pytesseract` — should work reasonably well; validate against a manual sample).
4. Join in **multiple passes**, not one big fuzzy match:
   - Exact ID match first (cheap wins).
   - Spatial join second: if footprint centroids and plan label positions are in the same local CRS (post Phase 1), a nearest-label-to-polygon join resolves most of the rest.
   - Manual resolution for the remainder — there will be a remainder, budget for it.
5. Schema: `footprint_id | chapel_id | plan_label | match_method | match_confidence`. Allow multiple `chapel_id` rows per `footprint_id`.
6. **Do not** pull in Fakhry/NASSCAL/Wikipedia chapel numbers as a fourth ID system — confirmed above that external literature numbering disagrees with itself across sources. Keep the crosswalk self-contained to your three internal sources; only cite literature for qualitative/narrative validation (Phase 8), never for ID resolution.

### Phase 3 — Entrance Point Extraction (Hybrid)
**Goal:** one entrance coordinate (and ideally a cardinal side) per chapel, for all 342 — not just the ones someone drew on.

**3a. Digitize the hand-marked PDF (ground truth where it exists)**
- Rasterize `Site_Plan.pdf` at 300–600 DPI (`fitz`/`pdf2image`).
- Convert to HSV; threshold the specific light-blue hue band used in the pen marks (tune empirically — sample a few known marks first to get the exact H/S/V window rather than guessing).
- Morphological close → connected-component analysis → centroid of each mark = a candidate digitized entrance point in PDF pixel space.
- Transform into the working CRS using the Phase-1 georeferencing.
- Associate each mark with the nearest footprint polygon (Phase 2 crosswalk) and record which **side/wall** of the polygon it sits closest to → gives a cardinal direction.

**3b. Attribute-driven inference (covers everything not hand-marked)**
- For every chapel with a recorded **entrance direction** in `Database Full` (the South/East/West majority you already summarized), compute the midpoint of the corresponding wall/edge of its footprint polygon programmatically (`shapely`: take the polygon's minimum rotated rectangle or its actual edges, pick the edge whose outward normal best matches the recorded compass direction, take its midpoint).
- This alone gives you a candidate entrance for the large majority of the 342 chapels with **zero manual digitization**.

**3c. Cross-validate 3a vs 3b**
- On the subset of buildings where both a hand mark and a derived-from-direction point exist, measure agreement (distance between the two candidate points, agreement on cardinal side).
- Use this to (i) sanity-check the color-threshold tuning in 3a, (ii) sanity-check the edge-selection logic in 3b, (iii) produce a per-building confidence flag.

**3d. Manual QA pass**
- Auto-generate a QA sheet/contact-sheet: for every chapel where 3a and 3b disagree, or where 3b had no direction recorded, render a small crop of the footprint + both candidate points for a 30-second human glance. Don't try to automate away every edge case — flag and move on.

Output: `data/processed/entrances.geojson` — point layer, one (or more, for multi-chamber buildings) entrance per chapel, with `source` (`hand_mark` / `attribute_derived` / `manual`) and `confidence`.

### Phase 4 — Cost-Surface / Movement-Feature Engineering
**Goal:** a raster (or stack of rasters) expressing how "expensive" it is to move through each cell — the substrate every path-finding method downstream depends on.

- **Slope/aspect** from `DEM_Subset-Original.tif`. Convert slope to a movement-cost using either:
  - **Tobler's hiking function** (Tobler 1993): walking speed `W = 6·exp(−3.5·|S + 0.05|)` km/h, where `S` = slope (rise/run); invert to cost = time/distance. Simple, widely used, asymmetric uphill/downhill.
  - **Llobera & Sluckin's (2007) quadratic energy-expenditure cost function** — derived from biomechanical energy models, also asymmetric, and specifically shown to perform well reconstructing real (Roman) roads in follow-up studies. Worth implementing both and comparing; they don't always agree.
  - Use an **8-, 16-, or 48-neighbourhood** movement kernel rather than the naive 4/8-connected default — Harris (2000) showed a 48-neighbourhood kernel keeps the path-length distortion versus the true optimum under ~1.4%, materially better than a plain 8-connected grid. `skimage.graph.MCP_Geometric` and most cost-distance implementations let you control connectivity.
- **Building obstruction mask**: difference `DEM_Subset-WithBuildings.tif − DEM_Subset-Original.tif` to get structure footprints/heights almost for free; rasterize `BuildingFootprints` directly as a hard "no-go" mask (infinite cost) so no computed path is ever allowed to cut through a wall.
- **SAR-MS exploration** (don't skip — this is your best shot at *direct* evidence rather than inference): inspect each band for linear, low-relief anomalies that could represent compacted ground/old paths. Try edge detection, ridge/vesselness filters (`skimage.filters.frangi`, tuned for thin linear features instead of vessels), or simple visual diffing against the orthoimage. If anything plausible turns up, this becomes a *demonstration trajectory* for Phase 5, not just a cost-layer input.
- **Node-importance weighting** (optional but well-motivated): use the Excel typology/condition fields to weight nodes — e.g., chapels with elaborate facades, paintings, or known significance (Peace/Exodus chapels, chapel 180) plausibly sat on primary routes more often than small undecorated single-chamber chapels. Encode as a small attractive-cost discount near high-importance nodes, not as a hard constraint.
- Combine into a single weighted multi-band cost raster; keep weights as named, tunable parameters (`src/cost_surface.py`), not hardcoded magic numbers — you'll be retuning this constantly in Phase 5–6.

### Phase 5 — Reward Learning (Generalizing the MaxEnt IRL Pilot)
**Goal:** stop hand-tuning cost weights; learn them from whatever plausible/observed routes you have.

- Treat the pilot's 3-point learned path, plus any SAR/ortho trace evidence from Phase 4, as **demonstration trajectories**.
- Re-run MaxEnt IRL (Ziebart et al.'s formulation, as in the pilot) over the **multi-feature** cost surface from Phase 4 rather than slope alone — recover feature weights, not just a single path.
- Sanity-check the learned reward: paths should never cross a building mask cell, should generally avoid steep slopes, and should look at least as good as the deterministic baseline from Phase 6 on held-out demonstration segments.
- If you have very few demonstrations (likely, at first — maybe just the 3-point pilot result), don't over-trust the learned weights yet; treat Phase 5's output as *one candidate weighting* to be compared against the literature-informed deterministic weighting (Tobler/Llobera-Sluckin) from Phase 4, not as the final answer. More demonstrations (from SAR finds, or from manual archaeological judgment on a larger sample) make this phase more trustworthy over time.

### Phase 6 — Full Network Generation (FETE / Cost-Distance)
**Goal:** generalize from "a path between 2 points" to "the network connecting 260+ points."

- **Don't** compute pairwise least-cost paths naively (~33,670 pairs for 260 nodes) by running point-to-point search 33,670 times. Instead:
  - Run a **multi-source accumulated-cost-distance** computation **once per node** (260 runs of Dijkstra/`MCP_Geometric` from each entrance over the Phase-4/5 cost raster) — this is the standard, much cheaper way to get all pairwise least-cost paths, and is well within "compute is not an issue" territory.
  - This is exactly the **FETE (From-Everywhere-To-Everywhere)** approach (White & Barber 2012) / "cumulative cost path" modeling (Verhagen 2013): generate least-cost paths between a dense set of points and look at where they **concentrate**, rather than trusting any single path.
- **Aggregate into a movement-potential / path-density raster**: for every cell, count how many of the pairwise LCPs pass through it. High-density cells = corridors with strong, convergent support across many origin-destination pairs = your best candidate for "real path." This density-as-probability-of-movement idea is the core insight from Llobera (2000) and the wider movement-potential literature (§13).
- **Vectorize**: threshold the density raster, skeletonize (`skimage.morphology.skeletonize`) to a 1-pixel-wide centerline network, then convert to a `networkx` graph and simplify (collapse degree-2 chains into single edges, snap stray spurs).
- **Optional refinement — Steiner-tree-style pruning**: if the raw FETE network is messier/denser than a real street plan would be, compute a minimum-cost connected subgraph (Steiner tree heuristic) spanning all 342 chapel entrances plus the anchor nodes — gives a cleaner "minimum necessary network" hypothesis to compare against the raw density map.

### Phase 7 — Complementary Techniques (the "different techniques" ask)
Run at least one of these alongside Phases 5–6, both for triangulation and because each captures something the cost-distance approach can't:

- **Space syntax / visibility-graph analysis**: compute intervisibility or axial accessibility between chapels; in a planned "city of the dead," major routes plausibly favored visibility/legibility, not just least physical effort. Complements pure terrain-cost reasoning.
- **Agent-based / stochastic movement simulation**: simulate many synthetic "pilgrims" performing cost-biased random walks across the site between plausible origin/destination pairs (e.g., site entrance → chapel 180 → individual chapels); aggregate their tracks the same way as Phase 6's density map. More expensive, more realistic about route variability than a single deterministic LCP per pair.
- **Direct trace detection from imagery**: revisit `SAR-MS.tif` and `OrthoImage_Subset.tif` with dedicated linear-feature detectors (Hough transform, Frangi/ridge filters, or — given "compute is not an issue" — a small CNN segmentation model fine-tuned to detect faint trail-like features) purely as an independent evidence source, not derived from the cost surface at all.
- **Network-topology cross-check**: once Phase 6 produces a candidate network, compute basic graph statistics (degree distribution, betweenness centrality) and check whether they look like a real street network (a few high-betweenness "trunk" routes, many low-degree spurs to individual chapels) rather than an unstructured mesh — real settlement path networks are rarely uniform.

Where methods agree, confidence goes up. Where they disagree, that disagreement *is* useful information (§10), not noise to be averaged away.

### Phase 8 — Validation
See §10 for the full framework. In short: literature-described "streets and alleyways," internal consistency between hand-marked and attribute-derived entrances, agreement across Phase 5–7 methods, and graph-topology plausibility, used together — there is no single ground-truth path layer to check against, so don't design the pipeline as if there will be one.

### Phase 9 — Deliverables & Visualization
- `outputs/path_network.geojson` — the network, confidence-scored per segment.
- `outputs/movement_potential.tif` — the density/heat-map raster.
- `outputs/confidence_report.md` — auto-generated summary: per-chapel entrance source/confidence, per-segment method agreement, flagged QA items.
- Figures: overlay of the network on the orthoimage and on the hand-marked `Site_Plan.pdf`, for direct visual sanity-checking against the original annotations.
- Cross-reference against `Building Assignments` to prioritize which chapels' modeling/texturing work (Josh A., Cam, Kit, Julianne, etc.) should be sequenced near high-confidence main routes first, since those are likely the most archaeologically/visually significant approach corridors.

---

## 7. Methodological Toolkit (the "different techniques")

| Technique | Answers | Strengths | Weaknesses | Key tools/refs |
|---|---|---|---|---|
| **Least-Cost Path (LCP)** | Cheapest route between 2 specific points | Simple, fast, deterministic, well-understood | Only as good as the cost function; gives one path, no uncertainty | `skimage.graph`, Tobler (1993), Harris (2000) |
| **FETE / cumulative cost-path** | Where do many plausible routes converge across the whole site | Doesn't need pre-chosen O/D pairs; directly gives a network, not just a line; validated elsewhere against known historical routes | Computationally heavier (mitigated: multi-source Dijkstra, not pairwise); density threshold choice is subjective | White & Barber (2012), Verhagen (2013) |
| **Movement-potential / focal mobility networks** | Same idea as FETE from a different angle — accumulated cost at multiple scales | Multi-scale (local/regional/global) reading of the same surface | Conceptually similar to FETE, mostly a complementary lens, not a separate result | Llobera (2000), Llobera et al. (2011), Fábrega-Álvarez (2006) |
| **MaxEnt IRL** | What cost-function weights best explain *observed/assumed* good paths | Learns weights instead of guessing them; directly extends the pilot | Needs demonstration trajectories — you have very few right now | Ziebart et al. 2008 (general method); your `task1.ipynb` |
| **Space syntax / visibility graphs** | Which routes are most legible/visible, independent of terrain effort | Captures a different (social/perceptual) logic of movement that pure terrain-cost misses | Computationally heavy at full-viewshed scale; less standard tooling | Llobera (2003) (total viewshed) |
| **Agent-based stochastic simulation** | Plausible *range* of routes, not just the optimum | Naturally produces uncertainty/variability instead of one deterministic answer | Slower, more parameters to justify | General ABM literature; same cost surface as LCP |
| **Direct imagery trace detection (SAR/Ortho)** | Is there physical evidence of a path right now | Independent of all modeling assumptions — actual evidence if found | May find nothing (preservation-dependent); needs careful tuning to avoid false positives | `skimage.filters.frangi`, Hough transform, optional CNN |
| **Steiner-tree network pruning** | The minimal connected network spanning all entrances | Clean, parsimonious hypothesis; good contrast against the "messy" density map | Real streets aren't always minimal — useful as a bound, not a final answer | `networkx` Steiner approximations |

---

## 8. Notebook / Script Map

| Notebook | Depends on | Produces |
|---|---|---|
| `00_data_audit.ipynb` | raw data | sanity report: CRS, extents, attribute schemas, row counts |
| `01_coordinate_alignment.ipynb` | `00` | unified working CRS, georeferenced `Site_Plan.pdf` control-point transform |
| `02_id_crosswalk.ipynb` | `01` | `data/crosswalk/building_id_crosswalk.csv` |
| `03_entrance_extraction.ipynb` | `01`, `02` | `data/processed/entrances.geojson` |
| `04_cost_surface.ipynb` | `01` | `data/processed/cost_surface.tif` (multi-band) |
| `05_irl_reward_learning.ipynb` | `04`, pilot demos | learned feature weights |
| `06_fete_network.ipynb` | `03`, `04`/`05` | `outputs/movement_potential.tif`, draft network |
| `07_complementary_methods.ipynb` | `03`, `04` | space-syntax / ABM / trace-detection outputs |
| `08_validation_and_confidence.ipynb` | `06`, `07` | `outputs/confidence_report.md` |
| `09_final_outputs_and_maps.ipynb` | all | final figures, `outputs/path_network.geojson` |

---

## 9. Code Skeletons (Appendix A)

> These are starting scaffolds, not finished code — paths/column names are placeholders until Phase 0–2 confirm the real schema.

**A. Rasterize and color-threshold the hand-marked PDF**
```python
import fitz  # PyMuPDF
import cv2
import numpy as np

def rasterize_pdf(path, dpi=400):
    doc = fitz.open(path)
    page = doc[0]
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return img[:, :, :3]  # drop alpha if present

def find_blue_marks(img_rgb, h_range=(85, 110), s_min=60, v_min=80):
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, (h_range[0], s_min, v_min), (h_range[1], 255, 255))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    return centroids[1:], stats[1:]  # skip background label 0
```
*Tune `h_range`/`s_min`/`v_min` empirically against a handful of known marks before running on the whole plan.*

**B. Attribute-driven entrance point from recorded direction**
```python
from shapely.geometry import Point
import numpy as np

DIRECTION_VECTORS = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}

def entrance_from_direction(polygon, direction):
    centroid = polygon.centroid
    target_vec = np.array(DIRECTION_VECTORS[direction])
    coords = list(polygon.exterior.coords)
    best_mid, best_score = None, -np.inf
    for a, b in zip(coords[:-1], coords[1:]):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        normal = np.array([mid[0] - centroid.x, mid[1] - centroid.y])
        normal = normal / (np.linalg.norm(normal) + 1e-9)
        score = np.dot(normal, target_vec)
        if score > best_score:
            best_score, best_mid = score, mid
    return Point(best_mid)
```

**C. Multi-source cost-distance (the FETE engine)**
```python
from skimage.graph import MCP_Geometric
import numpy as np

def all_pairs_density(cost_raster, node_pixels):
    """node_pixels: list of (row, col) entrance locations in raster space."""
    density = np.zeros_like(cost_raster, dtype=float)
    for src in node_pixels:
        mcp = MCP_Geometric(cost_raster, fully_connected=True)
        costs, traceback = mcp.find_costs([src])
        for dst in node_pixels:
            if dst == src:
                continue
            path = mcp.traceback(dst)
            for (r, c) in path:
                density[r, c] += 1
    return density
```
*This is O(N) cost-distance computations, not O(N²) point-to-point searches — feasible for N≈260–342 even on modest hardware.*

**D. Tobler's hiking-function cost from slope**
```python
import numpy as np

def tobler_cost(slope_rise_over_run):
    speed_kmh = 6 * np.exp(-3.5 * np.abs(slope_rise_over_run + 0.05))
    return 1.0 / np.maximum(speed_kmh, 1e-6)  # cost = time per unit distance
```

**E. Skeletonize density raster into a graph**
```python
from skimage.morphology import skeletonize
import networkx as nx
import numpy as np

def density_to_graph(density, threshold):
    binary = density > threshold
    skel = skeletonize(binary)
    G = nx.Graph()
    rows, cols = np.where(skel)
    coords = set(zip(rows, cols))
    for r, c in coords:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if (dr, dc) != (0, 0) and (r + dr, c + dc) in coords:
                    G.add_edge((r, c), (r + dr, c + dc))
    return G
```

---

## 10. Validation & Confidence Scoring

There is **no excavated ground-truth path layer** for this site at full scale — be explicit about that instead of implying false certainty. Build confidence from **triangulation**, not from a single check:

1. **Internal consistency** — Phase 3c agreement between hand-marked and attribute-derived entrances (per chapel).
2. **Cross-method agreement** — does the FETE density map, the IRL-weighted version, and any space-syntax/ABM result (Phase 7) all favor the same corridors? Segments that all three agree on are high confidence; segments only one method supports are flagged, not discarded.
3. **Physical evidence** — anything found via direct SAR/ortho trace detection (Phase 4/7) should outrank purely modeled segments when present.
4. **Literature plausibility** — the documented "streets and alleyways" framing, and named anchor points like chapel 180's central church role, give a qualitative check: does the network look like a settlement plan (a few trunk routes + spurs) rather than an undifferentiated mesh?
5. **Topological sanity** — every chapel entrance should connect to the network (no orphan nodes); no segment should cross a building mask cell; degree/betweenness distribution should look "street-like."

Publish a per-segment confidence score (e.g., 0–1, weighted combination of the above) rather than a binary "real/not real" — this is the honest output for a hypothesis-generation tool meant to guide further (eventually physical) verification, not a replacement for it.

---

## 11. Risks, Assumptions, Open Questions

- **Assumption:** the existing shapefile `.prj` and the raster CRSs are mutually consistent. *Verify in Phase 0 — don't assume from the pilot working once.*
- **Risk:** light-blue pen color may not threshold cleanly against scan artifacts, shadows, or other ink colors on `Site_Plan.pdf`. *Mitigation: tune per a manually-labeled subsample before running site-wide; keep a manual-override path open.*
- **Risk:** SAR-MS may simply not have the resolution/wavelength characteristics to show centuries-old compacted paths. *Don't over-invest before a quick exploratory pass confirms there's signal worth pursuing.*
- **Open question:** does `Building Assignments`' student/chapel list overlap meaningfully with priority/high-traffic chapels (Exodus, Peace, 180, 210/211)? If so, that's a natural sequencing signal for which parts of the network to validate first.
- **Open question:** how many demonstration trajectories will actually be available for IRL (Phase 5) beyond the original 3-point pilot? If the answer stays "very few," weight the deterministic Tobler/Llobera-Sluckin cost surface more heavily than the learned one in the final ensemble.
- **Known external-data trap:** do not pull in Fakhry/NASSCAL/Wikipedia chapel numbering as if it matches your dataset's chapel numbers — confirmed they don't agree with each other, let alone with your specific database.

---

## 12. Glossary

- **MaxEnt IRL** — Maximum Entropy Inverse Reinforcement Learning: recovers an implicit reward/cost function from example behavior (here, example "good" paths), instead of requiring the cost function to be specified by hand.
- **LCP** — Least-Cost Path: the cheapest route between two points over a cost raster.
- **FETE** — From-Everywhere-To-Everywhere: compute LCPs between many/all point pairs and look at where they concentrate, revealing likely corridors without needing to pre-specify origin/destination.
- **Cost-distance / accumulated cost surface** — a raster where each cell's value is the cumulative cost to reach it from a source, the basis for LCP and FETE.
- **Cost surface / friction surface** — a raster expressing how expensive it is to traverse each cell (slope, obstacles, etc.).
- **Space syntax** — analysis of spatial configuration (visibility, accessibility) as a driver of movement, independent of physical terrain cost.
- **Crosswalk table** — a mapping table reconciling IDs that differ across data sources.

---

## 13. References

- Fakhry, A. (1951). *The Necropolis of El-Bagawat in Kharga Oasis.* Government Press, Cairo. — the foundational survey; counted 263 chapels.
- Hauser, W. (1932). "The Christian Necropolis in Khargeh Oasis." *Bulletin of the Metropolitan Museum of Art* 27: 38–50.
- White, D. A., & Barber, S. B. (2012). "Geospatial modeling of pedestrian transportation networks: a case study from precolumbian Oaxaca, Mexico." *Journal of Archaeological Science* 39: 2684–2696. — introduces FETE, validated against known historical movement corridors.
- Verhagen, P. (2013). Independently described the same approach as "cumulative cost path" (CCP) modeling.
- Llobera, M. (2000). "Understanding Movement: A Pilot Model Towards the Sociology of Movement." In *Beyond the Map: Archaeology and Spatial Technologies.*
- Llobera, M., Fábrega-Álvarez, P., & Parcero-Oubiña, C. (2011). Focal mobility networks via hydrological flow accumulation on cost surfaces.
- Llobera, M., & Sluckin, T. J. (2007). "Zigzagging: Theoretical Insights on Climbing Strategies." *Journal of Theoretical Biology* 249: 206–217. — quadratic energy-expenditure cost function, shown effective for reconstructing real historical roads in later studies.
- Tobler, W. (1993). Tobler's hiking function for slope-to-speed conversion.
- Harris, M. (2000). Recommended 48-neighbourhood movement kernels to minimize path-length distortion in raster cost-distance analysis.
- Herzog, I., & Yépez, A. (2013). "Least-cost kernel density estimation" for movement potential.
- Ziebart, B. D., Maas, A., Bagnell, J. A., & Dey, A. K. (2008). Maximum Entropy Inverse Reinforcement Learning — the general method underlying `task1.ipynb`.

---

## 14. Execution Checklist

- [ ] Phase 0 — env set up, all libraries verified importable
- [ ] Phase 1 — single working CRS confirmed across shapefile + all rasters; `Site_Plan.pdf` georeferenced via control points
- [ ] Phase 2 — crosswalk table built and spot-checked (footprint ↔ chapel ↔ plan label, 1-to-many supported)
- [ ] Phase 3 — hand marks digitized (3a); attribute-driven entrances derived for all 342 (3b); agreement checked (3c); QA sheet generated and reviewed (3d)
- [ ] Phase 4 — slope/aspect cost layer built; building obstruction mask built; SAR-MS explored for direct trace evidence; node-importance weights (optional) added
- [ ] Phase 5 — MaxEnt IRL re-run on multi-feature cost surface using available demonstrations; weights sanity-checked
- [ ] Phase 6 — multi-source cost-distance run for all entrances; movement-potential raster generated; skeletonized into a draft network
- [ ] Phase 7 — at least one complementary method run (space syntax / ABM / direct trace detection) for triangulation
- [ ] Phase 8 — confidence scoring applied per segment; disagreements documented, not hidden
- [ ] Phase 9 — final `path_network.geojson`, `movement_potential.tif`, `confidence_report.md`, and figures produced and overlaid on both the orthoimage and the original hand-marked `Site_Plan.pdf`