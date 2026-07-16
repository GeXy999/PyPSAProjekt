#!/usr/bin/env python3
# =============================================================
#  🇩🇪  DEUTSCHLAND ENERGY MODEL v1.0  – basierend auf Lummerland v4
#  Reines Python-Skript – kein Jupyter / Colab erforderlich
#  Ausführen:  python deutschland_v1.py
#  GUI:        streamlit run deutschland_gui.py   (importiert dieses Modul)
#
#  ÜBERTRAGEN von Lummerland v4:
#  [OK] 5 Zonen: Nord, Ost, West, Sued, Offshore (Nordsee)
#  [OK] Sektorkopplung: Wärmepumpen + Wärmespeicher (Nord, Ost, West, Sued)
#  [OK] H₂-System: Elektrolyseur, H₂-Tank, Brennstoffzelle
#  [OK] ERA5-Wetterdaten via atlite (echte deutsche Koordinaten) + Fallback
#  [OK] CO₂-Budget (GlobalConstraint) + CO₂-Preis auf Gas/Kohle
#  [OK] Kapazitätsausbau mit Annuitäten (Greenfield-Optimierung)
#  [OK] Monte-Carlo-Robustheitsprüfung über mehrere Wetterjahre
#  [OK] Karte, Plots, PDF-Bericht
#  [OK] Gurobi optional (WLS via .env), sonst HiGHS
#
#  NEU gegenüber Lummerland:
#  [OK] Als Modul importierbar (alle Läufe hinter Funktionen / __main__)
#  [OK] Braunkohle (Ost), Steinkohle (West), Laufwasser + Pumpspeicher (Sued)
#  [OK] Zeitauflösung wählbar (Standard 1h – Deutschland-Modell bleibt lösbar)
# =============================================================

# ── stdlib ───────────────────────────────────────────────────
import datetime
import os
import subprocess
import sys
import warnings

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── .env laden (vor allem anderen!) ──────────────────────────
#   CDS_KEY=dein-key-hier
#   GRB_WLSACCESSID=... / GRB_WLSSECRET=... / GRB_LICENSEID=1234567
def _load_dotenv() -> None:
    """Lädt .env-Datei aus dem Skriptverzeichnis (kein Paket nötig)."""
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    print("[OK] .env geladen")

_load_dotenv()

# =============================================================
#  0) ABHÄNGIGKEITEN AUTO-INSTALLIEREN
# =============================================================
def install_if_missing(packages: list[tuple[str, str]]) -> None:
    import importlib
    for pkg, import_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"  Installing {pkg} …")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

install_if_missing([
    ("pypsa", "pypsa"), ("highspy", "highspy"), ("pandas", "pandas"),
    ("numpy", "numpy"), ("matplotlib", "matplotlib"), ("scipy", "scipy"),
    ("openpyxl", "openpyxl"),   # zum Einlesen der Referenz-Excel (Ein-Knoten-Modell)
])

# ── third-party ──────────────────────────────────────────────
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyBboxPatch

warnings.filterwarnings("ignore")

CDS_KEY         = os.getenv("CDS_KEY", "")
GRB_WLSACCESSID = os.getenv("GRB_WLSACCESSID", "")
GRB_WLSSECRET   = os.getenv("GRB_WLSSECRET", "")
try:
    GRB_LICENSEID = int(os.getenv("GRB_LICENSEID", "")) or None
except ValueError:
    GRB_LICENSEID = None

import pypsa
print(f"[OK] PyPSA {pypsa.__version__}")

try:
    import gurobipy as gp
    GUROBI_AVAILABLE = True
    print(f"[OK] Gurobi {gp.gurobi.version()}")
except Exception:
    GUROBI_AVAILABLE = False
    print("ℹ Gurobi nicht gefunden → HiGHS wird verwendet")

try:
    import atlite
    ATLITE_AVAILABLE = True
    print(f"[OK] Atlite {atlite.__version__}")
except Exception:
    ATLITE_AVAILABLE = False
    print("ℹ Atlite nicht gefunden → synthetischer Fallback")

# =============================================================
#  1) AUSGABE-ORDNER & PFADE
# =============================================================
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
ERA5_DIR   = os.path.join(SCRIPT_DIR, "era5_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ERA5_DIR, exist_ok=True)

if CDS_KEY not in ("DEIN_API_KEY", ""):
    try:
        with open(os.path.expanduser("~/.cdsapirc"), "w") as _f:
            _f.write("url: https://cds.climate.copernicus.eu/api\n")
            _f.write(f"key: {CDS_KEY}\n")
        print("[OK] CDS API Key konfiguriert")
    except Exception as e:
        print(f"[WARN] CDS Key Konfiguration fehlgeschlagen: {e}")

# =============================================================
#  2) GLOBALE PARAMETER  (Deutschland-Skala, alles in MW / MWh / t)
# =============================================================
TIME_RES      = 1                       # Stunden pro Zeitschritt (1 = volles Jahr stündlich)
HOURS         = 8760 // TIME_RES        # Anzahl Zeitschritte
DISCOUNT_RATE = 0.07
CO2_PRICE     = 80.0                    # €/tCO₂
CO2_BUDGET    = 120_000_000             # tCO₂/a  (~Stromsektor-Größenordnung)
BASE_LOAD     = 62_000.0                # MW mittlere el. Last (Peak ~80 GW)
BASE_HEAT     = 45_000.0                # MW mittlere elektrifizierbare Wärmelast
N_MC          = 5                       # Monte-Carlo-Wetterjahre

snapshots = pd.date_range("2025-01-01", periods=HOURS, freq=f"{TIME_RES}h")

# Zeitachsen-Hilfsgrößen (hängen nur an HOURS/TIME_RES → einmal berechnen)
_DOY = np.arange(HOURS) * TIME_RES / 24.0      # Tag-des-Jahres je Snapshot
_HOD = (np.arange(HOURS) * TIME_RES) % 24      # Stunde-des-Tages je Snapshot

# Regionen: Name → (lon, lat, Lastanteil, Wärmeanteil)
REGIONS = {
    "Nord": ( 9.7, 53.6, 0.18, 0.16),
    "Ost":  (13.2, 52.2, 0.22, 0.22),
    "West": ( 7.2, 51.3, 0.36, 0.38),
    "Sued": (11.3, 48.6, 0.24, 0.24),
}
OFFSHORE_POS = (7.0, 54.8)

# Regionale Wetter-Skalierungen (Synthese): (wind_scale, wind_shift, solar_scale, solar_shift)
REGION_WEATHER_FACTORS = {
    "Nord": (1.00, 0, 0.85, 0),
    "Ost":  (0.85, 2, 0.95, 1),
    "West": (0.75, 4, 0.90, 1),
    "Sued": (0.65, 6, 1.10, 2),
}

# ERA5-Boxen je Region: (x_min, x_max, y_min, y_max)
ERA5_BOXES = {
    "Nord":     ( 8.0, 11.0, 53.0, 55.0),
    "Ost":      (11.0, 15.0, 51.0, 53.5),
    "West":     ( 6.0,  9.0, 50.0, 52.0),
    "Sued":     ( 9.0, 13.0, 47.5, 50.0),
    "Offshore": ( 6.0,  8.0, 54.0, 55.5),
}

# Deutsche AC-Knoten (für DE-gefilterte Kennzahlen & CO₂-Budget)
DE_AC_BUSES = list(REGIONS) + ["Offshore"]

# =============================================================
#  2b) NACHBARLÄNDER (Ein-Knoten-Kopplung, „High-Complexity")
# =============================================================
#  Jedes Nachbarland = 1 AC-Knoten mit fester Erzeugungsflotte, Last und
#  einer Kuppelstelle (Link) zu einer deutschen Zone (NTC = Net Transfer
#  Capacity). Nachbarn werden NICHT ausgebaut (Randbedingung); nur Deutschland
#  optimiert Zubau. Das CO₂-Budget gilt nur für Deutschland, der CO₂-Preis
#  (EU-ETS) wirkt überall.
#
#  ⚠ Datenbasis: grobe, literaturbasierte Näherung (~2023) – installierte
#     Leistung [MW], Jahresverbrauch [TWh], NTC [MW]. Für belastbare Studien
#     durch ENTSO-E-/PyPSA-Eur-Werte ersetzen.
#
#  fleet-Schlüssel → Modell-Carrier: nuclear, lignite, hardcoal, gas, oil,
#     hydro, wind, solar, biomass.  wind_k/solar_k = länderspezifische
#     Skalierung der Kapazitätsfaktoren (Küste = mehr Wind, Süden = mehr Sonne).
NEIGHBORS = {
    "FR": dict(x= 2.3, y=48.9, demand_twh=445, zone="West", ntc=4800,
               wind_k=0.95, solar_k=1.05,
               fleet=dict(nuclear=61000, gas=12000, hardcoal=1800, oil=3000,
                          hydro=25700, wind=21000, solar=17000, biomass=2000)),
    "BE": dict(x= 4.4, y=50.8, demand_twh= 82, zone="West", ntc=1000,
               wind_k=1.00, solar_k=1.00,
               fleet=dict(nuclear=3900, gas=7000, oil=200, hydro=1400,
                          wind=5000, solar=8000, biomass=1000)),
    "LU": dict(x= 6.1, y=49.8, demand_twh=  6.5, zone="West", ntc=2300,
               wind_k=0.80, solar_k=0.95,
               fleet=dict(gas=300, hydro=1300, wind=400, solar=300, biomass=100)),
    "NL": dict(x= 5.3, y=52.1, demand_twh=113, zone="West", ntc=5000,
               wind_k=1.05, solar_k=1.00,
               fleet=dict(gas=20000, hardcoal=4000, nuclear=500, wind=8500,
                          solar=22000, biomass=5000, hydro=40)),
    "DK": dict(x= 9.5, y=56.0, demand_twh= 36, zone="Nord", ntc=2500,
               wind_k=1.15, solar_k=0.95,
               fleet=dict(wind=6300, solar=3300, gas=800, oil=500,
                          biomass=2200, hardcoal=1000)),
    "PL": dict(x=19.1, y=52.2, demand_twh=170, zone="Ost", ntc=3000,
               wind_k=0.95, solar_k=0.95,
               fleet=dict(hardcoal=24000, lignite=8000, gas=3500, wind=9000,
                          solar=12000, biomass=1500, hydro=2400)),
    "CZ": dict(x=14.4, y=50.1, demand_twh= 62, zone="Ost", ntc=2500,
               wind_k=0.80, solar_k=0.95,
               fleet=dict(nuclear=4000, lignite=8000, hardcoal=1500, gas=1200,
                          hydro=2200, solar=2200, wind=340, biomass=400)),
    "AT": dict(x=14.5, y=47.6, demand_twh= 70, zone="Sued", ntc=5400,
               wind_k=0.85, solar_k=1.00,
               fleet=dict(hydro=15000, gas=4000, wind=3700, solar=3800,
                          biomass=700)),
    "CH": dict(x= 8.2, y=46.8, demand_twh= 58, zone="Sued", ntc=4000,
               wind_k=0.60, solar_k=1.05,
               fleet=dict(hydro=15500, nuclear=3000, solar=4700, gas=300)),
    "SE": dict(x=15.0, y=59.0, demand_twh=135, zone="Nord", ntc=615,
               wind_k=1.00, solar_k=0.80,
               fleet=dict(hydro=16300, nuclear=6900, wind=12000, solar=1600,
                          biomass=4000)),
    "NO": dict(x= 9.0, y=60.5, demand_twh=140, zone="Nord", ntc=1400,
               wind_k=1.05, solar_k=0.75,
               fleet=dict(hydro=33000, wind=5100, solar=300)),
}

# ERA5-Bounding-Boxen je Nachbarland: (x_min, x_max, y_min, y_max)
# Optional – nur genutzt, wenn „Ausland: ERA5" aktiv ist (sonst synthetisch).
# atlite lädt die Box beim ersten Mal via CDS herunter (kann dauern).
ERA5_BOXES_NEIGHBORS = {
    "FR": ( 0.0,  6.0, 44.0, 49.5), "BE": ( 3.0,  6.0, 50.0, 51.5),
    "LU": ( 5.7,  6.5, 49.4, 50.2), "NL": ( 4.0,  7.0, 51.5, 53.5),
    "DK": ( 8.0, 12.0, 55.0, 57.5), "PL": (15.0, 22.0, 51.0, 54.0),
    "CZ": (13.0, 18.0, 49.0, 51.0), "AT": (10.0, 16.0, 46.5, 48.5),
    "CH": ( 6.0, 10.0, 46.0, 47.5), "SE": (12.0, 18.0, 56.0, 60.0),
    "NO": ( 6.0, 11.0, 58.0, 62.0),
}

# ── Kreis 2: 13 weitere europäische Länder – zweiter Länderring (je 1 Knoten) ──
#  Gleiche Struktur wie NEIGHBORS; einziger Unterschied: `zone` ist hier das
#  PARTNERLAND (Kuppelstelle Land↔Land statt Land↔DE-Zone), z. B. ES↔FR.
#  Reihenfolge so gewählt, dass der Partner-Bus beim Aufbau schon existiert
#  (PT nach ES, IE nach GB, HR nach SI, BG nach RO, GR nach BG …).
#  Flotten/Verbrauch: literaturbasierte Näherungen (~2023/24, ENTSO-E/IRENA),
#  bewusst vereinfacht – siehe DOKUMENTATION (Ehrlichkeit/Grenzen).
EUROPE2 = {
    "ES": dict(x=-3.7, y=40.4, demand_twh=233, zone="FR", ntc=2800,
               wind_k=0.95, solar_k=1.25,
               fleet=dict(nuclear=7100, gas=30000, hydro=17000, wind=31000,
                          solar=28000, hardcoal=500, biomass=1000)),
    "PT": dict(x=-9.1, y=38.7, demand_twh= 51, zone="ES", ntc=3000,
               wind_k=1.00, solar_k=1.20,
               fleet=dict(hydro=7200, wind=5600, solar=4700, gas=4600,
                          biomass=700)),
    "IT": dict(x=12.5, y=41.9, demand_twh=300, zone="CH", ntc=4200,
               wind_k=0.85, solar_k=1.15,
               fleet=dict(gas=42000, hydro=19000, solar=30000, wind=12000,
                          oil=1000, hardcoal=2000, biomass=3000)),
    "GB": dict(x=-0.1, y=51.5, demand_twh=275, zone="FR", ntc=4000,
               wind_k=1.15, solar_k=0.90,
               fleet=dict(gas=30000, nuclear=5900, wind=30000, solar=15000,
                          biomass=4000, hydro=1900)),
    "IE": dict(x=-6.3, y=53.3, demand_twh= 33, zone="GB", ntc=1000,
               wind_k=1.20, solar_k=0.85,
               fleet=dict(gas=4500, wind=5000, solar=700, hydro=500, oil=300)),
    "FI": dict(x=24.9, y=60.2, demand_twh= 82, zone="SE", ntc=2700,
               wind_k=1.00, solar_k=0.70,
               fleet=dict(nuclear=4400, hydro=3100, wind=6900, solar=900,
                          biomass=2000, hardcoal=500)),
    "SK": dict(x=17.1, y=48.2, demand_twh= 27, zone="CZ", ntc=2100,
               wind_k=0.75, solar_k=0.95,
               fleet=dict(nuclear=2700, gas=1000, hydro=1600, solar=500,
                          lignite=200)),
    "HU": dict(x=19.0, y=47.5, demand_twh= 43, zone="AT", ntc=900,
               wind_k=0.75, solar_k=1.05,
               fleet=dict(nuclear=2000, gas=4500, solar=5600, lignite=900,
                          biomass=300)),
    "SI": dict(x=14.5, y=46.1, demand_twh= 13, zone="AT", ntc=950,
               wind_k=0.70, solar_k=1.05,
               fleet=dict(nuclear=700, hydro=1300, gas=500, lignite=900,
                          solar=700)),
    "HR": dict(x=16.0, y=45.8, demand_twh= 17, zone="SI", ntc=1000,
               wind_k=0.90, solar_k=1.10,
               fleet=dict(hydro=2200, gas=800, wind=1100, solar=800, oil=300)),
    "RO": dict(x=26.1, y=44.4, demand_twh= 50, zone="HU", ntc=1000,
               wind_k=0.90, solar_k=1.10,
               fleet=dict(hydro=6600, nuclear=1400, gas=3000, lignite=3000,
                          wind=3000, solar=2000)),
    "BG": dict(x=23.3, y=42.7, demand_twh= 34, zone="RO", ntc=1000,
               wind_k=0.80, solar_k=1.15,
               fleet=dict(nuclear=2000, lignite=3800, hydro=3200, solar=3000,
                          wind=700)),
    "GR": dict(x=23.7, y=38.0, demand_twh= 51, zone="BG", ntc=800,
               wind_k=0.95, solar_k=1.25,
               fleet=dict(gas=5200, lignite=1200, hydro=3400, wind=5200,
                          solar=7000, oil=800)),
}

# ── Kreis 3: 12 weitere europäische Länder – dritter Länderring ────────────
#  Gleiche Struktur wie EUROPE2; `zone` = Partnerland (Kuppelstelle Land↔Land).
#  Reihenfolge so, dass der Partner-Bus beim Aufbau schon existiert:
#  EE→FI, LV→EE, LT→PL, RS→HU, BA→HR, ME/MK/XK→RS, AL→GR, MD→RO, UA→PL.
#  Alle liegen im ENTSO-E-Verbundnetz (Baltikum + Westbalkan seit 2025/lange,
#  MD/UA seit 2022 synchron mit Kontinentaleuropa). Flotten/Verbrauch:
#  literaturbasierte Näherungen (~2023, ENTSO-E/IRENA) – bewusst vereinfacht.
#  UA im Kriegskontext → Werte besonders unsicher (Vorkriegs-Größenordnung).
EUROPE3 = {
    # Baltikum
    "EE": dict(x=25.0, y=59.0, demand_twh=  8, zone="FI", ntc=1000,
               wind_k=1.05, solar_k=0.80,
               fleet=dict(oil=2000, wind=400, solar=500, biomass=300)),
    "LV": dict(x=24.1, y=56.9, demand_twh=  7, zone="EE", ntc=1000,
               wind_k=1.05, solar_k=0.80,
               fleet=dict(hydro=1600, gas=1000, wind=150, biomass=200)),
    "LT": dict(x=25.3, y=54.7, demand_twh= 11, zone="PL", ntc=1300,
               wind_k=1.10, solar_k=0.85,
               fleet=dict(gas=1000, wind=800, hydro=900, solar=300, biomass=100)),
    # Westbalkan
    "RS": dict(x=20.5, y=44.8, demand_twh= 35, zone="HU", ntc=1000,
               wind_k=0.85, solar_k=1.15,
               fleet=dict(lignite=4000, hydro=3000, gas=300, wind=400, solar=100)),
    "BA": dict(x=17.8, y=43.9, demand_twh= 13, zone="HR", ntc=800,
               wind_k=0.80, solar_k=1.15,
               fleet=dict(lignite=2000, hydro=2000, wind=300, solar=50)),
    "ME": dict(x=19.3, y=42.4, demand_twh=  3, zone="RS", ntc=600,
               wind_k=0.80, solar_k=1.20,
               fleet=dict(hydro=700, lignite=200, wind=120, solar=50)),
    "MK": dict(x=21.7, y=41.6, demand_twh=  7, zone="RS", ntc=800,
               wind_k=0.75, solar_k=1.20,
               fleet=dict(lignite=800, hydro=700, gas=300, solar=100, wind=40)),
    "AL": dict(x=19.8, y=41.3, demand_twh=  7, zone="GR", ntc=500,
               wind_k=0.80, solar_k=1.25,
               fleet=dict(hydro=2100, solar=150, wind=40)),
    "XK": dict(x=21.0, y=42.6, demand_twh=  6, zone="RS", ntc=500,
               wind_k=0.80, solar_k=1.15,
               fleet=dict(lignite=1300, hydro=100, solar=30, wind=140)),
    # Osteuropa
    "MD": dict(x=28.9, y=47.0, demand_twh=  5, zone="RO", ntc=700,
               wind_k=0.85, solar_k=1.10,
               fleet=dict(gas=2500, hydro=60, solar=50, wind=150)),
    "UA": dict(x=30.5, y=50.4, demand_twh=120, zone="PL", ntc=2000,
               wind_k=1.00, solar_k=1.10,
               fleet=dict(nuclear=13000, lignite=20000, hydro=6000, gas=2000,
                          wind=1700, solar=8000, biomass=200)),
}

# Alle Auslandsknoten zusammen (für GUI/Karte/Auswertung – Superset aller Kreise)
ALL_FOREIGN = {**NEIGHBORS, **EUROPE2, **EUROPE3}

def _foreign_set(include_europe: bool, include_kreis3: bool = False) -> dict:
    """Aktive Auslandsknoten je nach Kopplungstiefe. Verhaltensneutral zu früher:
    ohne Kreis 3 identisch zu {NEIGHBORS (+ EUROPE2 falls include_europe)}."""
    d = dict(NEIGHBORS)
    if include_europe:
        d.update(EUROPE2)
    if include_kreis3:
        d.update(EUROPE3)
    return d

ERA5_BOXES_EUROPE = {
    "ES": (-8.5,  2.5, 36.5, 43.0), "PT": (-9.5, -6.5, 37.0, 42.0),
    "IT": ( 8.0, 17.0, 38.0, 46.0), "GB": (-5.5,  1.5, 50.5, 57.5),
    "IE": (-10.0, -6.0, 51.5, 55.0), "FI": (21.0, 29.0, 60.0, 65.0),
    "SK": (17.0, 22.0, 47.8, 49.5), "HU": (16.0, 22.5, 45.8, 48.5),
    "SI": (13.5, 16.5, 45.4, 46.9), "HR": (13.5, 18.5, 42.5, 46.5),
    "RO": (20.5, 29.5, 43.5, 48.0), "BG": (22.5, 28.5, 41.0, 44.0),
    "GR": (20.0, 26.5, 35.0, 41.5),
}
ERA5_BOXES_EUROPE3 = {
    "EE": (22.0, 28.2, 57.5, 59.7), "LV": (21.0, 28.2, 55.7, 58.1),
    "LT": (21.0, 26.9, 53.9, 56.5), "RS": (18.8, 23.0, 42.2, 46.2),
    "BA": (15.7, 19.7, 42.5, 45.3), "ME": (18.4, 20.4, 41.8, 43.6),
    "MK": (20.4, 23.1, 40.8, 42.4), "AL": (19.2, 21.1, 39.6, 42.7),
    "XK": (20.0, 21.8, 41.8, 43.3), "MD": (26.6, 30.2, 45.4, 48.5),
    "UA": (22.1, 40.2, 44.3, 52.4),
}
ERA5_BOXES_FOREIGN = {**ERA5_BOXES_NEIGHBORS, **ERA5_BOXES_EUROPE,
                      **ERA5_BOXES_EUROPE3}

# =============================================================
#  3) ANNUITÄTEN & KOSTEN
# =============================================================
def annuity(lifetime: int, r: float = DISCOUNT_RATE) -> float:
    """Annuitätenfaktor einer Investition."""
    return r / (1 - (1 + r) ** (-lifetime)) if r > 0 else 1 / lifetime

CAPEX: dict[str, tuple[int, int]] = {          # (€/MW bzw. €/MWh, Lebensdauer a)
    "Wind_on":   (1_200_000, 25), "Wind_off":  (2_400_000, 25),
    "Solar":     (  550_000, 25), "Gas_CCGT":  (  800_000, 30),
    "Battery":   (  300_000, 15), "H2_elec":   (  700_000, 25),
    "H2_tank":   (    8_000, 30), "H2_FC":     (  900_000, 20),
    "HeatPump":  (  500_000, 20), "HeatStore": (   20_000, 30),
    "Line":      (  400_000, 40), "Line_off":  (  900_000, 40),
}

def capex_annual(key: str) -> float:
    """Annualisierte Kapitalkosten [€/MW/a] – nutzt den aktuellen DISCOUNT_RATE."""
    c, lt = CAPEX[key]
    return c * annuity(lt, DISCOUNT_RATE)

def opex(co2_price: float = CO2_PRICE, gas_price: float = 55.0) -> dict[str, float]:
    """Grenzkosten [€/MWh] inkl. CO₂-Preis auf fossile Träger.

    gas_price = Brennstoffkosten Gas [€/MWh_th]; Kohlepreise skalieren
    relativ dazu mit (Standard: Gas 55, Braunkohle 28, Steinkohle 40)."""
    return {
        "Wind_on": 0.1, "Wind_off": 0.1, "Solar": 0.05, "Hydro": 0.5,
        "Gas_CCGT":  gas_price + 0.370 * co2_price,
        "Lignite":   28. + 1.000 * co2_price,
        "Hardcoal":  40. + 0.800 * co2_price,
        "Battery": 0.5, "H2_elec": 1., "H2_FC": 2., "HeatPump": 1.,
        # Zusätzliche Träger der Nachbarländer (EU-ETS-Preis wirkt auch hier):
        "Nuclear": 9., "Biomass": 45., "Oil": 150. + 0.650 * co2_price,
        "Backup": 3000.,            # Lastabwurf/Import-Notreserve (VoLL)
    }

# =============================================================
#  4) WETTERDATEN (ERA5 oder synthetisch)
# =============================================================
def _synthetic_base(seed_s=0, seed_w=42, seed_wo=99, hours=HOURS):
    """Synthetische Basis-Profile (Solar, Wind onshore, Wind offshore)."""
    doy = np.arange(hours) * TIME_RES / 24.0
    hod = (np.arange(hours) * TIME_RES) % 24
    np.random.seed(seed_s)
    seas_s  = 0.55 + 0.45 * np.cos(2 * np.pi * (doy - 172) / 365)
    daily_s = np.maximum(0, np.sin(np.pi * (hod - 6) / 12))
    daily_s[(hod < 6) | (hod > 18)] = 0
    s_cf = np.clip(seas_s * daily_s * (1 - np.abs(np.random.normal(0, .07, hours))), 0, 1)
    np.random.seed(seed_w)
    seas_w = 0.38 + 0.22 * np.sin(2 * np.pi * doy / 365 + np.pi)
    w_cf   = np.clip(seas_w + np.random.weibull(2.2, hours) * 0.42 - 0.16, 0.03, 1.0)
    rng    = np.random.default_rng(seed_wo)
    seas_o = 0.48 + 0.18 * np.sin(2 * np.pi * doy / 365 + np.pi)
    w_off  = np.clip(seas_o + 0.10 * rng.standard_normal(hours), 0.05, 1.0)
    return s_cf, w_cf, w_off

def _shift_profile(profile, shift=0, scale=1.0, noise=0.0, seed=0):
    """Regional verwandtes Profil: zeitversetzt, skaliert, verrauscht."""
    rng = np.random.default_rng(seed)
    p = np.roll(profile, shift) * scale
    if noise > 0:
        p = p * (1 + rng.normal(0, noise, p.shape[0]))
    return np.clip(p, 0.0, 1.0)

def _era5_region(box, need_pv=True, concurrent=False):
    """Lädt Wind- (und ggf. PV-)Kapazitätsfaktoren einer ERA5-Box.
    concurrent=True reicht die Monats-Requests parallel ein (schneller, nur
    bei freier CDS-Queue sinnvoll – Vorabdownload); Standard sequenziell."""
    x0, x1, y0, y1 = box
    path = os.path.join(ERA5_DIR, f"de_{x0}_{y0}_2023.nc")
    cut = atlite.Cutout(path=path, module="era5",
                        x=slice(x0, x1), y=slice(y0, y1),
                        time=slice("2023-01-01", "2023-12-31"))
    # data_format="netcdf": lädt direkt als netCDF und vermeidet die
    # GRIB→netCDF-Konvertierung über cfgrib/eccodes (unter Windows/Py3.14
    # nicht lauffähig – native ecCodes-Lib fehlt).
    # monthly_requests=True: die CDS begrenzt die netCDF-Requestgröße →
    #   monatsweise anfragen (sonst 403 "request too large").
    # concurrent_requests=False: sequenziell einreichen, sonst überschreiten
    #   viele gleichzeitige Jobs das CDS-Queue-Limit (max. 150) → 400 "rejected".
    # Bereits vorhandene Cutouts werden nicht neu geladen.
    cut.prepare(["wind", "influx", "temperature"] if need_pv else ["wind"],
                data_format="netcdf", monthly_requests=True,
                concurrent_requests=concurrent)
    layout = cut.uniform_layout()          # einmal berechnen, für Wind + PV nutzen
    wind = np.clip(cut.wind(turbine="Vestas_V112_3MW", per_unit=True,
                            layout=layout).values.flatten(), 0, 1)
    pv = None
    if need_pv:
        pv = np.clip(cut.pv(panel="CSi", per_unit=True,
                            orientation={"slope": 35., "azimuth": 180.},
                            layout=layout).values.flatten(), 0, 1)
    return wind[::TIME_RES][:HOURS], (pv[::TIME_RES][:HOURS] if pv is not None else None)

def make_profiles(mc_seed: int | None = None,
                  foreign_era5: bool = False,
                  include_europe: bool = False,
                  include_kreis3: bool = False) -> tuple[dict, bool]:
    """Erzeugt Wetterprofile je Region.
    mc_seed=None  → ERA5 falls verfügbar, sonst synthetisch.
    mc_seed=i     → synthetisches Monte-Carlo-Wetterjahr i.
    foreign_era5  → Nachbarländer ebenfalls aus ERA5 (statt synthetisch).
    include_europe → zusätzlich Profile für den 2. Länderring (EUROPE2)."""
    prof: dict[str, np.ndarray] = {}
    i = 0 if mc_seed is None else mc_seed
    era5_ok = False
    if mc_seed is None and ATLITE_AVAILABLE:
        try:
            print("[atlite] Lade ERA5-Daten für 5 deutsche Regionen …")
            for reg in ["Nord", "Ost", "West", "Sued"]:
                w, s = _era5_region(ERA5_BOXES[reg], need_pv=True)
                prof[f"wind_{reg}"], prof[f"solar_{reg}"] = w, s
            prof["wind_Offshore"], _ = _era5_region(ERA5_BOXES["Offshore"], need_pv=False)
            print("[OK] ERA5-Daten geladen")
            era5_ok = True
        except Exception as e:
            print(f"[atlite] Fehler: {e} → synthetischer Fallback")
    if not era5_ok:
        s, w, wo = _synthetic_base(i * 17 + 3, i * 31 + 7, i * 17 + 102)
        prof["wind_Offshore"] = wo
        # Regionale Charakteristik: Nord windig, Süd sonnig
        for reg, (wsc, wsh, ssc, ssh) in REGION_WEATHER_FACTORS.items():
            prof[f"wind_{reg}"]  = _shift_profile(w, wsh, wsc, 0.05, seed=i * 7 + wsh)
            prof[f"solar_{reg}"] = _shift_profile(s, ssh, ssc, 0.04, seed=i * 7 + 50 + ssh)

    # Nachbarländer: standardmäßig synthetisch (länderspezifisch skaliert/
    # zeitversetzt). Mit foreign_era5=True je Land ERA5 laden (falls atlite +
    # CDS verfügbar), sonst pro Land automatischer synthetischer Fallback.
    sN, wN, _ = _synthetic_base(i * 17 + 5, i * 31 + 11, i * 17 + 103)
    use_foreign_era5 = foreign_era5 and mc_seed is None and ATLITE_AVAILABLE
    if use_foreign_era5:
        print("[atlite] Lade ERA5 für Nachbarländer (erster Lauf lädt via CDS) …")
    countries = _foreign_set(include_europe, include_kreis3)
    for k, (cc, d) in enumerate(countries.items()):
        if use_foreign_era5 and cc in ERA5_BOXES_FOREIGN:
            try:
                w_cc, s_cc = _era5_region(ERA5_BOXES_FOREIGN[cc], need_pv=True)
                prof[f"wind_{cc}"], prof[f"solar_{cc}"] = w_cc, s_cc
                print(f"  [OK] ERA5 {cc}")
                continue
            except Exception as e:
                print(f"  [atlite] {cc}: {e} → synthetisch")
        prof[f"wind_{cc}"]  = _shift_profile(wN, shift=k % 8, scale=d["wind_k"],
                                             noise=0.05, seed=i * 7 + 200 + k)
        prof[f"solar_{cc}"] = _shift_profile(sN, shift=k % 4, scale=d["solar_k"],
                                             noise=0.04, seed=i * 7 + 300 + k)
    return prof, era5_ok

def make_loads(load_scale=1.0, heat_scale=1.0, mc_seed=None) -> dict[str, np.ndarray]:
    """Strom- und Wärmelastprofile je Region [MW]."""
    if mc_seed is not None:
        np.random.seed(mc_seed * 17 + 4)
        load_scale *= 1 + np.random.uniform(-0.05, 0.05)
        heat_scale *= 1 + np.random.uniform(-0.05, 0.05)
    lt = BASE_LOAD * load_scale * (1 + .20 * np.cos(2*np.pi*(_DOY-355)/365)) \
                                * (1 + .15 * np.sin(np.pi*(_HOD-6)/12))
    ht = BASE_HEAT * heat_scale * (1 + .55 * np.cos(2*np.pi*(_DOY-355)/365)) \
                                * (1 + .08 * np.cos(2*np.pi*_HOD/24))
    out = {}
    for reg, (_, _, la, ha) in REGIONS.items():
        out[f"load_{reg}"] = lt * la
        out[f"heat_{reg}"] = ht * ha
    return out

# =============================================================
#  5) HILFSFUNKTIONEN
# =============================================================
def _pnom(comp_df, name) -> float:
    """Optimierte Nennleistung einer Komponente (p_nom_opt oder p_nom fallback)."""
    row = comp_df.loc[name]
    return max(0., float(row.get("p_nom_opt", row["p_nom"])))

BG, BGMAP, LAND, SHORE = "#0d1b2a", "#0a2540", "#4a7c2f", "#d9c98a"

def _style_ax(ax, title, xlabel="", ylabel="", bg_inner="#1a2a3a"):
    """Wendet einheitlichen Dark-Theme-Stil auf eine matplotlib-Achse an."""
    ax.set_facecolor(bg_inner)
    ax.tick_params(colors="white")
    ax.set_title(title, color="white", fontsize=10, fontweight="bold")
    if xlabel: ax.set_xlabel(xlabel, color="white")
    if ylabel: ax.set_ylabel(ylabel, color="white")
    for sp in ax.spines.values():
        sp.set_edgecolor("#444")

# =============================================================
#  6) NETZ-BUILDER  (Deutschland, 5 Zonen + Wärme + H₂)
# =============================================================
def build_network(prof: dict, loads: dict,
                  co2_budget: float = CO2_BUDGET,
                  co2_price: float = CO2_PRICE,
                  gas_price: float = 55.0,
                  include_neighbors: bool = False,
                  include_europe: bool = False,
                  include_kreis3: bool = False) -> "pypsa.Network":
    """Baut das 5-Zonen-Deutschland-Netz mit Sektorkopplung.
    include_neighbors=True koppelt zusätzlich die Nachbarländer (je 1 Knoten).
    include_europe=True   koppelt darüber hinaus den 2. Länderring (EUROPE2,
    Kuppelstelle jeweils ans Partnerland) – erfordert include_neighbors."""
    OP = opex(co2_price, gas_price)
    net = pypsa.Network()
    net.set_snapshots(snapshots)
    net.snapshot_weightings.loc[:, :] = TIME_RES   # TIME_RES-Stunden je Schritt korrekt gewichten

    for c, co2 in [("wind", 0.), ("solar", 0.), ("hydro", 0.), ("gas", 0.370),
                   ("lignite", 1.0), ("hardcoal", 0.8),
                   ("battery", 0.), ("H2", 0.), ("AC", 0.), ("heat", 0.),
                   ("nuclear", 0.), ("biomass", 0.), ("oil", 0.65),
                   ("backup", 0.)]:
        net.add("Carrier", c, co2_emissions=co2)

    for b, (x, y, _, _) in REGIONS.items():
        net.add("Bus", b, v_nom=380., carrier="AC", x=x, y=y)
    net.add("Bus", "Offshore", v_nom=380., carrier="AC",
            x=OFFSHORE_POS[0], y=OFFSHORE_POS[1])
    for b in REGIONS:
        net.add("Bus", f"Waerme_{b}", carrier="heat")
    net.add("Bus", "H2_Bus", carrier="H2")

    # ── Leitungen (MW, alle erweiterbar) ─────────────────────
    for ln, b0, b1, ckey, snom, smin in [
        ("Leitung_Nord_West",  "Nord",     "West", "Line",     8_000., 8_000.),
        ("Leitung_Nord_Ost",   "Nord",     "Ost",  "Line",     5_000., 5_000.),
        ("Leitung_Ost_Sued",   "Ost",      "Sued", "Line",     4_000., 4_000.),
        ("Leitung_West_Sued",  "West",     "Sued", "Line",     6_000., 6_000.),
        ("Leitung_Ost_West",   "Ost",      "West", "Line",     4_000., 4_000.),
        ("Leitung_Nord_Sued",  "Nord",     "Sued", "Line",     4_000., 4_000.),  # "SuedLink"
        ("Leitung_Off_Nord",   "Offshore", "Nord", "Line_off", 8_000., 8_000.),
    ]:
        net.add("Line", ln, bus0=b0, bus1=b1, x=0.10, r=0.01,
                s_nom=snom, s_nom_min=smin, s_nom_extendable=True,
                capital_cost=capex_annual(ckey))

    # ── Erzeuger ─────────────────────────────────────────────
    def gen(name, bus, carrier, ckey, p_nom, p_min, cf_key=None, ext=True):
        kw = dict(bus=bus, carrier=carrier, p_nom=p_nom,
                  marginal_cost=OP[ckey])
        if cf_key is not None:
            kw["p_max_pu"] = pd.Series(prof[cf_key], index=snapshots)
        if ext:
            kw |= dict(p_nom_min=p_min, p_nom_extendable=True,
                       capital_cost=capex_annual(ckey))
        net.add("Generator", name, **kw)

    gen("Wind_Offshore", "Offshore", "wind", "Wind_off", 9_000., 9_000., "wind_Offshore")
    for reg, (w0, s0) in {"Nord": (22_000., 5_000.), "Ost": (14_000., 12_000.),
                          "West": (12_000., 15_000.), "Sued": (5_000., 25_000.)}.items():
        gen(f"Wind_{reg}",  reg, "wind",  "Wind_on", w0, w0, f"wind_{reg}")
        gen(f"Solar_{reg}", reg, "solar", "Solar",   s0, s0, f"solar_{reg}")
    gen("Gas_Nord", "Nord", "gas", "Gas_CCGT",  6_000., 3_000.)
    gen("Gas_West", "West", "gas", "Gas_CCGT", 14_000., 6_000.)
    gen("Gas_Sued", "Sued", "gas", "Gas_CCGT", 11_000., 5_000.)
    # Bestandskraftwerke (nicht erweiterbar, keine Kapitalkosten)
    net.add("Generator", "Braunkohle_Ost", bus="Ost", carrier="lignite",
            p_nom=7_000., marginal_cost=OP["Lignite"])
    net.add("Generator", "Steinkohle_West", bus="West", carrier="hardcoal",
            p_nom=5_000., marginal_cost=OP["Hardcoal"])
    net.add("Generator", "Laufwasser_Sued", bus="Sued", carrier="hydro",
            p_nom=4_000., marginal_cost=OP["Hydro"],
            p_max_pu=pd.Series(np.full(HOURS, 0.55), index=snapshots))

    # ── Speicher ─────────────────────────────────────────────
    net.add("StorageUnit", "Pumpspeicher_Sued", bus="Sued", carrier="battery",
            p_nom=6_500., max_hours=8., cyclic_state_of_charge=True,
            efficiency_store=0.88, efficiency_dispatch=0.88, marginal_cost=0.3)
    for reg in ["Ost", "West", "Sued"]:
        net.add("StorageUnit", f"Batterie_{reg}", bus=reg, carrier="battery",
                p_nom=3_000., p_nom_min=1_000., p_nom_extendable=True,
                max_hours=4., efficiency_store=0.93, efficiency_dispatch=0.93,
                cyclic_state_of_charge=True, marginal_cost=OP["Battery"],
                capital_cost=capex_annual("Battery") * 4)

    # ── H₂-System (am Knoten Nord – Elektrolyse nahe Windstrom) ──
    net.add("Link", "Elektrolyseur", bus0="Nord", bus1="H2_Bus",
            p_nom=5_000., p_nom_min=1_000., p_nom_extendable=True, efficiency=0.70,
            marginal_cost=OP["H2_elec"], capital_cost=capex_annual("H2_elec"))
    net.add("Store", "H2_Tank", bus="H2_Bus", carrier="H2",
            e_nom=200_000., e_nom_min=20_000., e_nom_extendable=True, e_cyclic=True,
            capital_cost=capex_annual("H2_tank"))
    net.add("Link", "Brennstoffzelle", bus0="H2_Bus", bus1="Nord",
            p_nom=3_000., p_nom_min=500., p_nom_extendable=True, efficiency=0.55,
            marginal_cost=OP["H2_FC"], capital_cost=capex_annual("H2_FC"))

    # ── Wärme: WP + Speicher je Region ───────────────────────
    for reg, cop in {"Nord": 3.1, "Ost": 2.9, "West": 3.0, "Sued": 2.8}.items():
        net.add("Link", f"WP_{reg}", bus0=reg, bus1=f"Waerme_{reg}",
                p_nom=6_000., p_nom_min=1_000., p_nom_extendable=True,
                efficiency=cop, marginal_cost=OP["HeatPump"],
                capital_cost=capex_annual("HeatPump"))
        net.add("Store", f"WaermeSpeicher_{reg}", bus=f"Waerme_{reg}", carrier="heat",
                e_nom=40_000., e_nom_min=4_000., e_nom_extendable=True, e_cyclic=True,
                standing_loss=0.005, capital_cost=capex_annual("HeatStore") * 8)

    # ── Lasten ───────────────────────────────────────────────
    for reg in REGIONS:
        net.add("Load", f"Last_{reg}", bus=reg,
                p_set=pd.Series(loads[f"load_{reg}"], index=snapshots))
        net.add("Load", f"Waerme_Last_{reg}", bus=f"Waerme_{reg}",
                p_set=pd.Series(loads[f"heat_{reg}"], index=snapshots))

    # ── Nachbarländer (je 1 Knoten, feste Flotte, Kuppel-Link) ───
    if include_neighbors:
        # Zeitliche Lastform aus DE ableiten und je Land auf den Jahres-
        # verbrauch skalieren (Vereinfachung: gleiche Kurvenform wie DE).
        de_shape = sum(loads[f"load_{r}"] for r in REGIONS)
        de_shape = de_shape / de_shape.mean()          # Mittelwert = 1
        # fleet-Schlüssel → (Carrier, opex-Schlüssel, p_max_pu)
        _FLEET = {
            "nuclear":  ("nuclear",  "Nuclear",  0.90),
            "lignite":  ("lignite",  "Lignite",  1.00),
            "hardcoal": ("hardcoal", "Hardcoal", 1.00),
            "gas":      ("gas",      "Gas_CCGT", 1.00),
            "oil":      ("oil",      "Oil",      1.00),
            "biomass":  ("biomass",  "Biomass",  1.00),
            "hydro":    ("hydro",    "Hydro",    0.50),
        }
        countries = _foreign_set(include_europe, include_kreis3)
        for cc, d in countries.items():
            net.add("Bus", cc, v_nom=380., carrier="AC", x=d["x"], y=d["y"])
            avg_mw = d["demand_twh"] * 1e6 / (HOURS * TIME_RES)
            net.add("Load", f"Last_{cc}", bus=cc,
                    p_set=pd.Series(de_shape * avg_mw, index=snapshots))
            for tech, cap in d["fleet"].items():
                if cap <= 0:
                    continue
                if tech == "wind":
                    net.add("Generator", f"{cc}_wind", bus=cc, carrier="wind",
                            p_nom=cap, marginal_cost=OP["Wind_on"],
                            p_max_pu=pd.Series(prof[f"wind_{cc}"], index=snapshots))
                elif tech == "solar":
                    net.add("Generator", f"{cc}_solar", bus=cc, carrier="solar",
                            p_nom=cap, marginal_cost=OP["Solar"],
                            p_max_pu=pd.Series(prof[f"solar_{cc}"], index=snapshots))
                else:
                    car, opk, pmax = _FLEET[tech]
                    net.add("Generator", f"{cc}_{tech}", bus=cc, carrier=car,
                            p_nom=cap, marginal_cost=OP[opk], p_max_pu=pmax)
            # Backup/VoLL → garantiert lösbar (teure Import-/Lastabwurf-Reserve)
            net.add("Generator", f"{cc}_backup", bus=cc, carrier="backup",
                    p_nom=80_000., marginal_cost=OP["Backup"])
            # Kuppelstelle (Link, bidirektional) DE-Zone ↔ Land, NTC-begrenzt
            net.add("Link", f"IC_{cc}", bus0=d["zone"], bus1=cc,
                    p_nom=d["ntc"], p_min_pu=-1.0, marginal_cost=0.01)

    # ── CO₂-Budget ───────────────────────────────────────────
    if include_neighbors:
        # Budget nur für Deutschland (Custom-Constraint beim Solven), da die
        # GlobalConstraint sonst auch die Auslandsemissionen begrenzen würde.
        net._co2_budget_de = co2_budget
        net._de_ac_buses = list(DE_AC_BUSES)
    else:
        net.add("GlobalConstraint", "co2_limit", sense="<=",
                carrier_attribute="co2_emissions", constant=co2_budget)

    # Realistische Obergrenzen (verhindert Skalierungswarnungen)
    _P_MAX, _E_MAX = 250_000., 2_000_000.
    net.generators.loc[net.generators.p_nom_extendable, "p_nom_max"] = _P_MAX
    net.links.loc[net.links.p_nom_extendable, "p_nom_max"] = _P_MAX
    net.lines.loc[net.lines.s_nom_extendable, "s_nom_max"] = 30_000.
    net.stores.loc[net.stores.e_nom_extendable, "e_nom_max"] = _E_MAX
    net.storage_units.loc[net.storage_units.p_nom_extendable, "p_nom_max"] = _P_MAX
    return net

# =============================================================
#  6b) SOLVER & CO₂ – HELFER
# =============================================================
USE_GUROBI  = GUROBI_AVAILABLE and GRB_WLSACCESSID not in ("DEINE_ACCESS_ID", "")
_gurobi_env = None

def _get_gurobi_env():
    """Erzeugt oder gibt gecachte Gurobi-Umgebung mit WLS-Credentials zurück."""
    global _gurobi_env
    if _gurobi_env is None:
        _gurobi_env = gp.Env(params={
            "WLSACCESSID": GRB_WLSACCESSID, "WLSSECRET": GRB_WLSSECRET,
            "LICENSEID": GRB_LICENSEID, "OutputFlag": 0,
            "TimeLimit": 900, "Method": 2})
    return _gurobi_env

def _assert_optimal(res) -> None:
    """Wirft einen Fehler, wenn der Solver KEINE optimale Lösung fand.
    Ohne diese Prüfung würde die App eine unzulässige Zwischenlösung als
    'Müll' anzeigen (negative/absurde Leistungen, Preis 0, CO₂ über Budget) –
    typisch, wenn HiGHS in ein Zeitlimit läuft. optimize() liefert
    ('ok', 'optimal') im Erfolgsfall."""
    status = condition = None
    if isinstance(res, tuple):
        if len(res) >= 2:
            status, condition = res[0], res[1]
        elif len(res) == 1:
            condition = res[0]
    elif isinstance(res, str):
        condition = res
    if condition is not None and str(condition).lower() != "optimal":
        raise RuntimeError(
            f"Optimierung nicht optimal gelöst (status={status}, "
            f"condition={condition}). Modell zu groß für den Solver "
            f"(z. B. HiGHS im Zeit-/Speicherlimit) oder unzulässig.")


def _co2_de_extra(n, sns) -> None:
    """Custom-Constraint: begrenzt die CO₂-Emissionen NUR der deutschen
    Erzeuger auf das Budget (bei gekoppelten Nachbarländern). Wird als
    extra_functionality an optimize() übergeben."""
    import xarray as xr
    budget = getattr(n, "_co2_budget_de", None)
    if budget is None:
        return
    de_buses = getattr(n, "_de_ac_buses", [])
    emis = n.generators.carrier.map(n.carriers.co2_emissions).fillna(0.)
    gens = list(n.generators.index[n.generators.bus.isin(de_buses) & (emis > 0.)])
    if not gens:
        return
    p = n.model["Generator-p"]
    gdim = [d for d in p.dims if d != "snapshot"][0]   # Generator-Dimension
    p = p.sel({gdim: gens})
    f = xr.DataArray(emis[gens].to_numpy(), dims=gdim, coords={gdim: gens})
    w = xr.DataArray(n.snapshot_weightings.generators.reindex(sns).to_numpy(),
                     dims="snapshot", coords={"snapshot": list(sns)})
    n.model.add_constraints((p * f * w).sum() <= budget, name="co2_limit_DE")


def solve_network(net, verbose=True) -> bool:
    """Gurobi (falls lizensiert), sonst HiGHS. True = Gurobi verwendet.
    Prüft, dass die Lösung optimal ist – sonst Exception statt Müll-Plot."""
    ef = _co2_de_extra if getattr(net, "_co2_budget_de", None) is not None else None
    if USE_GUROBI:
        try:
            res = net.optimize(solver_name="gurobi",
                               assign_all_duals=True, extra_functionality=ef,
                               solver_options={"env": _get_gurobi_env(),
                                               "OutputFlag": int(verbose)})
            _assert_optimal(res)
            return True
        except Exception as e:
            print(f"  ⚠ Gurobi: {e} → HiGHS")
    res = net.optimize(solver_name="highs",
                       assign_all_duals=True, extra_functionality=ef,
                       solver_options={"time_limit": 900})
    _assert_optimal(res)
    return False

def total_co2(net, buses=None) -> float:
    """CO₂-Emissionen [t/a]. buses=None → gesamtes Netz; sonst nur Erzeuger
    an diesen Knoten (z. B. DE_AC_BUSES für Deutschland-only)."""
    try:
        g = net.generators
        if buses is not None:
            g = g[g.bus.isin(buses)]
        p = net.generators_t.p[g.index]
        return float((p * g.carrier.map(net.carriers.co2_emissions)
                      ).sum().sum() * TIME_RES)
    except (KeyError, AttributeError):
        return 0.0

def re_share(net, buses=None) -> float:
    """EE-Anteil [%] an der Stromerzeugung (optional auf Knoten gefiltert)."""
    g = net.generators if buses is None else net.generators[net.generators.bus.isin(buses)]
    p = net.generators_t.p[g.index].sum()
    ee = p[g.carrier.isin(["wind", "solar", "hydro"])].sum()
    tot = p.sum()
    return 100. * ee / tot if tot > 0 else 0.

def total_cost(net) -> float:
    """Gesamte annualisierte Systemkosten [€/a].

    PyPSA trennt die Zielfunktion in einen variablen Teil (`net.objective`)
    und einen konstanten Teil (`net.objective_constant` = Fixkosten der
    Bestandskapazität). Nur die Summe ergibt die realen Gesamtkosten – der
    variable Teil allein kann sogar negativ sein (z. B. bei billigem Import
    aus gekoppelten Nachbarländern)."""
    return float(net.objective + getattr(net, "objective_constant", 0.0))

# =============================================================
#  6c) REFERENZ – EIN-KNOTEN-MODELL FÜR DEN VERGLEICH
# =============================================================
#  Referenz = stündliche Dispatch-Zeitreihen (MW) je Technologie eines
#  Ein-Knoten-Deutschland-Modells (Kupferplatte) für zwei Wetterjahre
#  (2007, 2009) bei Verbrauchsjahr 2026 – plus die Last.
#
#  Quellen (in dieser Reihenfolge gesucht):
#    1) Referenzdaten/referenz_<jahr>.csv   (schlank, bevorzugt)
#    2) Produktionsdaten für PyPSA.xlsx     (Original, Fallback)
#    3) per Datei-Upload uebergeben         (fuer Streamlit Cloud)
REFERENCE_DIR    = os.path.join(SCRIPT_DIR, "data", "Referenzdaten")
REFERENCE_XLSX   = os.path.join(SCRIPT_DIR, "data", "Produktionsdaten für PyPSA.xlsx")
REFERENCE_SHEETS = ["2007", "2009"]        # verfügbare Wetterjahre


def reference_csv_path(sheet: str) -> str:
    """Pfad zur CSV eines Wetterjahres (z. B. Referenzdaten/referenz_2007.csv)."""
    return os.path.join(REFERENCE_DIR, f"referenz_{sheet}.csv")

# Excel-Spalte → Modell-Träger (mehrere Excel-Spalten dürfen zusammenfallen)
EXCEL_CARRIER_MAP = {
    "de-wind-on":  "wind",    "de-wind-off": "wind",
    "de-sun":      "solar",
    "de-water":    "hydro",   "de-pwater":   "hydro",
    "de-nat gas":  "gas",
    "de-lignite":  "lignite",
    "de-coal":     "hardcoal",
    # Träger ohne Entsprechung im 5-Zonen-Modell – bleiben als eigene Kategorie:
    "de-biomass":  "biomass", "de-waste":    "waste",
    "de-fuel oil": "oil",     "de-other":    "other",
}
# CO₂-Faktoren [t/MWh] für eine vergleichbare Referenz-Emission.
# wind/solar/hydro/biomass/waste = 0 (biogen), fossile analog zum Modell.
EXCEL_CO2 = {"gas": 0.370, "lignite": 1.0, "hardcoal": 0.8, "oil": 0.65}
# EE-Definition konsistent zu re_share(): nur wind, solar, hydro.
_RE_CARRIERS = ("wind", "solar", "hydro")


def reference_available(sheet: str | None = None) -> bool:
    """True, wenn Referenzdaten lokal vorliegen (CSV oder Excel).
    sheet=None → prüft, ob irgendein Wetterjahr verfügbar ist."""
    sheets = REFERENCE_SHEETS if sheet is None else [sheet]
    return (any(os.path.exists(reference_csv_path(s)) for s in sheets)
            or os.path.exists(REFERENCE_XLSX))


def _read_reference_raw(sheet: str, source=None) -> "pd.DataFrame":
    """Liest die Roh-Zeitreihe eines Wetterjahres als DataFrame.

    source=None          → lokale CSV, sonst Excel-Fallback.
    source=Pfad/Datei    → hochgeladene bzw. angegebene CSV/XLSX
                           (z. B. st.file_uploader in der Cloud)."""
    if source is not None:
        name = source if isinstance(source, str) else getattr(source, "name", "")
        if str(name).lower().endswith(".xlsx"):
            return pd.read_excel(source, sheet_name=sheet)
        return pd.read_csv(source)
    csv_p = reference_csv_path(sheet)
    if os.path.exists(csv_p):
        return pd.read_csv(csv_p)
    if os.path.exists(REFERENCE_XLSX):
        return pd.read_excel(REFERENCE_XLSX, sheet_name=sheet)
    raise FileNotFoundError(
        f"Keine Referenzdaten für Wetterjahr {sheet} gefunden "
        f"(weder {csv_p} noch {REFERENCE_XLSX}).")


def load_reference(sheet: str = "2007", source=None,
                   time_res: int | None = None,
                   index=None) -> dict:
    """Lädt ein Wetterjahr der Ein-Knoten-Referenz und bereitet es zum
    Vergleich mit dem 5-Zonen-Modell auf.

    sheet   : Wetterjahr ("2007"/"2009").
    source  : None → lokale CSV/Excel; sonst Pfad oder hochgeladene Datei.

    Rückgabe (dict):
      sheet        : Wetterjahr
      gen_hourly   : DataFrame – Erzeugung [MW] je Modell-Träger, auf die
                     Modell-Auflösung/-Snapshots ausgerichtet (für Overlay)
      load         : Series    – Stromlast [MW], gleiche Ausrichtung
      energy_twh   : Series    – Jahreserzeugung [TWh] je Modell-Träger
      kpi          : dict      – erzeugung_twh, last_twh, ee_pct, co2_mt,
                                 peak_last_gw, mittel_last_gw
    """
    tr = TIME_RES if time_res is None else time_res
    idx = snapshots if index is None else index

    raw = _read_reference_raw(sheet, source)
    raw["dim_1"] = pd.to_datetime(raw["dim_1"])
    # Nur das Verbrauchsjahr 2026 (die 2 Vorlaufstunden aus Dez. 2025 weg)
    df = raw[raw["dim_1"].dt.year == 2026].sort_values("dim_1").reset_index(drop=True)
    gen_cols = [c for c in df.columns if c not in ("dim_1", "load")]

    # Excel-Träger → Modell-Träger aggregieren (MW, stündlich)
    hourly = pd.DataFrame(index=range(len(df)))
    for col in gen_cols:
        tgt = EXCEL_CARRIER_MAP.get(col, col.replace("de-", ""))
        hourly[tgt] = hourly.get(tgt, 0.0) + df[col].to_numpy(dtype=float)
    load_h = df["load"].to_numpy(dtype=float)

    # Jahresenergie [TWh]  (stündlich → MWh → TWh)
    energy_twh = (hourly.sum() / 1e6)
    last_twh   = float(load_h.sum() / 1e6)

    # Vergleichbare CO₂-Emission [Mt/a]
    co2_t = sum(hourly[c].sum() * EXCEL_CO2[c]
                for c in EXCEL_CO2 if c in hourly)
    co2_mt = co2_t / 1e6

    # EE-Anteil [%]
    ee_twh = energy_twh[[c for c in _RE_CARRIERS if c in energy_twh]].sum()
    ee_pct = 100. * ee_twh / energy_twh.sum() if energy_twh.sum() > 0 else 0.

    # Auf Modell-Auflösung bringen: je tr Stunden mitteln, dann auf Länge
    # der Modell-Snapshots kürzen/auffüllen und mit deren Index versehen.
    n_steps = len(idx)
    if tr > 1:
        agg = hourly.groupby(np.arange(len(hourly)) // tr).mean()
        load_agg = pd.Series(load_h).groupby(np.arange(len(load_h)) // tr).mean()
    else:
        agg = hourly.copy()
        load_agg = pd.Series(load_h)
    agg = agg.iloc[:n_steps].reset_index(drop=True)
    load_agg = load_agg.iloc[:n_steps].reset_index(drop=True)
    # Positionsweise auf Modell-Snapshots ausrichten (Stunde-des-Jahres)
    agg.index = idx[:len(agg)]
    load_agg.index = idx[:len(load_agg)]

    return dict(
        sheet=sheet,
        gen_hourly=agg,
        load=load_agg,
        energy_twh=energy_twh,
        kpi=dict(
            erzeugung_twh=float(energy_twh.sum()),
            last_twh=last_twh,
            ee_pct=float(ee_pct),
            co2_mt=float(co2_mt),
            peak_last_gw=float(load_h.max() / 1000.),
            mittel_last_gw=float(load_h.mean() / 1000.),
        ),
    )


def de_generators(net) -> "pd.DataFrame":
    """Nur die deutschen Erzeuger (an den DE-AC-Knoten) – blendet bei
    gekoppelten Nachbarländern deren Anlagen aus."""
    return net.generators[net.generators.bus.isin(DE_AC_BUSES)]


def model_energy_by_carrier(net) -> pd.Series:
    """Jahreserzeugung [TWh] je Träger – nur Deutschland."""
    g = de_generators(net)
    p = net.generators_t.p[g.index]
    return (p.T.groupby(g.carrier).sum().T.sum() * TIME_RES / 1e6)


def model_gen_hourly(net) -> pd.DataFrame:
    """Erzeugung [MW] je Träger, stündlich – nur Deutschland (für Overlay)."""
    g = de_generators(net)
    return net.generators_t.p[g.index].T.groupby(g.carrier).sum().T


def has_neighbors(net) -> bool:
    """True, wenn Nachbarländer gekoppelt sind (Kuppel-Links vorhanden)."""
    return any(c.startswith("IC_") for c in net.links.index)


def neighbor_flows(net) -> pd.DataFrame:
    """Kuppelstellen-Flüsse [MW] je Nachbarland (Spalten = Länderkürzel).
    Vorzeichen: + = Import nach DE, − = Export aus DE. Leer ohne Kopplung."""
    ic = [c for c in net.links.index if c.startswith("IC_")]
    if not ic:
        return pd.DataFrame(index=net.snapshots)
    imp = -net.links_t.p0[ic]                 # p0 = Export DE→Land → Import = −p0
    imp.columns = [c[3:] for c in ic]         # "IC_FR" → "FR"
    return imp


def neighbor_net_import_twh(net) -> pd.Series:
    """Netto-Import je Nachbarland [TWh/a]  (+ = DE importiert, − = exportiert)."""
    f = neighbor_flows(net)
    if f.empty:
        return pd.Series(dtype=float)
    return f.sum() * TIME_RES / 1e6


# =============================================================
#  7) BASISOPTIMIERUNG + MONTE-CARLO (als Funktionen)
# =============================================================
def run_base(co2_budget=CO2_BUDGET, co2_price=CO2_PRICE,
             load_scale=1.0, heat_scale=1.0,
             discount_rate=None, gas_price=55.0,
             include_neighbors=False, foreign_era5=False, verbose=True,
             progress=None, include_europe=False, include_kreis3=False):
    """Baut, löst und liefert (Netz, ERA5-Flag).

    discount_rate     = WACC (z. B. 0.07); None → globaler Standard.
    gas_price         = Gas-Brennstoffkosten [€/MWh_th].
    include_neighbors = Nachbarländer koppeln (je 1 Knoten).
    include_europe    = zusätzlich 2. Länderring (nur mit include_neighbors).
    include_kreis3    = zusätzlich 3. Länderring (nur mit include_europe).
    foreign_era5      = Auslandswetter aus ERA5 (statt synthetisch)."""
    include_europe = include_europe and include_neighbors
    include_kreis3 = include_kreis3 and include_europe
    global DISCOUNT_RATE
    _prev_dr = DISCOUNT_RATE
    if discount_rate is not None:
        DISCOUNT_RATE = float(discount_rate)
    try:
        if progress: progress(0.05, "🌦 Wetterprofile laden …")
        prof, era5_ok = make_profiles(foreign_era5=foreign_era5,
                                      include_europe=include_europe,
                                      include_kreis3=include_kreis3)
        if progress: progress(0.30, "🔌 Lastprofile berechnen …")
        loads = make_loads(load_scale, heat_scale)
        if progress: progress(0.40, "🏗️ Netz aufbauen …")
        net = build_network(prof, loads, co2_budget, co2_price, gas_price,
                            include_neighbors=include_neighbors,
                            include_europe=include_europe,
                            include_kreis3=include_kreis3)
        if progress: progress(0.55, "⚙️ Solver läuft (kann etwas dauern) …")
        try:
            gur = solve_network(net, verbose)
        except Exception as e:
            print(f"⚠ Solver: {e} → 6h-Fallback")
            if progress: progress(0.65, "⚙️ Solver-Fallback (6h-Auflösung) …")
            net.set_snapshots(net.snapshots[::2])
            gur = solve_network(net, verbose)
        if progress: progress(1.0, "[OK] fertig")
    finally:
        DISCOUNT_RATE = _prev_dr   # globalen WACC wiederherstellen
    if verbose:
        print("[OK] Gurobi" if gur else "[OK] HiGHS",
              f"| {total_cost(net)/1e9:.2f} Mrd €/a "
              f"| CO₂(DE) {total_co2(net, DE_AC_BUSES)/1e6:.1f} Mt")
    return net, era5_ok

def run_monte_carlo(n_mc=N_MC, co2_budget=CO2_BUDGET, co2_price=CO2_PRICE,
                    include_neighbors=False, progress=None):
    """MC über synthetische Wetterjahre → DataFrame."""
    rows = []
    for i in range(n_mc):
        if progress:
            progress(i / max(n_mc, 1), f"🎲 Wetterjahr {i+1}/{n_mc} …")
        try:
            prof, _ = make_profiles(mc_seed=i)
            loads = make_loads(mc_seed=i)
            nm = build_network(prof, loads, co2_budget, co2_price,
                               include_neighbors=include_neighbors)
            solve_network(nm, verbose=False)
            rows.append(dict(Jahr=i + 1, Kosten_MrdEa=total_cost(nm) / 1e9,
                             CO2_Mt=total_co2(nm, DE_AC_BUSES) / 1e6,
                             RE_Anteil_pct=re_share(nm, DE_AC_BUSES),
                             Status="[OK] OK"))
            print(f"  MC {i+1}/{n_mc}: {rows[-1]['Kosten_MrdEa']:.2f} Mrd €/a "
                  f"| CO₂ {rows[-1]['CO2_Mt']:.1f} Mt | EE {rows[-1]['RE_Anteil_pct']:.1f}%")
        except Exception as e:
            rows.append(dict(Jahr=i + 1, Kosten_MrdEa=np.nan, CO2_Mt=np.nan,
                             RE_Anteil_pct=np.nan, Status=f"✗ {e}"))
    if progress:
        progress(1.0, "[OK] fertig")
    return pd.DataFrame(rows)

def run_co2_sweep(prices=None, co2_budget=CO2_BUDGET, include_neighbors=False,
                  verbose=False, progress=None, **run_kwargs):
    """CO₂-Preis-Sensitivität: pro Preis ein eigener Optimierungslauf.

    Für jeden CO₂-Preis wird run_base() mit exakt denselben Bauwegen wie im
    Standardlauf aufgerufen (ergebnisneutral gegenüber run_base). Gesammelt
    werden Systemkosten, CO₂-Ausstoß, EE-Anteil und die optimierten
    Kapazitäten je Erzeugungsträger (in GW).

    prices            = Liste von CO₂-Preisen [€/tCO₂]; None → Default-Raster.
    **run_kwargs      = weitergereicht an run_base (z. B. load_scale, gas_price,
                        discount_rate, foreign_era5, include_europe).
    Rückgabe          = pd.DataFrame, eine Zeile je Preis. Fehler pro Preis
                        werden abgefangen (NaN + Status), der Lauf läuft weiter.
    """
    if prices is None:
        prices = [0, 50, 100, 150, 200, 300]
    rows = []
    n_p = len(prices)
    for i, p in enumerate(prices):
        if progress:
            progress(i / max(n_p, 1), f"💨 CO₂-Preis {p:.0f} €/t ({i+1}/{n_p}) …")
        try:
            net, _ = run_base(co2_price=float(p), co2_budget=co2_budget,
                              include_neighbors=include_neighbors,
                              verbose=False, **run_kwargs)
            row = dict(CO2_Preis_EUR_t=float(p),
                       Kosten_MrdEa=total_cost(net) / 1e9,
                       CO2_Mt=total_co2(net, DE_AC_BUSES) / 1e6,
                       RE_Anteil_pct=re_share(net, DE_AC_BUSES),
                       Status="[OK] OK")
            # Kapazitäten je Carrier in GW (Summe der optimierten Nennleistung)
            for g in net.generators.index:
                car = net.generators.carrier[g]
                col = f"Kap_{car}_GW"
                row[col] = row.get(col, 0.0) + _pnom(net.generators, g) / 1000.
            rows.append(row)
            if verbose:
                print(f"  CO₂-Preis {p:.0f} €/t: {row['Kosten_MrdEa']:.2f} Mrd €/a "
                      f"| CO₂ {row['CO2_Mt']:.1f} Mt | EE {row['RE_Anteil_pct']:.1f}%")
        except Exception as e:
            rows.append(dict(CO2_Preis_EUR_t=float(p), Kosten_MrdEa=np.nan,
                             CO2_Mt=np.nan, RE_Anteil_pct=np.nan,
                             Status=f"✗ {e}"))
    if progress:
        progress(1.0, "[OK] fertig")
    return pd.DataFrame(rows)

# =============================================================
#  8) PLOTS  (Dispatch, Kapazitäten, Preise, Speicher)
# =============================================================
CARRIER_COLORS = {"wind": "#4A90D9", "solar": "#F5A623", "hydro": "#3FBFB2",
                  "gas": "#E8734C", "lignite": "#8B5A3C", "hardcoal": "#666666"}

def plot_dispatch(net, path):
    """Plot A: Erzeugungsmix + Last (1 Winter- und 1 Sommerwoche)."""
    fig, axes = plt.subplots(2, 1, figsize=(16, 9))
    fig.patch.set_facecolor(BG)
    gp_ = net.generators_t.p.T.groupby(net.generators.carrier).sum().T / 1000.
    last = net.loads_t.p_set[[f"Last_{r}" for r in REGIONS]].sum(axis=1) / 1000.
    weeks = [("Winterwoche (Jan)", slice(0, 7 * 24 // TIME_RES)),
             ("Sommerwoche (Jul)", slice(181 * 24 // TIME_RES, 188 * 24 // TIME_RES))]
    for ax, (title, sl) in zip(axes, weeks):
        seg = gp_.iloc[sl]
        ax.stackplot(seg.index, [seg[c] for c in seg.columns],
                     labels=seg.columns,
                     colors=[CARRIER_COLORS.get(c, "#999") for c in seg.columns])
        ax.plot(last.iloc[sl].index, last.iloc[sl], "w--", lw=1.5, label="Last")
        _style_ax(ax, title, ylabel="GW")
        ax.legend(loc="upper right", fontsize=8, facecolor="#1a2a3a", labelcolor="w")
    fig.tight_layout()
    plt.savefig(path, dpi=150, facecolor=BG, bbox_inches="tight"); plt.close()

def plot_capacities(net, path):
    """Plot B: optimierte Kapazitäten + Erzeugung nach Träger."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor(BG)
    caps = pd.Series({g: _pnom(net.generators, g) / 1000.
                      for g in net.generators.index})
    cols = [CARRIER_COLORS.get(net.generators.carrier[g], "#999") for g in caps.index]
    a1.barh(caps.index, caps.values, color=cols)
    _style_ax(a1, "Optimierte Kapazitäten", xlabel="GW")
    en = (net.generators_t.p.T.groupby(net.generators.carrier).sum().T.sum()
          * TIME_RES / 1e6)
    a2.pie(en, labels=en.index, autopct="%1.0f%%",
           colors=[CARRIER_COLORS.get(c, "#999") for c in en.index],
           textprops=dict(color="white"))
    _style_ax(a2, f"Jahreserzeugung ({en.sum():.0f} TWh)")
    fig.tight_layout()
    plt.savefig(path, dpi=150, facecolor=BG, bbox_inches="tight"); plt.close()

def plot_storage_prices(net, path):
    """Plot C: Speicherfüllstände + regionale Strompreise."""
    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(16, 11))
    fig.patch.set_facecolor(BG)
    if not net.storage_units_t.state_of_charge.empty:
        (net.storage_units_t.state_of_charge / 1000.).plot(ax=a1, lw=0.8)
    _style_ax(a1, "Speicherfüllstände (Batterien / Pumpspeicher)", ylabel="GWh")
    a1.legend(fontsize=7, facecolor="#1a2a3a", labelcolor="w")
    h2 = net.stores_t.e.get("H2_Tank")
    if h2 is not None:
        a2.fill_between(h2.index, h2 / 1000., color="#B57EDC", alpha=0.7)
    _style_ax(a2, "H₂-Tank Füllstand", ylabel="GWh")
    net.buses_t.marginal_price[list(REGIONS)].plot(ax=a3, lw=0.6)
    _style_ax(a3, "Regionale Strompreise", ylabel="€/MWh")
    a3.legend(fontsize=8, facecolor="#1a2a3a", labelcolor="w")
    fig.tight_layout()
    plt.savefig(path, dpi=150, facecolor=BG, bbox_inches="tight"); plt.close()

def plot_co2_sweep(df, path):
    """Plot D: CO₂-Preis-Sensitivität.

    Oben: Systemkosten, CO₂-Ausstoß und EE-Anteil über den CO₂-Preis.
    Unten: optimierte Kapazitäten je Erzeugungsträger über den CO₂-Preis.
    Erwartet den DataFrame aus run_co2_sweep()."""
    d = df.dropna(subset=["Kosten_MrdEa"]).sort_values("CO2_Preis_EUR_t")
    x = d["CO2_Preis_EUR_t"]
    fig, (a1, a3) = plt.subplots(2, 1, figsize=(14, 10))
    fig.patch.set_facecolor(BG)

    # --- oben: Kosten (links) + CO₂ und EE-Anteil (rechts) ---
    a1.plot(x, d["Kosten_MrdEa"], "o-", color="#4A90D9", lw=2, label="Systemkosten")
    _style_ax(a1, "Kosten, CO₂ und EE-Anteil über CO₂-Preis",
              xlabel="CO₂-Preis [€/tCO₂]", ylabel="Mrd €/a")
    a2 = a1.twinx()
    a2.plot(x, d["CO2_Mt"], "s--", color="#E8734C", lw=2, label="CO₂-Ausstoß")
    a2.plot(x, d["RE_Anteil_pct"], "^:", color="#3FBFB2", lw=2, label="EE-Anteil")
    a2.set_ylabel("CO₂ [Mt/a]  ·  EE-Anteil [%]", color="white")
    a2.tick_params(colors="white")
    for sp in a2.spines.values():
        sp.set_edgecolor("#444")
    h1, l1 = a1.get_legend_handles_labels()
    h2, l2 = a2.get_legend_handles_labels()
    a1.legend(h1 + h2, l1 + l2, loc="best", fontsize=8,
              facecolor="#1a2a3a", labelcolor="w")

    # --- unten: Kapazitäten je Carrier ---
    kap_cols = [c for c in d.columns if c.startswith("Kap_") and c.endswith("_GW")]
    for c in kap_cols:
        car = c[len("Kap_"):-len("_GW")]
        a3.plot(x, d[c], "o-", lw=2, label=car,
                color=CARRIER_COLORS.get(car, "#999"))
    _style_ax(a3, "Optimierte Kapazitäten je Träger über CO₂-Preis",
              xlabel="CO₂-Preis [€/tCO₂]", ylabel="GW")
    a3.legend(fontsize=8, facecolor="#1a2a3a", labelcolor="w", ncol=2)
    fig.tight_layout()
    plt.savefig(path, dpi=150, facecolor=BG, bbox_inches="tight"); plt.close()

# =============================================================
#  9) DEUTSCHLAND-KARTE (stilisiert, wie Lummerland-Karte)
# =============================================================
GERMANY_OUTLINE = [(7.0, 53.7), (8.5, 55.0), (9.5, 54.8), (11.0, 54.0),
                   (14.0, 54.6), (14.8, 51.1), (12.1, 50.3), (13.8, 48.7),
                   (12.9, 47.5), (10.0, 47.3), (7.6, 47.6), (7.5, 49.0),
                   (6.1, 49.5), (6.0, 51.0)]

def draw_turbine(ax, x, y, size=0.35, color="#4A90D9", z=15):
    ax.plot([x, x], [y - size*0.8, y + size*0.2], color=color, lw=2.0, zorder=z)
    ax.add_patch(Ellipse((x, y + size*0.2), size*0.25, size*0.12, facecolor=color, zorder=z+1))
    for ang in [90, 210, 330]:
        r = np.radians(ang)
        ax.add_patch(Ellipse((x + size*0.35*np.cos(r), y + size*0.2 + size*0.35*np.sin(r)),
                             size*0.12, size*0.28, angle=ang-90,
                             facecolor=color, alpha=0.85, zorder=z+1))

def draw_solar(ax, x, y, size=0.35, color="#F5A623", n=3, z=15):
    pw, ph, gap = size*0.45, size*0.28, size*0.05
    x0 = x - (n*pw + (n-1)*gap)/2
    for i in range(n):
        ax.add_patch(FancyBboxPatch((x0 + i*(pw+gap), y - ph/2), pw, ph,
                                    boxstyle="round,pad=0.02", facecolor=color,
                                    edgecolor="white", lw=0.8, alpha=0.85, zorder=z))

def _label_box(ax, x, y, txt, color, fs=8, z=20):
    ax.text(x, y, txt, fontsize=fs, color=color, ha="center", va="center", zorder=z,
            bbox=dict(facecolor=BGMAP, edgecolor=color, lw=0.8,
                      boxstyle="round,pad=0.3", alpha=0.93))

def _lc_color(pct):
    return "#6bcb77" if pct < 50 else ("#ffd93d" if pct < 80 else "#ff6b6b")

def plot_map(net, path, era5_ok):
    """Deutschlandkarte: Knoten, Leitungen mit Auslastung, KPIs."""
    fig, ax = plt.subplots(figsize=(14, 16))
    fig.patch.set_facecolor(BGMAP); ax.set_facecolor(BGMAP)
    ax.set_xlim(4.5, 16.5); ax.set_ylim(46.5, 56.0)
    ax.set_aspect(1.5); ax.axis("off")
    ax.add_patch(plt.Polygon(GERMANY_OUTLINE, facecolor=LAND,
                             edgecolor=SHORE, lw=2, alpha=0.85, zorder=1))
    pos = {b: (net.buses.at[b, "x"], net.buses.at[b, "y"])
           for b in list(REGIONS) + ["Offshore"]}
    # Leitungen mit mittlerer Auslastung
    for ln, row in net.lines.iterrows():
        x0, y0 = pos[row.bus0]; x1, y1 = pos[row.bus1]
        cap = float(row.get("s_nom_opt", row.s_nom)) or 1.
        flow = abs(net.lines_t.p0[ln]).mean()
        pct = 100. * flow / cap
        lw = 1.5 + min(cap / 4000., 4.)
        ls = "--" if "Off" in ln else "-"
        ax.plot([x0, x1], [y0, y1], color=_lc_color(pct), lw=lw, ls=ls, alpha=0.9,
                zorder=3, path_effects=[pe.Stroke(linewidth=lw+2, foreground="black",
                                                  alpha=0.4), pe.Normal()])
        _label_box(ax, (x0+x1)/2, (y0+y1)/2,
                   f"{cap/1000:.1f} GW | {pct:.0f}%", _lc_color(pct), fs=7)
    # Knoten
    bcol = {"Nord": "#00BCD4", "Ost": "#E040FB", "West": "#FF9800",
            "Sued": "#8BC34A", "Offshore": "#4A90D9"}
    for b, (bx, by) in pos.items():
        cap = sum(_pnom(net.generators, g) for g in net.generators.index
                  if net.generators.bus[g] == b) / 1000.
        load = (net.loads_t.p_set.get(f"Last_{b}", pd.Series(0)).mean()) / 1000.
        size = 0.25 + min(cap / 120., 0.5)
        ax.add_patch(plt.Circle((bx, by), size, facecolor=bcol[b],
                                edgecolor="white", lw=1.5, alpha=0.9, zorder=10))
        ax.text(bx, by + size + 0.25, b, ha="center", fontsize=12, fontweight="bold",
                color=bcol[b], zorder=12,
                path_effects=[pe.withStroke(linewidth=3, foreground="black")])
        _label_box(ax, bx, by - size - 0.45,
                   f"{cap:.0f} GW\n{load:.0f} GW Last", bcol[b], fs=8)
    # Icons
    draw_turbine(ax, 6.6, 55.2, 0.45, "#00BCD4")
    draw_turbine(ax, 7.5, 55.3, 0.45, "#00BCD4")
    draw_turbine(ax, 9.0, 54.2, 0.35)
    draw_turbine(ax, 13.9, 53.0, 0.35, "#E040FB")
    draw_solar(ax, 11.3, 47.9, 0.4)
    draw_solar(ax, 12.6, 51.5, 0.35, "#CE93D8")
    # KPI-Box
    h2t = net.stores.e_nom_opt.get("H2_Tank", 0.) / 1000.
    h2e = _pnom(net.links, "Elektrolyseur") / 1000.
    h2f = _pnom(net.links, "Brennstoffzelle") / 1000.
    wp = sum(_pnom(net.links, f"WP_{r}") for r in REGIONS) / 1000.
    kpi = (f"Gesamtkosten: {net.objective/1e9:.2f} Mrd €/a\n"
           f"CO₂: {total_co2(net)/1e6:.1f} Mt/a\nEE-Anteil: {re_share(net):.1f}%\n"
           f"H₂-Tank: {h2t:.0f} GWh | Elektrolyse: {h2e:.1f} GW | BZ: {h2f:.1f} GW\n"
           f"Wärmepumpen gesamt: {wp:.1f} GW")
    ax.text(4.8, 48.0, kpi, fontsize=9, color="white", va="top",
            bbox=dict(facecolor="#1a2a3a", edgecolor="#4A90D9", lw=1,
                      boxstyle="round,pad=0.5", alpha=0.92), zorder=20)
    ax.legend(handles=[Line2D([0], [0], color="#6bcb77", lw=2, label="<50%"),
                       Line2D([0], [0], color="#ffd93d", lw=2, label="50–80%"),
                       Line2D([0], [0], color="#ff6b6b", lw=2, label=">80%"),
                       Line2D([0], [0], color="white", lw=2, ls="--", label="Offshore")],
              loc="lower right", facecolor="#1a2a3a", labelcolor="white",
              fontsize=9, framealpha=0.9)
    ax.set_title(f"DEUTSCHLAND v1.0 – 5-Zonen-Modell  |  "
                 f"{'[OK] ERA5-Daten' if era5_ok else '⚠ Synthetische Daten'}",
                 fontsize=14, fontweight="bold", color="white", pad=15)
    fig.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BGMAP); plt.close()

# =============================================================
#  10) PDF-BERICHT
# =============================================================
def make_pdf(net, mc_df, img_paths: dict, pdf_path):
    with PdfPages(pdf_path) as pdf:
        fc = plt.figure(figsize=(16, 10)); fc.patch.set_facecolor(BG)
        ac = fc.add_axes([0, 0, 1, 1]); ac.set_facecolor(BG); ac.axis("off")
        ac.text(.5, .72, "🇩🇪 DEUTSCHLAND", ha="center", fontsize=42,
                fontweight="bold", color="#4A90D9", transform=ac.transAxes)
        ac.text(.5, .60, "Energy Model v1.0 – 5-Zonen-Modell mit Sektorkopplung",
                ha="center", fontsize=24, color="white", transform=ac.transAxes)
        ac.text(.5, .50, "Strom, Wärme & H₂  |  CO₂-Budget  |  "
                         "Monte-Carlo-Robustheitsprüfung",
                ha="center", fontsize=14, color="#aaaaaa", transform=ac.transAxes)
        ac.text(.5, .38, f"Gesamtkosten: {net.objective/1e9:.2f} Mrd €/a   |   "
                         f"CO₂: {total_co2(net)/1e6:.1f} Mt/a   |   "
                         f"Zeitschritte: {len(net.snapshots)} ({TIME_RES}h)",
                ha="center", fontsize=12, color="#4A90D9", transform=ac.transAxes)
        ac.text(.5, .28, f"Erstellt: {datetime.datetime.now():%d.%m.%Y %H:%M}",
                ha="center", fontsize=11, color="#888", transform=ac.transAxes)
        pdf.savefig(fc, facecolor=BG); plt.close(fc)
        for title, p in img_paths.items():
            fp = plt.figure(figsize=(16, 12)); fp.patch.set_facecolor(BG)
            ap = fp.add_axes([0, 0, 1, 1]); ap.axis("off")
            try:
                ap.imshow(plt.imread(p), aspect="auto")
            except (FileNotFoundError, OSError):
                ap.text(.5, .5, f"{title} nicht verfügbar", ha="center",
                        va="center", color="white", transform=ap.transAxes)
            pdf.savefig(fp, facecolor=BG); plt.close(fp)
        # MC-Tabelle
        fm = plt.figure(figsize=(14, 8)); fm.patch.set_facecolor(BG)
        am = fm.add_subplot(111); am.axis("off"); am.set_facecolor(BG)
        rows = [[str(int(r.Jahr)), f"{r.Kosten_MrdEa:.2f}", f"{r.CO2_Mt:.1f}",
                 f"{r.RE_Anteil_pct:.1f}", r.Status] for _, r in mc_df.iterrows()]
        tbl = am.table(cellText=rows,
                       colLabels=["Jahr", "Kosten [Mrd €/a]", "CO₂ [Mt/a]",
                                  "EE-Anteil [%]", "Status"],
                       cellLoc="center", loc="center", bbox=[.02, .1, .96, .75])
        tbl.auto_set_font_size(False); tbl.set_fontsize(11)
        for (ri, _), cell in tbl.get_celld().items():
            cell.set_facecolor("#1a2a3a" if ri > 0 else "#0a3060")
            cell.set_text_props(color="white"); cell.set_edgecolor("#333")
        am.text(.5, .92, "Monte-Carlo Robustheitsprüfung", ha="center",
                fontsize=14, fontweight="bold", color="white", transform=am.transAxes)
        valid = mc_df.dropna()
        if not valid.empty:
            am.text(.5, .06, f"Ø Kosten: {valid.Kosten_MrdEa.mean():.2f} Mrd €/a  |  "
                             f"Ø CO₂: {valid.CO2_Mt.mean():.1f} Mt/a  |  "
                             f"Ø EE: {valid.RE_Anteil_pct.mean():.1f}%",
                    ha="center", fontsize=11, color="#4A90D9", transform=am.transAxes)
        d = pdf.infodict()
        d["Title"] = "Deutschland Energy Model v1.0"
        d["Author"] = "PyPSA Optimierung"
        d["CreationDate"] = datetime.datetime.now()
        pdf.savefig(fm, facecolor=BG); plt.close(fm)

# =============================================================
#  11) HAUPTPROGRAMM  (nur bei direktem Aufruf, nicht bei Import!)
# =============================================================
if __name__ == "__main__":
    print("=" * 55)
    print(" DEUTSCHLAND v1.0 – 5-Zonen-Modell mit Sektorkopplung")
    print(f" Snapshots : {HOURS} ({TIME_RES}h-Auflösung, volles Jahr)")
    print(f" CO₂-Budget: {CO2_BUDGET/1e6:.0f} Mt/a | CO₂-Preis: {CO2_PRICE:.0f} €/t")
    print(f" Ausgabe   : {OUTPUT_DIR}")
    print("=" * 55)

    print("\n Annualisierte Kapitalkosten [€/MW/a]:")
    for k in ["Wind_on", "Wind_off", "Solar", "Gas_CCGT", "Battery",
              "H2_elec", "H2_FC", "HeatPump"]:
        print(f"   {k:<10}: {capex_annual(k):>10,.0f}")

    n, era5_ok = run_base()
    print(f"\n[OK] Optimierung fertig → {n.objective/1e9:.2f} Mrd €/a "
          f"| CO₂ {total_co2(n)/1e6:.1f} Mt | EE {re_share(n):.1f}%\n")
    for g in n.generators.index:
        print(f"  {g:<22} {_pnom(n.generators, g)/1000:>7.1f} GW")

    print("\n" + "=" * 55)
    print(f" Monte-Carlo: {N_MC} Wetterjahre")
    print("=" * 55)
    mc_df = run_monte_carlo()

    # Opt-in: CO₂-Preis-Sensitivität nur bei CO2_SWEEP=1 (Standardlauf bleibt unverändert)
    if os.environ.get("CO2_SWEEP") == "1":
        print("\n" + "=" * 55)
        print(" CO₂-Preis-Sensitivität (opt-in via CO2_SWEEP=1)")
        print("=" * 55)
        sweep_df = run_co2_sweep(verbose=True)
        _ps = os.path.join(OUTPUT_DIR, "deutschland_v1_co2_sweep.png")
        plot_co2_sweep(sweep_df, _ps)
        print(f"  [OK] {_ps}")

    print("\n Erstelle Plots …")
    _pa = os.path.join(OUTPUT_DIR, "deutschland_v1_dispatch.png")
    _pb = os.path.join(OUTPUT_DIR, "deutschland_v1_kapazitaeten.png")
    _pc = os.path.join(OUTPUT_DIR, "deutschland_v1_speicher_preise.png")
    _pm = os.path.join(OUTPUT_DIR, "deutschland_v1_karte.png")
    plot_dispatch(n, _pa);        print(f"  [OK] {_pa}")
    plot_capacities(n, _pb);      print(f"  [OK] {_pb}")
    plot_storage_prices(n, _pc);  print(f"  [OK] {_pc}")
    plot_map(n, _pm, era5_ok);    print(f"  [OK] {_pm}")

    pdf_path = os.path.join(OUTPUT_DIR, "Deutschland_v1_Bericht.pdf")
    make_pdf(n, mc_df, {"Karte": _pm, "Dispatch": _pa,
                        "Kapazitäten": _pb, "Speicher & Preise": _pc}, pdf_path)
    print(f"\n{'='*55}\n ✅ FERTIG!\n   PDF   → {pdf_path}\n"
          f"   Plots → {OUTPUT_DIR}\n{'='*55}")
