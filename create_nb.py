import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

# Cell 1: Markdown
cells.append(nbf.v4.new_markdown_cell("""# Master Vector Pipeline
This notebook implements the robust extraction pipeline:
1. **Topological Gap Detection**: Extracts entrances directly from DXF lines.
2. **CAD-to-GIS Affine Transform**: Computes precision alignment from DXF labels.
3. **Hungarian Bipartite Match**: Prevents overlapping label collisions.
4. **Master Geodatabase Assembly**: Consolidates all outputs."""))

# Cell 2: Imports
cells.append(nbf.v4.new_code_cell("""import ezdxf
import networkx as nx
from shapely.geometry import Point, LineString
import numpy as np
import geopandas as gpd
import pandas as pd
from scipy.optimize import linear_sum_assignment
import cv2
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# Paths
SHP_PATH = r"C:\\Users\\Public\\LAMP_DataStore\\ElBagawat\\100_Data\\130_BuildingFootprintsVectorData\\BuildingTracesCurrent\\Buildings_Mask.shp"
DXF_WORKING = r"C:\\Users\\Public\\LAMP_DataStore\\ElBagawat\\100_Data\\120_SiteReport\\BaseSiteCAD\\Site_CAD_Working_converted.dxf"
OUT_GPKG = r"C:\\Users\\Public\\LAMP_DataStore\\ElBagawat\\200_Projects\\210_GSOC\\code-manan\\ElBagawat_Master.gpkg"
OUT_CSV = r"C:\\Users\\Public\\LAMP_DataStore\\ElBagawat\\200_Projects\\210_GSOC\\code-manan\\ElBagawat_Crosswalk.csv"
"""))

# Cell 3: Gap Detection
cells.append(nbf.v4.new_code_cell("""def extract_dxf_entrances_and_plot(dxf_path, gap_min=0.5, gap_max=2.5, snap_tol=0.2):
    print("Extracting DXF Entrances via Topological Gap Detection...")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    lines = []
    for entity in msp.query('LINE'):
        lines.append(((entity.dxf.start.x, entity.dxf.start.y),
                      (entity.dxf.end.x, entity.dxf.end.y)))
    if not lines: return []
    
    G = nx.Graph()
    def snap(pt, nodes, tol):
        for n in nodes:
            if np.hypot(pt[0]-n[0], pt[1]-n[1]) < tol:
                return n
        return pt
        
    for p1, p2 in lines:
        n1 = snap(p1, G.nodes, snap_tol)
        n2 = snap(p2, G.nodes, snap_tol)
        G.add_edge(n1, n2)
        
    loose_ends = [n for n in G.nodes if G.degree(n) == 1]
    entrances = []
    
    for i in range(len(loose_ends)):
        for j in range(i+1, len(loose_ends)):
            p1, p2 = loose_ends[i], loose_ends[j]
            dist = np.hypot(p1[0]-p2[0], p1[1]-p2[1])
            if gap_min <= dist <= gap_max:
                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
                entrances.append(Point(mid_x, mid_y))
                
    print(f"Found {len(entrances)} entrances via gap detection in DXF.")
    
    # Plotting
    plt.figure(figsize=(10, 10))
    for p1, p2 in lines:
        plt.plot([p1[0], p2[0]], [p1[1], p2[1]], color='blue', alpha=0.3, linewidth=1)
    
    ex = [p.x for p in entrances]
    ey = [p.y for p in entrances]
    plt.scatter(ex, ey, color='red', s=30, label='Detected Entrances', zorder=5)
    plt.title("DXF Line Topology and Detected Gaps")
    plt.legend()
    plt.axis('equal')
    plt.savefig("step1_gaps.png")
    plt.show()
    
    return entrances

dxf_entrances_raw = extract_dxf_entrances_and_plot(DXF_WORKING)
"""))

# Cell 4: DXF Labels & Affine Transform
cells.append(nbf.v4.new_code_cell("""print("Extracting labels directly from DXF...")
doc = ezdxf.readfile(DXF_WORKING)
dxf_labels = {}
for e in doc.modelspace().query('TEXT MTEXT'):
    text = e.dxf.text.strip()
    if text.isdigit():
        dxf_labels[text] = (e.dxf.insert.x, e.dxf.insert.y)
print(f"Extracted {len(dxf_labels)} building labels from DXF.")

footprints = gpd.read_file(SHP_PATH)
footprints['ID'] = footprints['ID'].astype(str)

print("Computing Affine Transformation (DXF -> UTM)...")
bootstrap_ids = ['23', '24', '25', '26', '175', '210']
manual_dxf_pts, manual_utm_pts = [], []
for b_id in bootstrap_ids:
    if b_id in dxf_labels:
        px, py = dxf_labels[b_id]
        fp = footprints[footprints['ID'] == str(b_id)]
        if not fp.empty:
            cx, cy = fp.iloc[0].geometry.centroid.coords[0]
            manual_dxf_pts.append((px, py))
            manual_utm_pts.append((cx, cy))

M_init, _ = cv2.estimateAffinePartial2D(np.array(manual_dxf_pts), np.array(manual_utm_pts))
H_init = np.vstack([M_init, [0, 0, 1]])

def transform_pt(px, py, H):
    pt = np.array([[px, py, 1.0]], dtype=np.float64)
    mapped = (H @ pt.T).T
    return mapped[0, :2] / mapped[0, 2]

all_dxf_pts, all_utm_pts = [], []
for lbl, pt in dxf_labels.items():
    px, py = pt
    rough_utm = transform_pt(px, py, H_init)
    rough_pt = Point(rough_utm[0], rough_utm[1])
    dists = footprints.geometry.centroid.distance(rough_pt)
    min_idx = dists.idxmin()
    if dists.min() < 15.0:
        exact_utm = footprints.loc[min_idx].geometry.centroid.coords[0]
        all_dxf_pts.append((px, py))
        all_utm_pts.append(exact_utm)

M_final, mask = cv2.estimateAffinePartial2D(np.array(all_dxf_pts), np.array(all_utm_pts))
H_final = np.vstack([M_final, [0, 0, 1]])
inliers = mask.ravel().sum() if mask is not None else 0
print(f"Affine Transform fit: {inliers}/{len(all_dxf_pts)} DXF points used as inliers.")
"""))

# Cell 5: Bipartite Match & Plot
cells.append(nbf.v4.new_code_cell("""def transform_geometry(geom, H):
    def xform(x, y):
        pt = np.array([[x, y, 1.0]], dtype=np.float64)
        m = (H @ pt.T).T
        return m[0, 0]/m[0, 2], m[0, 1]/m[0, 2]
    if geom.geom_type == 'Point':
        rx, ry = xform(geom.x, geom.y)
        return Point(rx, ry)
    return geom

# Transform entrances
dxf_entrances_utm = [transform_geometry(pt, H_final) for pt in dxf_entrances_raw]
entrances_gdf = gpd.GeoDataFrame(geometry=dxf_entrances_utm, crs=footprints.crs)

print("Running Bipartite Label Matching...")
label_coords = []
label_texts = []
for text, (px, py) in dxf_labels.items():
    crs_pt = transform_pt(px, py, H_final)
    label_coords.append(crs_pt)
    label_texts.append(text)

label_coords = np.array(label_coords)
footprint_centroids = np.array([[geom.centroid.x, geom.centroid.y] for geom in footprints.geometry])
footprint_ids = footprints['ID'].values

cost_matrix = np.zeros((len(label_coords), len(footprint_centroids)))
for i in range(len(label_coords)):
    for j in range(len(footprint_centroids)):
        dist = np.hypot(label_coords[i][0] - footprint_centroids[j][0],
                        label_coords[i][1] - footprint_centroids[j][1])
        cost_matrix[i, j] = dist if dist < 10.0 else 1e6

row_ind, col_ind = linear_sum_assignment(cost_matrix)
results = []
for i, j in zip(row_ind, col_ind):
    if cost_matrix[i, j] < 1e6:
        results.append({
            "chapel_id": label_texts[i],
            "footprint_id": str(footprint_ids[j]),
            "dist_m": cost_matrix[i, j],
            "match_method": "bipartite",
            "label_x": label_coords[i][0],
            "label_y": label_coords[i][1],
            "centroid_x": footprint_centroids[j][0],
            "centroid_y": footprint_centroids[j][1]
        })

crosswalk = pd.DataFrame(results)

# Plot Bipartite Matching
plt.figure(figsize=(12, 12))
footprints.plot(ax=plt.gca(), facecolor='lightgray', edgecolor='black', alpha=0.5)

for _, row in crosswalk.iterrows():
    # Draw line from label to centroid
    plt.plot([row['label_x'], row['centroid_x']], 
             [row['label_y'], row['centroid_y']], color='green', linewidth=1)
    # Plot label text
    plt.text(row['label_x'], row['label_y'], row['chapel_id'], color='red', fontsize=8)

# Plot Entrances
if not entrances_gdf.empty:
    entrances_gdf.plot(ax=plt.gca(), color='blue', markersize=20, label='Entrances')

plt.title("Bipartite Match: Labels (Red) linked to Centroids + Entrances (Blue)")
plt.axis('equal')
plt.savefig("step2_bipartite_match.png")
plt.show()

# Save CSV output
crosswalk.drop(columns=['label_x', 'label_y', 'centroid_x', 'centroid_y']).to_csv(OUT_CSV, index=False)
print(f"Crosswalk CSV saved to {OUT_CSV}")
"""))

# Cell 6: Export Master Map
cells.append(nbf.v4.new_code_cell("""print("Generating Master Vector Map...")
master_polygons = footprints.merge(
    crosswalk[['footprint_id', 'chapel_id', 'match_method']], 
    left_on='ID', right_on='footprint_id', how='left'
)
for col in master_polygons.columns:
    if master_polygons[col].dtype == object:
        master_polygons[col] = master_polygons[col].astype(str)
        
master_polygons.to_file(OUT_GPKG, layer='buildings', driver='GPKG')
if not entrances_gdf.empty:
    entrances_gdf.to_file(OUT_GPKG, layer='entrances', driver='GPKG')
print(f"Master Vector Geodatabase saved to {OUT_GPKG}")
"""))

nb['cells'] = cells
with open('C:\\\\Users\\\\Public\\\\LAMP_DataStore\\\\ElBagawat\\\\200_Projects\\\\210_GSOC\\\\code-manan\\\\01_master_vector_pipeline.ipynb', 'w') as f:
    nbf.write(nb, f)
print("Notebook created successfully.")
