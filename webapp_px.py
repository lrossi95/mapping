import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import json
from pathlib import Path

# Get the absolute path of the current script
BASE_DIR = Path(__file__).parent

@st.cache_data
def load_data():
    gdf = gpd.read_file(BASE_DIR / "webapp_data" / "gdf.geojson")
    gdf = gdf.to_crs(epsg=4326)  # Keep it in WGS84 (lat/lon)

    conversion_table = pd.read_csv(BASE_DIR / "webapp_data" / "bpe_carreaux.csv")
    carreaux = gpd.read_file(BASE_DIR / "webapp_data" / "carreaux.geojson")
    bpe_points = gpd.read_file(BASE_DIR / "webapp_data" / "bpe_points.geojson")
    bpe_points = bpe_points.dropna(subset=["LATITUDE", "LONGITUDE"])

    return gdf, carreaux, bpe_points, conversion_table

def load_isochrone(LIBCOM):
    return gpd.read_file(BASE_DIR / "webapp_data" / "isochrones" / f"{LIBCOM}.geojson")

gdf, carreaux, bpe_points, conversion_table = load_data()

# 🟢 **Dropdown: Select a Commune**
communes_list = conversion_table["LIBCOM"].dropna().unique().tolist()
selected_commune = st.selectbox("Select a Commune", communes_list)

# Load Isochrones for the selected commune
isochrone = load_isochrone(selected_commune)

# 🟢 **Extract available profiles and ranges**
available_profiles = isochrone["profile"].unique().tolist()
available_ranges = sorted(isochrone["range"].unique().tolist())

# 🟢 **Multi-Select Dropdowns**
selected_profiles = st.multiselect("Select Profile(s)", options=available_profiles, default=available_profiles)
selected_ranges = st.multiselect("Select Range(s)", options=available_ranges, default=available_ranges)

# 🟢 **Dropdown: Select `Idcar_200m`**
filtered_idcar_list = conversion_table[conversion_table["LIBCOM"] == selected_commune]["Idcar_200m"].dropna().unique().tolist()
filtered_idcar_list = [
    idcar for idcar in filtered_idcar_list
    if (idcar in isochrone["carreaux_id"].values) and 
       (idcar in bpe_points["Idcar_200m"].values)
]

if not filtered_idcar_list:
    st.warning(f"No Carreaux available for {selected_commune}. Please select another commune.")
    st.stop()

selected_idcar = st.selectbox("Select Carreaux", filtered_idcar_list)

# 🟢 **Filter Isochrone Data**
filtered_data = isochrone[
    (isochrone["carreaux_id"] == selected_idcar) &
    (isochrone["profile"].isin(selected_profiles)) &
    (isochrone["range"].isin(selected_ranges))
]
filtered_bpe_data = bpe_points[bpe_points["LIBCOM"] == selected_commune]

isochrones_geojson = json.loads(filtered_data.to_json()) if not filtered_data.empty else None

# 🟢 **Compute Centroids**
carreau = carreaux[carreaux["Idcar_200m"] == selected_idcar].copy()
carreau["centroid"] = carreau.geometry.centroid
carreau["center_lon"] = carreau["centroid"].x
carreau["center_lat"] = carreau["centroid"].y

# Debugging: Display centroid coordinates
st.write("Centroid Coordinates:", carreau[["center_lat", "center_lon"]])

# 🟢 **Mapbox Plot**
fig = px.scatter_mapbox(
    bpe_points,
    lat="LATITUDE",
    lon="LONGITUDE",
    color_discrete_sequence=["blue"],
    size_max=1,
    zoom=12,
    opacity=0.1,
    mapbox_style="carto-positron"
)

# 🟢 **Plot Isochrones**
color_map = {
    "foot-walking": "rgba(255, 0, 0, 0.3)",  # Red
    "cycling-regular": "rgba(0, 255, 0, 0.3)",  # Green
    "driving-car": "rgba(0, 0, 255, 0.3)",  # Blue
}

mapbox_layers = []

if isochrones_geojson:
    for profile in selected_profiles:
        for range_value in selected_ranges:
            layer_data = filtered_data[
                (filtered_data["profile"] == profile) &
                (filtered_data["range"] == range_value)
            ]
            
            if not layer_data.empty:
                profile_geojson = json.loads(layer_data.to_json())
                color = color_map.get(profile)

                # Append `fill` layer for Mapbox
                mapbox_layers.append({
                    "source": profile_geojson,
                    "type": "fill",
                    "color": color,
                    "opacity": 0.7,
                    "below": "traces"
                })

if mapbox_layers:
    fig.update_layout(mapbox_layers=mapbox_layers)

# 🟢 **Plot Centroids**
fig.add_trace(px.scatter_mapbox(
    carreau,
    lat="center_lat",
    lon="center_lon",
    color_discrete_sequence=["red"],  # Red for centroids
    size_max=8,
    zoom=10
).data[0])

# 🟢 **Adjust Map Bounds with Buffer**
if not filtered_data.empty:
    buffer = 0.01

    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        mapbox_bounds={
            "west": filtered_data.total_bounds[0] - buffer, 
            "east": filtered_data.total_bounds[2] + buffer,
            "south": filtered_data.total_bounds[1] - buffer, 
            "north": filtered_data.total_bounds[3] + buffer
        }
    )

# 🟢 **Show the Map**
st.plotly_chart(fig, use_container_width=True)