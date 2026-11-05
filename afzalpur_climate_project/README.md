# Afzalpur Taluk Climate & Drought Analytics (1996–2055)

A multi-decadal meteorological analysis and predictive modeling portal for **Afzalpur Taluk, Kalaburagi District, Karnataka** (Latitude 17.20° N, Longitude 76.36° E).

## Features
- **Historical Observations (1996–2025):** Dynamic ingestion from NASA/POWER, FAO-56 Penman-Monteith reference evapotranspiration (ETo), and SPEI/SPI drought indexes.
- **Future 30-Year Projections (2026–2055):** Multi-step recursive Random Forest regression on autoregressive lag features.
- **Interactive Web Interface:** Real-time graphs using Plotly, automated data tables, and mathematical formulas via KaTeX.

## Quick Start
1. Double-click `run-app.bat` (Windows)
2. Or in terminal:
   ```bash
   pip install -r requirements.txt
   python scripts/forecast_engine.py
   python src/server.py
   ```
3. Open `http://localhost:8080` in your browser.
