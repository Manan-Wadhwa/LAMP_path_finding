# PLAN_06 — Repository Structure and Environment Specification
## El-Bagawat task2

---

## 1. Repository Structure

```
bagawat-paths/
|
|-- README.md                           # Project overview, how to run
|-- environment.yml                     # Conda environment (see Section 2)
|-- docs/
|   |-- decisions.md                    # Running log of parameter choices and dead ends
|   |-- method_notes.md                 # Supplementary methodological notes
|   `-- references/                     # PDF copies of key papers
|
|-- data/
|   |-- raw/                            # Untouched originals — READ ONLY after copy
|   |   |-- 110_GIS/                    # Bagawat_ROI.shp, BagawatROI_Smaller.shp
|   |   |-- 120_SiteReport/             # xlsx, PDFs, DXF, DWG files
|   |   |-- 130_Footprints/             # Buildings_Mask.shp + .points files
|   |   `-- 140_WV2/                    # All P001/P002/P003 tile directories
|   |
|   |-- interim/                        # Intermediate processing outputs (overwritable)
|   |   |-- wv2_merged_p001.tif         # Per-pass merged WV-2 (8-band MUL)
|   |   |-- wv2_merged_p002.tif
|   |   |-- wv2_merged_p003.tif
|   |   |-- wv2_pan_p001.tif            # Per-pass merged PAN
|   |   |-- wv2_pansharp_p001.tif       # Gram-Schmidt pan-sharpened at 0.46 m
|   |   |-- wv2_multitemporal_cv.tif    # Per-band coefficient of variation stack
|   |   |-- spi.tif                     # Spectral Path Indicator (0-1)
|   |   |-- ior.tif                     # Iron Oxide Ratio
|   |   |-- vesselness.tif              # Frangi vesselness response
|   |   |-- spectral_combined.tif       # Weighted combination of SPI + IOR + vesselness
|   |   |-- dem_working_crs.tif         # DEM reprojected to working CRS
|   |   |-- dem_slope.tif               # Slope (rise/run) computed from DEM
|   |   |-- cost_surface_tobler.tif     # Tobler composite cost
|   |   |-- cost_surface_llobera.tif    # Llobera-Sluckin composite cost
|   |   |-- building_mask.tif           # Rasterized footprint no-go layer (binary)
|   |   |-- pdf_raster_400dpi.tif       # bagawat print.pdf rasterized at 400 DPI
|   |   `-- free_space_skeleton.tif     # Medial axis of free space (for space syntax)
|   |
|   |-- processed/                      # Final analysis-ready layers
|   |   |-- entrances.geojson           # n=342, with source and confidence fields
|   |   |-- cost_composite.tif          # Final weighted multi-band composite cost
|   |   |-- fete_density.tif            # Movement potential raster (0-1 normalized)
|   |   |-- circuit_current.tif         # Electrical current density (0-1 normalized)
|   |   |-- space_syntax_integration.tif # Integration raster (0-1 normalized)
|   |   |-- proximity_edge_density.tif  # Gabriel+beta-skeleton edge density (0-1)
|   |   |-- ensemble.tif                # Weighted ensemble confidence raster (0-1)
|   |   |-- gabriel_graph.geojson       # Gabriel graph edges
|   |   |-- beta_skeleton_1.0.geojson   # Beta-skeleton for beta=1.0
|   |   |-- beta_skeleton_1.2.geojson
|   |   |-- beta_skeleton_1.5.geojson
|   |   `-- beta_skeleton_2.0.geojson
|   |
|   `-- crosswalk/
|       |-- building_id_crosswalk.csv   # footprint_id | chapel_ids | plan_labels | ...
|       |-- crosswalk_manual_review.csv # Unmatched records for human review
|       |-- crosswalk_audit.md          # Documentation of match decisions
|       `-- entrance_qa_review.csv      # Chapels where PDF mark vs attribute-derived disagree
|
|-- notebooks/
|   |-- 00_data_audit.ipynb             # Phase 0: inspect all data sources
|   |-- 01_coordinate_alignment.ipynb   # Phase 1: CRS reconciliation, PDF registration
|   |-- 02_id_crosswalk.ipynb           # Phase 2: build crosswalk table
|   |-- 03_entrance_extraction.ipynb    # Phase 3: DXF + PDF + attribute-derived entrances
|   |-- 04_cost_surface.ipynb           # Phase 4: Tobler and Llobera-Sluckin cost surfaces
|   |-- 05_wv2_spectral.ipynb           # Phase 5: DN->radiance, SPI, Frangi, pan-sharpen
|   |-- 06_fete_network.ipynb           # Phase 6: FETE engine, density raster, vectorize
|   |-- 07_circuit_model.ipynb          # Phase 7: conductance matrix, LGMRES solver
|   |-- 08_space_syntax.ipynb           # Phase 8: free-space skeleton, integration
|   |-- 09_proximity_graphs.ipynb       # Phase 9: Gabriel, beta-skeleton, Steiner tree
|   |-- 10_ensemble.ipynb               # Phase 10: combine all streams, confidence scoring
|   |-- 11_validation.ipynb             # Cross-method correlations, topology, anchor tests
|   `-- 12_final_outputs.ipynb          # Final figures, GeoJSON export, confidence report
|
|-- src/                                # Importable Python modules
|   |-- __init__.py
|   |-- align.py                        # CRS reconciliation, GCP reading, PDF homography
|   |-- crosswalk.py                    # ID reconciliation logic
|   |-- entrances.py                    # DXF extraction, PDF color-threshold, attr-derived
|   |-- cost.py                         # Tobler, Llobera-Sluckin, composite cost functions
|   |-- fete.py                         # FETE engine, multi-source Dijkstra
|   |-- circuit.py                      # Kirchhoff solver, conductance matrix
|   |-- spectral.py                     # WV-2 preprocessing, SPI, Frangi, pan-sharpening
|   |-- syntax.py                       # Axial line generation, integration computation
|   |-- graphs.py                       # Gabriel, beta-skeleton, Steiner tree
|   |-- ensemble.py                     # Evidence fusion, confidence scoring
|   `-- viz.py                          # All visualization helpers
|
`-- outputs/
    |-- path_network.geojson            # FINAL: confidence-scored vector network
    |-- movement_potential.tif          # FINAL: FETE density raster
    |-- spectral_path_indicator.tif     # FINAL: SPI raster
    |-- confidence_report.md            # FINAL: auto-generated per-segment summary
    |-- flagged_segments.geojson        # Segments requiring manual review
    |-- anchor_chapel_check.csv         # Chapel 25, 80, 180 proximity check
    `-- figures/
        |-- fete_overlay.png
        |-- circuit_overlay.png
        |-- spi_overlay.png
        |-- ensemble_heatmap.png
        |-- network_on_ortho.png
        `-- network_on_plan.png         # Network overlaid on bagawat print.pdf
```

---

## 2. Environment Specification

### 2.1 Conda Environment (environment.yml)

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
  - scikit-learn=1.3
  - jupyter=1.0
  - ipykernel=6.0
  - plotly=5.18
  - pip:
    - PyMuPDF==1.23.26
    - pdf2image==1.17.0
    - libpysal==4.9.0
```

### 2.2 Installation

```bash
# Create and activate environment
conda env create -f environment.yml
conda activate bagawat-paths

# Register kernel for Jupyter
python -m ipykernel install --user --name bagawat-paths --display-name "Bagawat Paths"

# System dependency for pytesseract (OCR)
# Linux/WSL:
sudo apt-get install tesseract-ocr
# macOS:
# brew install tesseract
# Windows: download from https://github.com/UB-Mannheim/tesseract/wiki

# For DWG conversion (if ezdxf cannot open the DWG directly):
# Linux/WSL:
sudo apt-get install libredwg-utils
# dwg2dxf "SITE CAD WORKING.dwg" -o working_converted.dxf
# Or: ODA File Converter (free, cross-platform, requires registration at opendesign.com)
```

### 2.3 Verifying the Installation

```python
# Run this cell in notebook 00_data_audit.ipynb to verify all imports work

import geopandas as gpd; print(f"geopandas {gpd.__version__}")
import rasterio; print(f"rasterio {rasterio.__version__}")
import shapely; print(f"shapely {shapely.__version__}")
import numpy as np; print(f"numpy {np.__version__}")
import scipy; print(f"scipy {scipy.__version__}")
import skimage; print(f"scikit-image {skimage.__version__}")
import networkx as nx; print(f"networkx {nx.__version__}")
import cv2; print(f"opencv {cv2.__version__}")
import pandas as pd; print(f"pandas {pd.__version__}")
import pytesseract; print(f"pytesseract {pytesseract.__version__}")
import momepy; print(f"momepy {momepy.__version__}")
import ezdxf; print(f"ezdxf {ezdxf.__version__}")
import fitz; print(f"PyMuPDF {fitz.__version__}")
from skimage.graph import MCP_Geometric; print("MCP_Geometric OK")
from skimage.filters import frangi; print("frangi OK")
from scipy.sparse.linalg import lgmres; print("lgmres OK")
print("All imports successful.")
```

---

## 3. Notebook Dependency Map

| Notebook | Depends on | Produces |
|---|---|---|
| 00_data_audit | raw data | sanity report: CRS, extents, attribute schemas, row counts |
| 01_coordinate_alignment | 00 | working CRS definition, PDF homography H, merged WV-2 tiles |
| 02_id_crosswalk | 01 | building_id_crosswalk.csv |
| 03_entrance_extraction | 01, 02 | entrances.geojson |
| 04_cost_surface | 01 | cost_surface_tobler.tif, cost_surface_llobera.tif, building_mask.tif |
| 05_wv2_spectral | 01 | spi.tif, ior.tif, vesselness.tif, spectral_combined.tif |
| 06_fete_network | 03, 04, 05 | fete_density.tif, draft path network GDF |
| 07_circuit_model | 03, 04 | circuit_current.tif |
| 08_space_syntax | 01, 03 | space_syntax_integration.tif |
| 09_proximity_graphs | 03, 04 | gabriel_graph.geojson, beta_skeleton_*.geojson, proximity_edge_density.tif |
| 10_ensemble | 06, 07, 08, 09, 05 | ensemble.tif, path_network.geojson (with all confidence fields) |
| 11_validation | 10, 03 | confidence_report.md, anchor_chapel_check.csv, cross_method_correlations.csv |
| 12_final_outputs | 11 | All final figures, flagged_segments.geojson |

---

## 4. Key Parameter Registry

All tunable parameters must be defined as named constants at the top of each notebook/script.
Document any changes from default in docs/decisions.md with rationale.

| Parameter | Default | Location | Notes |
|---|---|---|---|
| PDF_DPI | 400 | align.py | Higher = more precise mark detection but more memory |
| HOMOGRAPHY_RMSE_THRESHOLD | 5.0 | align.py | Map units; reject if exceeded |
| BLUE_HSV_H_LO | 90 | entrances.py | Tune against DXF-confirmed marks |
| BLUE_HSV_H_HI | 115 | entrances.py | Tune against DXF-confirmed marks |
| BLUE_HSV_S_MIN | 50 | entrances.py | Tune against DXF-confirmed marks |
| BLUE_HSV_V_MIN | 80 | entrances.py | Tune against DXF-confirmed marks |
| MARK_MIN_AREA_PX | 50 | entrances.py | Min connected component area at PDF_DPI |
| MARK_MAX_AREA_PX | 2000 | entrances.py | Max connected component area at PDF_DPI |
| ENTRANCE_TOLERANCE_M | 3.0 | entrances.py | Max distance from PDF mark to footprint |
| W_TERRAIN | 0.5 | cost.py | Terrain cost weight in composite |
| W_OBS | 1.0 | cost.py | Building obstruction weight (1e9 multiplier) |
| W_SPEC | 0.3 | cost.py | Spectral evidence weight in composite |
| FETE_THRESHOLD | 0.15 | fete.py | Density percentile for binarization |
| FETE_MIN_SPUR_PX | 3 | fete.py | Min dead-end spur length to keep |
| ENSEMBLE_WEIGHTS | (0.30, 0.25, 0.25, 0.10, 0.10) | ensemble.py | (FETE, Circuit, SPI, Syntax, Prox) |
| ENSEMBLE_THRESHOLD | 0.25 | ensemble.py | Minimum ensemble score to include in network |
| METHOD_AGREEMENT_FLAG | 2 | ensemble.py | Segments with agreement <= this get flagged |
| BETA_VALUES | [1.0, 1.2, 1.5, 2.0] | graphs.py | Beta-skeleton beta values to test |
| BARRIER_COST_PERCENTILE | 95 | graphs.py | Percentile above which edges are barrier-crossing |
| COVERAGE_TOLERANCE_PX | 3 | validation | Pixels; entrance must be within this of a segment |

---

## 5. Recommended docs/decisions.md Template

```markdown
# El-Bagawat task2 — Decisions Log

## [Date] Phase 0: DWG Layer Inspection
- SITE CAD WORKING.dwg opened with: [method]
- Layers found: [list all layer names]
- Path-related layers: [none / list them]
- Action taken: [description]

## [Date] Phase 0: GCP File Selection
- Files compared: Buildings_Mask.shp.points, .points1.points, .points2.points
- Selected: [which file and why]
- Number of enabled GCPs: [n]

## [Date] Phase 0: Excel Database Column Names
- Chapel number column: [actual column name]
- Entrance direction column: [actual column name]
- Direction distribution: S=[n], E=[n], W=[n], N=[n], other=[n], missing=[n]

## [Date] Phase 1: CRS Decision
- Working CRS: [EPSG code or proj4 string]
- Layers requiring reprojection: [list]
- PDF registration RMSE: [value] map units ([n] GCPs, [n] inliers)

## [Date] Phase 2: Crosswalk
- Exact matches: [n]
- Spatial matches: [n]
- DXF matches: [n]
- Manual resolutions: [n]
- Unresolvable: [n] (reasons: [list])

## [Date] Phase 3: Blue Mark Tuning
- Reference buildings: 23, 24, 25, 26
- HSV values sampled at confirmed marks: H=[range], S=[range], V=[range]
- Final thresholds: h_lo=[v], h_hi=[v], s_min=[v], v_min=[v]
- Site-wide marks detected: [n]

## [Date] Phase 4: Cost Surface Weights
- Chosen weights: w_terrain=[v], w_obs=[v], w_spec=[v]
- Rationale: [description]

## [Date] Phase 5: SPI Quality
- AUC of SPI against draft network: [value]
- Interpretation: [description]
- Action taken: [adjusted weights / no change]

## [Date] Phase 6: FETE Parameters
- Density threshold: [v]
- Min spur length: [v] pixels
- Reason for threshold choice: [description]

## [Date] Phase 7: Circuit Solver
- Solver used: lgmres / spsolve
- Convergence achieved: yes/no
- If no: action taken [description]

## [Date] Phase 9: Beta-Skeleton
- Best-aligning beta value with FETE density: [v]
- Correlation at that beta: [r value]

## [Date] Phase 10: Ensemble Weights
- Final weights: [tuple]
- Weight sensitivity: [sensitive/robust] — see docs/weight_sensitivity.csv
- Final ensemble threshold: [v]
```
