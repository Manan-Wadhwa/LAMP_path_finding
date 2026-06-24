import geopandas as gpd
import pandas as pd

shp_path = r"C:\Users\Public\LAMP_DataStore\ElBagawat\100_Data\130_BuildingFootprintsVectorData\BuildingTracesCurrent\Buildings_Mask.shp"
gdf = gpd.read_file(shp_path)
print(gdf.columns)
print(gdf.head())
