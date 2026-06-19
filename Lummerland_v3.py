#!/usr/bin/env python3
# =============================================================
#  🏝️  LUMMERLAND ISLAND ENERGY MODEL v3.0  (final)
#  Reines Python-Skript – kein Jupyter / Colab erforderlich
#  Ausführen: python Lummerland_v3_final.py
#
#  VERBESSERUNGEN:
#  ✓ .env-Datei Support (API-Keys sicher & bequem)
#  ✓ Imports nach PEP 8 sortiert (stdlib / third-party getrennt)
#  ✓ warnings.filterwarnings erst NACH den Imports
#  ✓ _style_ax() Hilfsfunktion – kein Copy-Paste mehr
#  ✓ Type Hints + Docstrings für alle Funktionen
#  ✓ Spezifische except-Klauseln statt blankem "except:"
#  ✓ FIX 1: p_nom_max / e_nom_max Bounds gesetzt
#  ✓ FIX 2: assign_solution() nach optimize()
#  ✓ FIX 3: Monte-Carlo Solver – Gurobi bevorzugt, HiGHS 600s
#  ✓ FIX 4: Warnung bei negativem Objective
# =============================================================

# ── stdlib ───────────────────────────────────────────────────
import datetime
import os
import subprocess
import sys
import warnings

# ── .env laden (vor allem anderen!) ──────────────────────────
# Erstelle eine Datei ".env" im selben Ordner mit folgendem Inhalt:
#
#   CDS_KEY=dein-key-hier
#   GRB_WLSACCESSID=dein-access-id
#   GRB_WLSSECRET=dein-secret
#   GRB_LICENSEID=1234567
# Dann werden die Keys automatisch geladen – nie mehr im Code ändern!
def _load_dotenv() -> None:
    """Lädt .env-Datei aus dem Skriptverzeichnis (kein Paket nötig)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # Nur setzen wenn noch nicht als echte Env-Variable vorhanden
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
    print("✓ .env geladen")

_load_dotenv()

# ── third-party (werden ggf. auto-installiert) ───────────────
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # Kein Fenster – speichert direkt als PNG/PDF
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patheffects as pe
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyBboxPatch

# Erst NACH allen Imports unterdrücken
warnings.filterwarnings("ignore")

# =============================================================
#  🔑 API-KEYS
#  Priorität: .env-Datei > Umgebungsvariable > Fallback unten
#  Trage deine Keys entweder hier ein ODER (besser) in .env
# =============================================================
CDS_KEY         = os.environ.get("CDS_KEY",         "bda61c6b-219b-4c88-bdb7-3b61b545877c")
GRB_WLSACCESSID = os.environ.get("GRB_WLSACCESSID", "964574c6-e2bc-4a47-ba1a-ba2bbab3e89b")
GRB_WLSSECRET   = os.environ.get("GRB_WLSSECRET",   "7d4f3f5e-5788-4d15-bfc5-c1d36a1fda38")
GRB_LICENSEID   = int(os.environ.get("GRB_LICENSEID", "2835597"))

# =============================================================
#  0) ABHÄNGIGKEITEN AUTO-INSTALLIEREN
# =============================================================
def install_if_missing(packages: list[tuple[str, str]]) -> None:
    """Installiert fehlende Pakete automatisch via pip."""
    import importlib
    for pkg, import_name in packages:
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"  Installing {pkg} …")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

install_if_missing([
    ("pypsa",      "pypsa"),
    ("highspy",    "highspy"),
    ("pandas",     "pandas"),
    ("numpy",      "numpy"),
    ("matplotlib", "matplotlib"),
    ("scipy",      "scipy"),
    ("xarray",     "xarray"),
    ("netCDF4",    "netCDF4"),
    ("geopandas",  "geopandas"),
    ("shapely",    "shapely"),
])

import pypsa
print(f"✓ PyPSA {pypsa.__version__}")

# Gurobi optional
try:
    import gurobipy as gp
    GUROBI_AVAILABLE = True
    print(f"✓ Gurobi {gp.gurobi.version()}")
except Exception:
    GUROBI_AVAILABLE = False
    print("ℹ Gurobi nicht gefunden → HiGHS wird verwendet")

# Atlite optional
try:
    import atlite
    ATLITE_AVAILABLE = True
    print(f"✓ Atlite {atlite.__version__}")
except Exception:
    ATLITE_AVAILABLE = False
    print("ℹ Atlite nicht gefunden → synthetischer Fallback")

# =============================================================
#  1) AUSGABE-ORDNER & PFADE
# =============================================================
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Lummerland_Output")
ERA5_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "era5_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ERA5_DIR,   exist_ok=True)

_path_onshore  = os.path.join(ERA5_DIR, "lummerland_era5_onshore_2023.nc")
_path_offshore = os.path.join(ERA5_DIR, "lummerland_era5_offshore_2023.nc")

# CDS API Key in ~/.cdsapirc schreiben (nur wenn gesetzt)
if CDS_KEY not in ("DEIN_API_KEY", ""):
    with open(os.path.expanduser("~/.cdsapirc"), "w") as _f:
        _f.write("url: https://cds.climate.copernicus.eu/api\n")
        _f.write(f"key: {CDS_KEY}\n")
    print("✓ CDS API Key konfiguriert")

# =============================================================
#  2) GLOBALE PARAMETER
# =============================================================
HOURS         = 8760
DISCOUNT_RATE = 0.07
CO2_PRICE     = 80.0
CO2_BUDGET    = 20_000
BASE_LOAD     = 80.0
BASE_HEAT     = 40.0
N_MC          = 5

snapshots = pd.date_range("2025-01-01", periods=HOURS, freq="h")

print("=" * 55)
print(" LUMMERLAND v3.0 – 4-Zonen-Inselmodell")
print(f" PyPSA Version  : {pypsa.__version__}")
print(f" Snapshots      : {HOURS} (1h, volles Jahr)")
print(f" CO₂-Budget     : {CO2_BUDGET:,} tCO₂/a")
print(f" Ausgabe-Ordner : {OUTPUT_DIR}")
print("=" * 55)

# =============================================================
#  3) ANNUITÄTEN & KOSTEN
# =============================================================
def annuity(lifetime: int, r: float = DISCOUNT_RATE) -> float:
    """Berechnet den Annuitätenfaktor für eine Investition."""
    return r / (1 - (1 + r) ** (-lifetime)) if r > 0 else 1 / lifetime

CAPEX: dict[str, tuple[int, int]] = {
    "Wind_on":   (1_200_000, 25), "Wind_off":  (1_500_000, 25),
    "Solar":     (  600_000, 25), "Nuclear":   (6_000_000, 40),
    "Gas_CCGT":  (  800_000, 30), "Battery":   (  300_000, 15),
    "H2_elec":   (  700_000, 25), "H2_tank":   (   30_000, 30),
    "H2_FC":     (  900_000, 20), "HeatPump":  (  500_000, 20),
    "HeatStore": (   20_000, 30), "Line":      (  200_000, 40),
    "Line_off":  (  400_000, 40),
}

def capex_annual(key: str) -> float:
    """Annualisierte Kapitalkosten [€/MW/a] für eine Technologie."""
    c, lt = CAPEX[key]
    return c * annuity(lt)

OPEX: dict[str, float] = {
    "Wind_on": 0., "Wind_off": 0., "Solar": 0., "Nuclear": 5.,
    "Gas_CCGT": 55. + 0.200 * CO2_PRICE, "Battery": 0.5,
    "H2_elec": 1., "H2_FC": 2., "HeatPump": 1.,
}

print("\n Annualisierte Kapitalkosten [€/MW/Jahr]:")
for k in ["Wind_on", "Wind_off", "Solar", "Gas_CCGT", "Battery", "H2_elec", "H2_FC", "HeatPump"]:
    print(f"   {k:<14}: {capex_annual(k):>10,.0f} €/MW/a")

# =============================================================
#  4) WETTERDATEN (ERA5 oder synthetisch)
# =============================================================
def _synthetic_profiles(
    seed_s: int = 0, seed_w: int = 42, seed_wo: int = 99
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Erzeugt synthetische Solar-, Wind- und Offshore-Lastprofile."""
    doy = np.arange(HOURS) / 24.0
    hod = np.arange(HOURS) % 24
    np.random.seed(seed_s)
    seas_s  = 0.55 + 0.45 * np.cos(2 * np.pi * (doy - 172) / 365)
    daily_s = np.maximum(0, np.sin(np.pi * (hod - 6) / 12))
    daily_s[hod < 6]  = 0
    daily_s[hod > 18] = 0
    s_cf = np.clip(seas_s * daily_s * (1 - np.abs(np.random.normal(0, 0.07, HOURS))), 0, 1)
    np.random.seed(seed_w)
    seas_w = 0.38 + 0.22 * np.sin(2 * np.pi * doy / 365 + np.pi)
    w_cf   = np.clip(seas_w + np.random.weibull(2.2, HOURS) * 0.42 - 0.16, 0.03, 1.0)
    rng    = np.random.default_rng(seed_wo)
    seas_wo = 0.45 + 0.18 * np.sin(2 * np.pi * doy / 365 + np.pi)
    w_off   = np.clip(seas_wo + 0.08 * rng.standard_normal(HOURS), 0.05, 1.0)
    return s_cf, w_cf, w_off

ERA5_AVAILABLE = False
if ATLITE_AVAILABLE:
    try:
        print("\n[atlite] Lade ERA5-Daten …")
        cutout_on = atlite.Cutout(
            path=_path_onshore, module="era5",
            x=slice(13., 15.), y=slice(54.5, 55.5),
            time=slice("2023-01-01", "2023-12-31"),
        )
        cutout_on.prepare(["wind", "influx", "temperature"])
        cutout_off = atlite.Cutout(
            path=_path_offshore, module="era5",
            x=slice(13., 16.), y=slice(55.5, 57.),
            time=slice("2023-01-01", "2023-12-31"),
        )
        cutout_off.prepare(["wind"])
        solar_cf    = np.clip(cutout_on.pv(
            panel="CSi", orientation={"slope": 35., "azimuth": 180.},
            layout=cutout_on.uniform_layout(),
        ).values.flatten()[:HOURS], 0, 1)
        wind_cf     = np.clip(cutout_on.wind(
            turbine="Vestas_V112_3MW", layout=cutout_on.uniform_layout(),
        ).values.flatten()[:HOURS], 0, 1)
        offshore_cf = np.clip(cutout_off.wind(
            turbine="Vestas_V112_3MW", layout=cutout_off.uniform_layout(),
        ).values.flatten()[:HOURS], 0, 1)
        ERA5_AVAILABLE = True
        print("✓ ERA5-Daten geladen")
    except Exception as _e:
        print(f"[atlite] Fehler: {_e} → Fallback")

if not ERA5_AVAILABLE:
    print("[Fallback] Erstelle synthetische Profile …")
    solar_cf, wind_cf, offshore_cf = _synthetic_profiles()

doy_h = np.arange(HOURS) / 24.0
hod_h = np.arange(HOURS) % 24
load_total   = BASE_LOAD * (1 + 0.20 * np.cos(2*np.pi*(doy_h-355)/365)) * (1 + 0.15 * np.sin(np.pi*(hod_h-6)/12))
load_nord    = load_total * 0.40
load_zentrum = load_total * 0.25
load_sued    = load_total * 0.35
heat_total   = BASE_HEAT * (1 + 0.55 * np.cos(2*np.pi*(doy_h-355)/365)) * (1 + 0.08 * np.cos(2*np.pi*hod_h/24))
heat_zentrum = heat_total * 0.60
heat_sued    = heat_total * 0.40

print(f"\nProfile (ERA5={'✓' if ERA5_AVAILABLE else '⚠ synthetisch'}):")
print(f"  Solar: Ø {solar_cf.mean():.3f}  Wind: Ø {wind_cf.mean():.3f}  Offshore: Ø {offshore_cf.mean():.3f}")

# =============================================================
#  5) HILFSFUNKTIONEN
# =============================================================
def _pnom(comp_df: "pd.DataFrame", name: str) -> float:
    """Gibt p_nom_opt oder p_nom einer Komponente zurück."""
    row = comp_df.loc[name]
    return max(0., float(row.get("p_nom_opt", row["p_nom"])))

def _style_ax(
    ax: "plt.Axes",
    title: str,
    xlabel: str = "",
    ylabel: str = "",
    bg_inner: str = "#1a2a3a",
    bg_spine: str = "#444",
) -> None:
    """Wendet das einheitliche Dark-Theme auf eine Achse an."""
    ax.set_facecolor(bg_inner)
    ax.tick_params(colors="white")
    ax.set_title(title, color="white", fontsize=10, fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, color="white")
    if ylabel:
        ax.set_ylabel(ylabel, color="white")
    for sp in ax.spines.values():
        sp.set_edgecolor(bg_spine)

# =============================================================
#  6) NETZ-BUILDER
# =============================================================
def build_network(
    s_cf: np.ndarray,
    w_cf: np.ndarray,
    w_off_cf: np.ndarray,
    l_nord: np.ndarray,
    l_zentrum: np.ndarray,
    l_sued: np.ndarray,
    h_zentrum: np.ndarray,
    h_sued: np.ndarray,
) -> "pypsa.Network":
    """Baut und gibt das 4-Zonen PyPSA-Netz zurück."""
    net = pypsa.Network()
    net.set_snapshots(snapshots)
    for c, co2 in [
        ("wind", 0.), ("solar", 0.), ("nuclear", 0.), ("gas", 0.200),
        ("battery", 0.), ("H2", 0.), ("AC", 0.), ("heat", 0.),
    ]:
        net.add("Carrier", c, co2_emissions=co2)
    for bname in ["Nord", "Zentrum", "Sued", "Offshore"]:
        net.add("Bus", bname, v_nom=110., carrier="AC")
    net.add("Bus", "Waerme_Zentrum", carrier="heat")
    net.add("Bus", "Waerme_Sued",    carrier="heat")
    net.add("Bus", "H2_Bus",         carrier="H2")
    for ln, b0, b1, ckey, snom, smin in [
        ("Leitung_NZ", "Nord",     "Zentrum", "Line",    60., 20.),
        ("Leitung_ZS", "Zentrum",  "Sued",    "Line",    60., 20.),
        ("Leitung_NS", "Nord",     "Sued",    "Line",    30.,  5.),
        ("Leitung_ON", "Offshore", "Nord",    "Line_off",50., 10.),
    ]:
        net.add("Line", ln, bus0=b0, bus1=b1, x=0.10, r=0.01,
                s_nom=snom, s_nom_min=smin, s_nom_extendable=True,
                capital_cost=capex_annual(ckey))
    net.add("Generator", "Wind_Offshore", bus="Offshore", carrier="wind",
            p_nom=80., p_nom_min=50., p_nom_extendable=True,
            p_max_pu=pd.Series(w_off_cf, index=snapshots),
            marginal_cost=OPEX["Wind_off"], capital_cost=capex_annual("Wind_off"))
    net.add("Generator", "Wind_Nord", bus="Nord", carrier="wind",
            p_nom=50., p_nom_min=20., p_nom_extendable=True,
            p_max_pu=pd.Series(w_cf, index=snapshots),
            marginal_cost=OPEX["Wind_on"], capital_cost=capex_annual("Wind_on"))
    net.add("Generator", "Atomkraft", bus="Nord", carrier="nuclear",
            p_nom=30., p_nom_extendable=False,
            marginal_cost=OPEX["Nuclear"], capital_cost=0.)
    net.add("Generator", "Solar_Nord", bus="Nord", carrier="solar",
            p_nom=20., p_nom_min=5., p_nom_extendable=True,
            p_max_pu=pd.Series(s_cf * 0.85, index=snapshots),
            marginal_cost=OPEX["Solar"], capital_cost=capex_annual("Solar"))
    net.add("Generator", "Wind_Zentrum", bus="Zentrum", carrier="wind",
            p_nom=25., p_nom_min=5., p_nom_extendable=True,
            p_max_pu=pd.Series(w_cf * 0.90, index=snapshots),
            marginal_cost=OPEX["Wind_on"], capital_cost=capex_annual("Wind_on"))
    net.add("Generator", "Gas_CCGT", bus="Zentrum", carrier="gas",
            p_nom=35., p_nom_min=5., p_nom_extendable=True,
            marginal_cost=OPEX["Gas_CCGT"], capital_cost=capex_annual("Gas_CCGT"))
    net.add("Generator", "Solar_Sued", bus="Sued", carrier="solar",
            p_nom=60., p_nom_min=20., p_nom_extendable=True,
            p_max_pu=pd.Series(s_cf, index=snapshots),
            marginal_cost=OPEX["Solar"], capital_cost=capex_annual("Solar"))
    net.add("StorageUnit", "Batterie", bus="Zentrum", carrier="battery",
            p_nom=25., p_nom_min=5., p_nom_extendable=True, max_hours=4.,
            efficiency_store=0.93, efficiency_dispatch=0.93, cyclic_state_of_charge=True,
            marginal_cost=OPEX["Battery"], capital_cost=capex_annual("Battery") * 4)
    net.add("Link", "Elektrolyseur", bus0="Zentrum", bus1="H2_Bus",
            p_nom=15., p_nom_min=2., p_nom_extendable=True, efficiency=0.70,
            marginal_cost=OPEX["H2_elec"], capital_cost=capex_annual("H2_elec"))
    net.add("Store", "H2_Tank", bus="H2_Bus", carrier="H2",
            e_nom=500., e_nom_min=50., e_nom_extendable=True, e_cyclic=True,
            capital_cost=capex_annual("H2_tank"))
    net.add("Link", "Brennstoffzelle", bus0="H2_Bus", bus1="Zentrum",
            p_nom=10., p_nom_min=2., p_nom_extendable=True, efficiency=0.55,
            marginal_cost=OPEX["H2_FC"], capital_cost=capex_annual("H2_FC"))
    net.add("Link", "WP_Zentrum", bus0="Zentrum", bus1="Waerme_Zentrum",
            p_nom=20., p_nom_min=3., p_nom_extendable=True, efficiency=3.0,
            marginal_cost=OPEX["HeatPump"], capital_cost=capex_annual("HeatPump"))
    net.add("Link", "WP_Sued", bus0="Sued", bus1="Waerme_Sued",
            p_nom=15., p_nom_min=2., p_nom_extendable=True, efficiency=2.8,
            marginal_cost=OPEX["HeatPump"], capital_cost=capex_annual("HeatPump"))
    net.add("Store", "WaermeSpeicher_Zentrum", bus="Waerme_Zentrum", carrier="heat",
            e_nom=160., e_nom_min=10., e_nom_extendable=True, e_cyclic=True,
            standing_loss=0.005, capital_cost=capex_annual("HeatStore") * 8)
    net.add("Store", "WaermeSpeicher_Sued", bus="Waerme_Sued", carrier="heat",
            e_nom=100., e_nom_min=10., e_nom_extendable=True, e_cyclic=True,
            standing_loss=0.005, capital_cost=capex_annual("HeatStore") * 8)
    net.add("Load", "Last_Nord",    bus="Nord",           p_set=pd.Series(l_nord,    index=snapshots))
    net.add("Load", "Last_Zentrum", bus="Zentrum",        p_set=pd.Series(l_zentrum, index=snapshots))
    net.add("Load", "Last_Sued",    bus="Sued",           p_set=pd.Series(l_sued,    index=snapshots))
    net.add("Load", "Waerme_Last_Zentrum", bus="Waerme_Zentrum", p_set=pd.Series(h_zentrum, index=snapshots))
    net.add("Load", "Waerme_Last_Sued",    bus="Waerme_Sued",    p_set=pd.Series(h_sued,    index=snapshots))
    net.add("GlobalConstraint", "co2_limit",
            sense="<=", carrier_attribute="co2_emissions", constant=CO2_BUDGET)

    # FIX 1: Realistische Obergrenzen setzen (verhindert HiGHS/Gurobi Skalierungswarnung)
    _P_MAX = 5_000.   # MW
    _E_MAX = 50_000.  # MWh
    net.generators.loc[net.generators.p_nom_extendable,    "p_nom_max"] = _P_MAX
    net.links.loc[net.links.p_nom_extendable,              "p_nom_max"] = _P_MAX
    net.lines.loc[net.lines.s_nom_extendable,              "s_nom_max"] = _P_MAX
    net.stores.loc[net.stores.e_nom_extendable,            "e_nom_max"] = _E_MAX
    net.storage_units.loc[net.storage_units.p_nom_extendable, "p_nom_max"] = _P_MAX

    return net

print("\n✓ build_network() definiert")

# =============================================================
#  7) BASISOPTIMIERUNG
# =============================================================
print("\n" + "=" * 55)
print(" Starte Basisoptimierung …")
print("=" * 55)

n = build_network(
    solar_cf, wind_cf, offshore_cf,
    load_nord, load_zentrum, load_sued,
    heat_zentrum, heat_sued,
)

GUROBI_USED = False
if GUROBI_AVAILABLE and GRB_WLSACCESSID not in ("DEINE_ACCESS_ID", ""):
    try:
        env = gp.Env(params={
            "WLSACCESSID": GRB_WLSACCESSID, "WLSSECRET": GRB_WLSSECRET,
            "LICENSEID":   GRB_LICENSEID,    "OutputFlag": 1,
            "TimeLimit":   600,              "MIPGap":     0.01,
            "Threads":     0,                "Method":     2,
        })
        n.optimize(solver_name="gurobi", solver_options={"env": env})
        # FIX 2: Shadow-Prices zuweisen
        try:
            n.optimize.assign_solution()
        except Exception as _sp:
            print(f"  ⚠ Shadow-Prices: {_sp}")
        GUROBI_USED = True
        print("✓ Gurobi erfolgreich")
    except Exception as _e:
        print(f"⚠ Gurobi: {_e}")

if not GUROBI_USED:
    print("→ HiGHS (8760h) …")
    try:
        n.optimize(solver_name="highs", solver_options={"time_limit": 300, "mip_rel_gap": 0.02})
        # FIX 2: Shadow-Prices zuweisen
        try:
            n.optimize.assign_solution()
        except Exception as _sp:
            print(f"  ⚠ Shadow-Prices: {_sp}")
    except Exception as _e2:
        print(f"⚠ HiGHS: {_e2} → 2h-Fallback")
        n.set_snapshots(n.snapshots[::2])
        n.optimize(solver_name="highs", solver_options={"time_limit": 120})

print(f"\n✓ Optimierung fertig  →  {n.objective / 1e6:.3f} M€/a")

# FIX 4: Hinweis bei negativem Objective
if n.objective < 0:
    print("  ⚠ Hinweis: Objective negativ – Modell enthält Erlösterme (z.B. negative marginal_cost)")
    print("  → Prüfen: Sind marginal_cost-Werte korrekt positiv (Kosten) oder negativ (Erlöse)?")

try:
    co2_total = (
        n.generators_t.p * n.generators.carrier.map(n.carriers.co2_emissions)
    ).sum().sum() / 1e3
    print(f"  CO₂: {co2_total:.0f} tCO₂/a")
except (KeyError, AttributeError):
    co2_total = 0.0

for name in n.generators.index:
    print(f"  {name:<25} {_pnom(n.generators, name):>8.1f} MW")

# =============================================================
#  8) MONTE-CARLO
# =============================================================
print("\n" + "=" * 55)
print(f" Monte-Carlo: {N_MC} Wetterjahre")
print("=" * 55)

mc_results = []
for mc_i in range(N_MC):
    s_mc, w_mc, w_off_mc = _synthetic_profiles(mc_i * 17 + 3, mc_i * 31 + 7, mc_i * 17 + 3 + 99)
    np.random.seed(mc_i * 17 + 4)
    lt = load_total * (1. + np.random.uniform(-0.05, 0.05))
    ht = heat_total * (1. + np.random.uniform(-0.05, 0.05))
    try:
        nm = build_network(s_mc, w_mc, w_off_mc, lt*0.40, lt*0.25, lt*0.35, ht*0.60, ht*0.40)

        # FIX 3: Gurobi bevorzugen, HiGHS mit 600s + verbesserter Skalierung
        _mc_solved = False
        if GUROBI_AVAILABLE and GRB_WLSACCESSID not in ("DEINE_ACCESS_ID", ""):
            try:
                _env_mc = gp.Env(params={
                    "WLSACCESSID": GRB_WLSACCESSID, "WLSSECRET": GRB_WLSSECRET,
                    "LICENSEID": GRB_LICENSEID, "OutputFlag": 0,
                    "TimeLimit": 600, "MIPGap": 0.01, "Threads": 0, "Method": 2,
                })
                nm.optimize(solver_name="gurobi", solver_options={"env": _env_mc})
                try:
                    nm.optimize.assign_solution()
                except Exception:
                    pass
                _mc_solved = True
            except Exception as _eg:
                print(f"  ⚠ Gurobi MC: {_eg} → HiGHS")
        if not _mc_solved:
            nm.optimize(solver_name="highs", solver_options={
                "time_limit": 600,
                "mip_rel_gap": 0.01,
                "simplex_scale_strategy": 2,
            })
            try:
                nm.optimize.assign_solution()
            except Exception:
                pass

        cost = nm.objective / 1e6
        co2  = (nm.generators_t.p * nm.generators.carrier.map(nm.carriers.co2_emissions)).sum().sum() / 1e3
        rg   = [g for g in nm.generators.index if nm.generators.at[g, "carrier"] in ["wind", "solar"]]
        re   = nm.generators_t.p[rg].sum().sum() / nm.generators_t.p.sum().sum() * 100
        mc_results.append({"Jahr": mc_i+1, "Kosten_MEa": cost, "CO2_t": co2, "RE_Anteil_%": re, "Status": "OK"})
        print(f" Jahr {mc_i+1}: {cost:.2f} M€/a | CO₂={co2:.0f} t | RE={re:.0f}%")
    except Exception as ex:
        mc_results.append({"Jahr": mc_i+1, "Kosten_MEa": float("nan"), "CO2_t": float("nan"),
                           "RE_Anteil_%": float("nan"), "Status": f"Fehler: {ex}"})
        print(f" Jahr {mc_i+1}: FEHLER – {ex}")

mc_df = pd.DataFrame(mc_results)
valid = mc_df[mc_df["Status"] == "OK"]
if not valid.empty:
    print(f"\n  Ø Kosten: {valid['Kosten_MEa'].mean():.2f} M€/a  σ={valid['Kosten_MEa'].std():.2f}")
    print(f"  Ø RE    : {valid['RE_Anteil_%'].mean():.1f}%")

# =============================================================
#  9–12) PLOTS (A / B / C / Karte)
# =============================================================
COLORS = {
    "Wind_Nord":     "#4A90D9",
    "Wind_Zentrum":  "#6db3f2",
    "Wind_Offshore": "#00BCD4",
    "Solar_Nord":    "#ffc966",
    "Solar_Sued":    "#F5A623",
    "Atomkraft":     "#7ED321",
    "Gas_CCGT":      "#D0021B",
    "Batterie":      "#9B59B6",
}
BG = "#0D1B2A"

_step_h    = int(round((n.snapshots[1] - n.snapshots[0]).total_seconds() / 3600)) if len(n.snapshots) > 1 else 1
_spd       = 24 // _step_h
idx_summer = slice(25 * 7 * _spd, 26 * 7 * _spd)
idx_winter = slice(0, 7 * _spd)

# ── Plot A ────────────────────────────────────────────────────
print("\n  Erstelle Plot A …")
fig_a = plt.figure(figsize=(18, 14))
fig_a.patch.set_facecolor(BG)
gs_a  = gridspec.GridSpec(3, 2, figure=fig_a, hspace=0.45, wspace=0.35, left=0.08, right=0.97, top=0.93, bottom=0.06)

ax = fig_a.add_subplot(gs_a[0, 0])
gen_sum = n.generators_t.p.sum() / 1e3
ax.bar(range(len(gen_sum)), gen_sum.values, color=[COLORS.get(k, "#888") for k in gen_sum.index], edgecolor="white", lw=0.5)
ax.set_xticks(range(len(gen_sum)))
ax.set_xticklabels(gen_sum.index, rotation=35, ha="right", fontsize=8, color="white")
_style_ax(ax, "Jährlicher Erzeugungsmix", ylabel="GWh/Jahr")

ax = fig_a.add_subplot(gs_a[0, 1])
week_p = n.generators_t.p.iloc[idx_summer]
bot = np.zeros(len(week_p))
for col in week_p.columns:
    ax.fill_between(range(len(week_p)), bot, bot + week_p[col].values, color=COLORS.get(col, "#888"), alpha=0.88, label=col)
    bot += week_p[col].values
ls = n.loads_t.p_set[["Last_Nord", "Last_Zentrum", "Last_Sued"]].iloc[idx_summer].sum(axis=1)
ax.plot(ls.values, "w--", lw=1.4, label="Stromlast")
ax.set_xticks(np.arange(0, 7 * _spd + 1, _spd))
ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
_style_ax(ax, "Sommer (KW 26)", ylabel="MW")
ax.legend(fontsize=7, facecolor=BG, labelcolor="white", loc="upper left", ncol=2, framealpha=0.85)

ax = fig_a.add_subplot(gs_a[1, 0])
week_pw = n.generators_t.p.iloc[idx_winter]
bot = np.zeros(len(week_pw))
for col in week_pw.columns:
    ax.fill_between(range(len(week_pw)), bot, bot + week_pw[col].values, color=COLORS.get(col, "#888"), alpha=0.88)
    bot += week_pw[col].values
lw2 = n.loads_t.p_set[["Last_Nord", "Last_Zentrum", "Last_Sued"]].iloc[idx_winter].sum(axis=1)
ax.plot(lw2.values, "w--", lw=1.4)
ax.set_xticks(np.arange(0, 7 * _spd + 1, _spd))
ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
_style_ax(ax, "Winter (KW 1)", ylabel="MW")

ax = fig_a.add_subplot(gs_a[1, 1])
try:
    h2_soc = n.stores_t.e["H2_Tank"]
    ax.fill_between(range(len(h2_soc)), h2_soc.values, alpha=0.6, color="#2ECC71", label="H₂-Füllstand")
    ax.axhline(n.stores.at["H2_Tank", "e_nom_opt"] * 0.2, color="#ffd93d", ls="--", lw=1.2, label="Min 20%")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
except (KeyError, AttributeError):
    ax.text(0.5, 0.5, "H₂ n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
_style_ax(ax, "H₂-Tank SoC")

ax = fig_a.add_subplot(gs_a[2, 0])
try:
    wpz = n.links_t.p0["WP_Zentrum"].iloc[idx_winter]
    wps = n.links_t.p0["WP_Sued"].iloc[idx_winter]
    tw  = range(len(wpz))
    ax.fill_between(tw, 0, wpz.values, alpha=0.75, color="#E74C3C", label="WP Zentrum")
    ax.fill_between(tw, wpz.values, wpz.values + wps.values, alpha=0.75, color="#C0392B", label="WP Süd")
    ax.plot(tw, heat_zentrum[idx_winter] + heat_sued[idx_winter], "w--", lw=1.2, label="Wärmelast")
    ax.set_xticks(np.arange(0, 169, 24))
    ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
except (KeyError, AttributeError):
    ax.text(0.5, 0.5, "WP n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
_style_ax(ax, "Wärmepumpen – Winter", ylabel="MW_el")

ax = fig_a.add_subplot(gs_a[2, 1])
if not valid.empty:
    ax.bar(valid["Jahr"], valid["Kosten_MEa"], color="#4A90D9", edgecolor="white", lw=0.5, alpha=0.85)
    ax.axhline(valid["Kosten_MEa"].mean(), color="#FFD700", ls="--", lw=1.5,
               label=f"Ø {valid['Kosten_MEa'].mean():.2f} M€/a")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
_style_ax(ax, "Monte-Carlo Kosten", xlabel="Wetterjahr", ylabel="M€/a")

fig_a.suptitle("LUMMERLAND v3.0 – Erzeugungsmix, H₂-System & Sektorkopplung",
               fontsize=14, fontweight="bold", color="white", y=0.97)
_path_a = os.path.join(OUTPUT_DIR, "lummerland_v3_ergebnisse.png")
plt.savefig(_path_a, dpi=140, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"  ✓ {_path_a}")

# ── Plot B ────────────────────────────────────────────────────
print("  Erstelle Plot B …")
fig_b = plt.figure(figsize=(18, 10))
fig_b.patch.set_facecolor(BG)
gs_b = gridspec.GridSpec(2, 3, figure=fig_b, hspace=0.48, wspace=0.38, left=0.07, right=0.97, top=0.92, bottom=0.08)

ax = fig_b.add_subplot(gs_b[0, 0])
inv = {g.replace("_", " "): _pnom(n.generators, g) * n.generators.at[g, "capital_cost"] / 1e6
       for g in n.generators.index}
inv.update({su.replace("_", " "): _pnom(n.storage_units, su) * n.storage_units.at[su, "capital_cost"] / 1e6
            for su in n.storage_units.index})
inv_s  = dict(sorted(inv.items(), key=lambda x: x[1], reverse=True))
clrs_b = ["#4A90D9","#00BCD4","#ffc966","#7ED321","#D0021B","#9B59B6","#2ECC71","#E74C3C"]
ax.barh(list(inv_s.keys()), list(inv_s.values()), color=clrs_b[:len(inv_s)][::-1], edgecolor="white", lw=0.4)
_style_ax(ax, "Kapitalkosten", xlabel="M€/Jahr")
ax.tick_params(labelsize=8)

ax = fig_b.add_subplot(gs_b[0, 1])
op   = {g.replace("_", " "): n.generators_t.p[g].sum() * n.generators.at[g, "marginal_cost"] / 1e6
        for g in n.generators.index}
op_s = dict(sorted(op.items(), key=lambda x: x[1], reverse=True))
ax.barh(list(op_s.keys()), list(op_s.values()), color="#F5A623", edgecolor="white", lw=0.4, alpha=0.85)
_style_ax(ax, "Betriebskosten", xlabel="M€/Jahr")
ax.tick_params(labelsize=8)

ax = fig_b.add_subplot(gs_b[0, 2])
co2_src = {
    g: n.generators_t.p[g].sum() * (
        n.carriers.at[n.generators.at[g, "carrier"], "co2_emissions"]
        if n.generators.at[g, "carrier"] in n.carriers.index else 0
    ) / 1e3
    for g in n.generators.index
}
co2_pos = {k: v for k, v in co2_src.items() if v > 0.1}
if co2_pos:
    ax.pie(co2_pos.values(), labels=co2_pos.keys(), autopct="%1.1f%%",
           colors=["#D0021B","#E67E22","#C0392B"], textprops=dict(color="white", fontsize=8))
else:
    ax.text(0.5, 0.5, "CO₂ = 0 ✓", ha="center", va="center",
            color="#7ED321", fontsize=14, fontweight="bold", transform=ax.transAxes)
_style_ax(ax, f"CO₂-Emissionen\n(Budget: {CO2_BUDGET:,} t/a)")

ax = fig_b.add_subplot(gs_b[1, 0])
caps = {g: _pnom(n.generators, g) for g in n.generators.index}
caps.update({su: _pnom(n.storage_units, su) for su in n.storage_units.index})
ax.bar(range(len(caps)), list(caps.values()), color=[COLORS.get(k, "#888") for k in caps], edgecolor="white", lw=0.4)
ax.set_xticks(range(len(caps)))
ax.set_xticklabels(list(caps.keys()), rotation=40, ha="right", fontsize=8, color="white")
_style_ax(ax, "Optimierte Kapazitäten", ylabel="MW")

ax = fig_b.add_subplot(gs_b[1, 1])
cf_vals = {g: n.generators_t.p[g].mean() / _pnom(n.generators, g)
           for g in n.generators.index if _pnom(n.generators, g) > 0}
cf_s = dict(sorted(cf_vals.items(), key=lambda x: x[1], reverse=True))
ax.barh(list(cf_s.keys()), list(cf_s.values()), color=[COLORS.get(k, "#888") for k in cf_s], edgecolor="white", lw=0.4)
ax.axvline(0.25, color="#ffd93d", ls="--", lw=1)
ax.set_xlim(0, 1)
_style_ax(ax, "Kapazitätsfaktoren", xlabel="CF [−]")
ax.tick_params(labelsize=8)

ax = fig_b.add_subplot(gs_b[1, 2])
if not valid.empty:
    sc = ax.scatter(valid["Kosten_MEa"], valid["RE_Anteil_%"],
                    c=valid["CO2_t"], cmap="RdYlGn_r", s=120, edgecolors="white", lw=1.2, zorder=5)
    for _, row in valid.iterrows():
        ax.annotate(f"J{int(row['Jahr'])}", (row["Kosten_MEa"], row["RE_Anteil_%"]),
                    fontsize=8, color="white", xytext=(4, 4), textcoords="offset points")
    cb = plt.colorbar(sc, ax=ax)
    cb.set_label("CO₂ [t/a]", color="white")
    cb.ax.yaxis.label.set_color("white")
_style_ax(ax, "MC: Kosten vs. RE-Anteil", xlabel="Kosten [M€/a]", ylabel="RE-Anteil [%]")

fig_b.suptitle("LUMMERLAND v3.0 – Kosten, CO₂ & Monte-Carlo Robustheit",
               fontsize=14, fontweight="bold", color="white", y=0.97)
_path_b = os.path.join(OUTPUT_DIR, "lummerland_v3_kosten.png")
plt.savefig(_path_b, dpi=140, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"  ✓ {_path_b}")

# ── Plot C ────────────────────────────────────────────────────
print("  Erstelle Plot C …")
fig_c = plt.figure(figsize=(18, 10))
fig_c.patch.set_facecolor(BG)
gs_c  = gridspec.GridSpec(2, 3, figure=fig_c, hspace=0.45, wspace=0.38, left=0.07, right=0.97, top=0.92, bottom=0.08)
t_ax  = range(len(n.generators_t.p.iloc[idx_summer]))

ax = fig_c.add_subplot(gs_c[0, 0])
sectors = {
    "Strom-\nErzeugung": n.generators_t.p.sum().sum() / 1e3,
    "Strom-\nLast":      n.loads_t.p_set[["Last_Nord","Last_Zentrum","Last_Sued"]].sum().sum() / 1e3,
}
try:
    sectors["Wärme-\nLast"]  = n.loads_t.p_set[["Waerme_Last_Zentrum","Waerme_Last_Sued"]].sum().sum() / 1e3
    sectors["H₂-\nErzeugt"] = (n.links_t.p0.get("Elektrolyseur", pd.Series(0))).sum() / 1e3
except (KeyError, AttributeError):
    pass
ax.bar(list(sectors.keys()), list(sectors.values()),
       color=["#4A90D9","white","#E74C3C","#2ECC71"][:len(sectors)], edgecolor="white", lw=0.5, alpha=0.85)
_style_ax(ax, "Jahresenergie-Übersicht", ylabel="GWh/Jahr")
ax.tick_params(labelsize=8)

ax = fig_c.add_subplot(gs_c[0, 1])
try:
    bat_soc = n.storage_units_t.state_of_charge["Batterie"].iloc[idx_summer]
    ax.fill_between(t_ax, bat_soc.values, alpha=0.7, color="#9B59B6", label="Batterie SoC")
    pno = _pnom(n.storage_units, "Batterie")
    ax.axhline(pno * 4 * 0.10, color="#ff6b6b", ls="--", lw=1, label="Min 10%")
    ax.axhline(pno * 4 * 0.90, color="#6bcb77", ls="--", lw=1, label="Max 90%")
    ax.set_xticks(np.arange(0, 169, 24))
    ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
    ax.set_ylabel("MWh", color="white")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
except (KeyError, AttributeError):
    ax.text(0.5, 0.5, "SoC n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
_style_ax(ax, "Batterie SoC – Sommer")

ax    = fig_c.add_subplot(gs_c[0, 2])
months = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
_sh   = (n.snapshots[1] - n.snapshots[0]).total_seconds() / 3600 if len(n.snapshots) > 1 else 1.
bot2  = np.zeros(12)
for g in n.generators.index:
    g_ts = n.generators_t.p[g].copy()
    g_ts.index = n.snapshots
    vals = [g_ts[g_ts.index.month == m].sum() * _sh / 1e3 for m in range(1, 13)]
    ax.bar(range(12), vals, bottom=bot2, color=COLORS.get(g, "#888"), alpha=0.85, label=g, edgecolor="none")
    bot2 += np.array(vals)
ax.set_xticks(range(12))
ax.set_xticklabels(months, fontsize=8, rotation=45, color="white")
_style_ax(ax, "Monatliche Erzeugung", ylabel="GWh/Monat")
ax.legend(fontsize=7, facecolor=BG, labelcolor="white", ncol=2, loc="upper right")

ax = fig_c.add_subplot(gs_c[1, 0])
re_gens  = [g for g in n.generators.index if n.generators.at[g, "carrier"] in ["wind","solar"]]
re_total = n.generators_t.p[re_gens].sum(axis=1)
demand   = n.loads_t.p_set[["Last_Nord","Last_Zentrum","Last_Sued"]].sum(axis=1)
residual = (demand - re_total).sort_values(ascending=False)
ax.fill_between(range(len(residual)), residual.values, 0,
                where=residual.values > 0, color="#D0021B", alpha=0.6, label="Residual >0")
ax.fill_between(range(len(residual)), residual.values, 0,
                where=residual.values < 0, color="#7ED321", alpha=0.6, label="EE-Überschuss")
ax.axhline(0, color="white", lw=0.8)
_style_ax(ax, "Dauerlinie Residuallast", xlabel="Stunden (sortiert)", ylabel="MW")
ax.legend(fontsize=8, facecolor=BG, labelcolor="white")

ax = fig_c.add_subplot(gs_c[1, 1])
line_cm = {"Leitung_NZ":"#4A90D9","Leitung_ZS":"#F5A623","Leitung_NS":"#2ECC71","Leitung_ON":"#00BCD4"}
for ln, lclr in line_cm.items():
    try:
        sopt = n.lines.at[ln, "s_nom_opt"] if "s_nom_opt" in n.lines.columns else n.lines.at[ln, "s_nom"]
        util = n.lines_t.p0[ln].abs() / sopt * 100
        ax.hist(util, bins=40, alpha=0.55, color=lclr, label=f"{ln} (max {util.max():.0f}%)", density=True)
    except (KeyError, AttributeError, ZeroDivisionError):
        pass
_style_ax(ax, "Leitungsauslastung", xlabel="Auslastung [%]", ylabel="Häufigkeitsdichte")
ax.legend(fontsize=8, facecolor=BG, labelcolor="white")

ax = fig_c.add_subplot(gs_c[1, 2])
if not valid.empty:
    ax.boxplot(
        [valid["RE_Anteil_%"].values, valid["Kosten_MEa"].values * 10],
        tick_labels=["RE-Anteil [%]", "Kosten [×10 M€/a]"],
        patch_artist=True,
        boxprops=dict(facecolor="#4A90D9", alpha=0.7),
        medianprops=dict(color="#FFD700", lw=2),
        whiskerprops=dict(color="white"),
        capprops=dict(color="white"),
        flierprops=dict(markerfacecolor="#ff6b6b", marker="o"),
    )
_style_ax(ax, "Monte-Carlo Streuung")

fig_c.suptitle("LUMMERLAND v3.0 – Sektorkopplung, Speicher & Versorgungssicherheit",
               fontsize=14, fontweight="bold", color="white", y=0.97)
_path_c = os.path.join(OUTPUT_DIR, "lummerland_v3_sektoren.png")
plt.savefig(_path_c, dpi=140, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"  ✓ {_path_c}")

# ── Karte D ───────────────────────────────────────────────────
print("  Erstelle Karte D …")

def _safe_pnom(df: "pd.DataFrame", name: str) -> float:
    if name not in df.index:
        return 0.
    row = df.loc[name]
    return max(0., float(row.get("p_nom_opt", row.get("p_nom", 0.))))

def _safe_enom(df: "pd.DataFrame", name: str) -> float:
    if name not in df.index:
        return 0.
    row = df.loc[name]
    return max(0., float(row.get("e_nom_opt", row.get("e_nom", 0.))))

def _line_flow(ln: str) -> float:
    try:
        return float(abs(n.lines_t.p0[ln]).mean())
    except (KeyError, AttributeError):
        return 0.

def _line_lpct(ln: str) -> float:
    try:
        sn = float(n.lines.at[ln, "s_nom_opt"] if "s_nom_opt" in n.lines.columns else n.lines.at[ln, "s_nom"])
        return _line_flow(ln) / sn * 100 if sn > 0 else 0.
    except (KeyError, AttributeError, ZeroDivisionError):
        return 0.

def _bus_load(bus_name: str) -> float:
    try:
        cols = [c for c in n.loads.index if n.loads.at[c, "bus"] == bus_name]
        return float(n.loads_t.p_set[cols].mean().sum()) if cols else 0.
    except (KeyError, AttributeError):
        return 0.

def lc_color(p: float) -> str:
    return "#6bcb77" if p < 50 else ("#ffd93d" if p < 80 else "#ff6b6b")

try:
    OC    = n.objective / 1e6
    CV    = co2_total
    CAP_M = {g: _safe_pnom(n.generators, g)
             for g in ["Wind_Nord","Wind_Offshore","Wind_Zentrum","Solar_Nord","Solar_Sued","Atomkraft","Gas_CCGT"]}
    BAT_CAP = _safe_pnom(n.storage_units, "Batterie")
    H2T  = _safe_enom(n.stores, "H2_Tank")
    H2E  = _safe_pnom(n.links, "Elektrolyseur")
    H2F  = _safe_pnom(n.links, "Brennstoffzelle")
    WPZ  = _safe_pnom(n.links, "WP_Zentrum")
    WPS  = _safe_pnom(n.links, "WP_Sued")
    rg2  = [g for g in n.generators.index if n.generators.at[g, "carrier"] in ["wind","solar"]]
    REP  = n.generators_t.p[rg2].sum().sum() / n.generators_t.p.sum().sum() * 100
    BCAP = {
        "Nord":     CAP_M["Wind_Nord"]    + CAP_M["Solar_Nord"] + CAP_M["Atomkraft"],
        "Zentrum":  CAP_M["Wind_Zentrum"] + CAP_M["Gas_CCGT"]  + BAT_CAP,
        "Sued":     CAP_M["Solar_Sued"],
        "Offshore": CAP_M["Wind_Offshore"],
    }
    BLOAD   = {b: _bus_load(b) for b in ["Nord","Zentrum","Sued","Offshore"]}
    LF2     = {k: _line_flow(k) for k in ["Leitung_NZ","Leitung_ZS","Leitung_NS","Leitung_ON"]}
    LPCT2   = {k: _line_lpct(k) for k in ["Leitung_NZ","Leitung_ZS","Leitung_NS","Leitung_ON"]}
    DATA_OK = True
except Exception as de:
    OC = 42.5; CV = 1250.; REP = 78.
    CAP_M   = {"Wind_Nord":65.,"Wind_Offshore":110.,"Wind_Zentrum":30.,"Solar_Nord":22.,"Solar_Sued":75.,"Atomkraft":30.,"Gas_CCGT":20.}
    BAT_CAP = 30.; H2T = 520.; H2E = 18.; H2F = 12.; WPZ = 22.; WPS = 16.
    BCAP    = {"Nord":117.,"Zentrum":80.,"Sued":75.,"Offshore":110.}
    BLOAD   = {"Nord":32.,"Zentrum":20.,"Sued":28.,"Offshore":0.}
    LF2     = {"Leitung_NZ":28.,"Leitung_ZS":22.,"Leitung_NS":12.,"Leitung_ON":55.}
    LPCT2   = {"Leitung_NZ":47.,"Leitung_ZS":37.,"Leitung_NS":40.,"Leitung_ON":73.}
    DATA_OK = False

BGMAP = "#0a1628"; LAND = "#2d5a1a"; SHORE = "#c8a96e"
BCOL  = {"Nord":"#4A90D9","Zentrum":"#7ED321","Sued":"#F5A623","Offshore":"#00BCD4"}
BUS_POS   = {"Nord":(14.8,13.2),"Zentrum":(11.8,9.8),"Sued":(18.8,8.2),"Offshore":(3.5,17.2)}
LINES_DEF = [
    ("Leitung_NZ", "Nord",     "Zentrum", False),
    ("Leitung_ZS", "Zentrum",  "Sued",    False),
    ("Leitung_NS", "Nord",     "Sued",    False),
    ("Leitung_ON", "Offshore", "Nord",    True),
]

def draw_turbine(ax: "plt.Axes", x: float, y: float, size: float = 0.5,
                 color: str = "#4A90D9", zorder: int = 15) -> None:
    ax.plot([x, x], [y - size*0.8, y + size*0.2], color=color, lw=2.5*size/0.5, zorder=zorder)
    ax.add_patch(Ellipse((x, y + size*0.2), size*0.25, size*0.12, facecolor=color, zorder=zorder+1))
    for angle in [90, 210, 330]:
        rad = np.radians(angle)
        ax.add_patch(Ellipse(
            (x + size*0.35*np.cos(rad), y + size*0.2 + size*0.35*np.sin(rad)),
            size*0.12, size*0.28, angle=angle-90, facecolor=color, alpha=0.85, zorder=zorder+1,
        ))

def draw_solar(ax: "plt.Axes", x: float, y: float, size: float = 0.5,
               color: str = "#F5A623", n_panels: int = 3, zorder: int = 15) -> None:
    pw = size*0.45; ph = size*0.28; gap = size*0.05
    x0 = x - (n_panels * pw + (n_panels - 1) * gap) / 2
    for i in range(n_panels):
        px = x0 + i * (pw + gap)
        ax.add_patch(FancyBboxPatch(
            (px, y - ph/2), pw, ph, boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="white", lw=0.8, alpha=0.85, zorder=zorder,
        ))

def label_box(ax: "plt.Axes", x: float, y: float, txt: str, color: str,
              fontsize: int = 8, zorder: int = 20) -> None:
    ax.text(x, y, txt, fontsize=fontsize, color=color, ha="center", va="center", zorder=zorder,
            bbox=dict(facecolor=BGMAP, edgecolor=color, lw=0.8, boxstyle="round,pad=0.3", alpha=0.93))

fig_map, ax_map = plt.subplots(figsize=(16, 14))
fig_map.patch.set_facecolor(BGMAP)
ax_map.set_facecolor(BGMAP)
ax_map.set_xlim(0, 24); ax_map.set_ylim(4, 22)
ax_map.set_aspect("equal"); ax_map.axis("off")
island = plt.Polygon(
    [(8,5),(22,5),(22,16),(18,17),(14,16),(10,15),(8,12)],
    facecolor=LAND, edgecolor=SHORE, lw=2, alpha=0.85, zorder=1,
)
ax_map.add_patch(island)
for ln, b0, b1, offshore in LINES_DEF:
    x0, y0 = BUS_POS[b0]; x1, y1 = BUS_POS[b1]
    pct = LPCT2.get(ln, 0); clr = lc_color(pct)
    lw3 = 1.5 + min(LF2.get(ln, 0) / 30, 3.); ls = "--" if offshore else "-"
    ax_map.plot([x0, x1], [y0, y1], color=clr, lw=lw3, ls=ls, alpha=0.9, zorder=3,
                path_effects=[pe.Stroke(linewidth=lw3+2, foreground="black", alpha=0.4), pe.Normal()])
    label_box(ax_map, (x0+x1)/2, (y0+y1)/2, f"{ln}\n{LF2.get(ln,0):.0f}MW | {pct:.0f}%", clr, fontsize=7)
for bname, (bx, by) in BUS_POS.items():
    bcol = BCOL[bname]
    size = 0.5 + min(BCAP.get(bname, 0) / 400, 0.8)
    ax_map.add_patch(plt.Circle((bx, by), size, facecolor=bcol, edgecolor="white", lw=1.5, alpha=0.9, zorder=10))
    ax_map.text(bx, by + size + 0.4, bname, ha="center", va="bottom", fontsize=11, fontweight="bold",
                color=bcol, zorder=12, path_effects=[pe.withStroke(linewidth=3, foreground="black")])
    label_box(ax_map, bx, by - size - 0.8, f"{BCAP.get(bname,0):.0f} MW\n{BLOAD.get(bname,0):.0f} MW Last", bcol, fontsize=8)
draw_turbine(ax_map, 13.5, 15.5, size=0.6, color="#4A90D9")
draw_turbine(ax_map, 15.2, 15.5, size=0.6, color="#4A90D9")
draw_turbine(ax_map, 10.5, 11.5, size=0.5, color="#6db3f2")
draw_turbine(ax_map,  2.5, 17.5, size=0.7, color="#00BCD4")
draw_turbine(ax_map,  4.2, 18.0, size=0.7, color="#00BCD4")
draw_solar(ax_map, 19.5, 10.0, size=0.55, color="#F5A623")
draw_solar(ax_map, 19.5,  9.0, size=0.55, color="#F5A623")
kpi = (f"Gesamtkosten: {OC:.2f} M€/a\nCO₂: {CV:.0f} t/a\nRE-Anteil: {REP:.1f}%\n"
       f"H₂-Tank: {H2T:.0f} MWh\nElektrolyseur: {H2E:.0f} MW\nBrennstoffzelle: {H2F:.0f} MW\n"
       f"WP Zentrum: {WPZ:.0f} MW | WP Süd: {WPS:.0f} MW")
ax_map.text(0.5, 5.8, kpi, fontsize=9, color="white", va="top", ha="left",
            bbox=dict(facecolor="#1a2a3a", edgecolor="#4A90D9", lw=1, boxstyle="round,pad=0.5", alpha=0.92), zorder=20)
ax_map.legend(
    handles=[
        Line2D([0],[0], color="#6bcb77", lw=2, label="<50%"),
        Line2D([0],[0], color="#ffd93d", lw=2, label="50–80%"),
        Line2D([0],[0], color="#ff6b6b", lw=2, label=">80%"),
        Line2D([0],[0], color="white",   lw=2, ls="--", label="Offshore"),
    ],
    loc="lower right", facecolor="#1a2a3a", labelcolor="white", fontsize=9, framealpha=0.9,
)
ax_map.set_title(
    f"LUMMERLAND v3.0 – 4-Zonen-Netzknoten-Karte  |  {'✓ Echte Daten' if DATA_OK else '⚠ Demo'}",
    fontsize=14, fontweight="bold", color="white", pad=15,
)
fig_map.tight_layout()
_path_map = os.path.join(OUTPUT_DIR, "lummerland_v3_karte.png")
plt.savefig(_path_map, dpi=150, bbox_inches="tight", facecolor=BGMAP)
plt.close()
print(f"  ✓ {_path_map}")

# =============================================================
#  13) PDF-BERICHT
# =============================================================
print("\n  Erstelle PDF-Bericht …")
pdf_path = os.path.join(OUTPUT_DIR, "Lummerland_v3_Bericht.pdf")

with PdfPages(pdf_path) as pdf:
    fc = plt.figure(figsize=(16, 10)); fc.patch.set_facecolor(BG)
    ac = fc.add_axes([0, 0, 1, 1]); ac.set_facecolor(BG); ac.axis("off")
    ac.text(0.5, 0.72, "🏝️ LUMMERLAND", ha="center", fontsize=42, fontweight="bold", color="#4A90D9", transform=ac.transAxes)
    ac.text(0.5, 0.60, "Island Energy Model v3.0", ha="center", fontsize=24, color="white", transform=ac.transAxes)
    ac.text(0.5, 0.50, "4-Zonen-Inselmodell mit Sektorkopplung,\nH₂-System & Monte-Carlo-Robustheitsprüfung",
            ha="center", fontsize=14, color="#aaaaaa", transform=ac.transAxes)
    ac.text(0.5, 0.38, f"Gesamtkosten: {n.objective/1e6:.3f} M€/a   |   CO₂: {co2_total:.0f} tCO₂/a   |   Zeitschritte: {len(n.snapshots)}",
            ha="center", fontsize=12, color="#4A90D9", transform=ac.transAxes)
    ac.text(0.5, 0.28, f"Erstellt: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ha="center", fontsize=11, color="#888", transform=ac.transAxes)
    ac.text(0.5, 0.22, f"Ausgabe: {OUTPUT_DIR}",
            ha="center", fontsize=9, color="#555", transform=ac.transAxes)
    pdf.savefig(fc, facecolor=BG); plt.close(fc)
    print("  ✓ Deckblatt")

    for path, title in [(_path_map,"Karte"), (_path_a,"Plot A"), (_path_b,"Plot B"), (_path_c,"Plot C")]:
        fp = plt.figure(figsize=(16, 12)); fp.patch.set_facecolor(BG)
        ap = fp.add_axes([0, 0, 1, 1]); ap.axis("off")
        try:
            ap.imshow(plt.imread(path), aspect="auto")
        except (FileNotFoundError, OSError):
            ap.text(0.5, 0.5, f"{title} nicht verfügbar", ha="center", va="center",
                    color="white", fontsize=14, transform=ap.transAxes)
        pdf.savefig(fp, facecolor=BG); plt.close(fp)
        print(f"  ✓ {title}")

    fm = plt.figure(figsize=(14, 8)); fm.patch.set_facecolor(BG)
    am = fm.add_subplot(111); am.axis("off"); am.set_facecolor(BG)
    try:
        rows = [[str(int(r["Jahr"])), f"{r['Kosten_MEa']:.2f}", f"{r['CO2_t']:.0f}",
                 f"{r['RE_Anteil_%']:.1f}", r["Status"]] for _, r in mc_df.iterrows()]
        tbl = am.table(
            cellText=rows,
            colLabels=["Jahr","Kosten [M€/a]","CO₂ [t/a]","RE-Anteil [%]","Status"],
            cellLoc="center", loc="center", bbox=[0.02, 0.1, 0.96, 0.75],
        )
        tbl.auto_set_font_size(False); tbl.set_fontsize(11)
        for (ri, ci), cell in tbl.get_celld().items():
            cell.set_facecolor("#1a2a3a" if ri > 0 else "#0a3060")
            cell.set_text_props(color="white"); cell.set_edgecolor("#333")
        am.text(0.5, 0.92, "Monte-Carlo Robustheitsprüfung",
                ha="center", fontsize=14, fontweight="bold", color="white", transform=am.transAxes)
        if not valid.empty:
            am.text(0.5, 0.06,
                    f"Ø Kosten: {valid['Kosten_MEa'].mean():.2f} M€/a  |  "
                    f"Ø CO₂: {valid['CO2_t'].mean():.0f} t/a  |  Ø RE: {valid['RE_Anteil_%'].mean():.1f}%",
                    ha="center", fontsize=11, color="#4A90D9", transform=am.transAxes)
    except Exception as ex:
        am.text(0.5, 0.5, f"MC-Tabelle n.v.: {ex}", ha="center", va="center",
                color="white", fontsize=12, transform=am.transAxes)
    d = pdf.infodict()
    d["Title"]        = "Lummerland Island Energy Model v3.0"
    d["Author"]       = "PyPSA Optimierung"
    d["CreationDate"] = datetime.datetime.now()
    pdf.savefig(fm, facecolor=BG); plt.close(fm)
    print("  ✓ MC-Tabelle")

print(f"\n{'='*55}")
print(f" ✅ FERTIG!")
print(f"   PDF   → {pdf_path}")
print(f"   Plots → {OUTPUT_DIR}")
print(f"{'='*55}")
