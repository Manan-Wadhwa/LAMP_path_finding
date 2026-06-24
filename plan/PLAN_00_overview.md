# El-Bagawat Necropolis — Full-Site Pedestrian Path Reconstruction
## Master Technical Plan · task2

**Site:** El-Bagawat Christian Necropolis, Kharga Oasis, Egypt (est. 3rd–7th c. CE)
**Codename:** task2 (full-site successor to the 3-entrance task1 pilot)
**Goal:** Reconstruct the most probable historical street-and-alley network connecting all 260+ chapel buildings — advancing from the 3-node MaxEnt-IRL pilot to a full 342-chapel multi-evidence ensemble pipeline.
**Key constraint:** Zero excavated path segments exist as ground truth; no analogous annotated desert necropolis exists for cross-site transfer learning.
**WV-2 imagery acquisition dates:** 2018-03-22 (P003), 2018-06-01 (P002), 2018-06-14 (P001)

---

## Document Map

| File | Contents |
|---|---|
| PLAN_00_overview.md | Research framing, site context, full data inventory (this file) |
| PLAN_01_foundations.md | Why MaxEnt IRL cannot scale; 5-stream ensemble mathematical foundations |
| PLAN_02_phases_0_3.md | Phases 0-3: Data audit, coordinate reconciliation, ID crosswalk, entrance extraction |
| PLAN_03_phases_4_6.md | Phases 4-6: Cost surface, WV-2 spectral analysis, FETE network generation |
| PLAN_04_phases_7_10.md | Phases 7-10: Electrical circuit model, space syntax, proximity graphs, ensemble |
| PLAN_05_validation_outputs.md | Validation framework, failure modes, deliverables, execution checklist |
| PLAN_06_repo_env.md | Repository structure and conda environment specification |
| PLAN_07_annotator_website.md | Manual entrance annotation web tool: architecture, preprocessing scripts, UI spec, post-processing |

---

## 1. Research Framing

### 1.1 What task1 actually showed

The task1.ipynb pilot applied MaxEnt IRL to three hand-picked building entrances (M0, M1, M2)
over a terrain-derived cost surface. The three output panels — SAR composite, DEM hillshade,
orthoimage with footprints — all show the same learned route. That result is a **model artifact**,
not a discovered path. It demonstrates that the IRL machinery works on the geometry and cost
surface; the route is a 3-node spanning tree trivially determined by the terrain between those
three specific points. It cannot serve as a training demonstration for the full site without
circularity (see PLAN_01 for the formal argument).

### 1.2 The actual research question

> Given terrain, building obstruction, recorded chapel entrance orientations, three acquisition
> dates of 8-band WorldView-2 satellite imagery, site-wide CAD geometry, and 342 chapel records
> with typological attributes — what is the most probable historical network of streets and
> alleyways that connected the El-Bagawat necropolis, and how should confidence be assigned to
> each hypothesized segment?

This is a recognised problem class in landscape archaeology: **movement network reconstruction
from passive evidence**. The correct methodological family is cost-surface accumulation / FETE
analysis (White & Barber 2012), complemented by spectral archaeology on the WV-2 imagery and
by network-theoretic graph inference. None of these require demonstration trajectories.

### 1.3 Why El-Bagawat is a real street-network problem

- The site is consistently described in the literature as a settlement-like necropolis where
  chapels are arranged along **streets and interconnecting narrow alleyways** — one of the
  earliest "cities of the dead." This reframes the problem from inferring desire lines from
  terrain alone to **recovering an attested but unmapped settlement street plan**.
- Fakhry's 1951 foundational survey counted **263 chapels** — strikingly close to the 260+
  footprint layer, confirming the shapefile is at the *building* granularity.
- **Chapel 180** is the large central church occupying a commanding mid-site position (visible
  in image.png as the large central rectangle). It is the highest-betweenness anchor node any
  plausible network must converge on.
- The Peace Chapel (25) and Exodus Chapel (80) are named sites useful as qualitative anchors.

### 1.4 Definition of "done"

A successful outcome is NOT a single deterministic line drawing. It is:

1. **annotator/annotations.geojson** — human-verified entrance point for every building;
   the primary ground-truth input for all downstream network analysis. Produced by the
   web annotation tool (PLAN_07) before any Phase 4+ analysis begins.
2. outputs/path_network.geojson — confidence-scored vector network; every segment tagged with
   per-method evidence scores and an ensemble confidence value.
3. outputs/movement_potential.tif — continuous density-of-crossing heatmap.
4. outputs/spectral_path_indicator.tif — independent physical evidence from multi-temporal WV-2.
5. data/crosswalk/building_id_crosswalk.csv — reconciling shapefile IDs, Excel chapel numbers,
   plan labels, and DXF filenames. Without this, nothing downstream is trustworthy.
6. outputs/confidence_report.md — per-segment: which methods agree, which disagree, which
   segments are flagged for manual verification.

---

## 2. Full Data Inventory

### 2.1 GIS Region of Interest (100_Data/110_GISRegionOfInterest/)

| File | Notes |
|---|---|
| Bagawat_ROI.shp | Full site boundary polygon. Defines outer analysis extent. |
| BagawatROI_Smaller.shp | Tighter ROI matching the task1 pilot red-box extent. For pilot-scale comparability. |

Both ship with .prj files. Read these FIRST in Phase 1 — they define the local working CRS
that every other layer must align to.

### 2.2 Site Report and CAD (100_Data/120_SiteReport/)

| File | Format | Size | Notes |
|---|---|---|---|
| 2026 El Bagawat Database Draft 1.xlsx | Excel, 3 sheets | 22 KB | Primary chapel attribute DB: 342 records, entrance directions, typology |
| bagawat print.pdf | PDF | 1.4 GB | Hand-annotated site plan with light-blue entrance ticks. Primary human-labelled source. |
| SiteReport_missing9-12.pdf | PDF | 617 MB | Supplementary report; inspect for additional entrance/path annotation |
| BaseSiteCAD/Building1.dxf | DXF | 119 KB | Individual building CAD for building 1 |
| BaseSiteCAD/Building23.dxf | DXF | 132 KB | Building 23 |
| BaseSiteCAD/Building24.dxf | DXF | 142 KB | Building 24 |
| BaseSiteCAD/Building25.dxf | DXF | 156 KB | Peace Chapel — priority calibration target |
| BaseSiteCAD/Building26.dxf | DXF | 122 KB | Building 26 |
| BaseSiteCAD/Building175.dxf | DXF | 126 KB | Building 175 |
| BaseSiteCAD/Building210.dxf | DXF | 119 KB | Chapel 210 — priority modelling target |
| BaseSiteCAD/scan557.tif | GeoTIFF | 769 KB | Scanned survey document (possibly Fakhry 1951 plan) |
| BaseSiteCAD/scan557.jpg | JPEG | 14.8 MB | High-res scan version |
| BaseSiteCAD/SITE CAD BUILDINGS ONLY.dwg | DWG | 106 KB | Site-wide CAD, building geometry only |
| BaseSiteCAD/SITE CAD WORKING.dwg | DWG | 222 KB | HIGHEST-VALUE UNEXPLORED ASSET. Inspect ALL layer names first. |

**Excel sheet breakdown:**
- Sheet4: Classification legends (10 architectural types, 7 facade types). Lookup/dimension table.
- Database Full: 342 chapel records. Entrance direction field is the key input to Phase 3.
  Distribution: South ~84-91 records, East ~60-62, West ~59-62.
- Building Assignments: Project-management sheet listing which chapels are being modelled/textured
  by which team member. Useful for sequencing validation priorities.

**DXF strategy:** Parse with ezdxf. List ALL layer names (doc.layers). Look for layers named
DOOR, ENTRANCE, OPENING, ARCH_FEATURE, ACCESS, THRESHOLD. Extract those entity geometries as
shapely objects. These 7 precisely known building entrances become the primary calibration set
for every other entrance-extraction method in Phase 3.

**DWG strategy:** Convert SITE CAD WORKING.dwg to DXF via ezdxf ODA wrapper or LibreDWG/dwg2dxf,
then parse. If ANY layer is named ROUTE, PATH, ROAD, STREET, ALLEY, WAY, or CIRCULATION, it may
represent the archaeologists' own path hypothesis. Treat that as highest-authority annotation,
superseding all modelled outputs.

### 2.3 Building Footprints (100_Data/130_BuildingFootprintsVectorData/)

| File | Notes |
|---|---|
| BuildingTracesCurrent/Buildings_Mask.shp | PRIMARY footprint layer. 260+ polygon features. |
| BuildingTracesCurrent/Buildings_Mask.shp.points | QGIS GCP file: mapX,mapY,pixelX,pixelY,enable. The authoritative tie between PDF pixel space and working CRS. |
| BuildingTracesCurrent/Buildings_Mask.shp.points1.points | Alternate GCP set — compare for consistency |
| BuildingTracesCurrent/Buildings_Mask.shp.points2.points | Third GCP set — may be a later re-registration |
| BuildingTraces-OLD/ | Superseded version — archive only, do not use |

The .points files are tab-delimited QGIS format readable with pandas.read_csv. Read all three
and compare — use the most recent consistent set for Phase 1 PDF registration.

### 2.4 WorldView-2 Imagery (100_Data/140_SAR_Imagery/DigitalGlobe_2018/MONO/)

Note: Directory is named SAR_Imagery but contains WorldView-2 optical multispectral, not SAR.
The task1 SAR-MS.tif was a derived/mosaicked product from these WV-2 tiles.

Three sub-directories = three order numbers = three acquisition passes:

| Pass | Directory | Date | Tile grid |
|---|---|---|---|
| P001 | 058239078010_01 | 2018-06-14 | 8 rows x 3 cols = 24 MUL + 24 PAN tiles |
| P002 | 058239078020_01 | 2018-06-01 | 2 rows x 3 cols = 6 MUL + 6 PAN tiles |
| P003 | 058239078030_01 | 2018-03-22 | 8 rows x 3 cols = 24 MUL + 24 PAN tiles |

**WorldView-2 band assignments (M2AS product):**

| Band | Name | Wavelength (nm) | Path-detection relevance |
|---|---|---|---|
| 1 | Coastal | 400-450 | Aerosol correction reference; low SNR — exclude from SPI |
| 2 | Blue | 450-510 | Bright compacted surfaces |
| 3 | Green | 510-580 | Soil albedo baseline |
| 4 | Yellow | 585-625 | Iron-oxide sensitivity |
| 5 | Red | 630-690 | Ferric iron / chlorophyll |
| 6 | Red Edge | 705-745 | Surface texture; vegetation stress |
| 7 | NIR1 | 770-895 | Strong vegetation/soil separation |
| 8 | NIR2 | 860-1040 | Atmospheric window |
| PAN | — | 450-800 | 0.46 m GSD — 4x finer than MUL; use for Frangi vesselness |

Key metadata files per pass:
- .IMD: absCalFactor and effectiveBandwidth per band (DN -> radiance), firstLineTime,
  sun elevation/azimuth.
- .RPB: RPC camera model for orthorectification without full photogrammetric bundle.

### 2.5 Digital Elevation Model (100_Data/150_DigitalElevationModel/)

| Resource | Notes |
|---|---|
| DEM_Process.md | Step-by-step ASP stereo pipeline documentation |
| Generated_DEMs/Current_DEM/ | Primary DEM at 1.5 m grid spacing — use for slope/cost computation |
| Generated_DEMs/Old_DEMs/ | Superseded — archive only |
| Generated_Meshes/ | 3D mesh outputs — for visualisation, not path analysis |

DEM pipeline (from DEM_Process.md):
- Input: WV-2 stereo panchromatic pairs + RPC .RPB files + Copernicus 30m reference DEM
- Stereo algorithm: asp_mgm with subpixel mode 3; optional bundle adjustment step
- Output: 1.5 m GSD DEM filled with dem_mosaic to remove holes

The task1 pilot used DEM_Subset-Original.tif (bare-earth) AND DEM_Subset-WithBuildings.tif
(structures present). The difference WithBuildings - Original gives an almost-free building
height/obstruction mask. Preserve this dual-DEM approach in task2.

### 2.6 The Annotation Image (plan/image.png)

This is a scan of the Necropolis of El-Bagawat site plan — a classic architectural survey
drawing showing all chapel buildings as rectangular outlines, numbered, with north arrow and
scale bar. Key observations for the analysis:

- Buildings are densely clustered in the upper-centre and right portions of the plan, with a
  clear central large rectangular enclosure (chapel 180, the main church).
- A dotted perimeter line delineates the site boundary ROI matching Bagawat_ROI.shp.
- The layout visibly suggests a hierarchical street network: a main spine through the centre
  cluster, with subsidiary alleys branching to peripheral chapel groups.
- Isolated chapels on the western and southern periphery are sparsely distributed — lower
  path-network confidence and wider spacing between inferred routes.
- Typeset numbered labels on this plan = the plan_label ID layer for Phase 2 crosswalk via
  OCR + spatial join to shapefile polygons.

---

## 3. The Four Hard Problems

| # | Problem | Why it matters | Resolution |
|---|---|---|---|
| 1 | No absolute georeference | Cannot trust lat/long; bagawat print.pdf is not natively in raster CRS | Local working CRS anchored to Buildings_Mask.shp.prj; use QGIS GCPs to register PDF (Phase 1) |
| 2 | Three incompatible ID systems + one external that must be ignored | "Chapel 25" in Excel may not be polygon 25 in shapefile or label "25" on plan | Explicit versioned crosswalk table with 1-to-many footprint:chapel links (Phase 2) |
| 3 | Blue-pen marks on plan are approximate, not exact coordinates | Pen marks on a scanned paper plan have ±1–3 mm precision after scan; the plan has no native georeference; automated color-threshold extraction has false positives and misses | Web annotation tool (PLAN_07): auto-extraction pre-populates candidates, human annotator confirms/corrects each building in the browser on the georeferenced image; pixel coordinates converted to CRS via homography H post-session |
| 4 | Scaling a 3-node pilot to 260+ nodes | Pairwise route computation != "run task1 N^2 times" | FETE + electrical circuit model: O(N) Dijkstra passes not O(N^2) (Phases 6-7) |

---

## 4. ID System Warning (Critical)

Four incompatible numbering systems exist:

| Source | ID type | Known conflicts |
|---|---|---|
| Buildings_Mask.shp attribute table | Shapefile polygon ID (inspect exact field name first) | May use sequential integers, not archaeological numbers |
| Database Full (Excel) | Chapel_No field | 342 records; multi-chamber buildings counted separately |
| bagawat print.pdf typeset labels | Physical position on plan; must be geocoded via OCR | Must be verified spatially against shapefile |
| External literature (Fakhry, NASSCAL, Wikipedia) | Fakhry 1951 numbering | CONFIRMED to conflict: Peace Chapel is #25 in one source, #80 in another. DO NOT IMPORT. |

The 1-to-many issue: 342 Excel chapel records vs ~260 footprint polygons. Many buildings
contain multiple chapels (domed chamber + apse room = 2 chapel records, 1 footprint polygon).
The crosswalk schema MUST support 1-to-many from day one. Never force a 1-to-1 join.
