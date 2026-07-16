#!/usr/bin/env python3
# =============================================================
#  🇩🇪  DEUTSCHLAND ENERGY MODEL – GRAFISCHES OVERLAY (Streamlit)
#  Importiert deutschland_v1.py und macht das Modell interaktiv.
#
#  Installation:  pip install streamlit plotly
#  Starten:       streamlit run deutschland_gui.py
#  (deutschland_v1.py muss im selben Ordner liegen)
# =============================================================
import os
import io
import subprocess
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ── Streamlit-Cloud: Secrets als Umgebungsvariablen bereitstellen ─────
#   Muss VOR dem Import von deutschland_v1 stehen, weil das Modell Keys
#   (CDS_KEY, GRB_WLSACCESSID/-SECRET, GRB_LICENSEID) beim Import einliest.
#   Lokal bleibt die .env unberührt (setdefault überschreibt nichts).
try:
    for _k, _v in dict(st.secrets).items():
        if isinstance(_v, (str, int, float)):
            os.environ.setdefault(str(_k), str(_v))
except Exception:
    pass   # keine secrets.toml vorhanden (lokaler Betrieb) → egal

import deutschland_v1 as dm   # ← das komplette Modell als Modul

st.set_page_config(page_title="Deutschland Energy Model", layout="wide",
                   page_icon="⚡", initial_sidebar_state="expanded")

# ── Plotly-Themes: dunkel (Default) + helles Pendant. Rein optisch – ändert
#    keine Werte. Gleiche Colorway, nur Hintergrund/Schrift invertiert. ──────
_COLORWAY = ["#4A90D9", "#F5A623", "#3FBFB2", "#E8734C", "#8B5A3C",
             "#9aa0a6", "#B57EDC", "#6bcb77", "#00BCD4", "#E040FB"]
pio.templates["de_energy"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0f2233",
    font=dict(color="#dbe7f3", family="Inter, Segoe UI, system-ui, sans-serif"),
    colorway=_COLORWAY,
    xaxis=dict(gridcolor="#20364d", zerolinecolor="#22384f", linecolor="#2f5170"),
    yaxis=dict(gridcolor="#20364d", zerolinecolor="#22384f", linecolor="#2f5170"),
    legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=10, r=10, t=44, b=10),
))
pio.templates["de_energy_light"] = go.layout.Template(layout=dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#f4f7fb",
    font=dict(color="#1b2b3a", family="Inter, Segoe UI, system-ui, sans-serif"),
    colorway=_COLORWAY,
    xaxis=dict(gridcolor="#dae3ec", zerolinecolor="#c8d4e0", linecolor="#a9b8c7"),
    yaxis=dict(gridcolor="#dae3ec", zerolinecolor="#c8d4e0", linecolor="#a9b8c7"),
    legend=dict(bgcolor="rgba(0,0,0,0)"), margin=dict(l=10, r=10, t=44, b=10),
))

# ── Hell/Dunkel-Umschalter (oben rechts). Ehrliche Grenze: nur Plotly-Charts
#    und die per CSS gestylten Flächen wechseln; Streamlits native Widgets
#    (Regler/Checkboxen) bleiben via config.toml dunkel → die Sidebar bleibt
#    bewusst dunkel, nur der Hauptbereich wird hell. ────────────────────────
_thl, _thr = st.columns([9, 1])
with _thr:
    _light = st.toggle("☀️", value=False, key="light_mode",
                       help="Helles Diagramm-/Oberflächen-Theme "
                            "(Sidebar bleibt dunkel)")
_tpl = "de_energy_light" if _light else "de_energy"
pio.templates.default = _tpl
px.defaults.template = _tpl

# ── Moderne Feinpolitur per CSS (Energie-/Deutschland-Look) ─────────────
st.markdown("""
<style>
.stApp { background:
  radial-gradient(1100px 520px at 16% -8%, #17344f 0%, rgba(13,27,42,0) 60%),
  linear-gradient(180deg, #0d1b2a 0%, #0b1826 100%) fixed; }
.block-container { padding-top: 1.1rem; }

/* Hero */
.de-hero { position:relative; overflow:hidden; border-radius:18px;
  padding:20px 28px 18px 32px; margin:2px 0 16px 0;
  background:linear-gradient(135deg,#0a2540 0%,#123a5c 60%,#0e2b45 100%);
  border:1px solid #23507a; box-shadow:0 10px 30px rgba(0,0,0,.42); }
.de-hero::before { content:""; position:absolute; left:0; top:0; bottom:0; width:7px;
  background:linear-gradient(#141414 0 33.3%,#DD0000 33.3% 66.6%,#FFCE00 66.6% 100%); }
.de-hero h1 { margin:0; color:#ffffff; font-size:1.95rem; font-weight:800; letter-spacing:.2px; }
.de-hero .sub { color:#a9cdf0; margin-top:6px; font-size:.95rem; }
.de-chips { margin-top:12px; }
.de-chip { display:inline-block; background:rgba(74,144,217,.12);
  border:1px solid #2f6ea3; color:#cfe6ff; border-radius:999px;
  padding:4px 13px; margin:0 7px 7px 0; font-size:.78rem; font-weight:600; }

/* KPI-Karten */
[data-testid="stMetric"], div[data-testid="metric-container"] {
  background:linear-gradient(180deg,#122a40 0%,#0f2233 100%);
  border:1px solid #24507a; border-left:4px solid #4A90D9;
  border-radius:14px; padding:14px 18px; box-shadow:0 4px 16px rgba(0,0,0,.30); }
[data-testid="stMetricValue"] { font-weight:800; color:#ffffff; }
[data-testid="stMetricLabel"] { color:#a9cdf0; font-weight:600; }

/* Sidebar */
[data-testid="stSidebar"] { background:#0a1a2b; border-right:1px solid #17324c; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color:#F5A623; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap:5px; }
.stTabs [data-baseweb="tab"] { background:#0f2135; border-radius:10px 10px 0 0;
  padding:7px 14px; color:#a9cdf0; }
.stTabs [aria-selected="true"] { background:#15406a; color:#ffffff;
  box-shadow:inset 0 -2px 0 #4A90D9; }

/* Buttons & Dataframes */
.stButton>button { border-radius:11px; font-weight:700; }
[data-testid="stDataFrame"] { border-radius:12px; overflow:hidden;
  border:1px solid #1c3a55; }
</style>
""", unsafe_allow_html=True)

# Light-Override (nur Hauptbereich – Sidebar & Hero bleiben dunkel; native
# Streamlit-Widgets bleiben ebenfalls dunkel, s. Toggle-Kommentar oben)
if _light:
    st.markdown("""
<style>
.stApp { background:
  radial-gradient(1100px 520px at 16% -8%, #e9f1fb 0%, rgba(244,247,251,0) 60%),
  linear-gradient(180deg, #f4f7fb 0%, #eef3f9 100%) fixed; }
.block-container { color:#1b2b3a; }
.block-container h1, .block-container h2, .block-container h3 { color:#12233a; }
[data-testid="stMetric"], div[data-testid="metric-container"] {
  background:linear-gradient(180deg,#ffffff 0%,#eef3f9 100%);
  border:1px solid #cdd9e6; border-left:4px solid #4A90D9; }
[data-testid="stMetricValue"] { color:#12233a; }
[data-testid="stMetricLabel"] { color:#436184; }
.stTabs [data-baseweb="tab"] { background:#e7eef7; color:#436184; }
.stTabs [aria-selected="true"] { background:#d3e3f4; color:#12233a;
  box-shadow:inset 0 -2px 0 #4A90D9; }
[data-testid="stDataFrame"] { border:1px solid #cdd9e6; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="de-hero">
  <h1>⚡ Deutschland Energy Model
      <span style="color:#9fc3e8;font-weight:600;font-size:1rem;">v1.3</span></h1>
  <div class="sub">Kostenminimales Stromsystem für Deutschland · PyPSA-Kapazitätsausbau</div>
  <div class="de-chips">
    <span class="de-chip">5 Zonen + Offshore</span>
    <span class="de-chip">Sektorkopplung · Wärme + H₂</span>
    <span class="de-chip">CO₂-Budget</span>
    <span class="de-chip">Kapazitätsausbau</span>
    <span class="de-chip">Monte-Carlo</span>
    <span class="de-chip">Kreis 1 · 11 Nachbarn</span>
    <span class="de-chip">+ Kreis 2 · 13</span>
    <span class="de-chip">+ Kreis 3 · 11</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Einheitliche Mono-SVG-Icons für Energieträger (20 px, Strich = Energie-Blau,
#    theme-neutral). Ersetzen Emojis dort, wo Träger visuell gezeigt werden. ──
_SVG = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="#4A90D9" stroke-width="1.9" stroke-linecap="round" '
        'stroke-linejoin="round" style="vertical-align:middle;">{}</svg>')
ICONS = {
    "wind":    _SVG.format('<path d="M3 8h11a3 3 0 1 0-3-3"/>'
                           '<path d="M3 12h7"/>'
                           '<path d="M3 16h15a3 3 0 1 1-3 3"/>'),
    "solar":   _SVG.format('<circle cx="12" cy="12" r="4"/>'
                           '<path d="M12 2v2M12 20v2M2 12h2M20 12h2'
                           'M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4'
                           'M6.4 17.6L5 19"/>'),
    "gas":     _SVG.format('<path d="M12 3c1 3 4 4 4 8a4 4 0 0 1-8 0'
                           'c0-1 .6-2 1.2-2.6C10 9.5 12 7 12 3z"/>'),
    "h2":      _SVG.format('<circle cx="7" cy="12" r="3"/>'
                           '<circle cx="17" cy="12" r="3"/><path d="M10 12h4"/>'),
    "battery": _SVG.format('<rect x="3" y="8" width="15" height="9" rx="1.6"/>'
                           '<path d="M21 11v3"/><path d="M7 12.5h4"/>'),
    "grid":    _SVG.format('<path d="M6 3v18M18 3v18M6 8h12M6 13h12"/>'),
}
_carrier_legend = (
    '<div style="display:flex;flex-wrap:wrap;gap:15px;align-items:center;'
    'margin:-6px 0 14px 3px;font-size:.82rem;color:#6b8299;font-weight:600;">'
    '<span style="opacity:.8;">Energieträger:</span>'
    + "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;">'
        f'{svg}<span>{label}</span></span>'
        for label, svg in [("Wind", ICONS["wind"]), ("Solar", ICONS["solar"]),
                           ("Gas", ICONS["gas"]), ("H₂", ICONS["h2"]),
                           ("Batterie", ICONS["battery"]), ("Netz", ICONS["grid"])])
    + '</div>')
st.markdown(_carrier_legend, unsafe_allow_html=True)

# ----------------------------------------------------------------------
# Sidebar: Szenario-Parameter
# ----------------------------------------------------------------------
sb = st.sidebar
sb.header("🎛️ Szenario")

# ── Parameter in Expandern gruppiert (kompaktere Sidebar). Jedes Widget hat
#    ein key= → Streamlit hält den Zustand über Reruns/Tab-Wechsel hinweg ──
with sb.expander("🌍 Klima", expanded=True):
    co2_budget_mt = st.slider("CO₂-Budget (Mt/a)", 0, 250, 120, step=10,
                              key="co2_budget_mt",
                              help="Jährliches Emissionslimit des Stromsektors")
    co2_price     = st.slider("CO₂-Preis (€/t)", 0, 400, 80, step=10,
                              key="co2_price",
                              help="Aufschlag auf fossile Grenzkosten")
    with st.expander("ℹ️ Budget vs. Preis – was ist der Unterschied?"):
        st.markdown(
            "- **CO₂-Budget** ist eine *harte* Obergrenze: Der Ausstoß des "
            "Stromsektors darf diesen Wert nicht überschreiten. Je kleiner das "
            "Budget, desto mehr muss das Modell auf Erneuerbare umsteigen.\n"
            "- **CO₂-Preis** ist ein *weicher* Anreiz: Er verteuert jede fossil "
            "erzeugte MWh und verschiebt so die Reihenfolge des Kraftwerks-"
            "einsatzes (Merit-Order). Fossile werden unattraktiver, ohne "
            "verboten zu sein.\n\n"
            "Beide wirken zusammen: Das Budget setzt die Grenze, der Preis "
            "steuert, *wie* teuer der Weg dorthin wird.")

with sb.expander("🔌 Nachfrage", expanded=False):
    load_scale = st.slider("Stromlast-Skalierung", 0.7, 1.5, 1.0, step=0.05,
                           key="load_scale",
                           help="Skaliert die elektrische Grundlast")
    heat_scale = st.slider("Wärmelast-Skalierung (Elektrifizierung)",
                           0.3, 1.5, 1.0, step=0.05, key="heat_scale",
                           help="Elektrifizierbare Wärmenachfrage (Wärmepumpen)")

with sb.expander("💰 Ökonomie", expanded=False):
    discount_pct = st.slider("Diskontsatz / WACC (%)", 1.0, 12.0, 7.0, step=0.5,
                             key="discount_pct",
                             help="Kapitalkosten des Zubaus – höher = teurer "
                                  "Ausbau, weniger Neubau erneuerbarer Kapazität")
    gas_price    = st.slider("Gaspreis (€/MWh_th)", 10, 120, 55, step=5,
                             key="gas_price",
                             help="Brennstoffkosten Gas – verschiebt die Merit-Order "
                                  "zwischen Gas, Kohle und Erneuerbaren")
    with st.expander("ℹ️ Warum beeinflusst der Diskontsatz den Ausbau?"):
        st.markdown(
            "Der **Diskontsatz / WACC** (Weighted Average Cost of Capital) sind "
            "die jährlichen Kapitalkosten für neue Anlagen. Da Wind, Solar und "
            "Netze fast nur aus **Investitionskosten** bestehen (kaum Brennstoff), "
            "reagieren sie besonders empfindlich: Ein höherer WACC macht ihren "
            "Zubau teurer, sodass das Modell tendenziell weniger Erneuerbare baut "
            "und länger auf bestehende (fossile) Kraftwerke setzt.")

with sb.expander("🌍 Europa", expanded=False):
    include_neighbors = st.checkbox("Nachbarländer koppeln", value=False,
                                    key="include_neighbors",
                                    help="11 Nachbarländer (FR, BE, LU, NL, DK, PL, "
                                         "CZ, AT, CH, SE, NO) als Ein-Knoten-Modelle "
                                         "mit Import/Export. Nur DE baut aus; "
                                         "CO₂-Budget gilt nur für DE.")
    include_europe = st.checkbox("Kreis 2: weitere Länder", value=False,
                                 disabled=not include_neighbors,
                                 key="include_europe",
                                 help="Koppelt einen 2. Länderkreis mit 13 weiteren "
                                      "(nicht allen!) europäischen Ländern: "
                                      "ES, PT, IT, GB, IE, FI, SK, HU, SI, HR, "
                                      "RO, BG, GR – Kuppelstelle jeweils ans "
                                      "Partnerland (z. B. ES↔FR). Gleiches "
                                      "Prinzip wie die Nachbarländer; Flotten "
                                      "literaturbasiert. Modell wird größer/"
                                      "langsamer.")
    include_kreis3 = st.checkbox("Kreis 3: restliches Europa", value=False,
                                 disabled=not include_europe,
                                 key="include_kreis3",
                                 help="Koppelt einen 3. Länderkreis mit 11 weiteren "
                                      "Ländern des ENTSO-E-Verbundnetzes: Baltikum "
                                      "(EE, LV, LT), Westbalkan (RS, BA, ME, MK, AL, "
                                      "XK), Moldau (MD) und Ukraine (UA). Nur "
                                      "zusammen mit Kreis 2. Flotten literaturbasiert "
                                      "(UA im Kriegskontext besonders unsicher). "
                                      "Modell wird nochmals größer/langsamer.")
    foreign_era5 = st.checkbox("Ausland: ERA5-Wetter", value=False,
                               disabled=not include_neighbors, key="foreign_era5",
                               help="Auslandswetter aus echten ERA5-Daten statt "
                                    "synthetisch. ⚠ Erster Lauf lädt je Land via CDS "
                                    "herunter (dauert, nur lokal mit atlite+CDS-Key). "
                                    "Automatischer Fallback auf synthetisch.")
    if include_neighbors and foreign_era5 and not dm.ATLITE_AVAILABLE:
        st.caption("⚠ atlite nicht verfügbar → Ausland bleibt synthetisch.")

sb.divider()
n_mc   = sb.slider("Monte-Carlo Wetterjahre", 0, 60, 0, key="n_mc",
                   help="Wie viele zufällige Wetterjahre durchgerechnet werden, "
                        "um zu prüfen, wie robust das Ergebnis gegenüber dem "
                        "Wetter ist. 0 = überspringen (schneller). Auswertung im "
                        "Tab „🎲 Monte-Carlo“.")
run_btn = sb.button("🚀 Modell optimieren", type="primary",
                    width="stretch")
sb.caption(f"Solver: {'Gurobi' if dm.USE_GUROBI else 'HiGHS'} · "
           f"Auflösung: {dm.TIME_RES}h · "
           f"Wetter: {'ERA5 möglich' if dm.ATLITE_AVAILABLE else 'synthetisch'}")
with sb.expander("ℹ️ Solver, Auflösung & Wetter"):
    st.markdown(
        "- **Solver** löst das Optimierungsproblem. **HiGHS** ist frei und "
        "vorinstalliert, **Gurobi** ist kommerziell, meist schneller und "
        "robuster bei großen Modellen (braucht eine Lizenz).\n"
        "- **Auflösung** ist der Zeitschritt in Stunden (z. B. 1h = alle 8760 "
        "Stunden, 3h = gröber, aber schneller).\n"
        "- **Wetter**: „ERA5“ nutzt echte Reanalyse-Wetterdaten; "
        "„synthetisch“ bedeutet vereinfachte, generierte Wetterprofile "
        "(wenn ERA5/atlite nicht verfügbar ist).")

# ── Programm-Update per Knopfdruck (git pull, nur Fast-Forward) ──────────
with sb.expander("🔄 Update", expanded=False):
    st.caption("Holt die neueste Version aus dem GitHub-Repo (git pull).")
    if st.button("Programm aktualisieren", key="update_btn"):
        try:
            r = subprocess.run(["git", "pull", "--ff-only"],
                               cwd=dm.SCRIPT_DIR, capture_output=True,
                               text=True, timeout=60)
            out = (r.stdout + r.stderr).strip()
            if r.returncode == 0:
                if "Already up to date" in out or "Bereits aktuell" in out:
                    st.success("✅ Bereits aktuell – kein Update nötig.")
                else:
                    st.success("✅ Update geladen! Bitte die App neu starten "
                               "(launcher\\stop_app.bat, dann Desktop-Icon).")
                    st.code(out or "(keine Ausgabe)", language=None)
            else:
                st.error("❌ Update fehlgeschlagen (lokale Änderungen oder "
                         "kein Netz?).")
                st.code(out or "(keine Ausgabe)", language=None)
        except Exception as e:
            st.error(f"❌ git nicht ausführbar: {e}")

# ----------------------------------------------------------------------
# Modelllauf (gecacht: gleiche Parameter → kein Neurechnen)
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def solve(co2_budget, co2_price, load_scale, heat_scale,
          discount_rate, gas_price, include_neighbors, foreign_era5,
          include_europe=False, include_kreis3=False):
    holder = st.empty()
    bar = holder.progress(0, text="⏳ Starte Optimierung …")
    def _prog(frac, label):
        bar.progress(min(int(frac * 100), 100), text=label)
    net, era5_ok = dm.run_base(co2_budget=co2_budget, co2_price=co2_price,
                               load_scale=load_scale, heat_scale=heat_scale,
                               discount_rate=discount_rate, gas_price=gas_price,
                               include_neighbors=include_neighbors,
                               foreign_era5=foreign_era5, verbose=False,
                               progress=_prog, include_europe=include_europe,
                               include_kreis3=include_kreis3)
    holder.empty()   # Balken nach Fertigstellung ausblenden
    return net, era5_ok

@st.cache_data(show_spinner=False)
def monte_carlo(n_mc, co2_budget, co2_price, include_neighbors):
    holder = st.empty()
    bar = holder.progress(0, text="⏳ Monte-Carlo startet …")
    def _prog(frac, label):
        bar.progress(min(int(frac * 100), 100), text=label)
    df = dm.run_monte_carlo(n_mc=n_mc, co2_budget=co2_budget,
                            co2_price=co2_price,
                            include_neighbors=include_neighbors, progress=_prog)
    holder.empty()
    return df

@st.cache_data(show_spinner=False)
def co2_sweep(prices, co2_budget, include_neighbors, load_scale, heat_scale,
              discount_rate, gas_price, foreign_era5, include_europe):
    holder = st.empty()
    bar = holder.progress(0, text="⏳ CO₂-Preis-Sensitivität startet …")
    def _prog(frac, label):
        bar.progress(min(int(frac * 100), 100), text=label)
    df = dm.run_co2_sweep(prices=prices, co2_budget=co2_budget,
                          include_neighbors=include_neighbors, verbose=False,
                          progress=_prog, load_scale=load_scale,
                          heat_scale=heat_scale, discount_rate=discount_rate,
                          gas_price=gas_price, foreign_era5=foreign_era5,
                          include_europe=include_europe)
    holder.empty()
    return df

@st.cache_data(show_spinner="⏳ Lade Referenzdaten (Ein-Knoten-Modell) …")
def load_ref(sheet, upload_bytes=None, upload_name=None):
    source = None
    if upload_bytes is not None:
        source = io.BytesIO(upload_bytes)
        source.name = upload_name or f"referenz_{sheet}.csv"
    return dm.load_reference(sheet=sheet, source=source)

if "ran" not in st.session_state:
    st.session_state.ran = False
if run_btn:
    st.session_state.ran = True
if not st.session_state.ran:
    st.info("👈 Parameter einstellen und **Modell optimieren** drücken.")
    st.stop()

try:
    n, era5_ok = solve(co2_budget_mt * 1e6, float(co2_price),
                       float(load_scale), float(heat_scale),
                       float(discount_pct) / 100., float(gas_price),
                       bool(include_neighbors), bool(foreign_era5),
                       bool(include_europe), bool(include_kreis3))
except Exception as _solve_err:
    solve.clear()   # kaputtes/leeres Ergebnis nicht cachen
    st.error(f"❌ Optimierung nicht erfolgreich gelöst.\n\n{_solve_err}")
    st.info(
        "**Häufigste Ursache in der Cloud:** ohne Gurobi-Lizenz rechnet HiGHS, "
        "und das volle Stundenmodell (8760 h) ist dafür oft zu groß → Zeit-/"
        "Speicherlimit. Abhilfe:\n"
        "- Gurobi-WLS-Lizenz als **Secret** hinterlegen (dann löst die Cloud wie "
        "lokal), **oder**\n"
        "- die Zeitauflösung vergröbern (`TIME_RES` z. B. auf 3) für ein "
        "kleineres Modell.")
    st.stop()

# ----------------------------------------------------------------------
# KPI-Zeile  (alle Erzeugungs-Kennzahlen auf Deutschland gefiltert)
# ----------------------------------------------------------------------
gekoppelt = dm.has_neighbors(n)
co2 = dm.total_co2(n, dm.DE_AC_BUSES) / 1e6
ee  = dm.re_share(n, dm.DE_AC_BUSES)
preis = n.buses_t.marginal_price[list(dm.REGIONS)].mean().mean()
erz_twh = float(dm.model_energy_by_carrier(n).sum())

# ── KPI-Trend-Historie für Sparklines (max. 15 echte Läufe, eigene Liste,
#    damit der „Läufe"-Tab/runs unangetastet bleibt) ───────────────────────
_ksig = (co2_budget_mt, co2_price, load_scale, heat_scale, discount_pct,
         gas_price, include_neighbors, foreign_era5, include_europe, include_kreis3)
if "kpi_hist" not in st.session_state:
    st.session_state.kpi_hist = []
if st.session_state.get("_kpi_hist_sig") != _ksig:      # nur echte neue Läufe
    st.session_state._kpi_hist_sig = _ksig
    st.session_state.kpi_hist.append(
        {"cost": dm.total_cost(n) / 1e9, "preis": float(preis),
         "co2": co2, "ee": ee, "erz": erz_twh})
    st.session_state.kpi_hist = st.session_state.kpi_hist[-15:]

def _spark(col, key, color):
    """Kompakte Sparkline (px.line, ohne Achsen) unter einer KPI-Metrik.
    Weniger als 2 Datenpunkte → Hinweistext statt Chart."""
    vals = [h[key] for h in st.session_state.kpi_hist]
    if len(vals) < 2:
        col.caption("Noch keine Trend-Daten – mehrfach optimieren")
        return
    sf = px.line(y=vals)
    sf.update_traces(line=dict(color=color, width=2))
    sf.update_layout(height=40, margin=dict(l=0, r=0, t=0, b=0),
                     showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                     plot_bgcolor="rgba(0,0,0,0)",
                     xaxis=dict(visible=False), yaxis=dict(visible=False))
    col.plotly_chart(sf, width="stretch", config={"displayModeBar": False})

# KPIs zweizeilig (3 + 2) statt fünfspaltig → auf schmalen/mobilen Viewports lesbar
kpi_r1 = st.columns(3)
kpi_r2 = st.columns(2)
kpi_r1[0].metric("Gesamtkosten", f"{dm.total_cost(n)/1e9:,.2f} Mrd €/a",
                 help="Annualisierte Systemkosten (variabler + konstanter Zielfunktions-"
                      "teil). Bei gekoppelten Nachbarn = Kosten des Gesamtsystems DE+Ausland.")
_spark(kpi_r1[0], "cost", "#4A90D9")
kpi_r1[1].metric("Ø Strompreis DE", f"{preis:,.1f} €/MWh",
                 help="Mittlerer Knoten-Strompreis über alle Zonen und Stunden. "
                      "Entspricht dem Schattenpreis (Grenzkosten) der "
                      "Stromversorgung – nicht dem Endkundenpreis.")
_spark(kpi_r1[1], "preis", "#F5A623")
kpi_r1[2].metric("CO₂-Emissionen DE", f"{co2:,.1f} Mt/a",
                 delta=f"{co2 - co2_budget_mt:+.1f} vs. Budget", delta_color="inverse",
                 help="Tatsächlicher CO₂-Ausstoß des deutschen Stromsektors. "
                      "Der Delta-Wert zeigt den Abstand zum eingestellten "
                      "CO₂-Budget (negativ = Budget eingehalten).")
_spark(kpi_r1[2], "co2", "#e06666")
kpi_r2[0].metric("EE-Anteil DE", f"{ee:,.1f} %",
                 help="Anteil erneuerbarer Energien (Wind, Solar, Wasser, "
                      "Biomasse) an der deutschen Jahreserzeugung.")
_spark(kpi_r2[0], "ee", "#6bcb77")
kpi_r2[1].metric("Erzeugung DE", f"{erz_twh:,.0f} TWh/a",
                 help="Tatsächlich erzeugte Strommenge pro Jahr (Energie in TWh) "
                      "– nicht zu verwechseln mit der installierten Leistung "
                      "(GW) im Tab „🏗️ Kapazitäten“.")
_spark(kpi_r2[1], "erz", "#B0BEC5")
if not era5_ok:
    st.caption("⚠ Synthetische Wetterdaten (atlite/ERA5 nicht verfügbar)")
if gekoppelt:
    st.caption("🌍 **Nachbarländer gekoppelt** – Erzeugungs-KPIs (CO₂, EE, "
               "Erzeugung) zeigen **nur Deutschland**; die Gesamtkosten umfassen "
               "das gekoppelte Gesamtsystem. Import/Export im Tab **🌍 Nachbarn**.")

FARBEN = dm.CARRIER_COLORS

def _csv_download(df, index=False):
    """DataFrame → CSV-Bytes (utf-8-sig, ';' + ',' als Dezimaltrenner →
    öffnet sich in deutschem Excel ohne Import-Dialog)."""
    return df.to_csv(index=index, sep=";", decimal=",").encode("utf-8-sig")

# ── Lauf-Historie (max. 5) für den Vergleich im Tab „Läufe" ──────────────
if "runs" not in st.session_state:
    st.session_state.runs = []
_sig = (co2_budget_mt, co2_price, load_scale, heat_scale, discount_pct,
        gas_price, include_neighbors, foreign_era5, include_europe, include_kreis3)
if st.session_state.get("_last_run_sig") != _sig:   # nur echte neue Läufe erfassen
    st.session_state._last_run_sig = _sig
    st.session_state.runs.append({
        "Zeit": pd.Timestamp.now().strftime("%H:%M:%S"),
        "Kosten (Mrd €/a)": round(dm.total_cost(n) / 1e9, 2),
        "CO₂ (Mt/a)": round(co2, 1),
        "EE (%)": round(ee, 1),
        "Erzeugung (TWh/a)": round(erz_twh, 0),
        "CO₂-Budget": co2_budget_mt, "CO₂-Preis": co2_price,
        "Last": load_scale, "Wärme": heat_scale, "WACC (%)": discount_pct,
        "Gas": gas_price,
        "Nachbarn": (("Kreis 3" if include_kreis3 else "Kreis 2") if include_europe
                     else "ja") if include_neighbors else "nein",
    })
    st.session_state.runs = st.session_state.runs[-5:]   # nur die letzten 5 behalten

# ── Auto-Erklärung des aktuellen Laufs (reine String-Formatierung, kein LLM) ──
if st.button("🧑‍🏫 Ergebnis erklären", key="explain_btn"):
    _lbl = {"wind": "Windkraft", "solar": "Solar", "hydro": "Wasserkraft",
            "gas": "Gas", "lignite": "Braunkohle", "hardcoal": "Steinkohle",
            "biomass": "Biomasse", "oil": "Öl", "nuclear": "Kernkraft"}
    _en = dm.model_energy_by_carrier(n)
    _dom = _en.idxmax()
    _dom_pct = 100. * _en.max() / _en.sum() if _en.sum() > 0 else 0.
    _zu = {}   # Netto-Zubau [GW] je deutscher Zone (Optimiert − Start)
    for _g in dm.de_generators(n).index:
        _b = n.generators.bus[_g]
        _zu[_b] = _zu.get(_b, 0.) + max(dm._pnom(n.generators, _g)
                                        - n.generators.p_nom[_g], 0.) / 1000.
    _zone = max(_zu, key=_zu.get) if _zu else "—"
    st.info(
        f"In diesem Szenario deckt **{_lbl.get(_dom, _dom)}** mit {_dom_pct:.0f} % "
        f"den größten Teil der deutschen Stromerzeugung. Die annualisierten "
        f"Gesamtkosten liegen bei {dm.total_cost(n)/1e9:.1f} Mrd €/a, der EE-Anteil "
        f"beträgt {ee:.0f} % bei {co2:.0f} Mt CO₂/a. Der stärkste Kapazitätszubau "
        f"erfolgt in der Zone **{_zone}** (+{_zu.get(_zone, 0.):.1f} GW). Insgesamt "
        f"werden rund {erz_twh:.0f} TWh/a erzeugt.")

(tab_disp, tab_kap, tab_preis, tab_spei, tab_karte, tab_eng,
 tab_vgl, tab_nb, tab_mc, tab_co2sw, tab_runs, tab_pdf) = st.tabs(
    ["📊 Dispatch", "🏗️ Kapazitäten", "💶 Preise", "🔋 Speicher & H₂",
     "🗺️ Karte", "🚧 Engpässe", "⚖️ Vergleich", "🌍 Nachbarn",
     "🎲 Monte-Carlo", "📈 CO₂-Preis", "📊 Läufe", "📄 Bericht"])

# ── Dispatch ──────────────────────────────────────────────────────────
with tab_disp:
    st.info("Stündliche Stromerzeugung je Energieträger für eine gewählte "
            "Woche, im Vergleich zur Stromlast.")
    woche = st.select_slider("Woche im Jahr", options=list(range(1, 53)), value=2)
    steps = 7 * 24 // dm.TIME_RES
    sl = slice((woche - 1) * steps, woche * steps)
    gen = dm.model_gen_hourly(n).iloc[sl] / 1000.   # nur DE-Erzeuger
    fig = px.area(gen, color_discrete_map=FARBEN,
                  labels={"value": "Leistung (GW)", "snapshot": ""})
    last = n.loads_t.p_set[[f"Last_{r}" for r in dm.REGIONS]].sum(axis=1).iloc[sl] / 1000.
    fig.add_scatter(x=last.index, y=last, name="Stromlast",
                    line=dict(color="white", dash="dot"))
    st.plotly_chart(fig, width="stretch")

# ── Kapazitäten ───────────────────────────────────────────────────────
with tab_kap:
    st.info("Optimierter Kraftwerks-Zubau und Jahreserzeugung je Träger sowie "
            "der Netz- und Sektorkopplungs-Ausbau.")
    st.caption("**Leistung (GW)** = installierte Kapazität (was maximal "
               "möglich ist). **Erzeugung (TWh)** = tatsächlich pro Jahr "
               "produzierte Energie. Solar hat z. B. viel GW, liefert aber "
               "wegen Nacht/Wetter weniger TWh als die Leistung vermuten lässt.")
    if gekoppelt:
        st.caption("Nur **deutsche** Erzeuger (Nachbarländer sind feste "
                   "Randbedingung, kein Ausbau).")
    deg = dm.de_generators(n)
    c1, c2 = st.columns(2)
    caps = pd.DataFrame({
        "Anlage": deg.index,
        "Träger": deg.carrier.values,
        "Start (GW)": deg.p_nom.values / 1000.,
        "Optimiert (GW)": [dm._pnom(n.generators, g) / 1000.
                           for g in deg.index]})
    caps["Zubau (GW)"] = (caps["Optimiert (GW)"] - caps["Start (GW)"]).round(2)
    with c1:
        fig = px.bar(caps, x="Optimiert (GW)", y="Anlage", color="Träger",
                     orientation="h", color_discrete_map=FARBEN)
        st.plotly_chart(fig, width="stretch")
    with c2:
        en = dm.model_energy_by_carrier(n)
        st.plotly_chart(px.pie(values=en.values, names=en.index,
                               color=en.index, color_discrete_map=FARBEN,
                               title="Jahreserzeugung (TWh)"),
                        width="stretch")
        st.dataframe(caps.round(2), width="stretch", hide_index=True)
        st.download_button("⬇️ Kapazitäten als CSV",
                           _csv_download(caps.round(2)),
                           "kapazitaeten_deutschland.csv", "text/csv",
                           key="dl_caps")
    st.subheader("Netz- & Sektorkopplungs-Ausbau")
    st.caption("**Sektorkopplung** verbindet den Stromsektor mit Wärme und "
               "Wasserstoff: **Wärmepumpen** wandeln Strom in Wärme, "
               "**Elektrolyseure** in H₂ (speicherbar), **Brennstoffzellen** "
               "H₂ zurück in Strom. So kann überschüssiger Wind-/Solarstrom "
               "genutzt statt abgeregelt werden.")
    netz = pd.DataFrame({
        "Leitung": n.lines.index,
        "Start (GW)": n.lines.s_nom.values / 1000.,
        "Optimiert (GW)": n.lines.s_nom_opt.values / 1000.})
    netz["Zubau (GW)"] = (netz["Optimiert (GW)"] - netz["Start (GW)"]).round(2)
    l1, l2 = st.columns(2)
    l1.dataframe(netz.round(2), width="stretch", hide_index=True)
    l1.download_button("⬇️ Netzausbau als CSV", _csv_download(netz.round(2)),
                       "netzausbau_deutschland.csv", "text/csv", key="dl_netz")
    sekt = pd.DataFrame({
        "Komponente": ["Elektrolyseur", "Brennstoffzelle", "H₂-Tank"]
                      + [f"Wärmepumpe {r}" for r in dm.REGIONS],
        "Optimiert": [f"{dm._pnom(n.links,'Elektrolyseur')/1000:.1f} GW",
                      f"{dm._pnom(n.links,'Brennstoffzelle')/1000:.1f} GW",
                      f"{n.stores.e_nom_opt['H2_Tank']/1000:.0f} GWh"]
                     + [f"{dm._pnom(n.links, f'WP_{r}')/1000:.1f} GW"
                        for r in dm.REGIONS]})
    l2.dataframe(sekt, width="stretch", hide_index=True)

# ── Preise ────────────────────────────────────────────────────────────
with tab_preis:
    st.info("Regionale Knoten-Strompreise als Zeitverlauf, Verteilung und "
            "Monatsmittel.")
    preise = n.buses_t.marginal_price[list(dm.REGIONS)]
    st.plotly_chart(px.line(preise, labels={"value": "€/MWh", "snapshot": ""}),
                    width="stretch")
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.box(preise, labels={"value": "€/MWh"},
                           title="Preisverteilung je Region"),
                    width="stretch")
    monat = preise.resample("ME").mean()
    monat.index = monat.index.strftime("%b")
    c2.plotly_chart(px.imshow(monat.T, aspect="auto",
                              labels=dict(color="€/MWh"),
                              title="Ø Monatspreise je Region"),
                    width="stretch")
    st.download_button("⬇️ Regionale Preise (stündlich) als CSV",
                       _csv_download(preise, index=True),
                       "preise_deutschland.csv", "text/csv", key="dl_preise")

# ── Speicher & H₂ ─────────────────────────────────────────────────────
with tab_spei:
    st.info("Füllstände von Batterien, Pumpspeicher, H₂-Tank und "
            "Wärmespeichern über das Jahr.")
    c1, c2 = st.columns(2)
    soc = n.storage_units_t.state_of_charge / 1000.
    c1.plotly_chart(px.line(soc, title="Batterien & Pumpspeicher (GWh)"),
                    width="stretch")
    h2 = n.stores_t.e["H2_Tank"] / 1000.
    figh = px.area(h2, title="H₂-Tank Füllstand (GWh)")
    figh.update_traces(line_color="#B57EDC")
    c2.plotly_chart(figh, width="stretch")
    waerme = n.stores_t.e[[f"WaermeSpeicher_{r}" for r in dm.REGIONS]] / 1000.
    st.plotly_chart(px.line(waerme, title="Wärmespeicher (GWh)"),
                    width="stretch")
    st.download_button("⬇️ Speicherfüllstände (SoC) als CSV",
                       _csv_download(soc, index=True),
                       "speicher_soc_deutschland.csv", "text/csv", key="dl_soc")

# ── Karte ─────────────────────────────────────────────────────────────
with tab_karte:
    st.info("Geografische Karte der Zonen, Leitungen (Auslastungs-Ampel) und – "
            "bei Kopplung – der Nachbarländer mit Kuppelstellen.")
    def _util(p):   # Ampelfarbe nach mittlerer Auslastung
        return "#6bcb77" if p < 50 else ("#ffd93d" if p < 80 else "#ff6b6b")
    fig = go.Figure()
    # ── Übertragungsleitungen (Farbe = Auslastung, Breite ∝ Kapazität) ──
    for ln, row in n.lines.iterrows():
        cap = float(row.s_nom_opt) or 1.
        pct = 100. * abs(n.lines_t.p0[ln]).mean() / cap
        fig.add_trace(go.Scattermap(
            lon=[n.buses.at[row.bus0, "x"], n.buses.at[row.bus1, "x"]],
            lat=[n.buses.at[row.bus0, "y"], n.buses.at[row.bus1, "y"]],
            mode="lines", opacity=0.85, hoverinfo="skip",
            line=dict(width=max(2, cap / 3000), color=_util(pct)),
            name=f"{ln}: {cap/1000:.1f} GW | {pct:.0f}%"))
    busse = list(dm.REGIONS) + ["Offshore"]
    texte = []
    for b in busse:
        cap = sum(dm._pnom(n.generators, g) for g in n.generators.index
                  if n.generators.bus[g] == b) / 1000.
        texte.append(f"<b>{b}</b><br>{cap:.0f} GW installiert")
    fig.add_trace(go.Scattermap(
        lon=[n.buses.at[b, "x"] for b in busse],
        lat=[n.buses.at[b, "y"] for b in busse],
        text=busse, hovertext=texte, hoverinfo="text",
        mode="markers+text", textposition="top center",
        textfont=dict(color="white", size=12),
        marker=dict(size=17, color=["#00BCD4", "#E040FB", "#FF9800",
                                    "#8BC34A", "#4A90D9"]),
        name="Regionen"))

    # Nachbarländer + Kuppelstellen (nur bei Kopplung)
    if gekoppelt:
        netimp = dm.neighbor_net_import_twh(n)
        for lk in [c for c in n.links.index if c.startswith("IC_")]:
            b0, b1 = n.links.at[lk, "bus0"], n.links.at[lk, "bus1"]
            cap = float(n.links.at[lk, "p_nom"]) or 1.
            pct = 100. * abs(n.links_t.p0[lk]).mean() / cap
            fig.add_trace(go.Scattermap(
                lon=[n.buses.at[b0, "x"], n.buses.at[b1, "x"]],
                lat=[n.buses.at[b0, "y"], n.buses.at[b1, "y"]],
                mode="lines", opacity=0.55, hoverinfo="skip",
                line=dict(width=max(1.5, cap / 2500), color=_util(pct)),
                name=f"{lk[3:]}: NTC {cap/1000:.1f} GW | {pct:.0f}%"))
        # alle gekoppelten Auslandsknoten (Nachbarn + ggf. 2. Länderring)
        ccs = [cc for cc in dm.ALL_FOREIGN if cc in n.buses.index]
        cc_txt = []
        for cc in ccs:
            imp = float(netimp.get(cc, 0.))
            inst = sum(dm.ALL_FOREIGN[cc]["fleet"].values()) / 1000.
            rich = "Import" if imp >= 0 else "Export"
            cc_txt.append(f"<b>{cc}</b><br>{inst:.0f} GW installiert<br>"
                          f"Netto-{rich}: {abs(imp):.1f} TWh/a")
        fig.add_trace(go.Scattermap(
            lon=[dm.ALL_FOREIGN[cc]["x"] for cc in ccs],
            lat=[dm.ALL_FOREIGN[cc]["y"] for cc in ccs],
            text=ccs, hovertext=cc_txt, hoverinfo="text",
            mode="markers+text", textposition="top center",
            textfont=dict(color="#cfd8dc", size=11),
            marker=dict(size=13, color="#B0BEC5"),
            name="Nachbarländer"))

    kreis3 = gekoppelt and any(cc in n.buses.index for cc in dm.EUROPE3)
    europa = gekoppelt and any(cc in n.buses.index for cc in dm.EUROPE2)
    center = (dict(lat=49.5, lon=18.0) if kreis3 else
              dict(lat=50.0, lon=10.0) if europa else
              dict(lat=54.0, lon=11.0) if gekoppelt else
              dict(lat=51.1, lon=10.3))
    zoom = 2.3 if kreis3 else 2.7 if europa else 3.6 if gekoppelt else 4.7
    fig.update_layout(
        map=dict(style="carto-darkmatter", center=center, zoom=zoom),
        height=660, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="#0d1b2a", legend_font_color="white",
        legend=dict(bgcolor="rgba(10,20,32,0.55)"))
    st.plotly_chart(fig, width="stretch")
    st.caption("Echtes Kartenmaterial (Carto Dark) · Linienfarbe = mittlere "
               "Auslastung: 🟢 <50 % · 🟡 50–80 % · 🔴 >80 % · Breite ∝ Kapazität · "
               "dünn/transparent = Kuppelstellen (NTC). ⚠ Kacheln brauchen "
               "Internet.")

# ── Engpässe & Schattenpreise ─────────────────────────────────────────
with tab_eng:
    st.info("Schattenpreise: wo Leitungen und Kraftwerke am Limit laufen, plus "
            "die Sektorpreise für Wärme und H₂.")
    # abs(): linopy liefert Duale von Obergrenzen mit negativem Vorzeichen
    mu_line = getattr(n.lines_t, "mu_upper", pd.DataFrame()).abs()
    mu_gen  = getattr(n.generators_t, "mu_upper", pd.DataFrame()).abs()
    if mu_line.empty and mu_gen.empty:
        st.warning("Keine Schattenpreise im Ergebnis – der gecachte Lauf "
                   "stammt noch von vor der Umstellung auf "
                   "`assign_all_duals=True`. Einmal neu rechnen:")
        if st.button("🔄 Cache leeren & neu optimieren"):
            solve.clear()
            st.rerun()
        st.stop()

    st.subheader("Leitungsengpässe")
    st.caption("Schattenpreis = Systemkosten-Ersparnis pro zusätzlichem MW "
               "Leitungskapazität in dieser Stunde (€/MWh)")
    eng = pd.DataFrame({
        "Leitung": n.lines.index,
        "Kapazität (GW)": n.lines.s_nom_opt.values / 1000.,
        "Ø Auslastung (%)": [
            100. * abs(n.lines_t.p0[ln]).mean()
            / max(float(n.lines.s_nom_opt[ln]), 1.) for ln in n.lines.index],
        "Engpass-Stunden (h/a)": [
            int((mu_line[ln] > 0.01).sum()) * dm.TIME_RES
            if ln in mu_line else 0 for ln in n.lines.index],
        "Ø Schattenpreis (€/MWh)": mu_line.mean().reindex(n.lines.index).values,
        "Max (€/MWh)": mu_line.max().reindex(n.lines.index).values})
    eng = eng.sort_values("Engpass-Stunden (h/a)", ascending=False)
    c1, c2 = st.columns(2)
    c1.dataframe(eng.round(2), width="stretch", hide_index=True)
    c2.plotly_chart(px.bar(eng, x="Leitung", y="Engpass-Stunden (h/a)",
                           color="Ø Schattenpreis (€/MWh)",
                           color_continuous_scale="OrRd",
                           title="Stunden am Kapazitätslimit"),
                    width="stretch")
    if not mu_line.empty:
        wo_l = mu_line.resample("W").mean()
        st.plotly_chart(px.line(wo_l, labels={"value": "€/MWh", "snapshot": ""},
                                title="Leitungs-Schattenpreise (Wochenmittel)"),
                        width="stretch")

    st.subheader("Kapazitätsknappheit der Erzeuger")
    st.caption("Wert eines zusätzlichen MW Erzeugungskapazität, wenn die "
               "Anlage an ihrer Leistungsgrenze läuft")
    knapp = pd.DataFrame({
        "Anlage": mu_gen.columns,
        "Träger": n.generators.carrier.reindex(mu_gen.columns).values,
        "Knappe Stunden (h/a)": (mu_gen > 0.01).sum().values * dm.TIME_RES,
        "Ø Schattenpreis (€/MWh)": mu_gen.mean().values,
        "Max (€/MWh)": mu_gen.max().values})
    knapp = knapp.sort_values("Ø Schattenpreis (€/MWh)",
                              ascending=False).reset_index(drop=True)
    c1, c2 = st.columns(2)
    c1.dataframe(knapp.round(2), width="stretch", hide_index=True)
    c2.plotly_chart(px.bar(knapp.head(12), x="Ø Schattenpreis (€/MWh)",
                           y="Anlage", color="Träger", orientation="h",
                           color_discrete_map=FARBEN,
                           title="Top 12 nach Ø Schattenpreis"),
                    width="stretch")

    st.subheader("Sektorpreise (Knotenpreise Wärme & H₂)")
    st.caption("Grenzkosten einer zusätzlichen MWh Wärme bzw. Wasserstoff – "
               "das Preissignal der Sektorkopplung")
    sektor = n.buses_t.marginal_price[
        ["H2_Bus"] + [f"Waerme_{r}" for r in dm.REGIONS]]
    wo_s = sektor.resample("W").mean()
    st.plotly_chart(px.line(wo_s, labels={"value": "€/MWh", "snapshot": ""},
                            title="H₂- und Wärmepreise (Wochenmittel)"),
                    width="stretch")

# ── Vergleich: 5-Zonen-Modell vs. Ein-Knoten-Referenz (Excel) ─────────
with tab_vgl:
    st.info("Gegenüberstellung des 5-Zonen-Modells mit dem Ein-Knoten-"
            "Referenzmodell (Excel).")
    st.subheader("⚖️ 5-Zonen-Modell vs. Ein-Knoten-Referenz")
    st.caption("Vergleich des aktuell optimierten 5-Zonen-Modells mit dem "
               "Ein-Knoten-Deutschland-Modell aus der Excel "
               "(Dispatch-Zeitreihen, Verbrauch 2026, ERA5-Wetter 2007/2009).")
    with st.expander("ℹ️ Was zeigt dieser Vergleich?"):
        st.markdown(
            "- Das **5-Zonen-Modell** teilt Deutschland in 5 Regionen mit "
            "Leitungen dazwischen – es kann so **Netzengpässe** und regionale "
            "Preisunterschiede abbilden.\n"
            "- Das **Ein-Knoten-Modell** (Referenz aus Excel) behandelt ganz "
            "Deutschland als einen Punkt ohne interne Netzgrenzen ("
            "„Kupferplatte“).\n\n"
            "Die Gegenüberstellung zeigt, wie sehr die räumliche Auflösung das "
            "Ergebnis verändert. Achtung: Beide nutzen verschiedene Wetterjahre, "
            "daher sind Abweichungen teils wetter- und teils modellbedingt.")

    jahr = st.radio("Wetterjahr der Referenz", dm.REFERENCE_SHEETS,
                    horizontal=True,
                    help="ERA5-Wetterjahr des Ein-Knoten-Modells")
    up = st.file_uploader(
        "Referenzdaten hochladen (optional – CSV oder XLSX)",
        type=["csv", "xlsx"], key="ref_upload",
        help="Lokal werden die Daten automatisch aus dem Ordner "
             "`Referenzdaten/` geladen. In der Cloud (kein lokaler Datenzugriff) "
             "hier die passende Datei des gewählten Wetterjahres hochladen.")
    if up is None and not dm.reference_available(jahr):
        st.info("Keine lokalen Referenzdaten für dieses Wetterjahr gefunden. "
                "Bitte oben die passende CSV/XLSX des Ein-Knoten-Modells "
                "hochladen (z. B. `referenz_2007.csv`).")
    else:
        ref = load_ref(jahr,
                       up.getvalue() if up is not None else None,
                       up.name if up is not None else None)
        rk = ref["kpi"]

        # Modell-KPIs (aus dem gelösten Netz)
        m_erz = dm.model_energy_by_carrier(n)
        m_last_series = n.loads_t.p_set[[f"Last_{r}" for r in dm.REGIONS]].sum(axis=1)
        m_last_twh = float(m_last_series.sum() * dm.TIME_RES / 1e6)
        m_peak_gw  = float(m_last_series.max() / 1000.)

        # ── KPI-Gegenüberstellung ────────────────────────────────────
        st.markdown("##### Kennzahlen im Vergleich")
        vgl = pd.DataFrame({
            "Kennzahl": ["Erzeugung (TWh/a)", "Stromlast (TWh/a)",
                         "EE-Anteil (%)", "CO₂ vergleichbar (Mt/a)",
                         "Peak-Last (GW)"],
            "5-Zonen-Modell": [float(m_erz.sum()), m_last_twh, ee, co2, m_peak_gw],
            f"Referenz {jahr}": [rk["erzeugung_twh"], rk["last_twh"],
                                 rk["ee_pct"], rk["co2_mt"], rk["peak_last_gw"]],
        })
        vgl["Δ (Modell − Ref.)"] = vgl["5-Zonen-Modell"] - vgl[f"Referenz {jahr}"]
        c1, c2, c3 = st.columns(3)
        c1.metric("EE-Anteil Modell", f"{ee:,.1f} %",
                  delta=f"{ee - rk['ee_pct']:+.1f} pp vs. Ref.")
        c2.metric("CO₂ Modell", f"{co2:,.1f} Mt/a",
                  delta=f"{co2 - rk['co2_mt']:+.1f} vs. Ref.",
                  delta_color="inverse")
        c3.metric("Erzeugung Modell", f"{m_erz.sum():,.0f} TWh/a",
                  delta=f"{m_erz.sum() - rk['erzeugung_twh']:+.0f} vs. Ref.")
        st.dataframe(vgl.round(2), width="stretch", hide_index=True)
        st.caption("CO₂ „vergleichbar\" = mit identischen Emissionsfaktoren "
                   "(Gas 0,37 · Steinkohle 0,8 · Braunkohle 1,0 · Öl 0,65 t/MWh) "
                   "aus dem Dispatch berechnet. Kosten werden nicht verglichen, "
                   "da die Excel keine Kostendaten enthält.")

        # ── Erzeugungsmix je Träger ──────────────────────────────────
        st.markdown("##### Jahreserzeugung je Träger (TWh)")
        traeger = sorted(set(m_erz.index) | set(ref["energy_twh"].index))
        mix = pd.DataFrame({
            "Träger": traeger,
            "5-Zonen-Modell": [float(m_erz.get(t, 0.)) for t in traeger],
            f"Referenz {jahr}": [float(ref["energy_twh"].get(t, 0.)) for t in traeger],
        })
        mix_long = mix.melt(id_vars="Träger", var_name="Modell", value_name="TWh")
        fig = px.bar(mix_long, x="Träger", y="TWh", color="Modell",
                     barmode="group",
                     color_discrete_map={"5-Zonen-Modell": "#4A90D9",
                                         f"Referenz {jahr}": "#E8734C"})
        st.plotly_chart(fig, width="stretch")
        st.caption("Träger wie **biomass, waste, oil, other** existieren nur im "
                   "Ein-Knoten-Modell; **battery/H₂/Pumpspeicher** des 5-Zonen-"
                   "Modells sind hier keine Generatoren und daher nicht im Mix.")

        # ── Zeitreihen-Overlay ───────────────────────────────────────
        st.markdown("##### Dispatch-Overlay (Stunde des Jahres)")
        m_hourly = dm.model_gen_hourly(n)
        r_hourly = ref["gen_hourly"]
        opt_carrier = sorted(set(m_hourly.columns) | set(r_hourly.columns))
        col_a, col_b = st.columns([1, 1])
        auswahl = col_a.selectbox(
            "Größe", ["Gesamterzeugung", "Stromlast", "EE (Wind+Solar+Hydro)"]
            + opt_carrier)
        woche = col_b.select_slider("Woche im Jahr",
                                    options=list(range(1, 53)), value=2,
                                    key="woche_vergleich")
        steps = 7 * 24 // dm.TIME_RES
        sl = slice((woche - 1) * steps, woche * steps)

        def _series(kind):
            """(Modell-Serie GW, Referenz-Serie GW) für die gewählte Größe."""
            ee_c = ["wind", "solar", "hydro"]
            if kind == "Gesamterzeugung":
                return m_hourly.sum(axis=1), r_hourly.sum(axis=1)
            if kind == "Stromlast":
                return m_last_series, ref["load"]
            if kind == "EE (Wind+Solar+Hydro)":
                m = m_hourly[[c for c in ee_c if c in m_hourly]].sum(axis=1)
                r = r_hourly[[c for c in ee_c if c in r_hourly]].sum(axis=1)
                return m, r
            z = pd.Series(0., index=m_hourly.index)
            m = m_hourly[kind] if kind in m_hourly else z
            r = r_hourly[kind] if kind in r_hourly else pd.Series(0., index=r_hourly.index)
            return m, r

        m_s, r_s = _series(auswahl)
        ov = pd.DataFrame({
            "5-Zonen-Modell": m_s.iloc[sl].to_numpy() / 1000.,
            f"Referenz {jahr}": r_s.iloc[sl].to_numpy() / 1000.,
        }, index=m_hourly.index[sl])
        figo = px.line(ov, labels={"value": "GW", "index": "", "snapshot": ""},
                       color_discrete_map={"5-Zonen-Modell": "#4A90D9",
                                           f"Referenz {jahr}": "#E8734C"})
        st.plotly_chart(figo, width="stretch")
        st.caption("Beide Modelle nutzen unterschiedliche Wetterjahre – die "
                   "Kurven sind positionsweise über die **Stunde des Jahres** "
                   "gelegt, nicht über das Kalenderdatum.")

# ── Nachbarländer: Import / Export ────────────────────────────────────
with tab_nb:
    st.info("Grenzüberschreitender Import/Export mit den gekoppelten "
            "Nachbarländern.")
    st.subheader("🌍 Grenzüberschreitender Handel mit den Nachbarländern")
    if not gekoppelt:
        st.info("Nachbarländer sind nicht gekoppelt. In der Sidebar unter "
                "**🌍 Europa** die Option **Nachbarländer koppeln** aktivieren "
                "und erneut optimieren.")
    else:
        imp = dm.neighbor_flows(n)                    # MW, + = Import nach DE
        netimp = dm.neighbor_net_import_twh(n)        # TWh/a je Land
        c1, c2, c3 = st.columns(3)
        c1.metric("Netto-Import DE", f"{netimp.sum():,.1f} TWh/a",
                  help="Summe über alle Grenzen (+ = Deutschland importiert netto)")
        c2.metric("Import (Bezug)", f"{imp.clip(lower=0).sum().sum()*dm.TIME_RES/1e6:,.0f} TWh/a")
        c3.metric("Export (Abgabe)", f"{-imp.clip(upper=0).sum().sum()*dm.TIME_RES/1e6:,.0f} TWh/a")

        bilanz = pd.DataFrame({
            "Land": netimp.index,
            "Netto-Import (TWh/a)": netimp.values,
        }).sort_values("Netto-Import (TWh/a)")
        f1 = px.bar(bilanz, x="Netto-Import (TWh/a)", y="Land", orientation="h",
                    color="Netto-Import (TWh/a)", color_continuous_scale="RdBu",
                    title="Jahres-Nettobilanz je Land (+ Import / − Export)")
        st.plotly_chart(f1, width="stretch")

        st.markdown("##### Kuppelstellen-Fluss über eine Woche")
        woche_nb = st.select_slider("Woche im Jahr", options=list(range(1, 53)),
                                    value=2, key="woche_nachbarn")
        steps = 7 * 24 // dm.TIME_RES
        sl = slice((woche_nb - 1) * steps, woche_nb * steps)
        f2 = px.line((imp.iloc[sl] / 1000.),
                     labels={"value": "Import nach DE (GW)", "snapshot": ""})
        st.plotly_chart(f2, width="stretch")
        st.caption("Positiv = Deutschland importiert, negativ = Deutschland "
                   "exportiert. Kapazität je Grenze ist die NTC (Net Transfer "
                   "Capacity). ⚠ Nachbardaten sind grobe ~2023-Näherungen.")

# ── Monte-Carlo ───────────────────────────────────────────────────────
with tab_mc:
    st.info("Streuung von Kosten, CO₂ und EE-Anteil über mehrere zufällige "
            "Wetterjahre (Robustheitsprüfung).")
    with st.expander("ℹ️ Was bedeutet das Ergebnis?"):
        st.markdown(
            "Wind und Sonne schwanken von Jahr zu Jahr. Monte-Carlo rechnet "
            "dasselbe Szenario mit mehreren zufälligen Wetterjahren durch und "
            "zeigt so, **wie stark das Ergebnis vom Wetter abhängt**.\n\n"
            "- Ein **kleiner** Streubereich (± / Standardabweichung) heißt: Das "
            "Ergebnis ist **robust** und kaum wetterabhängig.\n"
            "- Ein **großer** Streubereich heißt: Das Wetterjahr entscheidet "
            "spürbar mit – ein einzelner Lauf ist dann weniger aussagekräftig.")
    if n_mc == 0:
        st.info("Monte-Carlo in der Sidebar aktivieren (Wetterjahre > 0) "
                "und erneut optimieren.")
    else:
        mc_df = monte_carlo(n_mc, co2_budget_mt * 1e6, float(co2_price),
                            bool(include_neighbors))
        st.dataframe(mc_df.round(2), width="stretch", hide_index=True)
        valid = mc_df.dropna()
        if not valid.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Ø Kosten", f"{valid.Kosten_MrdEa.mean():.2f} Mrd €/a",
                      f"±{valid.Kosten_MrdEa.std():.2f}")
            c2.metric("Ø CO₂", f"{valid.CO2_Mt.mean():.1f} Mt/a")
            c3.metric("Ø EE-Anteil", f"{valid.RE_Anteil_pct.mean():.1f} %")
            st.plotly_chart(px.bar(valid, x="Jahr", y="Kosten_MrdEa",
                                   title="Kosten je Wetterjahr (Mrd €/a)"),
                            width="stretch")

# ── CO₂-Preis-Sensitivität ────────────────────────────────────
with tab_co2sw:
    st.info("Sensitivitätsanalyse: Systemkosten, CO₂ und EE-Anteil über einen "
            "Bereich von CO₂-Preisen.")

    # ── Sidebar-Bereich für CO₂-Sweep-spezifische Parameter ──────────
    st.subheader("⚙️ Parameter für CO₂-Preis-Sweep")
    col1, col2 = st.columns(2)
    with col1:
        co2_sweep_min = st.number_input("CO₂-Preis Min (€/t)", 0, 500, 0, step=10,
                                        key="co2_sweep_min",
                                        help="Niedrigster CO₂-Preis im Sweep")
        co2_sweep_step = st.number_input("Schrittweite (€/t)", 1, 100, 50, step=5,
                                         key="co2_sweep_step",
                                         help="Abstand zwischen den Preispunkten")
    with col2:
        co2_sweep_max = st.number_input("CO₂-Preis Max (€/t)", 0, 500, 300, step=10,
                                        key="co2_sweep_max",
                                        help="Höchster CO₂-Preis im Sweep")

    # Generiere Preis-Raster basierend auf Min/Max/Step
    prices_sweep = list(range(int(co2_sweep_min), int(co2_sweep_max) + 1, int(co2_sweep_step)))
    if prices_sweep[-1] != int(co2_sweep_max):
        prices_sweep.append(int(co2_sweep_max))

    st.caption(f"Raster: {len(prices_sweep)} Punkte: {prices_sweep}")

    # ── Optional: Nachbarn + ERA5 für Sweep ───────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        sweep_include_neighbors = st.checkbox("Nachbarländer (Sweep)",
                                              value=include_neighbors,
                                              key="sweep_include_neighbors",
                                              help="Nutze die Nachbarn-Kopplung im Sweep")
    with col_b:
        sweep_foreign_era5 = st.checkbox("Ausland-ERA5 (Sweep)",
                                         value=foreign_era5,
                                         disabled=not sweep_include_neighbors,
                                         key="sweep_foreign_era5",
                                         help="ERA5-Wetter für Ausland im Sweep")

    # ── Button zum Sweep starten ──────────────────────────────────────
    if st.button("🚀 CO₂-Sweep starten", type="primary", use_container_width=True,
                 key="co2_sweep_btn"):
        try:
            df_sweep = co2_sweep(
                prices=prices_sweep,
                co2_budget=co2_budget_mt * 1e6,
                include_neighbors=bool(sweep_include_neighbors),
                load_scale=float(load_scale),
                heat_scale=float(heat_scale),
                discount_rate=float(discount_pct) / 100.,
                gas_price=float(gas_price),
                foreign_era5=bool(sweep_foreign_era5),
                include_europe=bool(include_europe)
            )

            # ── Ergebnisse in DataFrame anzeigen ──────────────────
            st.subheader("📊 Sweep-Ergebnisse")
            valid_rows = df_sweep.dropna(subset=["Kosten_MrdEa"])
            failed_rows = df_sweep[df_sweep["Kosten_MrdEa"].isna()]

            if not valid_rows.empty:
                # Spalten-Reihenfolge: zentrale Kennzahlen zuerst
                display_cols = ["CO2_Preis_EUR_t", "Kosten_MrdEa", "CO2_Mt",
                               "RE_Anteil_pct", "Status"]
                # Füge Kapazitäts-Spalten hinzu (Kap_*_GW)
                kap_cols = sorted([c for c in df_sweep.columns
                                  if c.startswith("Kap_") and c.endswith("_GW")])
                display_cols.extend(kap_cols)

                st.dataframe(df_sweep[display_cols].round(2), width="stretch",
                            hide_index=True)
                st.download_button("⬇️ Sweep-Ergebnisse als CSV",
                                  _csv_download(df_sweep.round(2)),
                                  "co2_sweep_deutschland.csv", "text/csv",
                                  key="dl_co2_sweep")

            if not failed_rows.empty:
                st.warning(f"⚠ {len(failed_rows)} Preispunkt(e) fehlgeschlagen:")
                st.dataframe(failed_rows[["CO2_Preis_EUR_t", "Status"]],
                            width="stretch", hide_index=True)

            # ── Plot erstellen und anzeigen ──────────────────────────
            st.subheader("📈 Diagramm")
            if not valid_rows.empty:
                plot_path = os.path.join(dm.OUTPUT_DIR, "deutschland_v1_co2_sweep.png")
                dm.plot_co2_sweep(df_sweep, plot_path)
                st.image(plot_path, caption="CO₂-Preis-Sensitivität",
                        width="stretch")
                st.caption("Oben: Systemkosten (blau), CO₂-Ausstoß (rot), "
                          "EE-Anteil (türkis) über CO₂-Preis · "
                          "Unten: optimierte Kapazitäten je Träger")
            else:
                st.error("Keine gültigen Ergebnisse – Sweep konnte nicht berechnet werden.")

        except Exception as sweep_err:
            st.error(f"❌ Sweep fehlgeschlagen.\n\n{sweep_err}")

# ── Läufe: gespeicherte Optimierungsläufe dieser Sitzung vergleichen ──
with tab_runs:
    st.info("Vergleich der letzten (bis zu 5) Optimierungsläufe dieser Sitzung.")
    runs = st.session_state.get("runs", [])
    if not runs:
        st.caption("Noch keine Läufe gespeichert – Parameter ändern und "
                   "**Modell optimieren** drücken.")
    else:
        runs_df = pd.DataFrame(runs)
        st.dataframe(runs_df, width="stretch", hide_index=True)
        vergleich = runs_df.melt(id_vars="Zeit",
                                 value_vars=["Kosten (Mrd €/a)", "EE (%)"],
                                 var_name="Kennzahl", value_name="Wert")
        st.plotly_chart(px.bar(vergleich, x="Zeit", y="Wert", color="Kennzahl",
                               barmode="group",
                               color_discrete_map={"Kosten (Mrd €/a)": "#4A90D9",
                                                   "EE (%)": "#6bcb77"},
                               title="Gesamtkosten & EE-Anteil je Lauf"),
                        width="stretch")
        cda, cdb = st.columns(2)
        cda.download_button("⬇️ Läufe als CSV", _csv_download(runs_df),
                            "laeufe_vergleich.csv", "text/csv", key="dl_runs")
        if cdb.button("🗑️ Läufe zurücksetzen"):
            st.session_state.runs = []
            st.session_state.kpi_hist = []
            st.session_state._last_run_sig = _sig   # aktuellen Lauf nicht sofort neu erfassen
            st.session_state._kpi_hist_sig = _ksig
            st.rerun()

# ── PDF-Bericht ───────────────────────────────────────────────────────
with tab_pdf:
    st.info("Erzeugt Karte, Plots und einen PDF-Bericht zum Download.")
    st.write("Erzeugt Karte, Plots und PDF-Bericht wie im Original-Skript "
             "(inkl. Monte-Carlo-Tabelle, falls oben gerechnet).")
    if st.button("📄 Bericht erzeugen"):
        with st.spinner("Erstelle Plots & PDF …"):
            od = dm.OUTPUT_DIR
            pa = os.path.join(od, "deutschland_v1_dispatch.png")
            pb = os.path.join(od, "deutschland_v1_kapazitaeten.png")
            pc = os.path.join(od, "deutschland_v1_speicher_preise.png")
            pm = os.path.join(od, "deutschland_v1_karte.png")
            dm.plot_dispatch(n, pa)
            dm.plot_capacities(n, pb)
            dm.plot_storage_prices(n, pc)
            dm.plot_map(n, pm, era5_ok)
            mc_df = (monte_carlo(n_mc, co2_budget_mt * 1e6, float(co2_price),
                                 bool(include_neighbors))
                     if n_mc > 0 else
                     pd.DataFrame([dict(Jahr=1, Kosten_MrdEa=dm.total_cost(n)/1e9,
                                        CO2_Mt=co2, RE_Anteil_pct=ee,
                                        Status="Basislauf")]))
            pdf_path = os.path.join(od, "Deutschland_v1_Bericht.pdf")
            dm.make_pdf(n, mc_df, {"Karte": pm, "Dispatch": pa,
                                   "Kapazitäten": pb,
                                   "Speicher & Preise": pc}, pdf_path)
        st.success(f"✅ Bericht erstellt: `{pdf_path}`")
        with open(pdf_path, "rb") as f:
            st.download_button("⬇️ PDF herunterladen", f,
                               file_name="Deutschland_v1_Bericht.pdf",
                               mime="application/pdf")
        st.image(pm, caption="Deutschlandkarte")
