import streamlit as st
import geopandas as gpd
import pandas as pd
import plotly.express as px
import json

@st.cache_data
def load_data():
    gdf = gpd.read_file("/Users/lucarossi/Documents/gitprojects/mapping/webapp_data/gdf.geojson")
    gdf = gdf.to_crs(epsg=4326)  # Keep it in WGS84 (lat/lon)
    
    conversion_table = pd.read_csv("/Users/lucarossi/Documents/gitprojects/mapping/webapp_data/bpe_carreaux.csv")
    isochrones = gpd.read_file("/Users/lucarossi/Documents/gitprojects/mapping/webapp_data/isochrones.geojson")
    carreaux = gpd.read_file("/Users/lucarossi/Documents/gitprojects/mapping/webapp_data/carreaux.geojson")
    bpe_points = gpd.read_file("/Users/lucarossi/Documents/gitprojects/mapping/webapp_data/bpe_points.geojson")
    bpe_points = bpe_points.dropna(subset=["LATITUDE", "LONGITUDE"])

    return gdf, isochrones, carreaux, bpe_points, conversion_table

gdf, isochrones, carreaux, bpe_points, conversion_table = load_data()

# 🟢 **Dropdown 1: Select a `commune`**
communes_list = conversion_table["LIBCOM"].dropna().unique().tolist()
selected_commune = st.selectbox("Select a Commune", communes_list)

# 🟢 **Dropdown 2: Select `Idcar_200m` filtered by the selected commune**
filtered_idcar_list = conversion_table[conversion_table["LIBCOM"] == selected_commune]["Idcar_200m"].dropna().unique().tolist()

# 🟢 **Check availability of `Idcar_200m`**
filtered_idcar_list = [
    idcar for idcar in filtered_idcar_list
    if (idcar in isochrones["Idcar_200m"].values) and 
       (idcar in bpe_points["Idcar_200m"].values)
]

# 🛑 **Stop if no options available**
if not filtered_idcar_list:
    st.warning(f"No available `Idcar_200m` for {selected_commune}. Please select another commune.")
    st.stop()

# 🟢 **Dropdown 2: Select available `Idcar_200m`**
selected_idcar = st.selectbox("Select Idcar_200m", filtered_idcar_list)

# 🟢 **Filter Data**
filtered_data = isochrones[isochrones["Idcar_200m"] == selected_idcar]
filtered_bpe_data = bpe_points[bpe_points["LIBCOM"] == selected_commune]

# 🟢 **Ensure GeoJSON conversion for isochrones**
if not filtered_data.empty:
    isochrones_geojson = json.loads(filtered_data.to_json())
else:
    isochrones_geojson = None

# 🟢 **Create the Scattermapbox for Points**
fig = px.scatter_mapbox(
    filtered_bpe_data,
    lat="LATITUDE",
    lon="LONGITUDE",
    color_discrete_sequence=["blue"],
    size_max=1,
    zoom=12,
    mapbox_style="carto-positron",
    hover_data={"LATITUDE": True, "LONGITUDE": True, "NOMRS": True}
)

# 🟢 **Define colors with transparency for each isochrone profile**
color_map = {
    "foot-walking": "rgba(255, 0, 0, 0.3)",  # Red (30% opacity)
    "cycling-regular": "rgba(0, 255, 0, 0.3)",  # Green (30% opacity)
    "driving-car": "rgba(0, 0, 255, 0.3)",  # Blue (30% opacity)
}

# 🟢 **Add Isochrones as Mapbox `fill` Layers**
mapbox_layers = []

if isochrones_geojson:
    for profile in filtered_data["profile"].unique():
        layer_data = filtered_data[filtered_data["profile"] == profile]
        profile_geojson = json.loads(layer_data.to_json())  # Convert to valid JSON
        color = color_map.get(profile)  # Pick color

        # Append `fill` layer for Mapbox
        mapbox_layers.append({
            "source": profile_geojson,
            "type": "fill",
            "color": color,
            "opacity": 0.7,  # Keep transparency for visibility
            "below": "traces"
        })

# 🟢 **Apply Mapbox Layers**
if mapbox_layers:
    fig.update_layout(mapbox_layers=mapbox_layers)
    
# 🟢 **Generate legend annotations**
legend_annotations = []
y_position = 0.95  # Start position for the first legend entry

for profile, color in color_map.items():
    legend_annotations.append(
        dict(
            x=0.01, y=y_position,  # Position in the top-left corner
            xref="paper", yref="paper",
            text=f'<span style="color:{color.replace("0.3", "1")}">■</span> {profile.capitalize()}',
            showarrow=False,
            font=dict(size=14),
            bgcolor="white",
            bordercolor="black",
            borderwidth=1
        )
    )
    y_position -= 0.05  # Move the next item down

# 🟢 **Add the annotations to the layout**
fig.update_layout(annotations=legend_annotations)

# # 🟢 **Adjust Map Bounds to Fit ALL Isochrones**
# if not filtered_data.empty:
#     fig.update_layout(
#         margin={"r":0, "t":0, "l":0, "b":0},
#         mapbox_bounds={
#             "west": filtered_data.total_bounds[0], 
#             "east": filtered_data.total_bounds[2],
#             "south": filtered_data.total_bounds[1], 
#             "north": filtered_data.total_bounds[3]
#         }
#     )

# 🟢 Show the map in Streamlit
st.plotly_chart(fig, use_container_width=True)