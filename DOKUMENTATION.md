# 📘 Dokumentation – Deutschland Energy Model

> **Stand:** 08.07.2026 · **Version:** v1.1 (europäische Kopplung)
> Diese Datei erklärt die beiden Kern-Skripte des Projekts und die wichtigsten
> Funktionen & Formeln. Sie wird bei Änderungen am Code mitgepflegt.
>
> 💡 *Öffnen/Ansehen:* In VSCode diese Datei anklicken und oben rechts auf das
> Vorschau-Symbol drücken oder `Strg`+`Shift`+`V`. Bei Bedarf lässt sie sich nach
> Word/PDF exportieren (z. B. mit der VSCode-Erweiterung „Markdown PDF").

---

## Inhaltsverzeichnis
1. [Überblick](#1-überblick)
2. [Projektstruktur & Start](#2-projektstruktur--start)
3. [`deutschland_v1.py` – Das Modell](#3-deutschland_v1py--das-modell)
4. [`deutschland_gui.py` – Das Dashboard](#4-deutschland_guipy--das-dashboard)
5. [Der Vergleich mit dem Ein-Knoten-Modell](#5-der-vergleich-mit-dem-ein-knoten-modell)
6. [Formelsammlung (Kurzreferenz)](#6-formelsammlung-kurzreferenz)
7. [Häufige Fragen / Troubleshooting](#7-häufige-fragen--troubleshooting)
8. [Deployment (Streamlit Cloud) & Secrets](#8-deployment-streamlit-cloud--secrets)
9. [Europäische Kopplung (Nachbarländer)](#9-europäische-kopplung-nachbarländer)

---

## 1. Überblick

Das Projekt optimiert ein **kostenminimales Stromsystem für Deutschland** mit dem
Framework [PyPSA](https://pypsa.org). Es besteht aus zwei Teilen:

| Datei | Rolle |
|---|---|
| **`deutschland_v1.py`** | Das eigentliche Modell: baut das Netz, löst die Optimierung, rechnet Kennzahlen. Kann als Skript **oder** als importierbares Modul laufen. |
| **`deutschland_gui.py`** | Interaktives **Streamlit**-Dashboard, das `deutschland_v1.py` importiert und die Ergebnisse grafisch aufbereitet. |

**Was wird optimiert?** Eine *Greenfield*-Kapazitätsausbau-Rechnung: Der Solver
wählt Zubau von Wind, Solar, Gas, Speichern, Netz, Wärmepumpen und H₂ so, dass die
**annualisierten Gesamtkosten minimal** werden – unter Einhaltung von Lastdeckung
und CO₂-Budget.

**Modell-Charakteristik:**
- **5 Zonen:** Nord, Ost, West, Süd + Offshore (Nordsee), verbunden durch ein Übertragungsnetz.
- **Sektorkopplung:** Strom ↔ Wärme (Wärmepumpen + Wärmespeicher) und Strom ↔ Wasserstoff (Elektrolyse, H₂-Tank, Brennstoffzelle).
- **Zeitauflösung:** stündlich, 8760 Zeitschritte (Standardjahr).
- **Wetter:** echte ERA5-Daten via `atlite` (falls verfügbar), sonst synthetische Profile.

---

## 2. Projektstruktur & Start

```
D:\Project_PyPSA\
├── deutschland_v1.py        ← Modell (Kern)
├── deutschland_gui.py       ← Streamlit-Dashboard
├── DOKUMENTATION.md         ← diese Datei
├── Produktionsdaten für PyPSA.xlsx   ← Referenz-Ein-Knoten-Modell (nur lokal)
├── .venv\                   ← Python-Umgebung
└── Deutschland_v1_Output\   ← erzeugte Plots & PDF-Bericht
```

**Dashboard starten:**
```bash
# im Projektordner, mit der venv:
.venv\Scripts\streamlit.exe run deutschland_gui.py
```
Öffnet sich unter **http://localhost:8501**.

**Nur das Modell als Skript rechnen (ohne GUI):**
```bash
.venv\Scripts\python.exe deutschland_v1.py
```

> ℹ️ Unter Windows sollte `PYTHONUTF8=1` gesetzt sein, damit Sonderzeichen (✓, ⚠)
> in der Ausgabe nicht zu einem `UnicodeEncodeError` führen. Das Skript stellt
> stdout/stderr beim Start aber ohnehin auf UTF-8 um.

---

## 3. `deutschland_v1.py` – Das Modell

Aufbau in Abschnitten (die Nummern stehen als Kommentar-Banner im Code):

### 3.1 Globale Parameter (Abschnitt 2)

| Parameter | Wert | Bedeutung |
|---|---|---|
| `TIME_RES` | `1` | Stunden pro Zeitschritt (1 = volle Stundenauflösung) |
| `HOURS` | `8760 / TIME_RES` | Anzahl Zeitschritte |
| `DISCOUNT_RATE` | `0.07` | Kalkulationszins / WACC (per Slider änderbar) |
| `CO2_PRICE` | `80 €/t` | CO₂-Preis auf fossile Grenzkosten |
| `CO2_BUDGET` | `120 Mt/a` | Jährliches Emissionslimit |
| `BASE_LOAD` | `62 000 MW` | mittlere elektrische Last (Peak ≈ 80 GW) |
| `BASE_HEAT` | `45 000 MW` | mittlere elektrifizierbare Wärmelast |
| `REGIONS` | dict | Regionen mit (lon, lat, Lastanteil, Wärmeanteil) |

### 3.2 Annuitäten & Kosten (Abschnitt 3) — *wichtige Formeln*

**Annuitätenfaktor** `annuity(lifetime, r)` — verteilt eine Investition über die
Lebensdauer:

$$a(n, r) = \frac{r}{1 - (1+r)^{-n}} \qquad \text{(bzw. } 1/n \text{ falls } r = 0)$$

```python
def annuity(lifetime, r=DISCOUNT_RATE):
    return r / (1 - (1 + r) ** (-lifetime)) if r > 0 else 1 / lifetime
```

**Annualisierte Kapitalkosten** `capex_annual(key)`:

$$\text{capex\_annual} = \text{Investition} \;[\text{€/MW}] \times a(\text{Lebensdauer},\ \text{DISCOUNT\_RATE})$$

> Ein höherer Diskontsatz (WACC) → höhere jährliche Kapitalkosten → weniger
> attraktiver Zubau. Genau das steuert der **WACC-Slider** in der GUI.

**Grenzkosten (OPEX)** `opex(co2_price, gas_price)` — €/MWh je Technologie, inkl.
CO₂-Aufschlag auf fossile Träger:

| Träger | Grenzkosten-Formel |
|---|---|
| Gas (CCGT) | `gas_price + 0.370 · co2_price` |
| Braunkohle (Lignite) | `28 + 1.000 · co2_price` |
| Steinkohle (Hardcoal) | `40 + 0.800 · co2_price` |
| Wind/Solar/Hydro | ~0 (nur kleiner Betriebskosten-Term) |

> Der Faktor vor `co2_price` ist die **spezifische Emission** [t CO₂/MWh]. Dieselben
> Faktoren stecken in den Carriern des Netzes (`co2_emissions`) und werden für die
> CO₂-Bilanz genutzt.
> Der **Gaspreis-Slider** verschiebt hierüber die *Merit-Order* (Einsatzreihenfolge).

### 3.3 Wetterdaten (Abschnitt 4)

- **`make_profiles(mc_seed)`** — liefert Kapazitätsfaktoren (0–1) je Region für
  Wind & Solar.
  - `mc_seed=None` → ERA5 (echte Wetterdaten) falls `atlite` verfügbar, sonst synthetisch.
  - `mc_seed=i` → synthetisches Monte-Carlo-Wetterjahr `i`.
- **`_synthetic_base()`** — erzeugt Basisprofile aus Jahres- und Tagesgang (Sinus/Cosinus) plus Rauschen (Weibull-verteilter Wind).
- **`_era5_region(box)`** — lädt Wind-/PV-Kapazitätsfaktoren einer ERA5-Wetterbox über `atlite`.

### 3.4 Lastprofile (Abschnitt 4) — *Formel*

**`make_loads(load_scale, heat_scale, mc_seed)`** baut Strom- und Wärmelast je
Region [MW]. Die Stromlast folgt einem Jahres- und Tagesgang:

$$\text{last}(t) = \text{BASE\_LOAD} \cdot s_{\text{load}} \cdot \Big(1 + 0.20\cos\tfrac{2\pi(d-355)}{365}\Big)\cdot\Big(1 + 0.15\sin\tfrac{\pi(h-6)}{12}\Big)$$

mit Tag-des-Jahres `d`, Stunde-des-Tages `h`, Skalierung `s_load` (Slider). Winterpeak
(Tag 355 ≈ Weihnachten) und Tagesmittagsspitze sind eingebaut. Die Wärmelast ist analog,
aber mit stärkerer Winter-Abhängigkeit (Faktor 0.55). Regional wird mit dem jeweiligen
**Lastanteil** aus `REGIONS` multipliziert.

### 3.5 Netzaufbau (Abschnitt 6) — *Herzstück*

**`build_network(prof, loads, co2_budget, co2_price, gas_price)`** baut das komplette
PyPSA-Netz:

| Komponente | Details |
|---|---|
| **Carrier** | wind, solar, hydro, gas, lignite, hardcoal, battery, H2, AC, heat – jeweils mit `co2_emissions` |
| **Buses** | 5 AC-Knoten (Regionen + Offshore) + 4 Wärme-Knoten + 1 H₂-Knoten |
| **Lines** | 7 Übertragungsleitungen (u. a. „SuedLink"), alle erweiterbar |
| **Generators** | Wind (on/offshore), Solar, Gas-CCGT, Braun-/Steinkohle, Laufwasser |
| **StorageUnits** | Pumpspeicher Süd + Batterien (Ost/West/Süd) |
| **H₂-System** | Elektrolyseur → H₂-Tank → Brennstoffzelle |
| **Wärme** | Wärmepumpe (WP) + Wärmespeicher je Region, mit COP 2.8–3.1 |
| **Loads** | Strom- und Wärmelast je Region |
| **GlobalConstraint** | `co2_limit`: Summe der Emissionen ≤ `co2_budget` |

Erweiterbare Anlagen (`p_nom_extendable=True`) haben `capital_cost = capex_annual(...)`
und werden vom Solver optimal dimensioniert.

### 3.6 Solver & Kennzahlen (Abschnitt 6b/7)

- **`solve_network(net)`** — löst mit **Gurobi** (falls lizenziert), sonst **HiGHS**.
  Nutzt `assign_all_duals=True`, damit Schattenpreise (Engpässe) verfügbar sind.
- **`total_co2(net)`** — CO₂-Emissionen [t/a]:

  $$\text{CO}_2 = \sum_{\text{Gen},\,t} p_{\text{Gen}}(t)\cdot \text{co2\_factor}(\text{Träger})\cdot\text{TIME\_RES}$$

- **`re_share(net)`** — EE-Anteil [%] = Erzeugung aus **wind + solar + hydro**
  geteilt durch die Gesamterzeugung × 100.

### 3.7 Läufe

- **`run_base(co2_budget, co2_price, load_scale, heat_scale, discount_rate, gas_price)`**
  — baut + löst ein Szenario, liefert `(netz, era5_ok)`. Setzt bei Bedarf
  `DISCOUNT_RATE` temporär und stellt ihn danach wieder her.
- **`run_monte_carlo(n_mc, ...)`** — wiederholt den Lauf über `n_mc` synthetische
  Wetterjahre und sammelt Kosten/CO₂/EE-Anteil in einer Tabelle (Robustheitsprüfung).

### 3.8 Unter der Haube ① – Was der Solver *genau* macht

PyPSA übersetzt das Netz in ein **lineares Optimierungsproblem (LP)** und übergibt es
an den Solver (Gurobi/HiGHS). Da das Modell keine Ganzzahl-Entscheidungen enthält
(keine An/Aus-Schaltlogik/Unit-Commitment), ist es ein *reines* LP und wird zum
**globalen Kostenminimum** gelöst.

**Zielfunktion** (wird minimiert) – die annualisierten Gesamtkosten:

$$\min \;\underbrace{\sum_i c^{\text{capex}}_i \cdot P^{\text{nom}}_i}_{\text{Investition (Zubau)}} \;+\; \underbrace{\sum_{i,t} c^{\text{opex}}_i \cdot p_{i}(t)\cdot w_t}_{\text{Betrieb (Einsatz)}}$$

- $P^{\text{nom}}_i$ = zu bauende Kapazität (Entscheidungsvariable, für erweiterbare Anlagen),
- $p_i(t)$ = Einsatz/Erzeugung je Stunde (Entscheidungsvariable),
- $w_t$ = `snapshot_weightings` (bei `TIME_RES` Stunden pro Schritt),
- $c^{\text{capex}}$ = `capex_annual(...)`, $c^{\text{opex}}$ = `opex(...)`.

**Nebenbedingungen** (was der Solver einhalten *muss*):

| Bedingung | Bedeutung |
|---|---|
| **Energiebilanz je Knoten & Stunde** | An jedem Bus gilt: Erzeugung + Zufluss − Abfluss − Last = 0 (Kirchhoff'sche Knotenregel). |
| **Erzeuger-Grenzen** | $0 \le p_i(t) \le p^{\text{max,pu}}_i(t)\cdot P^{\text{nom}}_i$ — Wind/Solar sind über den **Kapazitätsfaktor** wetterabhängig gedeckelt. |
| **Leitungsflüsse** | Lastfluss ≤ Leitungskapazität; die Flüsse folgen der linearisierten (DC-)Lastflussphysik über die Reaktanzen. |
| **Speicher-Dynamik** | Ladezustand(t) = Ladezustand(t−1) + η·Laden − Entladen/η; zyklisch (Anfang = Ende). |
| **CO₂-Budget** | $\sum p \cdot \text{co2\_factor}\cdot w_t \le$ `co2_budget` (die `GlobalConstraint`). |
| **Ausbaugrenzen** | $P^{\text{nom}}_{\min} \le P^{\text{nom}}_i \le P^{\text{nom}}_{\max}$. |

**Wie wird gelöst?** Der Solver nutzt Simplex- oder Innere-Punkte-(Barrier-)Verfahren
und findet die kostenminimale Kombination aus **Zubau** *und* **stündlichem Einsatz**
gleichzeitig.

**Schattenpreise (Duale) = die Preise im Modell.** Zu jeder Nebenbedingung liefert das
LP einen „Dualwert": wie stark sinken die Gesamtkosten, wenn man die Bedingung um eine
Einheit lockert. Deshalb ist der **Knotenpreis** (Strompreis einer Region) exakt der
Dualwert der Energiebilanz – die Grenzkosten der nächsten MWh an diesem Knoten. Die
Engpass-Schattenpreise im Tab *Engpässe* sind die Duale der Leitungs-/Erzeugergrenzen
(dafür läuft der Solver mit `assign_all_duals=True`).

### 3.9 Unter der Haube ② – Wie `atlite` ERA5-Wetter in Erzeugung umrechnet

Das Modell rechnet **nicht** mit Windgeschwindigkeit oder Einstrahlung direkt, sondern
mit **Kapazitätsfaktoren** (0–1) – dem Anteil der Nennleistung, den eine Anlage in einer
Stunde liefern kann. Diese Umrechnung übernimmt die Bibliothek `atlite` in
`_era5_region()`; das Ergebnis wird als `p_max_pu` an die Generatoren gehängt.

**Wind** — `cut.wind(turbine="Vestas_V112_3MW", per_unit=True, …)`:
1. ERA5 liefert die **Windgeschwindigkeit** (≈100 m Höhe) je Gitterzelle und Stunde.
2. `atlite` **extrapoliert** sie auf die **Nabenhöhe** der Turbine (logarithmisches
   Windprofil mit der Oberflächen-Rauhigkeit aus ERA5).
3. Auf die Nabenhöhen-Windgeschwindigkeit wird die **Leistungskennlinie** der Turbine
   angewandt (Anlauf ~3 m/s, Nennleistung ~12 m/s, Abschaltung ~25 m/s). Das ergibt
   die momentane Leistung → geteilt durch die Nennleistung = **Kapazitätsfaktor**.

**Solar (PV)** — `cut.pv(panel="CSi", orientation={"slope":35, "azimuth":180}, …)`:
1. ERA5 liefert die **Solarstrahlung** (direkt + diffus) und die Lufttemperatur.
2. `atlite` berechnet den **Sonnenstand** und transponiert die Strahlung auf die
   **geneigte Modulebene** (hier 35° Neigung, nach Süden = Azimut 180°).
3. Ein **Panel-Modell** (kristallines Silizium, `CSi`) rechnet Einstrahlung → Leistung,
   inkl. **Temperatur-Korrektur** (heiße Module = etwas weniger Wirkungsgrad). Ergebnis:
   **Kapazitätsfaktor**.

**Danach im Modell:** Die tatsächliche Erzeugung ist immer

$$p_{\text{EE}}(t) \;=\; P^{\text{nom}} \times \text{Kapazitätsfaktor}(t)$$

wobei der Solver $P^{\text{nom}}$ (Zubau) optimiert und den Kapazitätsfaktor als feste
wetterabhängige Obergrenze `p_max_pu(t)` erhält. Ohne ERA5 (kein `atlite`) liefert
`_synthetic_base()` ersatzweise plausible Kapazitätsfaktoren aus Jahres-/Tagesgang plus
Zufall.

> ℹ️ **Kurz gesagt:** ERA5 = physikalisches Wetter → `atlite` macht daraus über
> Turbinen-/Panel-Kennlinien einen **Kapazitätsfaktor** → der Solver entscheidet, wie
> viel Kapazität sich lohnt und wie sie stündlich eingesetzt wird.

### 3.10 Unter der Haube ③ – Wie die Monte-Carlo-Analyse funktioniert

Ein einzelner Modelllauf nutzt **ein** Wetterjahr. Aber Wind- und Solarangebot
schwanken von Jahr zu Jahr stark – ein in einem windreichen Jahr optimales System kann
in einem Dunkelflauten-Jahr teuer werden. Die **Monte-Carlo-Analyse**
(`run_monte_carlo()`) prüft deshalb, wie **robust** die Ergebnisse gegenüber der
Wettervariabilität sind.

**Das Prinzip:** Statt einmal zu rechnen, wird das komplette Modell **N-mal** gelöst –
jedes Mal mit einem anderen, zufällig erzeugten „Wetterjahr" – und die Kennzahlen
werden gesammelt. Aus der Streuung dieser N Läufe entsteht ein Bild der Unsicherheit.

```python
for i in range(n_mc):                       # N Wetterjahre
    prof  = make_profiles(mc_seed=i)        # (1) zufälliges Wetter je Jahr
    loads = make_loads(mc_seed=i)           # (2) ±5 % zufällige Nachfrage
    nm = build_network(prof, loads, …)      # (3) Modell neu bauen
    solve_network(nm)                        # (4) neu optimieren
    → sammle Kosten, CO₂, EE-Anteil          # (5) Kennzahlen ablegen
```

**Was von Lauf zu Lauf variiert:**
1. **Wetter** – `make_profiles(mc_seed=i)` erzeugt über den Startwert (Seed) `i`
   andere synthetische Wind-/Solar-/Offshore-Profile (Jahres- und Tagesgang plus
   Zufall). Jedes `i` = ein anderes plausibles Wetterjahr.
2. **Nachfrage** – `make_loads(mc_seed=i)` skaliert Strom- und Wärmelast um jeweils
   **±5 %** zufällig (`1 + U(−0.05, 0.05)`).
3. CO₂-Budget und CO₂-Preis bleiben **fest** (aus der Sidebar) – variiert wird nur die
   „Natur", nicht die Politik.

**Reproduzierbar:** Die Seeds sind deterministisch aus `i` abgeleitet
(`_synthetic_base(i·17+3, …)`), d. h. dieselbe Anzahl Jahre liefert **immer dieselben**
Ergebnisse – gut für eine nachvollziehbare Beleg-/Forschungsarbeit.

**Was ausgewertet wird:** Pro Jahr werden **Gesamtkosten**, **CO₂** und **EE-Anteil**
in eine Tabelle geschrieben (fehlgeschlagene Läufe → `NaN` mit Fehlerstatus). Der
Monte-Carlo-Tab zeigt daraus **Mittelwert ± Standardabweichung** und die Kosten je
Jahr. Interpretation: **große Streuung = wetterempfindliches System**, kleine Streuung
= robuste Auslegung.

> ⚠️ **Ehrliche Einordnung (wichtig fürs Verständnis):**
> - Es wird **synthetisches** Wetter gewürfelt, **nicht** aus historischen ERA5-Jahren
>   gezogen – die Bandbreite ist plausibel, aber nicht empirisch kalibriert.
> - In **jedem** Jahr wird der Kapazitätsausbau **neu optimiert** (Greenfield). Die
>   Analyse misst also die Streuung des *jeweils optimalen* Systems über Wetterjahre –
>   **nicht**, wie gut *ein fest gebautes* System viele Jahre übersteht. Ein echter
>   „Robustheitstest einer Auslegung" würde die Kapazitäten fixieren und nur das Wetter
>   variieren (mögliche Ausbaustufe).
> - Jeder Lauf hat **perfekte Voraussicht** über sein Jahr (wie das Grundmodell).

> 💡 **Rechenzeit:** N Jahre = N komplette Optimierungen. Der Slider erlaubt bis 60 –
> für einen schnellen Eindruck 5–10 nehmen.

---

## 4. `deutschland_gui.py` – Das Dashboard

Ein **Streamlit**-Overlay über das Modell. Grundprinzip: Sidebar-Parameter → Klick
auf *„Modell optimieren"* → gecachter Lauf → Ergebnis-Tabs.

### 4.1 Sidebar-Slider

| Gruppe | Slider | Wirkung im Modell |
|---|---|---|
| 🌍 Klima | **CO₂-Budget (Mt/a)** | Obergrenze `co2_limit` |
| 🌍 Klima | **CO₂-Preis (€/t)** | Aufschlag in `opex()` |
| 🔌 Nachfrage | **Stromlast-Skalierung** | `load_scale` in `make_loads()` |
| 🔌 Nachfrage | **Wärmelast-Skalierung** | `heat_scale` (Elektrifizierung/Wärmepumpen) |
| 💰 Ökonomie | **Diskontsatz / WACC (%)** | `DISCOUNT_RATE` → Kapitalkosten des Zubaus |
| 💰 Ökonomie | **Gaspreis (€/MWh_th)** | `gas_price` → Merit-Order |
| — | **Monte-Carlo Wetterjahre (0–60)** | Anzahl Robustheitsläufe |

### 4.2 Caching (wichtig zu verstehen)

```python
@st.cache_resource   # solve(): pro Parameter-Kombination genau ein Lauf
@st.cache_data       # monte_carlo(), load_ref(): Ergebnisse gecacht
```
→ Gleiche Slider-Werte = **kein** Neurechnen. Neue Werte = neuer Lauf. Der Button
„🔄 Cache leeren & neu optimieren" (Tab *Engpässe*) erzwingt eine Neuberechnung.

### 4.3 Die Tabs

| Tab | Inhalt |
|---|---|
| 📊 **Dispatch** | Wochenweiser Erzeugungsverlauf (gestapelt) vs. Last |
| 🏗️ **Kapazitäten** | Optimierter Zubau je Anlage, Jahreserzeugung, Netz-/Sektorausbau |
| 💶 **Preise** | Knotenpreise je Region (Verlauf, Verteilung, Monatsheatmap) |
| 🔋 **Speicher & H₂** | Füllstände Batterien, Pumpspeicher, H₂-Tank, Wärmespeicher |
| 🗺️ **Karte** | Geografische Karte mit Leitungsauslastung (Ampelfarben) |
| 🚧 **Engpässe** | Schattenpreise (Duale): Leitungs- & Erzeuger-Knappheit, Sektorpreise |
| ⚖️ **Vergleich** | 5-Zonen-Modell vs. Ein-Knoten-Referenz (→ Kapitel 5) |
| 🎲 **Monte-Carlo** | Kosten/CO₂/EE über mehrere Wetterjahre |
| 📄 **Bericht** | Erzeugt Plots + PDF-Bericht zum Download |

> ⚠️ **Streamlit-Regel:** Jedes interaktive Widget braucht eine eindeutige ID. Zwei
> gleiche Widgets (z. B. zwei „Woche im Jahr"-Slider) mit identischen Parametern
> kollidieren → `StreamlitDuplicateElementId`. Lösung: `key="…"` vergeben (siehe
> `key="woche_vergleich"` im Vergleich-Tab).

---

## 5. Der Vergleich mit dem Ein-Knoten-Modell

Der Tab **⚖️ Vergleich** stellt das eigene 5-Zonen-Modell einem externen
**Ein-Knoten-Deutschland-Modell** („Kupferplatte", ein einziger Knoten) gegenüber,
das als Excel vorliegt.

### 5.1 Die Referenzdaten

Die Referenz enthält je **Wetterjahr (2007 / 2009**, Verbrauchsjahr 2026) stündliche
**Dispatch-Zeitreihen** [MW] je Technologie plus die Last. Die Daten werden **nicht im
Git-Repo** abgelegt (Datenschutz/Rechte) und in dieser Reihenfolge gesucht:

1. `Referenzdaten/referenz_<jahr>.csv` — schlanke CSV (bevorzugt, je ~1 MB)
2. `Produktionsdaten für PyPSA.xlsx` — Original-Excel (Fallback)
3. **Datei-Upload** in der App — für die Cloud, wo es keinen lokalen Datenzugriff gibt
   (`st.file_uploader` im Vergleich-Tab, akzeptiert CSV **oder** XLSX)

Die CSVs entstehen aus der Excel per `pandas.read_excel(...).to_csv(...)` (ein Blatt →
eine Datei).

### 5.2 Träger-Mapping (`EXCEL_CARRIER_MAP`)

| Excel-Spalte | → Modell-Träger |
|---|---|
| `de-wind-on`, `de-wind-off` | **wind** |
| `de-sun` | **solar** |
| `de-water`, `de-pwater` | **hydro** |
| `de-nat gas` | **gas** |
| `de-lignite` | **lignite** |
| `de-coal` | **hardcoal** |
| `de-biomass`, `de-waste`, `de-fuel oil`, `de-other` | eigene Kategorien (im Modell nicht vorhanden) |

### 5.3 Wichtige Funktionen (in `deutschland_v1.py`)

- **`load_reference(sheet)`** — liest ein Wetterjahr-Blatt, aggregiert die
  Excel-Träger auf die Modell-Träger, richtet die Zeitreihen positionsweise auf die
  Modell-Snapshots aus (Stunde-des-Jahres) und berechnet Kennzahlen:
  - Jahreserzeugung [TWh] je Träger, Stromlast [TWh]
  - **EE-Anteil** (gleiche Definition wie `re_share`: wind + solar + hydro)
  - **Vergleichbare CO₂-Emission** mit denselben Emissionsfaktoren
    (`EXCEL_CO2 = {gas 0.37, lignite 1.0, hardcoal 0.8, oil 0.65}`)
- **`model_energy_by_carrier(net)`** — Jahreserzeugung [TWh] je Träger des Modells.
- **`model_gen_hourly(net)`** — stündliche Erzeugung je Träger (für das Overlay).

### 5.4 Was der Tab zeigt

1. **KPI-Gegenüberstellung** (Erzeugung, Last, EE-Anteil, CO₂, Peak-Last) + Deltas.
2. **Erzeugungsmix** als gruppiertes Balkendiagramm (Modell vs. Referenz je Träger).
3. **Dispatch-Overlay** — beide Kurven übereinander, wählbar nach Größe
   (Gesamterzeugung / Last / EE / einzelner Träger) und Woche.

> **Ehrliche Einschränkungen** (stehen auch als Hinweis im Tab):
> - **Kosten** werden nicht verglichen (die Excel enthält keine Kostendaten).
> - Träger wie *biomass/waste/oil* gibt es nur im Ein-Knoten-Modell; *Batterie/H₂/
>   Pumpspeicher* des 5-Zonen-Modells sind keine Generatoren und daher nicht im Mix.
> - Die Wetterjahre unterscheiden sich → Overlay erfolgt über die **Stunde des
>   Jahres**, nicht über das Kalenderdatum.

---

## 6. Formelsammlung (Kurzreferenz)

| Größe | Formel |
|---|---|
| Annuitätenfaktor | `a(n,r) = r / (1 − (1+r)^−n)` |
| Jährl. Kapitalkosten | `capex_annual = Investition · a(Lebensdauer, WACC)` |
| Grenzkosten Gas | `gas_price + 0.370 · co2_price` |
| Grenzkosten Braunkohle | `28 + 1.000 · co2_price` |
| Grenzkosten Steinkohle | `40 + 0.800 · co2_price` |
| CO₂-Emission | `Σ p_gen · co2_factor(Träger) · TIME_RES` |
| EE-Anteil | `100 · Σp(wind,solar,hydro) / Σp_gesamt` |
| Stromlast | `BASE_LOAD · s · (1+0.20·cos…) · (1+0.15·sin…)` |
| Referenz-CO₂ | `Σ dispatch[c] · EXCEL_CO2[c]` |

**Emissionsfaktoren [t CO₂/MWh]:** Gas 0.370 · Steinkohle 0.800 · Braunkohle 1.000 ·
Öl 0.650 · Wind/Solar/Hydro/Biomasse 0.

---

## 7. Häufige Fragen / Troubleshooting

| Problem | Ursache & Lösung |
|---|---|
| `UnicodeEncodeError: … '✓'` | Windows-Konsole nutzt cp1252. Skript stellt stdout auf UTF-8 um; alternativ `PYTHONUTF8=1` setzen. |
| `ModuleNotFoundError: openpyxl` | Für den Excel-Import nötig: `pip install openpyxl` (steht in der Auto-Install-Liste). |
| `StreamlitDuplicateElementId` | Zwei gleiche Widgets → einem ein `key="…"` geben. |
| `did not find executable … python.exe` | `.venv\pyvenv.cfg` zeigt auf einen alten Profilpfad → Pfad dort korrigieren. |
| Vergleich-Tab: „Keine Referenzdaten gefunden" | CSV in `Referenzdaten/` legen **oder** in der App hochladen (CSV/XLSX). |
| Optimierung dauert ewig | Monte-Carlo-Jahre reduzieren; jeder Lauf ist eine komplette Optimierung. |

---

## 8. Deployment (Streamlit Cloud) & Secrets

Die App lässt sich über **Streamlit Community Cloud** direkt aus dem GitHub-Repo
online stellen. Wichtig ist das Verständnis: **Die Cloud läuft auf fremden Servern und
hat keinen Zugriff auf deinen PC** – also weder auf die lokale `.env`, lokale Dateien
noch eine PC-gebundene Lizenz. Alles, was die App braucht, muss ihr auf einem der
folgenden Wege bereitgestellt werden.

### 8.1 Abhängigkeiten – `requirements.txt`

Die Cloud installiert **ausschließlich** Pakete aus `requirements.txt`. Fehlt sie,
scheitert der Start mit `ModuleNotFoundError` (z. B. `plotly`). Die Datei liegt im
Repo-Wurzelverzeichnis; `gurobipy` ist enthalten (nur mit Lizenz aktiv), `atlite`
bewusst **nicht** (ERA5-Download in der Cloud unpraktikabel → synthetisches Wetter).

### 8.2 Geheimnisse – Streamlit Secrets

API-Keys und Lizenzen gehören **nicht** ins Repo, sondern unter
*Manage app → Settings → Secrets* (ein TOML-Feld). Beispiel:

```toml
# CDS / ERA5 (nur relevant, wenn atlite lokal genutzt wird)
CDS_KEY = "dein-cds-key"

# Gurobi WLS-Lizenz (Web License Service – funktioniert in der Cloud!)
GRB_WLSACCESSID = "…"
GRB_WLSSECRET   = "…"
GRB_LICENSEID   = "1234567"
```

**Wie kommen die Secrets ins Modell?** `deutschland_v1.py` liest die Zugangsdaten aus
Umgebungsvariablen (`os.getenv`). `deutschland_gui.py` spiegelt daher die Secrets
**vor** dem Import des Modells nach `os.environ`:

```python
for _k, _v in dict(st.secrets).items():
    if isinstance(_v, (str, int, float)):
        os.environ.setdefault(str(_k), str(_v))
```

> Damit ist eine **Cloud-Lizenz** (Gurobi WLS) tatsächlich nutzbar – der Aufruf läuft
> vom Cloud-Server, nicht von deinem PC. Ist kein Secret gesetzt, fällt das Modell
> automatisch auf **HiGHS** zurück.

### 8.3 Referenzdaten in der Cloud

Der Datensatz (~2–3 MB als CSV) ist **zu groß für Secrets** (die sind für kleine
Schlüssel gedacht). Da die Daten außerdem privat bleiben sollen, liegen sie **nicht**
im Repo. In der Cloud stellt man sie deshalb über den **Datei-Upload** im Vergleich-Tab
bereit (CSV oder XLSX, passend zum gewählten Wetterjahr). Lokal werden sie automatisch
aus `Referenzdaten/` geladen – kein Upload nötig.

### 8.4 Realistische Grenzen des kostenlosen Tiers

- **Speicher/Zeit:** Der Free-Tier hat ~1 GB RAM. Eine volle stündliche
  Jahresoptimierung – erst recht Monte-Carlo über viele Jahre – kann daran scheitern.
  Für eine flüssige Online-Demo `TIME_RES` erhöhen (z. B. 3) → deutlich leichter.
- **Python-Version:** Falls ein Paket beim Build fehlt, unter *Settings* eine
  unterstützte Version wählen (z. B. 3.11/3.12; nicht 3.14).

### 8.5 Alternativen

| Weg | Wofür |
|---|---|
| **Docker-Container** | Reproduzierbarer Betrieb (App + Abhängigkeiten paketiert) – gut für Forschung/Server. |
| **Eigener Server / VPS** | Dauerbetrieb, mehr RAM/CPU für schwere Läufe. |
| **`start_app.bat`-Launcher** | Lokale „Doppelklick"-Weitergabe ohne echte EXE (startet venv + `streamlit run`). |

---

## 9. Europäische Kopplung (Nachbarländer)

Optional lassen sich **11 Nachbarländer** als je **ein Knoten** ankoppeln
(Sidebar → 🌍 Europa → *Nachbarländer koppeln*). So werden **Import/Export**,
realistischere Preise und Grenzengpässe abbildbar. Aktiviert wird das über
`run_base(..., include_neighbors=True)` bzw. `build_network(..., include_neighbors=True)`.

### 9.1 Modellierungsansatz

| Aspekt | Umsetzung |
|---|---|
| **Länder** | FR, BE, LU, NL, DK, PL, CZ, AT, CH, SE, NO – je 1 AC-Knoten |
| **Erzeugung** | feste Flotte je Land (nuclear, lignite, hardcoal, gas, oil, hydro, wind, solar, biomass) – **nicht** erweiterbar |
| **Last** | Jahresverbrauch je Land, zeitliche Form aus der DE-Last abgeleitet |
| **Kuppelstellen** | `Link` DE-Zone ↔ Land mit **NTC**-Grenze (bidirektional). Bewusst `Link` statt `Line`, damit Karte/Engpässe-Tab DE-intern bleiben |
| **Ausbau** | **nur Deutschland** optimiert Zubau; Nachbarn sind Randbedingung |
| **CO₂-Budget** | gilt **nur für DE** (Custom-Constraint `co2_limit_DE` via `extra_functionality`); der CO₂-Preis (EU-ETS) wirkt dagegen **überall** |
| **Backup/VoLL** | je Auslandsknoten ein teurer Reserve-Generator (3000 €/MWh) → garantiert lösbar |

Die Daten stehen im `NEIGHBORS`-Dict in `deutschland_v1.py`
(Koordinaten, `demand_twh`, `zone`, `ntc`, `fleet`, `wind_k`/`solar_k`).

**Wetter im Ausland:** standardmäßig synthetisch (länderspezifisch skaliert).
Optional per Sidebar-Schalter **Ausland: ERA5-Wetter** (`foreign_era5=True`) aus
echten ERA5-Daten – je Land über `ERA5_BOXES_NEIGHBORS` und dieselbe
`_era5_region()`-Funktion wie für DE. ⚠ Der erste Lauf lädt je Land via CDS herunter
(dauert, nur lokal mit `atlite` + CDS-Key); pro Land automatischer synthetischer
Fallback bei Fehler.

**Karte:** Bei Kopplung erscheinen die Nachbarländer als graue Marker (Hover:
installierte Leistung + Netto-Import), und die Kuppelstellen werden als gepunktete
Linien mit Auslastungs-Ampel (grün/gelb/rot) gezeichnet.

### 9.2 Was sich an den Kennzahlen ändert

- **Erzeugungs-KPIs** (CO₂, EE-Anteil, Erzeugung) werden auf **deutsche Knoten
  gefiltert** (`total_co2(net, DE_AC_BUSES)`, `re_share(net, DE_AC_BUSES)`,
  `model_energy_by_carrier`), damit sie nicht mit dem Ausland vermischt werden.
- **Gesamtkosten** = `total_cost(net)` = `objective + objective_constant`. Bei
  Kopplung umfasst das das **gesamte** gekoppelte System (DE + Nachbarn).
- Neuer Tab **🌍 Nachbarn**: Netto-Import DE, Jahresbilanz je Land und der
  Kuppelstellen-Fluss über eine Woche.

> ⚠️ **Wichtige Korrektur an „Gesamtkosten" (betrifft auch den Solo-DE-Lauf):**
> PyPSA trennt die Zielfunktion in `objective` (variabel) und `objective_constant`
> (Fixkosten der Bestandskapazität). Früher zeigte die GUI nur `objective` – der
> **konstante** Teil (~18 Mrd €/a Bestandskapazität) fehlte. Jetzt wird konsistent
> `total_cost = objective + objective_constant` verwendet. Dadurch steigt die
> angezeigte „Gesamtkosten"-Zahl auch **ohne** Nachbarn – das ist die **korrektere**
> Gesamtsystemkosten-Angabe, kein Fehler.

### 9.3 Ehrliche Einordnung (für Review/Beleg)

- **Datenbasis** der Nachbarn: grobe, **literaturbasierte ~2023-Näherung**
  (installierte Leistung, Verbrauch, NTC). Für belastbare Studien durch
  **ENTSO-E**-/**PyPSA-Eur**-Daten ersetzen.
- **Wetter im Ausland**: standardmäßig **synthetisch**; optional **ERA5** per
  Schalter (nur lokal, erster Lauf lädt via CDS).
- **Nachbarn ohne Ausbau, ohne Speicher/Sektorkopplung** – reine Randbedingung.
- **Auslandshydro** vereinfacht als flache Verfügbarkeit (`p_max_pu`), Kernkraft als
  Baseload (`p_max_pu≈0.9`).
- **Rechenlast** steigt (mehr Knoten/Variablen) – mit Gurobi unkritisch, für HiGHS
  ggf. `TIME_RES` erhöhen.

> **Mögliche nächste Ausbaustufen:** echte ENTSO-E-Kapazitäten/NTC, ERA5-Wetter je
> Land, Speicher/Pumpspeicher im Ausland, mehrere Gebotszonen (z. B. DK1/DK2, NO2/NO5).

---

*Diese Doku wird bei Code-Änderungen aktualisiert. Letzte inhaltliche Pflege siehe
„Stand" ganz oben.*
