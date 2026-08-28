# app.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
import random
import math
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit.components.v1 as components

# -----------------------
# Configuration & seeds
# -----------------------
st.set_page_config(page_title="Taiwan Trip Generator — Altitude & Traffic", layout="wide")
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

OSRM_URL = "http://router.project-osrm.org/route/v1/driving/"

# Taiwan main island bbox
TAIWAN_LAT_MIN, TAIWAN_LAT_MAX = 21.8, 25.3
TAIWAN_LON_MIN, TAIWAN_LON_MAX = 120.0, 121.8

# City list (for dropdown)
CITIES = {
    "Taipei": (25.0330, 121.5654),
    "New Taipei": (25.0169, 121.4628),
    "Taoyuan": (24.9936, 121.2969),
    "Hsinchu": (24.8138, 120.9675),
    "Taichung": (24.1477, 120.6736),
    "Changhua": (24.0515, 120.5161),
    "Nantou": (23.8388, 120.9876),
    "Chiayi": (23.4800, 120.4490),
    "Tainan": (22.9999, 120.2270),
    "Kaohsiung": (22.6273, 120.3014),
    "Pingtung": (22.5511, 120.5483),
    "Yilan": (24.7596, 121.7572),
    "Hualien": (23.9750, 121.6120),
    "Taitung": (22.7583, 121.1443)
}

# Elevation anchors (approx)
ELEVATION_ANCHORS = [
    (25.0330, 121.5654, 7),
    (24.1477, 120.6736, 30),
    (22.6273, 120.3014, 8),
    (23.9739, 121.6015, 20),
    (23.5, 121.0, 600),
    (23.5, 120.8, 1200),
    (24.0, 121.3, 1000),
    (23.5, 120.7, 2000),
    (24.8, 121.7, 10),
    (23.0, 120.5, 50)
]

# Traffic bias
TRAFFIC_CITY_PROBS = {
    "Taipei": (25.0330, 121.5654, 25, 0.25),
    "New Taipei": (25.0169, 121.4628, 20, 0.20),
    "Taoyuan": (24.9936, 121.2969, 20, 0.15),
    "Hsinchu": (24.8138, 120.9675, 15, 0.12),
    "Taichung": (24.1477, 120.6736, 25, 0.18),
    "Tainan": (22.9999, 120.2270, 20, 0.12),
    "Kaohsiung": (22.6273, 120.3014, 25, 0.18)
}

# -----------------------
# Utility functions
# -----------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def estimate_altitude(lat, lon):
    weights, vals = [], []
    for a_lat, a_lon, a_elev in ELEVATION_ANCHORS:
        d = haversine_km(lat, lon, a_lat, a_lon)
        w = 1.0 / (d + 0.001)
        weights.append(w)
        vals.append(a_elev)
    elev = float(np.sum(np.array(weights) * np.array(vals)) / np.sum(weights))
    elev += np.random.normal(0, min(30, elev * 0.02))
    return round(max(0.0, elev), 1)

def traffic_level_at(lat, lon):
    base_high, base_med = 0.05, 0.15
    high_prob, med_prob = base_high, base_med
    for _, (c_lat, c_lon, radius_km, c_high_prob) in TRAFFIC_CITY_PROBS.items():
        d = haversine_km(lat, lon, c_lat, c_lon)
        if d <= radius_km:
            boost = c_high_prob * (1 - d / radius_km)
            high_prob += boost
            med_prob += boost * 0.8
    high_prob = min(0.6, high_prob)
    med_prob = min(0.6, med_prob)
    low_prob = max(0.0, 1.0 - (high_prob + med_prob))
    r = random.random()
    if r < high_prob:
        return "High"
    elif r < high_prob + med_prob:
        return "Medium"
    else:
        return "Low"

def fetch_route_osrm(start_lat, start_lon, end_lat, end_lon, timeout=10):
    coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    url = OSRM_URL + coords + "?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        route_coords = data['routes'][0]['geometry']['coordinates']
        filtered = [(lat, lon) for lon, lat in route_coords
                    if TAIWAN_LAT_MIN <= lat <= TAIWAN_LAT_MAX and TAIWAN_LON_MIN <= lon <= TAIWAN_LON_MAX]
        if len(filtered) < 5:
            return None
        return filtered
    except:
        return None

def simulate_trip(route_coords, start_time="2024-12-02 08:09:00", profile="normal", initial_speed=None, initial_serial=2102838636):
    rows, current_time, last_speed, serial_number = [], datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"), 0.0, initial_serial
    current_speed = random.uniform(20, 45) if initial_speed is None else float(initial_speed)
    for i, (lat, lon) in enumerate(route_coords):
        if i == 0:
            angle = 0
        else:
            prev_lat, prev_lon = route_coords[i - 1]
            dlon = math.radians(lon - prev_lon)
            lat1, lat2 = math.radians(prev_lat), math.radians(lat)
            x = math.sin(dlon) * math.cos(lat2)
            y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
            angle = int((math.degrees(math.atan2(x, y)) + 360) % 360)

        satellites = random.randint(6, 12)
        altitude_m = estimate_altitude(lat, lon)
        traffic = traffic_level_at(lat, lon)

        if profile == "drunk":
            target_speed = 34.0
            if traffic == "Low":
                target_speed = 42.0
            elif traffic == "Medium":
                target_speed = 30.0
            else:
                target_speed = 22.0

            if altitude_m >= 1000:
                target_speed -= min(8.0, (altitude_m - 1000) / 180.0)

            if i % 18 == 0 and i != 0:
                target_speed += random.choice([-18.0, -12.0, 10.0, 16.0])
            if i % 7 == 0:
                target_speed += random.uniform(-8.0, 8.0)

            target_speed += np.random.normal(0, 6.0)
            target_speed = max(0.0, min(110.0, target_speed))

            max_accel = 2.5
            max_decel = 4.5
            reaction_lag = 0.65
            delta = (target_speed - current_speed) * reaction_lag
            delta = max(-max_decel, min(max_accel, delta))
            delta += np.random.normal(0, 1.4)
        else:
            target_speed = 55.0
            if traffic == "Low":
                target_speed = 65.0
            elif traffic == "Medium":
                target_speed = 48.0
            else:
                target_speed = 32.0

            if altitude_m >= 1000:
                target_speed -= min(12.0, (altitude_m - 1000) / 120.0)

            if i % 80 == 0 and i != 0:
                target_speed *= 0.65

            target_speed += np.random.normal(0, 3.0)
            target_speed = max(0.0, min(110.0, target_speed))

            max_accel = 4.5
            max_decel = 6.5
            delta = target_speed - current_speed
            delta = max(-max_decel, min(max_accel, delta))
            delta += np.random.normal(0, 0.6)

        current_speed = max(0.0, min(110.0, current_speed + delta))
        speed = round(current_speed, 1)

        acceleration = speed - last_speed
        if profile == "drunk":
            if speed == 0:
                hr, br = int(np.random.normal(92, 8)), int(np.random.normal(18, 3))
            elif acceleration > 8:
                hr, br = int(np.random.normal(122, 10)), int(np.random.normal(26, 4))
            elif abs(acceleration) > 4:
                hr, br = int(np.random.normal(108, 9)), int(np.random.normal(22, 3))
            elif i % 14 == 0:
                hr, br = int(np.random.normal(115, 11)), int(np.random.normal(24, 4))
            else:
                hr, br = int(np.random.normal(101, 8)), int(np.random.normal(20, 3))
        else:
            if speed == 0:
                hr, br = int(np.random.normal(75, 5)), int(np.random.normal(14, 2))
            elif acceleration > 10:
                hr, br = int(np.random.normal(110, 8)), int(np.random.normal(22, 3))
            elif abs(acceleration) > 5:
                hr, br = int(np.random.normal(95, 7)), int(np.random.normal(18, 2))
            elif i % 40 == 0:
                hr, br = int(np.random.normal(90, 6)), int(np.random.normal(17, 2))
            else:
                hr, br = int(np.random.normal(85, 5)), int(np.random.normal(16, 2))

        if traffic == "High":
            pct = random.uniform(0.01, 0.03)
            hr, br = max(40, int(hr * (1 + pct))), max(8, int(br * (1 + pct * 0.6)))
        elif traffic == "Medium":
            pct = random.uniform(0.005, 0.015)
            hr, br = max(40, int(hr * (1 + pct))), max(8, int(br * (1 + pct * 0.6)))

        if altitude_m >= 1000:
            alt_factor = min(0.03, (altitude_m - 1000) / 10000)
            alt_pct = random.uniform(0.01, alt_factor if alt_factor > 0.01 else 0.01)
            hr, br = max(40, int(hr * (1 + alt_pct))), max(8, int(br * (1 + alt_pct * 0.5)))

        last_speed = speed
        rows.append({
            "Serial Number": serial_number,
            "Latitude": round(lat, 6),
            "Longitude": round(lon, 6),
            "Altitude (m)": altitude_m,
            "Speed (km/h)": speed,
            "Angle (°)": angle,
            "Date Time": current_time.strftime("%d-%m-%Y %H:%M"),
            "Satellites": satellites,
            "Timestamp": current_time.strftime("%d/%m/%Y %H:%M:%S"),
            "Traffic Level": traffic,
            "Heart Rate (BPM)": int(hr),
            "Breathing Rate (breaths/min)": int(br)
        })

        current_time += timedelta(seconds=random.randint(60, 150) if speed == 0 else random.randint(10, 40))
        serial_number += 1

    return pd.DataFrame(rows)
    # for i, (lat, lon) in enumerate(route_coords):
    #     speed = 0.0 if i % 30 == 0 else max(0.0, float(np.random.normal(30.0, 10.0)))
    #     if i == 0:
    #         angle = 0
    #     else:
    #         prev_lat, prev_lon = route_coords[i-1]
    #         dlon = math.radians(lon - prev_lon)
    #         lat1, lat2 = math.radians(prev_lat), math.radians(lat)
    #         x = math.sin(dlon) * math.cos(lat2)
    #         y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    #         angle = int((math.degrees(math.atan2(x, y)) + 360) % 360)
    #     satellites = random.randint(6, 12)
    #     altitude_m = estimate_altitude(lat, lon)
    #     traffic = traffic_level_at(lat, lon)

    #     acceleration = speed - last_speed
    #     if speed == 0:
    #         hr, br = int(np.random.normal(75,5)), int(np.random.normal(14,2))
    #     elif acceleration > 10:
    #         hr, br = int(np.random.normal(110,8)), int(np.random.normal(22,3))
    #     elif abs(acceleration) > 5:
    #         hr, br = int(np.random.normal(95,7)), int(np.random.normal(18,2))
    #     elif i % 40 == 0:
    #         hr, br = int(np.random.normal(90,6)), int(np.random.normal(17,2))
    #     else:
    #         hr, br = int(np.random.normal(85,5)), int(np.random.normal(16,2))

    #     if traffic == "High":
    #         pct = random.uniform(0.01, 0.03)
    #         hr, br = max(40,int(hr*(1+pct))), max(8,int(br*(1+pct*0.6)))
    #     elif traffic == "Medium":
    #         pct = random.uniform(0.005, 0.015)
    #         hr, br = max(40,int(hr*(1+pct))), max(8,int(br*(1+pct*0.6)))

    #     if altitude_m >= 1000:
    #         alt_factor = min(0.03, (altitude_m-1000)/10000)
    #         alt_pct = random.uniform(0.01, alt_factor if alt_factor>0.01 else 0.01)
    #         hr, br = max(40,int(hr*(1+alt_pct))), max(8,int(br*(1+alt_pct*0.5)))

    #     last_speed = speed
    #     rows.append({
    #         "Serial Number": serial_number,
    #         "Latitude": round(lat,6),
    #         "Longitude": round(lon,6),
    #         "Altitude (m)": altitude_m,
    #         "Speed (km/h)": round(speed,1),
    #         "Angle (°)": angle,
    #         "Date Time": current_time.strftime("%d-%m-%Y %H:%M"),
    #         "Satellites": satellites,
    #         "Timestamp": current_time.strftime("%d/%m/%Y %H:%M:%S"),
    #         "Traffic Level": traffic,
    #         "Heart Rate (BPM)": int(hr),
    #         "Breathing Rate (breaths/min)": int(br)
    #     })
    #     current_time += timedelta(seconds=random.randint(60,150) if speed==0 else random.randint(10,40))
    #     serial_number += 1
    # return pd.DataFrame(rows)

# -----------------------
# Map creation helper
# -----------------------
def create_map(route, df, show_health=False):
    m = folium.Map(location=route[0], zoom_start=10)
    folium.PolyLine(locations=[(lat, lon) for lat, lon in route], weight=3, color="#3388ff").add_to(m)
    folium.Marker(location=route[0], popup="Start", icon=folium.Icon(color="blue", icon="play")).add_to(m)
    folium.Marker(location=route[-1], popup="End", icon=folium.Icon(color="red", icon="stop")).add_to(m)
    for i, (lat, lon) in enumerate(route):
        lvl = df.loc[i, "Traffic Level"]
        color = "green" if lvl=="Low" else "orange" if lvl=="Medium" else "red"
        folium.CircleMarker(location=(lat, lon), radius=3, color=color, fill=True, fill_opacity=0.8).add_to(m)
    legend_html = """
     <div style="position: fixed; bottom: 60px; left: 20px; width:180px; height:110px; 
          z-index:9999; font-size:14px; background-color: grey; opacity: 0.9; padding:10px; border:1px solid grey;">
     <b>Legend</b><br>
     <span style="color:green">●</span> Low traffic<br>
     <span style="color:orange">●</span> Medium traffic<br>
     <span style="color:red">●</span> High traffic<br>
     <span style="color:#3388ff">—</span> Route
     </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))
    return m

# -----------------------
# Streamlit UI
# -----------------------
st.title("Taiwan Road Trip Generator — Altitude & Traffic-aware")
st.markdown("Generate realistic road-following trip data (GPS + altitude + traffic + biometrics).")
def render_basic_chatbot_widget():
    chatbot_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            :root {
                color-scheme: light;
                --chat-accent: #2563eb;
                --chat-accent-hover: #1d4ed8;
                --chat-surface: #ffffff;
                --chat-surface-alt: #f8fafc;
                --chat-border: rgba(37, 99, 235, 0.16);
                --chat-text: #0f172a;
                --chat-muted: #475569;
                --chat-shadow: 0 16px 40px rgba(15, 23, 42, 0.16);
                --chat-input-bg: #ffffff;
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    color-scheme: dark;
                    --chat-surface: #111827;
                    --chat-surface-alt: #0f172a;
                    --chat-border: rgba(96, 165, 250, 0.22);
                    --chat-text: #e5e7eb;
                    --chat-muted: #cbd5e1;
                    --chat-shadow: 0 18px 42px rgba(0, 0, 0, 0.45);
                    --chat-input-bg: #0b1220;
                }
            }

            html, body {
                margin: 0;
                padding: 0;
                background: transparent;
                overflow: hidden;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            }

            .chat-container {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 9999;
            }

            .chat-toggle {
                width: 60px;
                height: 60px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, var(--chat-accent), var(--chat-accent-hover));
                color: #ffffff;
                font-size: 26px;
                cursor: pointer;
                box-shadow: var(--chat-shadow);
            }

            .chat-window {
                display: none;
                width: 300px;
                height: 260px;
                background: var(--chat-surface);
                border-radius: 14px;
                box-shadow: var(--chat-shadow);
                margin-bottom: 12px;
                overflow: hidden;
                border: 1px solid var(--chat-border);
            }

            .chat-header {
                background: linear-gradient(135deg, var(--chat-accent), var(--chat-accent-hover));
                color: #ffffff;
                padding: 10px 14px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-weight: bold;
            }

            .close-btn {
                background: transparent;
                border: none;
                color: inherit;
                font-size: 18px;
                cursor: pointer;
            }

            .chat-body {
                padding: 12px;
                min-height: 150px;
                font-size: 14px;
                color: var(--chat-text);
                background: var(--chat-surface-alt);
            }

            .chat-input-area {
                display: flex;
                gap: 8px;
                padding: 10px;
                border-top: 1px solid var(--chat-border);
                background: var(--chat-surface);
                box-sizing: border-box;
            }

            .chat-input-area input {
                flex: 1;
                padding: 8px 10px;
                border: 1px solid var(--chat-border);
                border-radius: 8px;
                outline: none;
                background: var(--chat-input-bg);
                color: var(--chat-text);
            }

            .chat-input-area input::placeholder {
                color: var(--chat-muted);
            }

            .chat-input-area button {
                padding: 8px 12px;
                border: none;
                border-radius: 8px;
                background: linear-gradient(135deg, var(--chat-accent), var(--chat-accent-hover));
                color: #ffffff;
                cursor: pointer;
            }

            .chat-input-area button:hover,
            .chat-toggle:hover {
                filter: brightness(1.03);
            }

            .show {
                display: block;
            }
        </style>
    </head>
    <body>
        <div class="chat-container">
            <div id="chatWindow" class="chat-window">
                <div class="chat-header">
                    <span>Chatbot</span>
                    <button class="close-btn" onclick="toggleChat()">×</button>
                </div>
                <div class="chat-body">
                    Hi, how can I help you?
                </div>
                <div class="chat-input-area">
                    <input type="text" placeholder="Type your message..." />
                    <button>Send</button>
                </div>
            </div>

            <button class="chat-toggle" onclick="toggleChat()">💬</button>
        </div>

        <script>
            function toggleChat() {
                const chatWindow = document.getElementById("chatWindow");
                chatWindow.classList.toggle("show");
            }

            function pinWidget() {
                const frame = window.frameElement;
                if (!frame) return;

                frame.style.position = "fixed";
                frame.style.bottom = "20px";
                frame.style.right = "20px";
                frame.style.left = "auto";
                frame.style.top = "auto";
                frame.style.width = "360px";
                frame.style.height = "420px";
                frame.style.display = "block";
                frame.style.zIndex = "999999";
                frame.style.background = "transparent";
                frame.style.border = "0";
                frame.style.overflow = "visible";
            }

            window.addEventListener("load", pinWidget);
            window.addEventListener("resize", pinWidget);
        </script>
    </body>
    </html>
    """
    components.html(chatbot_html, height=1, width=1)
# -----------------------
# Session state
# -----------------------
for key in ["df_trip", "route", "trip_map", "rand_pts", "trip_split_idx"]:
    if key not in st.session_state:
        st.session_state[key] = None

# -----------------------
# Sidebar controls
# -----------------------
st.sidebar.header("Trip Options")
mode = st.sidebar.radio("Mode", ["Random Trip", "City to City", "Manual Coordinates"])
start_time_input = st.sidebar.text_input("Start time (YYYY-MM-DD HH:MM:SS)", "2024-12-02 08:09:00")
preview_n = st.sidebar.slider("Preview rows", 5, 500, 50)
show_health = st.sidebar.checkbox("Show Driver Health Graphs", True)

# Pick endpoints
start_lat = start_lon = end_lat = end_lon = None
if mode == "City to City":
    start_city = st.sidebar.selectbox("Start City", list(CITIES.keys()))
    end_city = st.sidebar.selectbox("End City", list(CITIES.keys()))
    start_lat, start_lon = CITIES[start_city]
    end_lat, end_lon = CITIES[end_city]
elif mode == "Manual Coordinates":
    start_lat = st.sidebar.number_input("Start Latitude", TAIWAN_LAT_MIN, TAIWAN_LAT_MAX, 24.0, format="%.6f")
    start_lon = st.sidebar.number_input("Start Longitude", TAIWAN_LON_MIN, TAIWAN_LON_MAX, 121.0, format="%.6f")
    end_lat = st.sidebar.number_input("End Latitude", TAIWAN_LAT_MIN, TAIWAN_LAT_MAX, 24.5, format="%.6f")
    end_lon = st.sidebar.number_input("End Longitude", TAIWAN_LON_MIN, TAIWAN_LON_MAX, 121.5, format="%.6f")
else:
    if st.session_state.rand_pts is None:
        st.session_state.rand_pts = (
            random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX),
            random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX),
            random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX),
            random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX)
        )
    if st.sidebar.button("New random endpoints"):
        st.session_state.rand_pts = (
            random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX),
            random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX),
            random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX),
            random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX)
        )
    start_lat, start_lon, end_lat, end_lon = st.session_state.rand_pts
    st.sidebar.write(f"Start: {start_lat:.6f}, {start_lon:.6f}")
    st.sidebar.write(f"End:   {end_lat:.6f}, {end_lon:.6f}")

# -----------------------
# Buttons
# -----------------------
generate_clicked = st.sidebar.button("Generate Trip")
reset_clicked = st.sidebar.button("Reset Trip & Map")

if reset_clicked:
    for key in ["df_trip", "route", "trip_map", "rand_pts", "trip_split_idx"]:
        st.session_state[key] = None
    st.success("Reset complete. Generate a new trip.")

# -----------------------
# Generate Trip
# -----------------------
if generate_clicked:
    route = None
    attempts = 0
    while route is None and attempts < 10:
        route = fetch_route_osrm(start_lat, start_lon, end_lat, end_lon)
        attempts += 1
        if route is None:
            start_lat = random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX)
            start_lon = random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX)
            end_lat = random.uniform(TAIWAN_LAT_MIN, TAIWAN_LAT_MAX)
            end_lon = random.uniform(TAIWAN_LON_MIN, TAIWAN_LON_MAX)
    if route is None:
        st.error("Failed to obtain a routable path from OSRM.")
    else:
        df_normal = simulate_trip(route, start_time=start_time_input, profile="normal")
        last_timestamp = datetime.strptime(df_normal["Timestamp"].iloc[-1], "%d/%m/%Y %H:%M:%S")
        last_speed = float(df_normal["Speed (km/h)"].iloc[-1])
        last_serial = int(df_normal["Serial Number"].iloc[-1])

        drunk_start_time = last_timestamp + timedelta(seconds=15)
        df_drunk = simulate_trip(
            route,
            start_time=drunk_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            profile="drunk",
            initial_speed=random.uniform(6, 18),
            initial_serial=last_serial + 1,
        )

        df = pd.concat([df_normal, df_drunk], ignore_index=True)
        st.session_state.df_trip = df
        st.session_state.trip_split_idx = len(df_normal)
        st.session_state.route = route
        st.session_state.trip_map = create_map(route, df, show_health)

# -----------------------
# Display Trip Data
# -----------------------
if st.session_state.df_trip is not None:
    df = st.session_state.df_trip
    st.subheader("Trip Summary")
    split_idx = st.session_state.trip_split_idx or len(df)
    df_normal = df.iloc[:split_idx].copy()
    df_drunk = df.iloc[split_idx:].copy()

    def render_segment_summary(label, segment_df):
        avg_alt = segment_df["Altitude (m)"].mean()
        max_alt = segment_df["Altitude (m)"].max()
        avg_hr = segment_df["Heart Rate (BPM)"].mean()
        avg_br = segment_df["Breathing Rate (breaths/min)"].mean()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{label} Avg Altitude (m)", f"{avg_alt:.1f}", f"Max {max_alt:.1f}")
        c2.metric(f"{label} Avg Heart Rate (BPM)", f"{avg_hr:.1f}")
        c3.metric(f"{label} Avg Breathing Rate", f"{avg_br:.1f}")
        c4.metric(f"{label} Points", len(segment_df))

    st.write("Normal driver")
    render_segment_summary("Normal", df_normal)
    st.write("Drunk driver")
    render_segment_summary("Drunk", df_drunk)
    st.subheader("Preview (first rows)")
    st.caption(f"Normal trip rows: 0 to {split_idx - 1}. Drunk-driver trip starts at row {split_idx}.")
    st.write("Normal trip")
    st.dataframe(df.iloc[:split_idx].head(preview_n))
    st.write("Drunk-driver trip")
    st.dataframe(df.iloc[split_idx:].head(preview_n))
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv_bytes, file_name="taiwan_trip.csv", mime="text/csv")

# -----------------------
# Display Map
# -----------------------
st.subheader("Trip Map")
if st.session_state.df_trip is not None and st.session_state.route is not None:
    # Rebuild the map each rerun instead of using stored map
    m = create_map(st.session_state.route, st.session_state.df_trip, show_health)
    st_folium(m, width=1000, height=500)
else:
    st.info("Map will appear here after generating a trip.")

# -----------------------
# Driver Health Graphs
# -----------------------
if show_health:
    st.subheader("Driver Health over Trip")

    if 'df' in locals() and isinstance(df, pd.DataFrame) and not df.empty:
        split_idx = st.session_state.trip_split_idx or len(df)
        df_normal = df.iloc[:split_idx].copy()
        df_drunk = df.iloc[split_idx:].copy()

        def plot_health(segment_df, title):
            if 'Timestamp' not in segment_df.columns:
                st.error("⚠️ 'Timestamp' column missing in dataframe.")
                return

            plot_df = segment_df.copy()
            plot_df['Timestamp'] = plot_df['Timestamp'].astype(str).str.strip()
            plot_df['Timestamp_dt'] = pd.to_datetime(plot_df['Timestamp'], errors='coerce')
            plot_df = plot_df.dropna(subset=['Timestamp_dt'])

            if plot_df.empty:
                st.warning(f"⚠️ No valid timestamps found after parsing for {title}.")
                return

            n_points = min(80, len(plot_df))
            indices = np.linspace(0, len(plot_df) - 1, n_points).astype(int)
            df_small = plot_df.iloc[indices].copy()

            df_small['HR_smooth'] = df_small['Heart Rate (BPM)'].rolling(window=5, min_periods=1).mean()
            df_small['BR_smooth'] = df_small['Breathing Rate (breaths/min)'].rolling(window=5, min_periods=1).mean()

            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(df_small['Timestamp_dt'], df_small['HR_smooth'], color='red', label='Heart Rate (BPM)', linewidth=2)
            ax.plot(df_small['Timestamp_dt'], df_small['BR_smooth'], color='blue', label='Breathing Rate (breaths/min)', linewidth=2)

            ax.set_title(title)
            ax.set_xlabel("Time")
            ax.set_ylabel("Rate")
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            fig.autofmt_xdate(rotation=45)
            ax.legend(loc='upper left')
            ax.grid(alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)

        st.write("Normal driver")
        plot_health(df_normal, "Normal Driver Health over Trip")
        st.write("Drunk driver")
        plot_health(df_drunk, "Drunk Driver Health over Trip")
    else:
        st.warning("⚠️ No data available yet. Please generate or upload trip data before visualization.")

st.markdown("---")
render_basic_chatbot_widget()

st.markdown(
    """
    <style>
    iframe[title="streamlit_html"] {
        background: transparent !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)