#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plot- und Reporting-Helfer für Lummerland v4.2."""

from __future__ import annotations
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages

BG = "#0D1B2A"
COLORS = {
    "Wind_Nord": "#4A90D9",
    "Wind_Zentrum": "#6db3f2",
    "Wind_Offshore": "#00BCD4",
    "Solar_Nord": "#ffc966",
    "Solar_Sued": "#F5A623",
    "Atomkraft": "#7ED321",
    "Gas_CCGT": "#D0021B",
    "Wind_Lstadt": "#E040FB",
    "Solar_Lstadt": "#CE93D8",
    "Gas_Lstadt": "#8E244D",
    "Batterie": "#9B59B6",
}


def style_ax(ax, title: str, xlabel: str = "", ylabel: str = "", bg_inner: str = "#1a2a3a", bg_spine: str = "#444") -> None:
    ax.set_facecolor(bg_inner)
    ax.tick_params(colors="white")
    ax.set_title(title, color="white", fontsize=10, fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, color="white")
    if ylabel:
        ax.set_ylabel(ylabel, color="white")
    for sp in ax.spines.values():
        sp.set_edgecolor(bg_spine)


def pnom(comp_df: "pd.DataFrame", name: str) -> float:
    row = comp_df.loc[name]
    return max(0.0, float(row.get("p_nom_opt", row.get("p_nom", 0.0))))


def create_plot_bundle(n, valid, output_dir: str, power_loads: list[str], heat_loads: list[str], heat_zentrum, heat_sued, version: str = "v4.2") -> dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    step_h = int(round((n.snapshots[1] - n.snapshots[0]).total_seconds() / 3600)) if len(n.snapshots) > 1 else 1
    spd = max(1, 24 // step_h)
    idx_summer = slice(25 * 7 * spd, 26 * 7 * spd)
    idx_winter = slice(0, 7 * spd)

    fig_a = plt.figure(figsize=(18, 14))
    fig_a.patch.set_facecolor(BG)
    gs_a = gridspec.GridSpec(3, 2, figure=fig_a, hspace=0.45, wspace=0.35, left=0.08, right=0.97, top=0.93, bottom=0.06)

    ax = fig_a.add_subplot(gs_a[0, 0])
    gen_sum = n.generators_t.p.sum() / 1e3
    ax.bar(range(len(gen_sum)), gen_sum.values, color=[COLORS.get(k, "#888") for k in gen_sum.index], edgecolor="white", lw=0.5)
    ax.set_xticks(range(len(gen_sum)))
    ax.set_xticklabels(gen_sum.index, rotation=35, ha="right", fontsize=8, color="white")
    style_ax(ax, "Jährlicher Erzeugungsmix", ylabel="GWh/Jahr")

    ax = fig_a.add_subplot(gs_a[0, 1])
    week_p = n.generators_t.p.iloc[idx_summer]
    bot = np.zeros(len(week_p))
    for col in week_p.columns:
        ax.fill_between(range(len(week_p)), bot, bot + week_p[col].values, color=COLORS.get(col, "#888"), alpha=0.88, label=col)
        bot += week_p[col].values
    ls = n.loads_t.p_set[power_loads].iloc[idx_summer].sum(axis=1)
    ax.plot(ls.values, "w--", lw=1.4, label="Stromlast")
    ax.set_xticks(np.arange(0, 7 * spd + 1, spd))
    ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
    style_ax(ax, "Sommer (KW 26)", ylabel="MW")
    ax.legend(fontsize=7, facecolor=BG, labelcolor="white", loc="upper left", ncol=2, framealpha=0.85)

    ax = fig_a.add_subplot(gs_a[1, 0])
    week_pw = n.generators_t.p.iloc[idx_winter]
    bot = np.zeros(len(week_pw))
    for col in week_pw.columns:
        ax.fill_between(range(len(week_pw)), bot, bot + week_pw[col].values, color=COLORS.get(col, "#888"), alpha=0.88)
        bot += week_pw[col].values
    lw2 = n.loads_t.p_set[power_loads].iloc[idx_winter].sum(axis=1)
    ax.plot(lw2.values, "w--", lw=1.4)
    ax.set_xticks(np.arange(0, 7 * spd + 1, spd))
    ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
    style_ax(ax, "Winter (KW 1)", ylabel="MW")

    ax = fig_a.add_subplot(gs_a[1, 1])
    try:
        h2_soc = n.stores_t.e["H2_Tank"]
        ax.fill_between(range(len(h2_soc)), h2_soc.values, alpha=0.6, color="#2ECC71", label="H₂-Füllstand")
        ax.axhline(n.stores.at["H2_Tank", "e_nom_opt"] * 0.2, color="#ffd93d", ls="--", lw=1.2, label="Min 20%")
        ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
    except Exception:
        ax.text(0.5, 0.5, "H₂ n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
    style_ax(ax, "H₂-Tank SoC")

    ax = fig_a.add_subplot(gs_a[2, 0])
    try:
        wpz = n.links_t.p0["WP_Zentrum"].iloc[idx_winter]
        wps = n.links_t.p0["WP_Sued"].iloc[idx_winter]
        tw = range(len(wpz))
        ax.fill_between(tw, 0, wpz.values, alpha=0.75, color="#E74C3C", label="WP Zentrum")
        ax.fill_between(tw, wpz.values, wpz.values + wps.values, alpha=0.75, color="#C0392B", label="WP Süd")
        ax.plot(tw, heat_zentrum[idx_winter] + heat_sued[idx_winter], "w--", lw=1.2, label="Wärmelast")
        ax.set_xticks(np.arange(0, 169, 24))
        ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
        ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
    except Exception:
        ax.text(0.5, 0.5, "WP n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
    style_ax(ax, "Wärmepumpen – Winter", ylabel="MW_el")

    ax = fig_a.add_subplot(gs_a[2, 1])
    if not valid.empty:
        ax.bar(valid["Jahr"], valid["Kosten_MEa"], color="#4A90D9", edgecolor="white", lw=0.5, alpha=0.85)
        ax.axhline(valid["Kosten_MEa"].mean(), color="#FFD700", ls="--", lw=1.5, label=f"Ø {valid['Kosten_MEa'].mean():.2f} M€/a")
        ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
    style_ax(ax, "Monte-Carlo Kosten", xlabel="Wetterjahr", ylabel="M€/a")

    fig_a.suptitle(f"LUMMERLAND {version} – Erzeugungsmix, H₂-System & Sektorkopplung", fontsize=14, fontweight="bold", color="white", y=0.97)
    path_a = os.path.join(output_dir, "lummerland_v4_2_ergebnisse.png")
    plt.savefig(path_a, dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close()
    paths["plot_a"] = path_a

    fig_b = plt.figure(figsize=(18, 10))
    fig_b.patch.set_facecolor(BG)
    gs_b = gridspec.GridSpec(2, 3, figure=fig_b, hspace=0.48, wspace=0.38, left=0.07, right=0.97, top=0.92, bottom=0.08)

    ax = fig_b.add_subplot(gs_b[0, 0])
    inv = {g.replace("_", " "): pnom(n.generators, g) * n.generators.at[g, "capital_cost"] / 1e6 for g in n.generators.index}
    inv.update({su.replace("_", " "): pnom(n.storage_units, su) * n.storage_units.at[su, "capital_cost"] / 1e6 for su in n.storage_units.index})
    inv_s = dict(sorted(inv.items(), key=lambda x: x[1], reverse=True))
    ax.barh(list(inv_s.keys()), list(inv_s.values()), color="#4A90D9", edgecolor="white", lw=0.4)
    style_ax(ax, "Kapitalkosten", xlabel="M€/Jahr")
    ax.tick_params(labelsize=8)

    ax = fig_b.add_subplot(gs_b[0, 1])
    op = {g.replace("_", " "): n.generators_t.p[g].sum() * n.generators.at[g, "marginal_cost"] / 1e6 for g in n.generators.index}
    op_s = dict(sorted(op.items(), key=lambda x: x[1], reverse=True))
    ax.barh(list(op_s.keys()), list(op_s.values()), color="#F5A623", edgecolor="white", lw=0.4, alpha=0.85)
    style_ax(ax, "Betriebskosten", xlabel="M€/Jahr")
    ax.tick_params(labelsize=8)

    ax = fig_b.add_subplot(gs_b[0, 2])
    co2_src = {g: n.generators_t.p[g].sum() * (n.carriers.at[n.generators.at[g, "carrier"], "co2_emissions"] if n.generators.at[g, "carrier"] in n.carriers.index else 0) / 1e3 for g in n.generators.index}
    co2_pos = {k: v for k, v in co2_src.items() if v > 0.1}
    if co2_pos:
        ax.pie(co2_pos.values(), labels=co2_pos.keys(), autopct="%1.1f%%", colors=["#D0021B","#E67E22","#C0392B"], textprops=dict(color="white", fontsize=8))
    else:
        ax.text(0.5, 0.5, "CO₂ = 0 ✓", ha="center", va="center", color="#7ED321", fontsize=14, fontweight="bold", transform=ax.transAxes)
    style_ax(ax, "CO₂-Emissionen")

    ax = fig_b.add_subplot(gs_b[1, 0])
    caps = {g: pnom(n.generators, g) for g in n.generators.index}
    caps.update({su: pnom(n.storage_units, su) for su in n.storage_units.index})
    ax.bar(range(len(caps)), list(caps.values()), color=[COLORS.get(k, "#888") for k in caps], edgecolor="white", lw=0.4)
    ax.set_xticks(range(len(caps)))
    ax.set_xticklabels(list(caps.keys()), rotation=40, ha="right", fontsize=8, color="white")
    style_ax(ax, "Optimierte Kapazitäten", ylabel="MW")

    ax = fig_b.add_subplot(gs_b[1, 1])
    cf_vals = {g: n.generators_t.p[g].mean() / pnom(n.generators, g) for g in n.generators.index if pnom(n.generators, g) > 0}
    cf_s = dict(sorted(cf_vals.items(), key=lambda x: x[1], reverse=True))
    ax.barh(list(cf_s.keys()), list(cf_s.values()), color=[COLORS.get(k, "#888") for k in cf_s], edgecolor="white", lw=0.4)
    ax.axvline(0.25, color="#ffd93d", ls="--", lw=1)
    ax.set_xlim(0, 1)
    style_ax(ax, "Kapazitätsfaktoren", xlabel="CF [−]")
    ax.tick_params(labelsize=8)

    ax = fig_b.add_subplot(gs_b[1, 2])
    if not valid.empty:
        sc = ax.scatter(valid["Kosten_MEa"], valid["RE_Anteil_%"], c=valid["CO2_t"], cmap="RdYlGn_r", s=120, edgecolors="white", lw=1.2, zorder=5)
        for _, row in valid.iterrows():
            ax.annotate(f"J{int(row['Jahr'])}", (row["Kosten_MEa"], row["RE_Anteil_%"]), fontsize=8, color="white", xytext=(4, 4), textcoords="offset points")
        cb = plt.colorbar(sc, ax=ax)
        cb.set_label("CO₂ [t/a]", color="white")
        cb.ax.yaxis.label.set_color("white")
    style_ax(ax, "MC: Kosten vs. RE-Anteil", xlabel="Kosten [M€/a]", ylabel="RE-Anteil [%]")

    fig_b.suptitle(f"LUMMERLAND {version} – Kosten, CO₂ & Monte-Carlo Robustheit", fontsize=14, fontweight="bold", color="white", y=0.97)
    path_b = os.path.join(output_dir, "lummerland_v4_2_kosten.png")
    plt.savefig(path_b, dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close()
    paths["plot_b"] = path_b

    fig_c = plt.figure(figsize=(18, 10))
    fig_c.patch.set_facecolor(BG)
    gs_c = gridspec.GridSpec(2, 3, figure=fig_c, hspace=0.45, wspace=0.38, left=0.07, right=0.97, top=0.92, bottom=0.08)
    t_ax = range(len(n.generators_t.p.iloc[idx_summer]))

    ax = fig_c.add_subplot(gs_c[0, 0])
    sectors = {
        "Strom-\nErzeugung": n.generators_t.p.sum().sum() / 1e3,
        "Strom-\nLast": n.loads_t.p_set[power_loads].sum().sum() / 1e3,
    }
    try:
        sectors["Wärme-\nLast"] = n.loads_t.p_set[heat_loads].sum().sum() / 1e3
        sectors["H₂-\nErzeugt"] = (n.links_t.p0.get("Elektrolyseur", pd.Series(0))).sum() / 1e3
    except Exception:
        pass
    ax.bar(list(sectors.keys()), list(sectors.values()), color=["#4A90D9","white","#E74C3C","#2ECC71"][:len(sectors)], edgecolor="white", lw=0.5, alpha=0.85)
    style_ax(ax, "Jahresenergie-Übersicht", ylabel="GWh/Jahr")
    ax.tick_params(labelsize=8)

    ax = fig_c.add_subplot(gs_c[0, 1])
    try:
        bat_soc = n.storage_units_t.state_of_charge["Batterie"].iloc[idx_summer]
        ax.fill_between(t_ax, bat_soc.values, alpha=0.7, color="#9B59B6", label="Batterie SoC")
        pno = pnom(n.storage_units, "Batterie")
        ax.axhline(pno * 4 * 0.10, color="#ff6b6b", ls="--", lw=1, label="Min 10%")
        ax.axhline(pno * 4 * 0.90, color="#6bcb77", ls="--", lw=1, label="Max 90%")
        ax.set_xticks(np.arange(0, 169, 24))
        ax.set_xticklabels(["Mo","Di","Mi","Do","Fr","Sa","So","Mo"], fontsize=8, color="white")
        ax.set_ylabel("MWh", color="white")
        ax.legend(fontsize=8, facecolor=BG, labelcolor="white")
    except Exception:
        ax.text(0.5, 0.5, "SoC n.v.", transform=ax.transAxes, ha="center", va="center", color="white")
    style_ax(ax, "Batterie SoC – Sommer")

    ax = fig_c.add_subplot(gs_c[0, 2])
    months = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
    sh = (n.snapshots[1] - n.snapshots[0]).total_seconds() / 3600 if len(n.snapshots) > 1 else 1.0
    bot2 = np.zeros(12)
    for g in n.generators.index:
        g_ts = n.generators_t.p[g].copy()
        g_ts.index = n.snapshots
        vals = [g_ts[g_ts.index.month == m].sum() * sh / 1e3 for m in range(1, 13)]
        ax.bar(range(12), vals, bottom=bot2, color=COLORS.get(g, "#888"), alpha=0.85, label=g, edgecolor="none")
        bot2 += np.array(vals)
    ax.set_xticks(range(12))
    ax.set_xticklabels(months, fontsize=8, rotation=45, color="white")
    style_ax(ax, "Monatliche Erzeugung", ylabel="GWh/Monat")
    ax.legend(fontsize=7, facecolor=BG, labelcolor="white", ncol=2, loc="upper right")

    ax = fig_c.add_subplot(gs_c[1, 0])
    re_gens = [g for g in n.generators.index if n.generators.at[g, "carrier"] in ["wind", "solar"]]
    re_total = n.generators_t.p[re_gens].sum(axis=1)
    demand = n.loads_t.p_set[power_loads].sum(axis=1)
    residual = (demand - re_total).sort_values(ascending=False)
    ax.fill_between(range(len(residual)), residual.values, 0, where=residual.values > 0, color="#D0021B", alpha=0.6, label="Residual >0")
    ax.fill_between(range(len(residual)), residual.values, 0, where=residual.values < 0, color="#7ED321", alpha=0.6, label="EE-Überschuss")
    ax.axhline(0, color="white", lw=0.8)
    style_ax(ax, "Dauerlinie Residuallast", xlabel="Stunden (sortiert)", ylabel="MW")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")

    ax = fig_c.add_subplot(gs_c[1, 1])
    line_cm = {"Leitung_NZ":"#4A90D9","Leitung_ZS":"#F5A623","Leitung_NS":"#2ECC71","Leitung_ON":"#00BCD4","Leitung_NL":"#E040FB","Leitung_OL":"#CE93D8"}
    for ln, lclr in line_cm.items():
        try:
            sopt = n.lines.at[ln, "s_nom_opt"] if "s_nom_opt" in n.lines.columns else n.lines.at[ln, "s_nom"]
            util = n.lines_t.p0[ln].abs() / sopt * 100
            ax.hist(util, bins=40, alpha=0.55, color=lclr, label=f"{ln} (max {util.max():.0f}%)", density=True)
        except Exception:
            pass
    style_ax(ax, "Leitungsauslastung", xlabel="Auslastung [%]", ylabel="Häufigkeitsdichte")
    ax.legend(fontsize=8, facecolor=BG, labelcolor="white")

    ax = fig_c.add_subplot(gs_c[1, 2])
    if not valid.empty:
        ax.boxplot([valid["RE_Anteil_%"].values, valid["Kosten_MEa"].values * 10], tick_labels=["RE-Anteil [%]", "Kosten [×10 M€/a]"], patch_artist=True, boxprops=dict(facecolor="#4A90D9", alpha=0.7), medianprops=dict(color="#FFD700", lw=2), whiskerprops=dict(color="white"), capprops=dict(color="white"), flierprops=dict(markerfacecolor="#ff6b6b", marker="o"))
    style_ax(ax, "Monte-Carlo Streuung")

    fig_c.suptitle(f"LUMMERLAND {version} – Sektorkopplung, Speicher & Versorgungssicherheit", fontsize=14, fontweight="bold", color="white", y=0.97)
    path_c = os.path.join(output_dir, "lummerland_v4_2_sektoren.png")
    plt.savefig(path_c, dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close()
    paths["plot_c"] = path_c
    return paths


def write_simple_pdf(pdf_path: str, title: str, subtitle: str, image_paths: list[str]) -> str:
    with PdfPages(pdf_path) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.patch.set_facecolor(BG)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(BG)
        ax.axis("off")
        ax.text(0.5, 0.70, title, ha="center", va="center", fontsize=22, color="white", fontweight="bold", transform=ax.transAxes)
        ax.text(0.5, 0.58, subtitle, ha="center", va="center", fontsize=12, color="white", transform=ax.transAxes)
        pdf.savefig(fig, facecolor=BG, bbox_inches="tight")
        plt.close(fig)
        for img in image_paths:
            if os.path.exists(img):
                fig = plt.figure(figsize=(11.69, 8.27))
                ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
                ax.axis("off")
                ax.imshow(plt.imread(img))
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
    return pdf_path
