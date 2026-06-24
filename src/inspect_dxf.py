import ezdxf
import collections

doc = ezdxf.readfile(r'C:\Users\Public\LAMP_DataStore\ElBagawat\100_Data\120_SiteReport\BaseSiteCAD\Site_CAD_Working_converted.dxf')
msp = doc.modelspace()

stats = collections.defaultdict(lambda: {'closed': 0, 'open': 0, 'total_pts': 0})
for e in msp:
    if e.dxftype() == 'LWPOLYLINE':
        layer = e.dxf.layer
        pts = e.get_points('xy')
        if e.closed:
            stats[layer]['closed'] += 1
        else:
            stats[layer]['open'] += 1
        stats[layer]['total_pts'] += len(pts)

for layer, s in sorted(stats.items()):
    total = s['closed'] + s['open']
    avg_pts = s['total_pts'] / total
    print(f"Layer {layer}: closed={s['closed']}, open={s['open']}, avg_pts={avg_pts:.1f}")

# Now check ARC radii distribution - are any of these door-swing arcs?
arcs = [e for e in msp if e.dxftype() == 'ARC']
print(f"\n=== ARC radius distribution ===")
radii = [e.dxf.radius for e in arcs]
import numpy as np
radii = np.array(radii)
print(f"Min: {radii.min():.1f}, Max: {radii.max():.1f}, Median: {np.median(radii):.1f}")
print(f"Radii < 500 (possible door swings): {(radii < 500).sum()}")
print(f"Radii 500-2500 (likely door swings): {((radii >= 500) & (radii <= 2500)).sum()}")
print(f"Radii > 2500 (structural arcs): {(radii > 2500).sum()}")

# Show the small arcs
print("\n=== Small ARCs (R < 500, likely door swings) ===")
for e in arcs:
    if e.dxf.radius < 500:
        sweep = abs(e.dxf.end_angle - e.dxf.start_angle)
        if sweep > 180:
            sweep = 360 - sweep
        print(f"  Layer={e.dxf.layer} R={e.dxf.radius:.1f} Sweep={sweep:.1f}deg Center=({e.dxf.center.x:.1f},{e.dxf.center.y:.1f})")

# Check LW1 vs LW2 — maybe one is walls, one is doors?
print("\n=== LW1 sample polylines ===")
count = 0
for e in msp:
    if e.dxftype() == 'LWPOLYLINE' and e.dxf.layer == 'LW1' and count < 5:
        pts = e.get_points('xy')
        print(f"  pts={len(pts)}, closed={e.closed}, first=({pts[0][0]:.1f},{pts[0][1]:.1f})")
        count += 1

print("\n=== LW2 sample polylines ===")
count = 0
for e in msp:
    if e.dxftype() == 'LWPOLYLINE' and e.dxf.layer == 'LW2' and count < 5:
        pts = e.get_points('xy')
        print(f"  pts={len(pts)}, closed={e.closed}, first=({pts[0][0]:.1f},{pts[0][1]:.1f})")
        count += 1
