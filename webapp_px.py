import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import json
from pathlib import Path
import numpy as np


# Get the absolute path of the current script
BASE_DIR = Path(__file__).parent

@st.cache_data
def load_data():
    gdf = gpd.read_file(BASE_DIR / "webapp_data" / "gdf.geojson").to_crs(epsg=4326)
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

# 🟢 **Custom Labels for Profiles**
profile_labels = {
    "foot-walking": "Walking",
    "cycling-regular": "Cycling",
    "driving-car": "Car"
}

# 🟢 **Multi-Select Dropdowns**
selected_profiles = st.multiselect("Select Profile(s)", options=available_profiles, default=available_profiles, format_func=lambda x: profile_labels.get(x, x))
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

# Make a safe copy for JSON export
export_data = filtered_data.copy()

for col in export_data.columns:
    if col == export_data.geometry.name:
        continue
    if isinstance(export_data[col].dtype, pd.CategoricalDtype):
        export_data[col] = export_data[col].astype(str)
    elif pd.api.types.is_datetime64_any_dtype(export_data[col]):
        export_data[col] = export_data[col].astype(str)

    def to_native(val):
        if isinstance(val, np.ndarray):
            return val.tolist()
        if isinstance(val, (list, tuple)):
            return [to_native(v) for v in val]
        if isinstance(val, np.generic):
            return val.item()
        return val

# Sanitize the problem columns BEFORE calling to_json()
if "geometry.coordinates" in export_data.columns:
    export_data["geometry.coordinates"] = export_data["geometry.coordinates"].apply(to_native)
if "properties.center" in export_data.columns:
    export_data["properties.center"] = export_data["properties.center"].apply(to_native)

isochrones_geojson = json.loads(export_data.to_json()) if not export_data.empty else None

filtered_bpe_data = bpe_points[bpe_points["LIBCOM"] == selected_commune]

# 🟢 **Compute Centroids**
carreau = carreaux[carreaux["Idcar_200m"] == selected_idcar].copy()
carreau["centroid"] = carreau.geometry.centroid
carreau["center_lon"] = carreau["centroid"].x
carreau["center_lat"] = carreau["centroid"].y

# 🟢 **Mapbox Plot**
fig = px.scatter_map(
    bpe_points,
    lat="LATITUDE",
    lon="LONGITUDE",
    color_discrete_sequence=["blue"],
    size_max=1,
    zoom=12,
    opacity=0.3,
    map_style="carto-positron",
)

# 🟢 **Define Colors for Profiles**
color_map = {
    "foot-walking": "rgba(255, 0, 0, 0.3)",  # Red
    "cycling-regular": "rgba(0, 255, 0, 0.3)",  # Green
    "driving-car": "rgba(0, 0, 255, 0.3)",  # Blue
}

filtered_data = isochrone[
    (isochrone["carreaux_id"] == selected_idcar) &
    (isochrone["profile"].isin(selected_profiles)) &
    (isochrone["range"].isin(selected_ranges))
]

# Drop columns that break to_json() for every use of filtered_data downstream
cols_to_drop = ["geometry.coordinates", "geometry.type", "properties.center",
                "properties.value", "properties.group_index"]
filtered_data = filtered_data.drop(
    columns=[c for c in cols_to_drop if c in filtered_data.columns]
)

map_layers = []

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

                # **Count BPE points within the isochrone**
                if not filtered_bpe_data.empty:
                    joined = gpd.sjoin(filtered_bpe_data, layer_data, predicate="within", how="inner")
                    bpe_count = len(joined)
                else:
                    bpe_count = 0

                # 🟢 **Display BPE count per profile & range**
                st.write(f"BPE count for {profile_labels.get(profile, profile)} ({range_value}s): {bpe_count}")

                # Append `fill` layer for the map
                map_layers.append({
                    "source": profile_geojson,
                    "type": "fill",
                    "color": color,
                    "opacity": 0.7,
                    "below": "traces"
                })

if map_layers:
    fig.update_layout(map_layers=map_layers)   # "map_layers" not "mapbox_layers"

# 🟢 **Plot Centroids**
fig.add_trace(px.scatter_map(
    carreau,
    lat="center_lat",
    lon="center_lon",
    color_discrete_sequence=["red"],  # Red for centroids
    zoom=10
).data[0])

# 🟢 **Generate Legend Annotations**
legend_annotations = []
y_position = 0.95  

for profile, color in color_map.items():
    legend_annotations.append(
        dict(
            x=0.01, y=y_position,
            xref="paper", yref="paper",
            text=f'<span style="color:{color.replace("0.3", "1")}">■</span> {profile_labels.get(profile, profile)}',
            showarrow=False,
            font=dict(size=14),
            bgcolor="white",
            bordercolor="black",
            borderwidth=1
        )
    )
    y_position -= 0.05  

fig.update_layout(annotations=legend_annotations)

# 🟢 **Adjust Map Bounds with Buffer**
if not filtered_data.empty:
    buffer = 0.01

    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        map={
            "bounds": {
                "west": filtered_data.total_bounds[0] - buffer,
                "south": filtered_data.total_bounds[1] - buffer,
                "east": filtered_data.total_bounds[2] + buffer,
                "north": filtered_data.total_bounds[3] + buffer,
            }
        }
    )

# 🟢 **Show the Map**
st.plotly_chart(fig, use_container_width=True)
