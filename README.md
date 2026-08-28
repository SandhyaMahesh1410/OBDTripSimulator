# 🚗 OBD Trip Simulator V2

A Streamlit-based OBD-II trip simulator that generates realistic synthetic vehicle and driver health data using road-based routes across Taiwan.

This project helps students, researchers, and developers test transportation analytics, AI/ML models, and telematics systems without requiring real OBD devices.

## 🧩 Key Features

- 🛣️ Realistic road-based trip generation using OSRM routing
- 🚦 Traffic-aware driving simulation
- ❤️ Driver health monitoring (Heart Rate & Breathing Rate)
- 🍺 Normal Driver and Drunk Driver dataset generation
- ⛰️ Altitude estimation across Taiwan routes
- 🗺️ Interactive route visualization with Folium
- 📊 Driver health analytics and comparison graphs
- 📤 CSV dataset export
- 💬 Chatbot UI prototype for future trip assistance

## 🎯 Usage

- Generate synthetic OBD-II and GPS datasets
- Compare normal and impaired driving patterns
- Support AI/ML training and transportation research
- Simulate driver health and traffic conditions
- Test telematics and smart mobility applications

🧠 How It Works

Randomized data points are generated for GPS, speed, altitude, traffic, and driver health metrics.

Route is either random, city-to-city, or manually defined.

Each point is time-stamped and smoothed for realism.

The Streamlit dashboard allows visualization, previewing, and exporting data.

## 📦 Installation & Setup

### Clone the repository

```bash
git clone https://github.com/SandhyaMahesh1410/OBDTripSimulator.git
cd OBDTripSimulator-main
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the application

```bash
streamlit run main.py
```

## 🛠️ Technologies Used

- Python
- Streamlit
- Pandas
- NumPy
- Folium
- Matplotlib
- OSRM Routing API
