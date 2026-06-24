# PLAN_07 — Manual Entrance Annotation Web Tool
## El-Bagawat task2

---

## 1. Why This Tool Exists

The automated PDF color-threshold extraction (Phase 3a) will inevitably produce:

- **False positives** — blue artefacts on the plan that are not entrance marks (ink bleed,
  registration marks, legend symbols, dimension lines).
- **False negatives** — marks too faint, partially occluded by building outlines, or outside
  the HSV threshold window due to scan variation across the 1.4 GB PDF.
- **Corner ambiguity** — marks near building corners where the nearest-wall assignment flips
  between two cardinal sides depending on sub-pixel centroid position.
- **Multi-mark buildings** — some chapels with two documented access points; the automated
  pipeline silently keeps only the first.

The plan already required a manual QA step (entrance_qa_review.csv). Rather than reviewing a
spreadsheet with X/Y numbers, a purpose-built interactive map tool makes this fast and
visually unambiguous. A trained annotator can verify or correct 260+ buildings in 2–4 hours.

**Role in the pipeline:**

```
Phase 3a (auto extract PDF marks)  -->  candidates JSON   [pre-population only]
         |
         v
Phase 3b (web annotator)           -->  verified entrances GeoJSON  [primary source]
         |
         v
Phase 3c (attribute fallback)      -->  fills any still-missing buildings
         |
         v
Phase 3d (DXF calibration set)     -->  overrides with sub-cm precision for 7 buildings
         |
         v
Phase 3e (merge & output)          -->  data/processed/entrances.geojson
```

---

## 2. Tool Architecture

### 2.1 Inputs

| File | Description | How produced |
|---|---|---|
| `annotator/image.png` | Site plan scan (already exists in plan/) | Copy from plan/image.png |
| `annotator/buildings.geojson` | Building footprint polygons in image-pixel coordinates | Preprocessing script (section 3a) |
| `annotator/auto_marks.json` | Candidate entrance centroids from Phase 3a color-threshold | Phase 3a script output |
| `annotator/dxf_entrances.json` | 7 DXF-derived precision entrances | Phase 3 DXF extraction output |
| `annotator/annotations.geojson` | Saved annotation output (written by the tool, resumed on reload) | Tool output |

### 2.2 Output Schema

`annotator/annotations.geojson` — one GeoJSON Feature per annotated entrance:

```json
{
  "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [px, py] },
  "properties": {
    "footprint_id": "42",
    "wall_side": "S",
    "source": "web_annotated",
    "auto_candidate": true,
    "candidate_moved": false,
    "confidence": 0.90,
    "annotator_note": "",
    "timestamp": "2026-06-23T15:00:00Z"
  }
}
```

Confidence assignment rules:

| Situation | Confidence |
|---|---|
| Annotator confirmed auto-candidate without moving it | 0.90 |
| Annotator moved auto-candidate by less than 1 building width | 0.85 |
| Annotator moved auto-candidate by more than 1 building width | 0.80 |
| Annotator placed new mark where no auto-candidate existed | 0.75 |
| Annotator marked as "uncertain" (mark ambiguous on plan) | 0.60 |

### 2.3 Pixel-to-CRS Conversion (Post-annotation)

The tool works entirely in **image pixel coordinates** (annotator clicks on the PNG).
After annotation is complete, a post-processing Python script converts pixel coordinates
to working CRS using the homography H from Phase 1b.

```python
def px_to_crs(px, py, H):
    """Convert annotated pixel coordinate to working CRS via homography."""
    pt = np.array([[px, py, 1.0]], dtype=np.float64)
    mapped = (H @ pt.T).T
    return mapped[0, :2] / mapped[0, 2]  # [mapX, mapY]
```

This keeps the web tool stateless (no CRS knowledge required in the browser) and makes
coordinate conversion auditable and repeatable independently of the tool itself.

---

## 3. Preprocessing Script (Python)

Run before opening the web tool. Produces all JSON input files the tool needs at runtime.

### 3a — Convert Shapefile to Image-Pixel GeoJSON

The shapefile is in working CRS. The inverse homography H_inv (CRS to pixel) projects
each building polygon into image space for overlay on the PNG.

```python
import json
import numpy as np
import geopandas as gpd

def crs_to_px(x, y, H_inv):
    """Map a working CRS coordinate to an image pixel coordinate."""
    pt = np.array([[x, y, 1.0]], dtype=np.float64)
    mapped = (H_inv @ pt.T).T
    return (mapped[0, :2] / mapped[0, 2]).tolist()

def export_buildings_for_annotator(footprints_path, H_inv, out_path):
    """
    Project all building footprint polygons into image pixel space.

    footprints_path: path to Buildings_Mask.shp
    H_inv: 3x3 inverse homography (working CRS -> pixel).
           Computed as np.linalg.inv(H) where H is from Phase 1b fit_pdf_to_crs().
    out_path: output path for annotator/buildings.geojson
    """
    gdf = gpd.read_file(footprints_path)
    features = []

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue

        # Handle MultiPolygon (some chapels share a compound building)
        if geom.geom_type == "MultiPolygon":
            rings = [list(p.exterior.coords) for p in geom.geoms]
        else:
            rings = [list(geom.exterior.coords)]

        px_rings = []
        for ring in rings:
            px_ring = [crs_to_px(x, y, H_inv) for x, y in ring]
            px_rings.append(px_ring)

        # Centroid in pixel space for label positioning
        cx, cy = crs_to_px(geom.centroid.x, geom.centroid.y, H_inv)

        # Bounding box in pixel space for spatial indexing in JS
        xs = [p[0] for ring in px_rings for p in ring]
        ys = [p[1] for ring in px_rings for p in ring]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": px_rings
            },
            "properties": {
                "footprint_id": str(row["ID"]),
                "elevation": float(row["Elevation"]) if row["Elevation"] else None,
                "type": str(row.get("Type", "")),
                "centroid_px": [round(cx, 1), round(cy, 1)],
                "bbox_px": [round(min(xs), 1), round(min(ys), 1),
                            round(max(xs), 1), round(max(ys), 1)]
            }
        })

    fc = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w") as f:
        json.dump(fc, f)
    print(f"Exported {len(features)} buildings -> {out_path}")

# Usage:
# H = fit_pdf_to_crs(gcps_df)   # from Phase 1b
# H_inv = np.linalg.inv(H)
# export_buildings_for_annotator(
#     "100_Data/130_BuildingFootprintsVectorData/BuildingTracesCurrent/Buildings_Mask.shp",
#     H_inv,
#     "annotator/buildings.geojson"
# )
```

### 3b — Export Auto-Candidate Marks

```python
import cv2

def export_auto_marks(centroids_pdf, stats_pdf, out_path):
    """
    Export Phase 3a color-threshold candidates to JSON for the annotator.

    centroids_pdf: Nx2 array of [px, py] in image pixel space
                   (output of find_blue_marks() from PLAN_02 Phase 3a)
    stats_pdf: corresponding Nx7 stats array from cv2.connectedComponentsWithStats
    out_path: output path for annotator/auto_marks.json
    """
    marks = []
    for i, (cx, cy) in enumerate(centroids_pdf):
        marks.append({
            "id": i,
            "px": round(float(cx), 1),
            "py": round(float(cy), 1),
            "area_px": int(stats_pdf[i, cv2.CC_STAT_AREA]),
            "source": "auto_threshold",
            "verified": False
        })

    with open(out_path, "w") as f:
        json.dump(marks, f)
    print(f"Exported {len(marks)} auto-candidate marks -> {out_path}")

# Usage (after running find_blue_marks on the rasterized PDF):
# centroids, stats = find_blue_marks(img_rgb)
# export_auto_marks(centroids, stats, "annotator/auto_marks.json")
```

### 3c — Export DXF Calibration Entrances

```python
def export_dxf_entrances(dxf_entrance_dict, H_inv, out_path):
    """
    dxf_entrance_dict: {footprint_id: shapely.Point in working CRS}
                       Output of extract_dxf_entrances() from Phase 0d.
    H_inv: inverse homography (working CRS -> pixel)
    """
    marks = []
    for fp_id, pt in dxf_entrance_dict.items():
        px, py = crs_to_px(pt.x, pt.y, H_inv)
        marks.append({
            "footprint_id": str(fp_id),
            "px": round(px, 1),
            "py": round(py, 1),
            "source": "dxf",
            "confidence": 1.0
        })

    with open(out_path, "w") as f:
        json.dump(marks, f)
    print(f"Exported {len(marks)} DXF entrances -> {out_path}")

# Usage:
# dxf_dict = {25: dxf_pt_25, 175: dxf_pt_175, ...}  # from Phase 0d
# export_dxf_entrances(dxf_dict, H_inv, "annotator/dxf_entrances.json")
```

---

## 4. Web Tool Specification

### 4.1 Interface Layout

```
+-------------------------------------------------------------------------+
|  El-Bagawat Entrance Annotator          [Progress: 47 / 263]  [Export]  |
+-------------------------------------------------------------------------+
|  [Site Plan] [Satellite]  Zoom: [-][+]  Layer: [Buildings][Marks][DXF]  |
+-------------------------------------------------------------------------+
|                                                                         |
|   (full-screen pan/zoom canvas with image + polygon overlay)            |
|                                                                         |
|   Legend:  [] pending   [G] annotated   [B] DXF-exact   [Y] auto-mark  |
|                                                                         |
+-------------------------------------------------------------------------+
|  Selected: Building 42  | Wall: South  | (o) Confirm  ( ) Move  ( ) ?  |
|  [<- Prev]              [Skip]                           [Next ->]       |
+-------------------------------------------------------------------------+
```

### 4.2 Interaction Flow

**Step 1 — Select a building**
- Annotator clicks on any building polygon on the canvas (highlighted on hover).
- Alternatively, the "Next" button cycles through all 263 buildings in ID order,
  prioritising unvisited buildings first.
- Selected building animates to centre of viewport with a smooth pan/zoom if needed.

**Step 2 — Review auto-candidate (if one exists)**
- Any auto-detected blue mark whose centroid falls within the building's bounding box
  is shown as a yellow dot snapped to the nearest wall.
- The information panel shows: footprint_id, auto-mark area in pixels, inferred wall side.
- Annotator chooses:
  - **Confirm** — accept the auto-candidate as-is. Assigned confidence = 0.90.
  - **Move** — click the correct point on the building's wall edge; marker snaps to wall.
    Confidence = 0.85 or 0.80 depending on move distance.
  - **Uncertain** — plan mark is ambiguous or absent. Flag for offline expert review.
    Confidence = 0.60.

**Step 3 — No auto-candidate**
- Building shown in pending (grey) state.
- Annotator clicks directly on the wall edge of the building polygon.
- Wall-snap logic places the marker exactly on the boundary. Confidence = 0.75.

**Step 4 — Multi-entrance buildings**
- A "+Add entrance" button allows placing a second (or third) marker on the same building.
- Each entrance gets its own GeoJSON feature with the same `footprint_id`.
- The network graph Phase downstream will create one node per entrance feature for such
  buildings — this is the correct handling.

**Step 5 — Persistence and export**
- Every confirmed mark is saved to browser localStorage immediately (session is resumable).
- "Export" button downloads `annotations.geojson` to the local filesystem.
- The tool must be opened as a local file in a browser (no server required) — all data
  files are loaded via fetch() relative to the HTML file location.

### 4.3 Wall-Snap Logic

When the annotator clicks anywhere near a selected building:

```
1. Enumerate all edge segments of the building polygon exterior ring.
2. For each segment AB, compute the perpendicular foot F of the click point P:
       t = dot(P - A, B - A) / dot(B - A, B - A)
       t_clamped = clamp(t, 0, 1)
       F = A + t_clamped * (B - A)
3. Keep the foot F_min with the minimum distance to P.
4. Place entrance marker at F_min (guaranteed to lie on the polygon boundary).
5. Determine wall_side:
       outward_normal = rotate(B - A, -90 degrees) (right-hand side of directed edge)
       wall_side = argmax( dot(outward_normal / |outward_normal|, {N:[0,1], S:[0,-1],
                                                                    E:[1,0], W:[-1,0]}) )
```

This approach is correct for any polygon shape — it does not assume rectangles.

### 4.4 Map Layers

| Layer | Toggle Key | Default | Description |
|---|---|---|---|
| Site plan (image.png) | `1` | ON | Scanned architectural drawing with original blue pen marks |
| Satellite (WV-2 RGB) | `2` | OFF | Natural-colour composite (Bands 5-3-2) for real-world orientation |
| Building polygons | `B` | ON | Buildings_Mask.shp footprints; colour = annotation status |
| Auto-mark candidates | `A` | ON | Yellow dots from Phase 3a; dims after confirmation |
| Confirmed marks | `M` | ON | Green circles with wall-direction tick |
| DXF reference marks | `D` | ON | Blue diamonds; display only, not editable |

**Satellite layer prerequisite:** A pan-sharpened or RGB-composite GeoTIFF from the WV-2
data must be resampled to the same pixel grid as image.png using the homography H.
This is a Phase 1c product. If not yet available when annotation begins, satellite toggle
stays disabled — annotation on the site plan alone is sufficient.

### 4.5 Keyboard Shortcuts

| Key | Action |
|---|---|
| `C` | Confirm auto-candidate for selected building |
| `U` | Mark current building as uncertain |
| `Right arrow` | Next building |
| `Left arrow` | Previous building |
| `S` | Skip building (return to it later) |
| `Z` | Undo last placed/confirmed mark |
| `+` / `-` | Zoom in / out canvas |
| `E` | Export annotations.geojson |
| `1` / `2` | Toggle site plan / satellite layer |

---

## 5. Post-Processing Script

After annotation session is complete, run to convert pixel coordinates to working CRS
and produce the input file for the Phase 3e merge step.

```python
import json
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

def postprocess_annotations(annotations_path, H, footprints_path, out_geojson_path):
    """
    Convert annotated pixel coordinates to working CRS.
    Merge with footprint IDs and compute coverage report.

    annotations_path: annotator/annotations.geojson
    H: 3x3 homography (pixel -> working CRS) from Phase 1b fit_pdf_to_crs()
    footprints_path: Buildings_Mask.shp
    out_geojson_path: data/processed/web_annotated_entrances.geojson
    """
    with open(annotations_path) as f:
        ann = json.load(f)

    gdf = gpd.read_file(footprints_path)
    rows = []

    for feat in ann["features"]:
        props = feat["properties"]
        px = feat["geometry"]["coordinates"][0]
        py = feat["geometry"]["coordinates"][1]

        # Pixel -> working CRS
        pt_h = np.array([[px, py, 1.0]], dtype=np.float64)
        mapped = (H @ pt_h.T).T
        map_x, map_y = mapped[0, :2] / mapped[0, 2]

        rows.append({
            "geometry": Point(map_x, map_y),
            "footprint_id": props["footprint_id"],
            "wall_side": props.get("wall_side", ""),
            "source": "web_annotated",
            "auto_candidate": props.get("auto_candidate", False),
            "candidate_moved": props.get("candidate_moved", False),
            "confidence": props.get("confidence", 0.80),
            "annotator_note": props.get("annotator_note", ""),
            "px_original": round(px, 1),
            "py_original": round(py, 1),
        })

    result = gpd.GeoDataFrame(rows, crs=gdf.crs)
    result.to_file(out_geojson_path, driver="GeoJSON")
    print(f"Exported {len(result)} annotated entrances -> {out_geojson_path}")

    # Coverage report
    n_total = len(gdf)
    n_annotated = result["footprint_id"].nunique()
    n_uncertain = sum(1 for f in ann["features"]
                      if f["properties"].get("confidence", 1.0) == 0.60)
    n_multi = (result.groupby("footprint_id").size() > 1).sum()
    n_confirmed = sum(1 for f in ann["features"]
                      if f["properties"].get("auto_candidate") and
                         not f["properties"].get("candidate_moved"))
    n_moved = sum(1 for f in ann["features"]
                  if f["properties"].get("candidate_moved"))

    print(f"\n=== Annotation Coverage Report ===")
    print(f"Buildings annotated : {n_annotated}/{n_total} "
          f"({100*n_annotated/n_total:.1f}%)")
    print(f"Uncertain flags     : {n_uncertain}")
    print(f"Multi-entrance      : {n_multi}")
    print(f"Auto confirmed      : {n_confirmed}")
    print(f"Auto moved          : {n_moved}")
    print(f"New marks (no auto) : {len(result) - n_confirmed - n_moved}")

    return result

# Usage (after annotation session):
# web_annotated = postprocess_annotations(
#     "annotator/annotations.geojson",
#     H,
#     "100_Data/130_BuildingFootprintsVectorData/BuildingTracesCurrent/Buildings_Mask.shp",
#     "data/processed/web_annotated_entrances.geojson"
# )
```

---

## 6. Quality Metrics to Report After Annotation

| Metric | Target | Action if missed |
|---|---|---|
| Coverage: buildings with confirmed entrance | >= 95% of 263 | Second annotation pass for remaining buildings |
| Auto-candidate confirmation rate | Report; no threshold | Low rate = Phase 3a threshold needs retuning |
| Auto-candidate move rate | Report; no threshold | High move rate = auto-extraction has poor precision |
| Uncertain flags | <= 10 buildings | Send to domain expert (archaeologist) for offline review |
| Multi-entrance buildings detected | Record count | Each entrance becomes a separate node in Phase 4+ graph |
| Median move distance (moved candidates) | Report in map units | Quantifies systematic bias in auto-extraction |

---

## 7. Repository Locations

```
annotator/
+-- index.html                       <- The annotation tool (single self-contained HTML file)
+-- image.png                        <- Site plan (copied from plan/image.png)
+-- buildings.geojson                <- Preprocessing output (script 3a)
+-- auto_marks.json                  <- Preprocessing output (script 3b)
+-- dxf_entrances.json               <- Preprocessing output (script 3c)
+-- annotations.geojson              <- Tool output (written during annotation session)
+-- README.md                        <- How to run preprocessing + tool

scripts/
+-- prepare_annotator_inputs.py      <- Runs preprocessing scripts 3a + 3b + 3c above
+-- postprocess_annotations.py       <- Runs section 5 post-processing

data/processed/
+-- web_annotated_entrances.geojson  <- CRS-converted output; input to Phase 3e merge
```

---

## 8. Sequencing Within the Master Pipeline

```
Phase 1b  (register PDF via GCPs -> H homography matrix)
    |
    v
Phase 3a  (run find_blue_marks on rasterized PDF -> auto_marks.json)
    |
    v
scripts/prepare_annotator_inputs.py
    (export buildings.geojson + auto_marks.json + dxf_entrances.json)
    |
    v
[Human: open annotator/index.html in browser, annotate all 263 buildings]
  Estimated time: 2-4 hours for one trained annotator
    |
    v
scripts/postprocess_annotations.py
    (pixel -> working CRS; produce web_annotated_entrances.geojson)
    |
    v
Phase 3e merge:
  priority = dxf (1.0) > web_annotated (0.75-0.90) > attribute_derived (0.70)
                                                    > centroid_fallback (0.30)
    |
    v
Phase 4+: FETE, circuit model, SPI all use entrances.geojson as the node set
```

The annotation session is a **hard sequential blocker** for Phase 4.
It cannot be parallelised with the Phase 4+ analysis.
Phase 3c (attribute-driven fallback) should be run first so it pre-populates coverage
for any buildings the annotator skips — the merge step then overwrites those with
web_annotated entries where they exist.
