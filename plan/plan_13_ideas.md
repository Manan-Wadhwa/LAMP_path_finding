# Comprehensive Plan: 13 Approaches to Door Detection at El Bagawat

This document outlines 13 distinct methodologies for extracting door locations, divided into two categories: **Geometric/DXF-Based** and **Computer Vision/Image-Based**. Each approach is treated as an independent task with its own implementation strategy, potential pitfalls, and solutions.

---

## Part 1: DXF & Geometric Approaches

### Idea 1: ARC-Based Door Detection
**The Concept:** The DXF drafter explicitly drew door swings as ARC entities on the `LW1` and `ABOVE` layers. We extract these arcs, use their centers as door hinges, and their radii as door widths.
- **Implementation:** 
  1. Filter `ezdxf` modelspace for `ARC` entities on specific layers.
  2. Filter by radius (e.g., 150 < R < 500) and sweep angle (~160-180°).
  3. Transform the ARC center to UTM using the global affine matrix.
  4. Snap the UTM center to the nearest Shapefile polygon edge.
- **Pitfalls:** 
  - *Not all doors have arcs.* Only ~50 arcs exist for ~256 buildings.
  - *Global affine drift.* If the affine transform is off by 5m, snapping to the nearest edge might place the door on the wrong wall entirely.
- **Solutions:** 
  - Use this as a high-confidence *partial* solution. 
  - Apply the Per-Building Local Transform (Idea 4) to the arc centers before snapping to guarantee they land on the correct wall.

### Idea 2: Layer-Filtered Gap Detection
**The Concept:** The original topological gap detection failed because it included interior walls and dividers from layers `LW1` and `LW2`. We filter to ONLY use the `BUILDINGS` layer.
- **Implementation:** 
  1. Extract only `LWPOLYLINE` entities from the `BUILDINGS` layer.
  2. Run the existing graph-based loose-end detection algorithm.
  3. Transform and project to the Shapefile.
- **Pitfalls:** 
  - *Shared walls.* Row buildings share a continuous polyline, meaning no gaps exist between them on the exterior `BUILDINGS` layer.
  - *Drafting inconsistencies.* Some exterior walls might have accidentally been drawn on `LW1`.
- **Solutions:** 
  - Combine with Idea 1: use arcs for row buildings, and layer-filtered gaps for isolated chapels.

### Idea 3: Closed-Polyline Shape Matching
**The Concept:** Abandon coordinates entirely. Cluster DXF lines by proximity to form building "shapes." Match these shapes to Shapefile polygons using scale-invariant and rotation-invariant shape metrics (e.g., Hu Moments).
- **Implementation:** 
  1. Group DXF lines into spatial clusters.
  2. Compute the convex hull or contour of each cluster.
  3. Calculate shape descriptors for DXF clusters and Shapefile polygons.
  4. Find the best match, align the shapes, and find the gap.
- **Pitfalls:** 
  - *Ambiguous shapes.* Many chapels are nearly identical squares; shape matching will easily confuse them.
  - *Incomplete clusters.* Broken DXF lines might create shapes that don't look like their corresponding Shapefile polygons.
- **Solutions:** 
  - Use the existing Bipartite Label Match as a prior. Only compare shape features for buildings that are already spatially correlated by their text labels.

### Idea 4: Per-Building ICP (Iterative Closest Point)
**The Concept:** Instead of one global affine transform, compute a rigid transformation (translation + rotation) for *each individual building* to align its DXF walls to its Shapefile boundary.
- **Implementation:** 
  1. Iterate through matched buildings.
  2. Buffer the DXF label by 15m and extract local DXF lines.
  3. Extract the target Shapefile polygon coordinates.
  4. Run an ICP algorithm to minimize the distance between the DXF lines and the polygon edges.
  5. The gaps in the aligned DXF lines indicate the door.
- **Pitfalls:** 
  - *Local minima.* ICP requires a good initial guess. If the DXF walls are initially too far off, ICP might align the North DXF wall to the East Shapefile wall.
  - *Symmetry.* Square buildings have symmetric edges, confusing the optimizer.
- **Solutions:** 
  - Use the global affine transform *first* as the initial guess, then run ICP to handle the remaining 2-5m local refinement.

### Idea 5: Rasterize + CV Subtraction
**The Concept:** Convert both the DXF and the Shapefile into high-resolution binary images and use image subtraction to find the gaps.
- **Implementation:** 
  1. Rasterize a building's Shapefile boundary (white lines on black background).
  2. Rasterize the locally-aligned DXF walls (white lines).
  3. Apply morphological dilation to the DXF image to account for slight misalignments.
  4. XOR the two images. White blobs remaining on the boundary indicate doors.
- **Pitfalls:** 
  - *Resolution tradeoffs.* High resolution requires massive memory; low resolution loses the 1m door gap.
  - *Thick walls.* Dilation might accidentally close the door gap entirely.
- **Solutions:** 
  - Rasterize on a per-building basis (e.g., a 40x40 meter grid at 5cm/px) rather than the entire site at once.

### Idea 6: Perimeter Coverage Ratio
**The Concept:** Project DXF lines onto the Shapefile polygon. The wall with the least projected coverage is the wall with the door.
- **Implementation:** 
  1. Explode the Shapefile polygon into its constituent line segments (North, South, East, West walls).
  2. For each segment, calculate the distance to all nearby DXF lines.
  3. Sum the length of DXF lines that are parallel and close to the segment.
  4. The segment with a coverage ratio significantly less than 1.0 contains the door.
- **Pitfalls:** 
  - *Partial destruction.* If a wall is ruined and missing from the DXF, it will be flagged as a massive door.
- **Solutions:** 
  - Cap the maximum door width (e.g., 2.0m). If a gap is larger than that, place a standard 1.0m door in the center of the gap.

### Idea 7: Pure DXF Space Analysis
**The Concept:** Perform all door detection logic entirely within the raw DXF coordinate space, completely ignoring the Shapefile until the final step.
- **Implementation:** 
  1. Detect gaps or arcs in raw DXF space.
  2. Calculate the parametric position of the door relative to its building (e.g., "Centered on the South wall").
  3. Apply that parametric rule ("Center of South Wall") natively to the corresponding Shapefile polygon.
- **Pitfalls:** 
  - *Shape mismatch.* If the DXF building is a rectangle but the Shapefile building was digitized as a slightly angled trapezoid, "South wall" might be ambiguous.
- **Solutions:** 
  - Use bounding box edge proximity to robustly define "South wall" regardless of minor topological variations.

---

## Part 2: Computer Vision & Map Image Approaches

### Idea 8: CV on the Map Image Directly (Blue Channel Extraction)
**The Concept:** The hand-annotated `map.png` has blue marks indicating doors. Extract these using color thresholding.
- **Implementation:** 
  1. Read `map.png` with OpenCV.
  2. Convert to HSV color space.
  3. Mask out everything except the specific blue hue of the annotations.
  4. Run contour detection on the mask to find the door blobs.
  5. Calculate the centroid and orientation of each blob.
- **Pitfalls:** 
  - *Color bleed/artifacts.* JPEG compression or scanning artifacts might introduce stray blue pixels.
  - *Overlapping annotations.* Blue marks might cross black wall lines, splitting a single door into two contours.
- **Solutions:** 
  - Apply Gaussian blurring and morphological closing (dilate then erode) to merge split contours and remove noise before centroid calculation.

### Idea 9: Diff the Map Against a DXF Raster
**The Concept:** If color thresholding fails, subtract a clean rasterization of the DXF from the annotated map to isolate the hand-drawn additions.
- **Implementation:** 
  1. Rasterize the clean DXF to an image matching the dimensions of `map.png`.
  2. Align the two images using feature matching (SIFT/ORB) or manual control points.
  3. Subtract the DXF image from `map.png`.
  4. The remaining high-contrast pixels are the hand annotations.
- **Pitfalls:** 
  - *Alignment mismatch.* The scanned map might have lens distortion or paper warping that the perfect CAD raster lacks.
- **Solutions:** 
  - Use an elastic/non-rigid registration algorithm (like Thin Plate Spline) rather than a rigid transform to align the images.

### Idea 10: Map -> Shapefile Registration (Georeferencing)
**The Concept:** Once we extract the door pixels from `map.png` (using Idea 8), we need them in real-world UTM coordinates. We georeference the image itself.
- **Implementation:** 
  1. Identify 4-6 distinct building corners in `map.png` (pixel coordinates).
  2. Identify the same 4-6 corners in the Shapefile (UTM coordinates).
  3. Compute a perspective transform matrix (Homography).
  4. Warp the extracted door centroids through the matrix into UTM space.
- **Pitfalls:** 
  - *Non-linear distortion.* A global homography assumes the map is a perfectly flat plane. Paper folds or scanning warps will cause localized errors.
- **Solutions:** 
  - Georeference locally. Match building labels from the map to the Shapefile, and apply local translations for the door marks nearest to each label.

### Idea 11: Template Matching for Blue Crosses
**The Concept:** Instead of just looking for blue pixels, look for the specific *shape* of the annotation (e.g., a "T" shape where the blue mark hits a black wall).
- **Implementation:** 
  1. Crop 5-10 clean examples of annotated doors from the map.
  2. Use OpenCV's `matchTemplate` to slide these examples across the whole image.
  3. Threshold the correlation map to find all matches.
- **Pitfalls:** 
  - *Rotation and Scale.* Template matching is strictly scale and rotation dependent. The doors are drawn at many different angles.
- **Solutions:** 
  - Rotate the template 360 degrees in 5-degree increments and match at each angle, taking the maximum response.

### Idea 12: Annotations as Training Data (ML Classifier)
**The Concept:** Use the annotated map not just for extracting doors, but as ground truth to train a model that learns *where* doors typically belong based on building geometry.
- **Implementation:** 
  1. Extract the geometric features of every building (area, aspect ratio, orientation, neighbor proximity).
  2. Use the map annotations to label the "Target Wall" (North, South, East, West) for each building.
  3. Train a Random Forest or simple MLP classifier.
  4. Use the model to predict doors for any buildings where annotations are missing or unclear.
- **Pitfalls:** 
  - *Small dataset.* ~256 buildings might not be enough data for an ML model to generalize complex architectural rules.
- **Solutions:** 
  - Keep the feature space extremely small and interpretable (e.g., just orientation and neighbor distance).

### Idea 13: Hybrid — ARC Entities + Map CV
**The Concept:** Combine the highest-confidence data sources. The DXF Arcs provide mathematically perfect geometry, while the annotated map provides human ground truth.
- **Implementation:** 
  1. Extract ARC entities (Idea 1).
  2. Extract map annotations via CV (Idea 8).
  3. Cross-reference: If an ARC exists, use it. If no ARC exists but a map annotation does, use the CV coordinate. If neither exists, fall back to Idea 7 (Parametric placement based on neighbor logic).
- **Pitfalls:** 
  - *Conflicting data.* The DXF arc might be on the East wall, but the hand annotation might be on the South wall.
- **Solutions:** 
  - Establish a strict hierarchy of trust. Usually, the human-annotated map is the ultimate ground truth, superseding the CAD drafter's assumptions.
