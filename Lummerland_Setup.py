#!/usr/bin/env python3
# =============================================================
#  🏝️  LUMMERLAND – Setup & Installations-Skript
#  Installiert ALLE benötigten Pakete für Lummerland_v3.py
#  Ausführen: python Lummerland_Setup.py
# =============================================================

import subprocess
import sys
import os

print("=" * 60)
print("  🏝️  LUMMERLAND v3.0 – Paket-Installation")
print(f"  Python: {sys.executable}")
print(f"  Version: {sys.version.split()[0]}")
print("=" * 60)

# ─────────────────────────────────────────────────────────────
# PAKETE
# ─────────────────────────────────────────────────────────────
PACKAGES = [
    # Kern-Optimierung
    ("pypsa",                   "pypsa",        "Energiesystem-Optimierung"),
    ("highspy",                 "highspy",       "HiGHS Open-Source Solver"),
    ("gurobipy",                "gurobipy",      "Gurobi Solver (Lizenz optional)"),

    # Wetterdaten
    ("atlite",                  "atlite",        "ERA5 Wetterdaten-Interface"),
    ("cdsapi",                  "cdsapi",        "Copernicus CDS API"),
    ("xarray",                  "xarray",        "Multidimensionale Arrays (NetCDF)"),
    ("netCDF4",                 "netCDF4",       "NetCDF Dateiformat"),
    ("rioxarray",               "rioxarray",     "Raster-Daten für atlite"),
    ("dask",                    "dask",          "Parallele Berechnung"),

    # Daten & Berechnung
    ("numpy",                   "numpy",         "Numerische Berechnungen"),
    ("pandas",                  "pandas",        "Datenverarbeitung"),
    ("scipy",                   "scipy",         "Wissenschaftliche Berechnungen"),

    # Visualisierung
    ("matplotlib",              "matplotlib",    "Plots & PDF-Export"),
    ("Pillow",                  "PIL",           "Bild-Verarbeitung (PNG lesen)"),

    # Geo-Pakete
    ("geopandas",               "geopandas",     "Geodaten-Verarbeitung"),
    ("shapely",                 "shapely",       "Geometrie-Operationen"),
    ("pyproj",                  "pyproj",        "Koordinaten-Transformation"),

    # Sonstige
    ("tqdm",                    "tqdm",          "Fortschrittsbalken"),
    ("requests",                "requests",      "HTTP-Anfragen"),
]

# ─────────────────────────────────────────────────────────────
# INSTALLATION
# ─────────────────────────────────────────────────────────────
print("\n📦 Installiere Pakete ...\n")

failed   = []
skipped  = []
installed = []

for pkg, import_name, desc in PACKAGES:
    # Erst prüfen ob schon vorhanden
    try:
        __import__(import_name)
        print(f"  ✓  {pkg:<20} bereits installiert   ({desc})")
        skipped.append(pkg)
        continue
    except ImportError:
        pass

    # Installieren mit dem EXAKTEN Python dieser Instanz
    print(f"  ↓  {pkg:<20} installiere ...      ({desc})")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "-q", pkg],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            installed.append(pkg)
            print(f"  ✅ {pkg:<20} erfolgreich installiert")
        else:
            failed.append((pkg, result.stderr.strip()))
            print(f"  ❌ {pkg:<20} FEHLER:\n     {result.stderr.strip()[:120]}")
    except Exception as e:
        failed.append((pkg, str(e)))
        print(f"  ❌ {pkg:<20} FEHLER: {e}")

# ─────────────────────────────────────────────────────────────
# VERIFIKATION
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  🔍 Verifikation – Imports testen")
print("=" * 60)

results = {}
for pkg, import_name, desc in PACKAGES:
    try:
        mod = __import__(import_name)
        ver = getattr(mod, "__version__", "?")
        results[pkg] = ("✅", ver)
        print(f"  ✅ {pkg:<20} v{ver}")
    except ImportError as e:
        results[pkg] = ("❌", str(e))
        print(f"  ❌ {pkg:<20} Import fehlgeschlagen: {e}")

# ─────────────────────────────────────────────────────────────
# GUROBI LIZENZ CHECK
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  🔑 Gurobi Lizenz-Check")
print("=" * 60)

try:
    import gurobipy as gp
    print(f"  ✅ gurobipy importiert  (v{gp.gurobi.version()})")

    # Versuche eine Mini-Lizenz-Verbindung
    try:
        env = gp.Env()
        m   = gp.Model(env=env)
        m.dispose(); env.dispose()
        print("  ✅ Lizenz gültig – Gurobi einsatzbereit!")
    except gp.GurobiError as ge:
        print(f"  ⚠️  Lizenz-Fehler: {ge}")
        print("     → Trage deine WLS-Zugangsdaten in Lummerland_v3.py ein:")
        print("       GRB_WLSACCESSID = 'deine-access-id'")
        print("       GRB_WLSSECRET   = 'dein-secret'")
        print("       GRB_LICENSEID   = 12345")
        print("     → HiGHS wird als Fallback genutzt (kostenlos, kein Key nötig)")
except ImportError:
    print("  ❌ gurobipy nicht installiert")

# ─────────────────────────────────────────────────────────────
# CDS API CHECK
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  🌤️  CDS API (ERA5 Wetterdaten) Check")
print("=" * 60)

cdsrc = os.path.expanduser("~/.cdsapirc")
if os.path.exists(cdsrc):
    with open(cdsrc) as f:
        content = f.read()
    if "DEIN_API_KEY" in content or "key:" not in content:
        print("  ⚠️  ~/.cdsapirc existiert, aber kein gültiger Key")
    else:
        print("  ✅ ~/.cdsapirc gefunden – ERA5-Daten aktiv")
    print(f"     Inhalt: {content.strip()}")
else:
    print("  ℹ️  Kein ~/.cdsapirc → synthetische Profile werden genutzt")
    print("     Optional: https://cds.climate.copernicus.eu → Account → API-Key")
    print("     Dann in Lummerland_v3.py eintragen: CDS_KEY = 'dein-key'")

# ─────────────────────────────────────────────────────────────
# ZUSAMMENFASSUNG
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  📋 Zusammenfassung")
print("=" * 60)
print(f"  ✅ Bereits vorhanden  : {len(skipped)}")
print(f"  ✅ Neu installiert    : {len(installed)}")
print(f"  ❌ Fehlgeschlagen     : {len(failed)}")

if failed:
    print("\n  Fehlgeschlagene Pakete:")
    for pkg, err in failed:
        print(f"    - {pkg}: {err[:100]}")
    print("\n  💡 Tipp: Führe manuell aus:")
    for pkg, _ in failed:
        print(f"    {sys.executable} -m pip install {pkg}")
else:
    print("\n  🚀 Alle Pakete installiert – Lummerland_v3.py kann starten!")
    print(f"\n  Ausführen: python Lummerland_v3.py")

print(f"\n  Python-Pfad: {sys.executable}")
print("=" * 60)
