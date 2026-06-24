# PLAN_02 — Phases 0-3: Audit, Coordinate Reconciliation, ID Crosswalk, Entrance Extraction
## El-Bagawat task2

---

## Phase 0 — Data Audit and Environment Setup

Do this before touching any analysis. No code produces trustworthy output until this is done.

### Step 0a — Inspect the DWG [AUDIT COMPLETED]

*Audit Result (2026-06-24)*: Converted drawing layers are `['0', 'BUILDINGS', 'NUMBERING', 'LW1', 'LW2', 'ABOVE', 'Defpoints']`. No layers match path/road keywords. Geometries in layers `LW1`, `LW2`, and `ABOVE` are architectural detail floor plans in Space B ($X > 200,000$, $Y < 50,000$), not pathways. **No pre-digitized paths exist in this CAD file.** Path network extraction must rely entirely on synthetic modeling (FETE, circuits, spectral). See findings in [0a_dwg_audit.md](file:///C:/Users/Public/LAMP_DataStore/ElBagawat/200_Projects/210_GSOC/code-manan/findings/0a_dwg_audit.md).

### Step 0b — Read the QGIS GCP Files [AUDIT COMPLETED]

*Audit Result (2026-06-24)*: Verified GCP file set relationships. The points in `points` (23 points) are a strict subset of `points1` (29 points), which are a strict subset of `points2` (32 points). Overlapping coordinate pairs match with zero difference. **`Buildings_Mask.shp.points2.points`** (32 active points) is selected as the authoritative set for georeferencing to minimize registration errors. Details are saved in [0b_gcp_selection.md](file:///C:/Users/Public/LAMP_DataStore/ElBagawat/200_Projects/210_GSOC/code-manan/findings/0b_gcp_selection.md).

mapX/mapY are in working CRS; pixelX/pixelY are in PDF image coordinates.
These GCPs are exactly what Phase 1 needs for PDF georeferencing.

### Step 0c — CRS Audit [AUDIT COMPLETED]

*Audit Result (2026-06-24)*: Spatial layer coordinate references have been verified:
- **`Buildings_Mask.shp` (footprints)**: `EPSG:32636` (WGS 84 / UTM zone 36N). Matches the working CRS.
- **`Bagawat_ROI.shp` and `BagawatROI_Smaller.shp`**: `EPSG:4326` (Geographic WGS 84). **Must be reprojected** to `EPSG:32636` using geopandas `to_crs(epsg=32636)`.
- **DEM and WV-2 Rasters**: `EPSG:32636` natively. No coordinate resampling required.

Details are documented in [0c_crs_audit.md](file:///C:/Users/Public/LAMP_DataStore/ElBagawat/200_Projects/210_GSOC/code-manan/findings/0c_crs_audit.md).

### Step 0d — Parse Individual DXF Files

```python
import ezdxf
from shapely.geometry import Point, LineString

ENTRANCE_LAYER_KEYWORDS = [
    "door", "entrance", "opening", "threshold", "access",
    "portal", "seuil", "arch", "feature"
]

def extract_dxf_entrances(dxf_path):
    """Extract entrance-related geometry from a DXF file."""
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    
    # First: print all layers so you know what exists
    all_layers = [layer.dxf.name for layer in doc.layers]
    print(f"{dxf_path} layers: {all_layers}")
    
    entrance_geoms = []
    for entity in msp:
        layer = entity.dxf.layer.lower()
        if any(kw in layer for kw in ENTRANCE_LAYER_KEYWORDS):
            if entity.dxftype() == "LINE":
                pts = [(entity.dxf.start.x, entity.dxf.start.y),
                       (entity.dxf.end.x, entity.dxf.end.y)]
                entrance_geoms.append(LineString(pts).centroid)
            elif entity.dxftype() in ("POINT", "INSERT"):
                entrance_geoms.append(
                    Point(entity.dxf.insert.x, entity.dxf.insert.y))
    return entrance_geoms  # in DXF coordinate space; transform to working CRS after

dxf_files = {
    1: "BaseSiteCAD/Building1.dxf",
    23: "BaseSiteCAD/Building23.dxf",
    24: "BaseSiteCAD/Building24.dxf",
    25: "BaseSiteCAD/Building25.dxf",  # Peace Chapel
    26: "BaseSiteCAD/Building26.dxf",
    175: "BaseSiteCAD/Building175.dxf",
    210: "BaseSiteCAD/Building210.dxf",
}

for bld_num, path in dxf_files.items():
    geoms = extract_dxf_entrances(path)
    print(f"Building {bld_num}: {len(geoms)} entrance geometry objects found")
```

Verify DXF coordinate system by overlaying one DXF footprint against Buildings_Mask.shp
for the same building. *Audit Finding (2026-06-24)*: The main map coordinates (Space A, $X < 200,000$) match UTM meters via a 1:1000 scale (millimeters) and global translation. However, the individual building DXFs (Space B, $X > 200,000$) are offset and require building-specific **local translations** derived from matching the detail label 'N' text position in DXF to the building footprint centroid in the shapefile:
$$T_x = X_{utm\_centroid} - 0.001 \times X_{dxf\_label\_insert}$$
$$T_y = Y_{utm\_centroid} - 0.001 \times Y_{dxf\_label\_insert}$$
Applying this translation and scale ($0.001 \times \text{dxf\_coord} + T$) aligns DXF geometry to UTM space with sub-millimeter precision (see [0a_approach_updates.md](file:///C:/Users/Public/LAMP_DataStore/ElBagawat/200_Projects/210_GSOC/code-manan/findings/0a_approach_updates.md)).

### Step 0e — Inspect Excel Database [AUDIT COMPLETED]

*Audit Result (2026-06-24)*: Verified correct Excel database path following assistant feedback: **`100_Data/120_SiteReport/2026 El Bagawat Database Draft 1.xlsx`**.
- **Sheet Verified**: Main database is `Database Full` sheet (342 rows, 42 columns). Columns: `Chapel Number (according to Fakhry)`, `Entrace Direction` (exact spelling), `Type`.
- **Data Availability**: Contains **215 non-null entrance directions** (South=89, East=61, West=63, Compound=2), leaving 127 `NaN` values.
- **Pipeline Decision**: The attribute-driven fallback strategy (Phase 3c) is highly viable and will provide offsets for 215 chapels. The remaining 127 chapels will use geometric centroids as fallbacks (confidence = 0.30).

Details are saved in [0e_excel_audit.md](file:///C:/Users/Public/LAMP_DataStore/ElBagawat/200_Projects/210_GSOC/code-manan/findings/0e_excel_audit.md).

### Environment Libraries Required

```
geopandas>=0.14     - Vector handling
rasterio>=1.3       - Raster I/O and reprojection
shapely>=2.0        - Geometry operations
fiona>=1.9          - Vector file I/O
pyproj>=3.6         - CRS transformations
numpy>=1.26         - Numerical arrays
scipy>=1.11         - Sparse linear algebra, cost-distance
scikit-image>=0.22  - MCP_Geometric, skeletonize, Frangi, phase_cross_correlation
networkx>=3.2       - Graph construction and analysis
opencv-python>=4.8  - Color thresholding, morphology, homography
PyMuPDF>=1.23       - PDF rasterization (import as fitz)
pandas>=2.1         - Excel and CSV handling
openpyxl>=3.1       - Excel reading backend
pytesseract>=0.3    - OCR for plan labels
momepy>=0.7         - Space syntax metrics
ezdxf>=1.1          - DXF/DWG parsing
scikit-learn>=1.3   - Linear regression for pan-sharpening
matplotlib>=3.8     - Visualization
plotly>=5.18        - Interactive QA maps
```

Full conda environment YAML is in PLAN_06_repo_env.md.

---

## Phase 1 — Coordinate Reconciliation

**Goal:** One consistent local CRS that every layer can be read into.

### 1a — Establish Working CRS

The Buildings_Mask.shp CRS is the authority. Every other layer must be reprojected to it.
Document the CRS string in docs/decisions.md before any other analysis.

```python
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

# Establish working CRS
footprints = gpd.read_file("BuildingTracesCurrent/Buildings_Mask.shp")
WORKING_CRS = footprints.crs
print(f"Working CRS: {WORKING_CRS}")

def reproject_raster(src_path, dst_path, target_crs):
    """Reproject a raster to the working CRS."""
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds)
        profile = src.profile.copy()
        profile.update(crs=target_crs, transform=transform,
                       width=width, height=height)
        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.bilinear)
```

### 1b — Register bagawat print.pdf Using GCPs

```python
import numpy as np
import cv2
import fitz  # PyMuPDF

def rasterize_pdf(pdf_path, dpi=400):
    """Rasterize the first page of a PDF at specified DPI."""
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = np.frombuffer(pix.samples, dtype=np.uint8)
    img = img.reshape(pix.height, pix.width, pix.n)
    return img[:, :, :3]  # RGB only (drop alpha if present)

def fit_pdf_to_crs(gcps_df, pdf_dpi=400):
    """
    Fit a homography from PDF pixel space to working CRS.
    gcps_df: DataFrame with columns mapX, mapY, pixelX, pixelY
    Note: pixelX/pixelY in the GCP file are in the PDF image coordinate system
    at the DPI used when the GCPs were created. Check the GCP file header for DPI.
    """
    src = gcps_df[["pixelX", "pixelY"]].values.astype(np.float64)
    dst = gcps_df[["mapX", "mapY"]].values.astype(np.float64)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, ransacReprojThreshold=5.0)
    inliers = mask.ravel().sum()
    print(f"Homography fit: {inliers}/{len(src)} GCPs used as inliers")
    return H, mask

def pdf_px_to_crs(px, py, H):
    """Transform a PDF pixel coordinate to working CRS using the homography H."""
    pt = np.array([[px, py, 1.0]], dtype=np.float64)
    mapped = (H @ pt.T).T
    return mapped[0, :2] / mapped[0, 2]

def compute_registration_rmse(gcps_df, H):
    """Compute RMSE of reprojection over all GCPs."""
    predicted = np.array([pdf_px_to_crs(r.pixelX, r.pixelY, H)
                          for _, r in gcps_df.iterrows()])
    actual = gcps_df[["mapX", "mapY"]].values
    rmse = np.sqrt(np.mean(np.sum((predicted - actual)**2, axis=1)))
    print(f"Registration RMSE: {rmse:.3f} map units")
    return rmse
```

**Target RMSE:** <= 1 building width (~3-5 map units in local coordinates).
If RMSE is higher: identify outlier GCPs (highest residuals) via the RANSAC mask,
remove and re-fit. Document all outliers and reasons in docs/decisions.md.

### 1c — Merge and Reproject WV-2 Tiles

```python
import glob
from rasterio.merge import merge
import rasterio

def merge_wv2_pass(tile_dir, pass_pattern, out_path, target_crs):
    """
    Merge all WV-2 MUL tiles from one acquisition pass into a single raster.
    tile_dir: directory containing the tiles
    pass_pattern: glob pattern to match tiles (e.g., "*-M2AS*.TIF")
    """
    tif_files = sorted(glob.glob(f"{tile_dir}/{pass_pattern}"))
    if not tif_files:
        raise FileNotFoundError(f"No tiles found in {tile_dir} matching {pass_pattern}")
    
    src_files = [rasterio.open(f) for f in tif_files]
    mosaic, transform = merge(src_files)
    
    # Build output profile
    profile = src_files[0].profile.copy()
    profile.update({
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": transform,
        "count": mosaic.shape[0],
    })
    
    # Write merged (may need reprojection to working CRS in same step)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mosaic)
    
    for src in src_files:
        src.close()
    
    print(f"Merged {len(tif_files)} tiles -> {out_path}")

# Run for each pass:
# merge_wv2_pass(".../058239078010_01", "*-M2AS*.TIF", "interim/wv2_merged_p001.tif", WORKING_CRS)
# merge_wv2_pass(".../058239078020_01", "*-M2AS*.TIF", "interim/wv2_merged_p002.tif", WORKING_CRS)
# merge_wv2_pass(".../058239078030_01", "*-M2AS*.TIF", "interim/wv2_merged_p003.tif", WORKING_CRS)
```

Coregister the three merged passes to sub-pixel accuracy using phase cross-correlation
before computing the multi-temporal SPI (Phase 5). Even small registration errors (~1 pixel)
will create artificial temporal variation that masks real path signals.

```python
from skimage.registration import phase_cross_correlation

def coregister_rasters(reference_path, target_path, output_path):
    """Coregister target raster to reference using phase cross-correlation."""
    with rasterio.open(reference_path) as ref:
        ref_band = ref.read(3).astype(float)  # Use green band as reference
    with rasterio.open(target_path) as tgt:
        tgt_band = tgt.read(3).astype(float)
    
    shift, error, phase_diff = phase_cross_correlation(ref_band, tgt_band)
    print(f"Shift: {shift}, Error: {error:.4f}")
    # Apply integer pixel shift (sub-pixel shift requires more complex resampling)
    # For sub-pixel accuracy, use cv2.findTransformECC instead
    return shift
```

---

## Phase 2 — Building ID Crosswalk

**Goal:** A versioned table mapping shapefile polygon ID <-> Excel chapel number <->
PDF plan label <-> DXF filename, with explicit 1-to-many support.

### 2a — Define the Schema

```
footprint_id  | chapel_ids   | plan_labels  | dxf_file        | match_method    | confidence
--------------+--------------+--------------+-----------------+-----------------+-----------
FP_023        | 23, 24       | "23", "24"   | Building23.dxf  | spatial+exact   | 0.95
FP_025        | 25           | "25"         | Building25.dxf  | exact           | 1.00
FP_180        | 180          | "180"        | None            | spatial         | 0.85
FP_007        | 7a, 7b       | "7"          | None            | manual          | 0.70
```

Key decisions:
- chapel_ids is a comma-separated list (not a single value) — supports 1-to-many
- match_method records how the match was made: "exact", "spatial", "dxf", "manual"
- confidence is 0.0-1.0; manual matches that look plausible get 0.6-0.7

### 2b — Extract Attribute Table from Shapefile

```python
import geopandas as gpd
import pandas as pd

footprints = gpd.read_file("BuildingTracesCurrent/Buildings_Mask.shp")
print(f"Footprint count: {len(footprints)}")
print(f"Columns: {list(footprints.columns)}")
print(footprints.head(5))

# Note the exact ID field name (e.g., "id", "OBJECTID", "FID", "chapel_no")
# This is the footprint_id in the crosswalk
```

### 2c — Extract Chapel Numbers from Excel

```python
xl = pd.ExcelFile("2026 El Bagawat Database Draft 1.xlsx")
db = xl.parse("Database Full")

# Find the chapel number column — inspect column names carefully
print(list(db.columns))

# Extract chapel numbers and clean
chapel_col = "Chapel Number (according to Fakhry)"  # Updated from audit
chapel_ids = db[chapel_col].dropna().astype(str).str.strip()
print(f"Excel chapel count: {len(chapel_ids)}")
print(f"Sample: {chapel_ids.head(10).tolist()}")
```

### 2d — OCR Plan Labels from PDF

```python
import pytesseract
import cv2
import numpy as np

def extract_plan_labels(img_rgb, footprints_mask=None):
    """
    Extract typeset building number labels from the rasterized PDF.
    img_rgb: RGB image from rasterize_pdf()
    footprints_mask: optional binary mask of building polygon regions
    Returns: list of (text, centroid_x, centroid_y) in PDF pixel coordinates
    """
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    
    # Threshold: typeset numbers are dark on white/light background
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # If footprints mask available, restrict to near-building areas
    if footprints_mask is not None:
        dilated = cv2.dilate(footprints_mask.astype(np.uint8), np.ones((20, 20)))
        thresh = thresh & dilated
    
    # OCR with numeric-only whitelist
    config = "--psm 6 -c tessedit_char_whitelist=0123456789"
    data = pytesseract.image_to_data(thresh, config=config,
                                      output_type=pytesseract.Output.DICT)
    
    results = []
    for i, text in enumerate(data["text"]):
        if (text.strip().isdigit() and
                int(data["conf"][i]) > 60 and
                len(text.strip()) >= 1):
            cx = data["left"][i] + data["width"][i] // 2
            cy = data["top"][i] + data["height"][i] // 2
            results.append((text.strip(), cx, cy))
    
    return results  # coordinates are in PDF pixel space; transform via homography H
```

### 2e — Join Strategy (In Order)

**Pass 1 — Exact string match:**
```python
def exact_match(footprints_gdf, excel_db, fp_id_col, excel_id_col):
    """Match footprint IDs to Excel chapel numbers by exact string equality."""
    matches = []
    for _, row in footprints_gdf.iterrows():
        fp_id = str(row[fp_id_col]).strip()
        exact = excel_db[excel_db[excel_id_col].astype(str).str.strip() == fp_id]
        if not exact.empty:
            matches.append({
                "footprint_id": fp_id,
                "chapel_ids": fp_id,
                "match_method": "exact",
                "confidence": 1.0
            })
    return pd.DataFrame(matches)
```

**Pass 2 — Spatial join using OCR-derived plan label positions:**
Transform OCR label centroids from PDF pixel space to working CRS using H.
Assign each label to the nearest footprint polygon within 5 m tolerance.
```python
from shapely.geometry import Point
import geopandas as gpd

def spatial_label_match(labels_pdf, H, footprints_gdf, tolerance_m=5.0):
    """
    labels_pdf: list of (text, px, py) from OCR
    H: homography from PDF pixel to working CRS
    footprints_gdf: building footprint GeoDataFrame
    """
    label_points = []
    for text, px, py in labels_pdf:
        crs_pt = pdf_px_to_crs(px, py, H)
        label_points.append({"label": text,
                              "geometry": Point(crs_pt[0], crs_pt[1])})
    
    labels_gdf = gpd.GeoDataFrame(label_points, crs=footprints_gdf.crs)
    
    # Spatial join: nearest footprint to each label
    joined = gpd.sjoin_nearest(labels_gdf, footprints_gdf[["geometry", "id"]],
                                how="left", max_distance=tolerance_m,
                                distance_col="dist_m")
    return joined
```

**Pass 3 — DXF filename matching:**
Building{N}.dxf -> chapel N. Verify by overlaying DXF geometry against shapefile polygon.

**Pass 4 — Manual resolution:**
For all unmatched records after Passes 1-3, generate a QA CSV with:
footprint_id, footprint_centroid_x, footprint_centroid_y, nearest_label, nearest_label_dist
Output to: data/crosswalk/crosswalk_manual_review.csv

**FORBIDDEN:** Do not use Fakhry/NASSCAL/Wikipedia chapel numbering. Confirmed conflicts exist.
Do not perform any fuzzy matching without a human reviewing each fuzzy match result.

### 2f — Validate Crosswalk Completeness

```python
def validate_crosswalk(crosswalk_df, footprints_gdf, excel_db):
    n_footprints = len(footprints_gdf)
    n_matched = crosswalk_df["footprint_id"].nunique()
    n_excel = len(excel_db)
    n_excel_matched = len(set(",".join(crosswalk_df["chapel_ids"].dropna()).split(",")))
    
    print(f"Footprints matched: {n_matched}/{n_footprints} ({100*n_matched/n_footprints:.1f}%)")
    print(f"Excel chapels matched: {n_excel_matched}/{n_excel} ({100*n_excel_matched/n_excel:.1f}%)")
    
    # Report unmatched footprints
    matched_ids = set(crosswalk_df["footprint_id"])
    unmatched = footprints_gdf[~footprints_gdf["id"].astype(str).isin(matched_ids)]
    print(f"Unmatched footprints: {len(unmatched)}")
    
    # Report 1-to-many instances
    multichapel = crosswalk_df[crosswalk_df["chapel_ids"].str.contains(",")]
    print(f"Multi-chapel footprints: {len(multichapel)}")
    return unmatched
```

Target: > 90% of footprints matched; remainder documented with reason.

---

## Phase 3 — Entrance Point Extraction

**Goal:** One entrance coordinate (and cardinal side) per chapel, for all 342 chapels.

Entrance locations are hand-marked on `bagawat print.pdf` with a blue pen. These marks are
approximate (pen width ~1-3 mm on paper = several pixels at 400 DPI after scan, then
further distorted by the scan-to-CRS registration). The approach is therefore:

1. Run automated color-threshold extraction on the PDF scan (Phase 3a) — produces
   **candidate marks only**, not final data.
2. Human annotator reviews all 263 buildings in the web tool (PLAN_07 / Phase 3b)
   and confirms, corrects, or replaces each candidate. This is the **primary source**.
3. Attribute-driven derivation from Excel entrance directions (Phase 3c) fills any
   buildings the annotator skipped or that have no visible mark on the plan.
4. DXF-derived entrances (Phase 3d) override with sub-centimetre precision for the
   7 buildings with individual DXF files.
5. Merge all sources by priority (Phase 3e) and output a single entrances.geojson.

**Hard constraint:** Phase 3b (web annotation session) is a blocking prerequisite for
Phase 4+. It must complete before any FETE, circuit, or spectral analysis begins.

### 3a — Automated PDF Color-Threshold Extraction (Pre-population Only)

**Purpose:** Detect the blue pen entrance marks on the scanned plan and export them as
candidate JSON for the web annotation tool to pre-populate. This step does NOT produce
final entrance coordinates. Its output is consumed only by the web annotator (Phase 3b).

**Why automated extraction alone is insufficient:**
- Pen marks are approximate (±1–3 mm on paper).
- HSV color thresholding will have false positives (blue ink elsewhere on the plan) and
  false negatives (faint marks, marks overlapping building outlines).
- Corner ambiguity: marks near corners can be assigned to the wrong wall side.
- Multi-entrance buildings: the automated pipeline silently keeps only the first mark found.

This step runs first because the web tool (Phase 3b) uses its output as a starting point
for the annotator, reducing annotation time significantly.

```python
def find_blue_marks(img_rgb, h_lo=90, h_hi=115, s_min=50, v_min=80):
    """
    Extract light-blue pen entrance marks from the rasterized PDF.
    
    TUNING PROCEDURE (must do this before running site-wide):
    1. Identify 5 marks near buildings 23-26 (confirmed from DXF)
    2. Convert those image patches to HSV
    3. Sample H, S, V values at the mark centroids
    4. Set h_lo = min(H_samples) - 5,  h_hi = max(H_samples) + 5
    5. Set s_min = min(S_samples) - 10, v_min = min(V_samples) - 10
    6. Run site-wide, then spot-check 10 random marks visually
    
    OpenCV HSV ranges: H in [0,179], S in [0,255], V in [0,255]
    Light blue pen in OpenCV HSV: H ~ 90-115, S >= 50, V >= 80
    """
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    
    mask = cv2.inRange(hsv,
                       np.array([h_lo, s_min, v_min]),
                       np.array([h_hi, 255, 255]))
    
    # Morphological close: connect dashes in dashed marks
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # Morphological open: remove isolated speckle noise
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    
    # Connected components
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    
    # Filter by area: marks are typically 50-2000 pixels at 400 DPI
    valid_idx = np.where(
        (stats[1:, cv2.CC_STAT_AREA] > 50) &
        (stats[1:, cv2.CC_STAT_AREA] < 2000)
    )[0] + 1  # +1 to skip background label 0
    
    valid_centroids = centroids[valid_idx]   # in PDF pixel space
    valid_stats = stats[valid_idx]
    
    return valid_centroids, valid_stats

def assign_marks_to_footprints(centroids_pdf, H, footprints_gdf, tolerance_m=3.0):
    """
    Transform PDF mark centroids to working CRS and assign to nearest footprint.
    Returns GeoDataFrame with mark locations and associated footprint IDs.
    """
    from shapely.geometry import Point
    
    results = []
    for cx, cy in centroids_pdf:
        crs_pt = pdf_px_to_crs(cx, cy, H)
        pt = Point(crs_pt[0], crs_pt[1])
        
        # Find nearest footprint
        dists = footprints_gdf.geometry.distance(pt)
        nearest_idx = dists.idxmin()
        nearest_dist = dists.min()
        
        if nearest_dist <= tolerance_m:
            fp = footprints_gdf.loc[nearest_idx]
            # Determine which wall the mark is nearest to
            wall_side = get_nearest_wall_side(pt, fp.geometry)
            results.append({
                "geometry": pt,
                "footprint_id": fp["id"],
                "dist_to_footprint_m": nearest_dist,
                "wall_side": wall_side,
                "source": "pdf_mark",
                "confidence": max(0.5, 1.0 - nearest_dist / tolerance_m)
            })
    
    return gpd.GeoDataFrame(results, crs=footprints_gdf.crs)

def get_nearest_wall_side(point, polygon):
    """
    Determine which cardinal wall side (N/S/E/W) of a polygon a point is closest to.
    """
    centroid = polygon.centroid
    dx = point.x - centroid.x
    dy = point.y - centroid.y
    
    if abs(dx) > abs(dy):
        return "E" if dx > 0 else "W"
    else:
        return "N" if dy > 0 else "S"
```

**Tuning procedure (run before site-wide extraction):**
1. Identify 5 marks on buildings 23–26 that were also found via DXF (known ground truth).
2. Convert those image patches to HSV and sample H, S, V at the mark centroids.
3. Set h_lo = min(H) - 5, h_hi = max(H) + 5, s_min = min(S) - 10, v_min = min(V) - 10.
4. Run site-wide; spot-check 10 random marks visually to assess false-positive rate.
5. If false-positive rate > 20%, tighten s_min or reduce area filter upper bound.

**After running find_blue_marks()**, export results using the preprocessing scripts
defined in PLAN_07 section 3b:

```python
# Export candidate marks for the web annotator
export_auto_marks(centroids, stats, "annotator/auto_marks.json")
```

Also export the shapefile footprints in pixel space (PLAN_07 section 3a) and the DXF
entrances in pixel space (PLAN_07 section 3c) so the annotator has all three layers.

Then open `annotator/index.html` in a browser to begin Phase 3b.

### 3b — Web Annotation Tool (Primary Source — Human Verified)

**Full specification in PLAN_07.** Summary for sequencing purposes:

The annotator opens `annotator/index.html` in a browser. The tool displays:
- The site plan (image.png) with building footprint polygons overlaid.
- Auto-candidate marks (from Phase 3a) shown as yellow dots on each building.
- DXF reference marks shown as blue diamonds on the 7 calibration buildings.

For each of the 263 buildings, the annotator:
1. Reviews the auto-candidate if one exists.
2. Confirms it (press C), moves it to the correct wall point, or marks as uncertain.
3. If no auto-candidate exists, clicks directly on the wall edge to place a mark.

Output: `annotator/annotations.geojson` with source = "web_annotated" and
confidence in [0.60, 0.90] depending on the action taken.

After the annotation session, run the post-processing script from PLAN_07 section 5:

```python
# Convert pixel coordinates to working CRS
postprocess_annotations(
    "annotator/annotations.geojson",
    H,  # from Phase 1b
    "100_Data/130_BuildingFootprintsVectorData/BuildingTracesCurrent/Buildings_Mask.shp",
    "data/processed/web_annotated_entrances.geojson"
)
```

This produces `data/processed/web_annotated_entrances.geojson`, which is the primary
entrance dataset for Phase 3f merge and all downstream analysis.

**Coverage audit (run immediately after post-processing):**

```python
import geopandas as gpd

footprints = gpd.read_file("BuildingTracesCurrent/Buildings_Mask.shp")
web_ann = gpd.read_file("data/processed/web_annotated_entrances.geojson")

marks_per_fp = web_ann.groupby("footprint_id").size()
missing = set(footprints["ID"].astype(str)) - set(marks_per_fp.index)
multi = marks_per_fp[marks_per_fp > 1]
uncertain = web_ann[web_ann["confidence"] == 0.60]

print(f"Annotated   : {len(marks_per_fp)} / {len(footprints)} buildings")
print(f"Missing     : {len(missing)} buildings (will use attribute fallback)")
print(f"Multi-entry : {len(multi)} buildings with 2+ entrances")
print(f"Uncertain   : {len(uncertain)} buildings flagged for expert review")
print(f"Missing IDs : {sorted(missing)}")
```

Buildings in `missing` proceed to Phase 3c (attribute fallback).
Buildings in `uncertain` are sent to the domain archaeologist; their Phase 3c
attribute-derived value is used as a placeholder until resolved.

### 3c — Attribute-Driven Entrance Derivation (Fallback for Unannotated Buildings)

```python
DIRECTION_VECTORS = {
    "N":  np.array([0,   1]),
    "S":  np.array([0,  -1]),
    "E":  np.array([1,   0]),
    "W":  np.array([-1,  0]),
    "NE": np.array([1,   1]) / np.sqrt(2),
    "NW": np.array([-1,  1]) / np.sqrt(2),
    "SE": np.array([1,  -1]) / np.sqrt(2),
    "SW": np.array([-1, -1]) / np.sqrt(2),
}

def entrance_from_direction(polygon, direction_str):
    """
    Pick the polygon edge whose outward normal best aligns with direction_str.
    Handles composite directions like "S/E" by trying both and returning the
    higher-scoring edge.
    
    polygon: shapely Polygon (footprint)
    direction_str: string like "S", "E", "S/E", "North", etc.
    Returns: shapely Point at the midpoint of the best-matching wall
    """
    # Parse composite directions
    direction_str = str(direction_str).upper().strip()
    directions = [d.strip() for d in direction_str.replace("/", " ").split()]
    
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
            norm_len = np.linalg.norm(normal)
            if norm_len < 1e-9:
                continue
            score = np.dot(normal / norm_len, target)
            if score > best_score:
                best_score = score
                best_pt = mid
    
    if best_pt is None:
        return polygon.centroid  # fallback if direction is unparseable
    
    from shapely.geometry import Point
    return Point(best_pt)

def derive_all_entrances(footprints_gdf, excel_db, crosswalk_df, entrace_dir_col):
    """
    Derive entrance points for all chapels using recorded entrance direction.
    """
    results = []
    
    for _, chapel_row in excel_db.iterrows():
        chapel_id = str(chapel_row["Chapel Number (according to Fakhry)"]).strip()  # Updated from audit
        direction = chapel_row.get(entrace_dir_col, None)
        
        # Find matching footprint via crosswalk
        cw_row = crosswalk_df[crosswalk_df["chapel_ids"].str.contains(chapel_id)]
        if cw_row.empty:
            continue
        
        fp_id = cw_row.iloc[0]["footprint_id"]
        fp_row = footprints_gdf[footprints_gdf["id"].astype(str) == fp_id]
        if fp_row.empty:
            continue
        
        polygon = fp_row.iloc[0].geometry
        
        if pd.notna(direction) and str(direction).strip():
            entrance_pt = entrance_from_direction(polygon, str(direction))
            source = "attribute_derived"
            confidence = 0.7
        else:
            entrance_pt = polygon.centroid
            source = "centroid_fallback"
            confidence = 0.3
        
        results.append({
            "geometry": entrance_pt,
            "chapel_id": chapel_id,
            "footprint_id": fp_id,
            "direction_recorded": str(direction),
            "source": source,
            "confidence": confidence,
        })
    
    return gpd.GeoDataFrame(results, crs=footprints_gdf.crs)
```

**Apply only to buildings not covered by Phase 3b (web_annotated).**

```python
web_ids = set(web_annotated["footprint_id"])
attr_fallback = attr_derived[~attr_derived["footprint_id"].isin(web_ids)]
print(f"Attribute fallback fills {len(attr_fallback)} buildings not covered by annotator")
```

### 3d — DXF-Derived Entrances (Highest Precision — Calibration + Override Set)

Use the extract_dxf_entrances() function from Phase 0d. Transform DXF coordinates to working
CRS by verifying alignment against shapefile footprints for the same buildings.

The 7 buildings with DXF files (1, 23, 24, 25, 26, 175, 210) have sub-centimetre entrance
precision from the architectural survey drawings. These override any web_annotated or
attribute_derived value for those buildings in the Phase 3f merge.

During Phase 3a tuning, verify that the auto-detected blue marks for these 7 buildings
are within 2 m of the DXF entrances — this validates the color-threshold parameters
before running site-wide extraction.

```python
# Validate Phase 3a candidates against DXF for calibration buildings
for fp_id, dxf_pt in dxf_entrances.items():
    candidates = auto_candidates[auto_candidates["footprint_id"] == str(fp_id)]
    if candidates.empty:
        print(f"WARNING: no auto-candidate for calibration building {fp_id}")
        continue
    dist = candidates.iloc[0].geometry.distance(dxf_pt)
    status = "OK" if dist < 2.0 else "MISMATCH"
    print(f"Building {fp_id}: auto vs DXF distance = {dist:.2f} m [{status}]")
```

Assign source = "dxf", confidence = 1.0.

### 3e — QA: Web Annotation vs Attribute Derivation Disagreement

```python
def entrance_agreement(pt_a, pt_b, polygon):
    """
    Compute agreement between two candidate entrance points.
    Returns: distance in map units, agreement confidence score (0-1).
    """
    dist = pt_a.distance(pt_b)
    bounds = polygon.bounds
    diag = np.sqrt((bounds[2]-bounds[0])**2 + (bounds[3]-bounds[1])**2)
    confidence = max(0.0, 1.0 - dist / diag)
    return dist, confidence

def generate_qa_sheet(web_annotated_gdf, attr_derived_gdf, footprints_gdf,
                      disagreement_threshold_m=2.0):
    """
    For each building covered by both web_annotated and attribute_derived,
    flag cases where the two sources disagree by more than the threshold.
    """
    qa_rows = []
    for _, fp in footprints_gdf.iterrows():
        fp_id = str(fp["ID"])
        web = web_annotated_gdf[web_annotated_gdf["footprint_id"] == fp_id]
        attr = attr_derived_gdf[attr_derived_gdf["footprint_id"] == fp_id]
        if web.empty or attr.empty:
            continue
        dist, conf = entrance_agreement(
            web.iloc[0].geometry, attr.iloc[0].geometry, fp.geometry)
        if dist > disagreement_threshold_m:
            qa_rows.append({
                "footprint_id": fp_id,
                "web_x": web.iloc[0].geometry.x,
                "web_y": web.iloc[0].geometry.y,
                "attr_x": attr.iloc[0].geometry.x,
                "attr_y": attr.iloc[0].geometry.y,
                "web_wall": web.iloc[0].get("wall_side", ""),
                "attr_wall": attr.iloc[0].get("wall_side", ""),
                "disagreement_m": round(dist, 2),
                "agreement_confidence": round(conf, 3),
            })
    qa_df = pd.DataFrame(qa_rows).sort_values("disagreement_m", ascending=False)
    qa_df.to_csv("data/crosswalk/entrance_qa_review.csv", index=False)
    print(f"QA sheet: {len(qa_df)} buildings need review")
    return qa_df
```

This QA step runs after Phases 3b and 3c are both complete. Its purpose is to identify
buildings where the web annotator placed a mark on a different wall than the Excel
entrance direction records — these may indicate:
- A recording error in the Excel database.
- A misidentification of the building in the web annotator.
- A genuine dual-access building where one source captured a different entrance.

Flagged rows go into `entrance_qa_review.csv` for archaeologist review.

### 3f — Merge All Entrance Sources and Output

Priority order (highest wins on conflict for a given building):
1. **dxf** (confidence = 1.0) — sub-centimetre architectural survey; 7 buildings
2. **web_annotated** (confidence = 0.75–0.90) — human-verified on registered site plan
3. **attribute_derived** (confidence = 0.70) — inferred from Excel entrance direction field
4. **centroid_fallback** (confidence = 0.30) — last resort for buildings with no direction

```python
def merge_entrance_sources(dxf_entrances, web_annotated, attr_derived, crosswalk_df):
    """
    Merge all entrance sources with priority:
        dxf > web_annotated > attribute_derived > centroid_fallback
    Output: one entrance per chapel_id (or multiple for multi-entrance buildings).
    """
    all_entrances = pd.concat([
        dxf_entrances.assign(priority=1),
        web_annotated.assign(priority=2),
        attr_derived.assign(priority=3),
    ], ignore_index=True)

    # For each footprint_id, keep the highest-priority (lowest priority number) source.
    # Exception: web_annotated multi-entrance buildings keep ALL their entries.
    multi_fp = (web_annotated.groupby("footprint_id")
                             .size()[lambda s: s > 1].index)

    single = (all_entrances[~all_entrances["footprint_id"].isin(multi_fp)]
              .sort_values("priority")
              .groupby("footprint_id")
              .first()
              .reset_index())

    multi = web_annotated[web_annotated["footprint_id"].isin(multi_fp)]

    merged = pd.concat([single, multi], ignore_index=True)
    return gpd.GeoDataFrame(merged, crs=attr_derived.crs)
```

**Output:** `data/processed/entrances.geojson` with fields:
- footprint_id (from Buildings_Mask.shp ID field)
- chapel_id (from crosswalk; may be a comma-separated list for multi-chapel footprints)
- geometry (entrance point in working CRS)
- source: "dxf" | "web_annotated" | "attribute_derived" | "centroid_fallback"
- wall_side: N/S/E/W (cardinal wall the entrance is on)
- confidence: 0.0–1.0
- direction_recorded: raw Excel field value (present for attribute_derived only)
- auto_candidate: True/False (web_annotated only — was there an auto-mark to start from)
- candidate_moved: True/False (web_annotated only — did annotator reposition it)
- agreement_dist_m: distance to closest alternative-source candidate (QA field)

**Final coverage check before proceeding to Phase 4:**

```python
print(f"Total entrance features  : {len(merged)}")
print(f"Unique footprints covered: {merged['footprint_id'].nunique()} / {len(footprints)}")
print(f"Source breakdown:")
print(merged['source'].value_counts())
print(f"Confidence distribution:")
print(merged['confidence'].describe())
assert merged['footprint_id'].nunique() == len(footprints), \
    "ERROR: not all buildings have an entrance — check attribute fallback coverage"
```

Do not proceed to Phase 4 until this assertion passes.
