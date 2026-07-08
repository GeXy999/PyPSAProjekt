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
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
                   page_icon="⚡")
st.title("⚡ Deutschland Energy Model v1.0 – Interaktives Dashboard")
st.caption("5 Zonen · Sektorkopplung (Wärme + H₂) · CO₂-Budget · "
           "Kapazitätsausbau · Monte-Carlo")

# ----------------------------------------------------------------------
# Sidebar: Szenario-Parameter
# ----------------------------------------------------------------------
sb = st.sidebar
sb.header("🎛️ Szenario")

sb.subheader("🌍 Klima")
co2_budget_mt = sb.slider("CO₂-Budget (Mt/a)", 0, 250, 120, step=10,
                          help="Jährliches Emissionslimit des Stromsektors")
co2_price     = sb.slider("CO₂-Preis (€/t)", 0, 400, 80, step=10,
                          help="Aufschlag auf fossile Grenzkosten")

sb.subheader("🔌 Nachfrage")
load_scale    = sb.slider("Stromlast-Skalierung", 0.7, 1.5, 1.0, step=0.05,
                          help="Skaliert die elektrische Grundlast")
heat_scale    = sb.slider("Wärmelast-Skalierung (Elektrifizierung)",
                          0.3, 1.5, 1.0, step=0.05,
                          help="Elektrifizierbare Wärmenachfrage (Wärmepumpen)")

sb.subheader("💰 Ökonomie")
discount_pct  = sb.slider("Diskontsatz / WACC (%)", 1.0, 12.0, 7.0, step=0.5,
                          help="Kapitalkosten des Zubaus – höher = teurer "
                               "Ausbau, weniger Neubau erneuerbarer Kapazität")
gas_price     = sb.slider("Gaspreis (€/MWh_th)", 10, 120, 55, step=5,
                          help="Brennstoffkosten Gas – verschiebt die Merit-Order "
                               "zwischen Gas, Kohle und Erneuerbaren")

sb.subheader("🌍 Europa")
include_neighbors = sb.checkbox("Nachbarländer koppeln", value=False,
                                help="11 Nachbarländer (FR, BE, LU, NL, DK, PL, "
                                     "CZ, AT, CH, SE, NO) als Ein-Knoten-Modelle "
                                     "mit Import/Export. Nur DE baut aus; "
                                     "CO₂-Budget gilt nur für DE.")
foreign_era5 = sb.checkbox("Ausland: ERA5-Wetter", value=False,
                           disabled=not include_neighbors,
                           help="Auslandswetter aus echten ERA5-Daten statt "
                                "synthetisch. ⚠ Erster Lauf lädt je Land via CDS "
                                "herunter (dauert, nur lokal mit atlite+CDS-Key). "
                                "Automatischer Fallback auf synthetisch.")
if include_neighbors and foreign_era5 and not dm.ATLITE_AVAILABLE:
    sb.caption("⚠ atlite nicht verfügbar → Ausland bleibt synthetisch.")

sb.divider()
n_mc   = sb.slider("Monte-Carlo Wetterjahre", 0, 60, 0,
                   help="0 = überspringen (schneller)")
run_btn = sb.button("🚀 Modell optimieren", type="primary",
                    width="stretch")
sb.caption(f"Solver: {'Gurobi' if dm.USE_GUROBI else 'HiGHS'} · "
           f"Auflösung: {dm.TIME_RES}h · "
           f"Wetter: {'ERA5 möglich' if dm.ATLITE_AVAILABLE else 'synthetisch'}")

# ----------------------------------------------------------------------
# Modelllauf (gecacht: gleiche Parameter → kein Neurechnen)
# ----------------------------------------------------------------------
@st.cache_resource(show_spinner="⏳ Optimiere Deutschland-Modell … "
                                "(je nach Rechner 1–10 min)")
def solve(co2_budget, co2_price, load_scale, heat_scale,
          discount_rate, gas_price, include_neighbors, foreign_era5):
    net, era5_ok = dm.run_base(co2_budget=co2_budget, co2_price=co2_price,
                               load_scale=load_scale, heat_scale=heat_scale,
                               discount_rate=discount_rate, gas_price=gas_price,
                               include_neighbors=include_neighbors,
                               foreign_era5=foreign_era5, verbose=False)
    return net, era5_ok

@st.cache_data(show_spinner="⏳ Monte-Carlo läuft …")
def monte_carlo(n_mc, co2_budget, co2_price, include_neighbors):
    return dm.run_monte_carlo(n_mc=n_mc, co2_budget=co2_budget,
                              co2_price=co2_price,
                              include_neighbors=include_neighbors)

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
                       bool(include_neighbors), bool(foreign_era5))
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

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Gesamtkosten", f"{dm.total_cost(n)/1e9:,.2f} Mrd €/a",
          help="Annualisierte Systemkosten (variabler + konstanter Zielfunktions-"
               "teil). Bei gekoppelten Nachbarn = Kosten des Gesamtsystems DE+Ausland.")
k2.metric("Ø Strompreis DE", f"{preis:,.1f} €/MWh")
k3.metric("CO₂-Emissionen DE", f"{co2:,.1f} Mt/a",
          delta=f"{co2 - co2_budget_mt:+.1f} vs. Budget", delta_color="inverse")
k4.metric("EE-Anteil DE", f"{ee:,.1f} %")
k5.metric("Erzeugung DE", f"{erz_twh:,.0f} TWh/a")
if not era5_ok:
    st.caption("⚠ Synthetische Wetterdaten (atlite/ERA5 nicht verfügbar)")
if gekoppelt:
    st.caption("🌍 **Nachbarländer gekoppelt** – Erzeugungs-KPIs (CO₂, EE, "
               "Erzeugung) zeigen **nur Deutschland**; die Gesamtkosten umfassen "
               "das gekoppelte Gesamtsystem. Import/Export im Tab **🌍 Nachbarn**.")

FARBEN = dm.CARRIER_COLORS

(tab_disp, tab_kap, tab_preis, tab_spei, tab_karte, tab_eng,
 tab_vgl, tab_nb, tab_mc, tab_pdf) = st.tabs(
    ["📊 Dispatch", "🏗️ Kapazitäten", "💶 Preise", "🔋 Speicher & H₂",
     "🗺️ Karte", "🚧 Engpässe", "⚖️ Vergleich", "🌍 Nachbarn",
     "🎲 Monte-Carlo", "📄 Bericht"])

# ── Dispatch ──────────────────────────────────────────────────────────
with tab_disp:
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
    st.subheader("Netz- & Sektorkopplungs-Ausbau")
    netz = pd.DataFrame({
        "Leitung": n.lines.index,
        "Start (GW)": n.lines.s_nom.values / 1000.,
        "Optimiert (GW)": n.lines.s_nom_opt.values / 1000.})
    netz["Zubau (GW)"] = (netz["Optimiert (GW)"] - netz["Start (GW)"]).round(2)
    l1, l2 = st.columns(2)
    l1.dataframe(netz.round(2), width="stretch", hide_index=True)
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

# ── Speicher & H₂ ─────────────────────────────────────────────────────
with tab_spei:
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

# ── Karte ─────────────────────────────────────────────────────────────
with tab_karte:
    fig = go.Figure()
    for ln, row in n.lines.iterrows():
        cap = float(row.s_nom_opt) or 1.
        pct = 100. * abs(n.lines_t.p0[ln]).mean() / cap
        clr = "#6bcb77" if pct < 50 else ("#ffd93d" if pct < 80 else "#ff6b6b")
        fig.add_trace(go.Scattergeo(
            lon=[n.buses.at[row.bus0, "x"], n.buses.at[row.bus1, "x"]],
            lat=[n.buses.at[row.bus0, "y"], n.buses.at[row.bus1, "y"]],
            mode="lines",
            line=dict(width=max(2, cap / 3000), color=clr,
                      dash="dash" if "Off" in ln else "solid"),
            name=f"{ln}: {cap/1000:.1f} GW | {pct:.0f}%"))
    busse = list(dm.REGIONS) + ["Offshore"]
    texte = []
    for b in busse:
        cap = sum(dm._pnom(n.generators, g) for g in n.generators.index
                  if n.generators.bus[g] == b) / 1000.
        texte.append(f"<b>{b}</b><br>{cap:.0f} GW installiert")
    fig.add_trace(go.Scattergeo(
        lon=[n.buses.at[b, "x"] for b in busse],
        lat=[n.buses.at[b, "y"] for b in busse],
        text=busse, hovertext=texte, hoverinfo="text",
        mode="markers+text", textposition="top center",
        marker=dict(size=16, color=["#00BCD4", "#E040FB", "#FF9800",
                                    "#8BC34A", "#4A90D9"]),
        name="Regionen"))

    # Nachbarländer + Kuppelstellen (nur bei Kopplung)
    if gekoppelt:
        netimp = dm.neighbor_net_import_twh(n)
        for lk in [c for c in n.links.index if c.startswith("IC_")]:
            b0, b1 = n.links.at[lk, "bus0"], n.links.at[lk, "bus1"]
            cap = float(n.links.at[lk, "p_nom"]) or 1.
            pct = 100. * abs(n.links_t.p0[lk]).mean() / cap
            clr = "#6bcb77" if pct < 50 else ("#ffd93d" if pct < 80 else "#ff6b6b")
            fig.add_trace(go.Scattergeo(
                lon=[n.buses.at[b0, "x"], n.buses.at[b1, "x"]],
                lat=[n.buses.at[b0, "y"], n.buses.at[b1, "y"]],
                mode="lines",
                line=dict(width=max(1.5, cap / 2500), color=clr, dash="dot"),
                name=f"{lk[3:]}: NTC {cap/1000:.1f} GW | {pct:.0f}%"))
        ccs = list(dm.NEIGHBORS)
        cc_txt = []
        for cc in ccs:
            imp = float(netimp.get(cc, 0.))
            inst = sum(dm.NEIGHBORS[cc]["fleet"].values()) / 1000.
            rich = "Import" if imp >= 0 else "Export"
            cc_txt.append(f"<b>{cc}</b><br>{inst:.0f} GW installiert<br>"
                          f"Netto-{rich}: {abs(imp):.1f} TWh/a")
        fig.add_trace(go.Scattergeo(
            lon=[dm.NEIGHBORS[cc]["x"] for cc in ccs],
            lat=[dm.NEIGHBORS[cc]["y"] for cc in ccs],
            text=ccs, hovertext=cc_txt, hoverinfo="text",
            mode="markers+text", textposition="top center",
            marker=dict(size=12, color="#B0BEC5"),
            name="Nachbarländer"))

    fig.update_geos(fitbounds="locations", resolution=50, showcountries=True,
                    showland=True, landcolor="#22331a", bgcolor="#0a2540",
                    countrycolor="#555")
    fig.update_layout(height=650, margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="#0a2540", legend_font_color="white")
    st.plotly_chart(fig, width="stretch")
    st.caption("Grün <50 % · Gelb 50–80 % · Rot >80 % mittlere Auslastung · "
               "gestrichelt = Offshore-Anbindung · gepunktet = Kuppelstelle "
               "(NTC) zu Nachbarländern (graue Marker).")

# ── Engpässe & Schattenpreise ─────────────────────────────────────────
with tab_eng:
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
    st.subheader("⚖️ 5-Zonen-Modell vs. Ein-Knoten-Referenz")
    st.caption("Vergleich des aktuell optimierten 5-Zonen-Modells mit dem "
               "Ein-Knoten-Deutschland-Modell aus der Excel "
               "(Dispatch-Zeitreihen, Verbrauch 2026, ERA5-Wetter 2007/2009).")

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
        col_a, col_b = st.columns([1, 2])
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

# ── PDF-Bericht ───────────────────────────────────────────────────────
with tab_pdf:
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
