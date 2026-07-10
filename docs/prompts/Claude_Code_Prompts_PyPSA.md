# Claude Code Prompts – PyPSA Deutschland-Projekt Erweiterung

> Sammlung von einsetzbaren Prompts für Claude Code, um das Projekt
> `PyPSAProjekt-main` (deutschland_v1.py + deutschland_gui.py) schrittweise
> zu erweitern. Jeder Prompt ist für sich nutzbar – am besten nacheinander
> abarbeiten und nach jedem Schritt testen/committen.

---

## 1. Batteriespeicher als vollwertige Komponente

```
Analysiere deutschland_v1.py und finde alle Stellen, an denen "battery"
oder Batteriespeicher bereits erwähnt werden. Erweitere das Modell um
eine vollwertige Großbatterie-Speicherkomponente (StorageUnit oder
Store+Link-Kombination) pro Zone, mit:
- Konfigurierbarer Kapazität (MWh) und Leistung (MW) als Ausbauoption
  (p_nom_extendable=True) mit Annuitätskosten wie bei den anderen
  Speichern im Code.
- Wirkungsgrad (round-trip efficiency) als Parameter.
- Ausgabe der optimalen Batteriekapazität je Zone in den bestehenden
  Ergebnis-DataFrames und Plots (plot_capacities, plot_storage_prices).
Halte dich an den bestehenden Code-Stil (Kommentare, Funktionsnamen,
Annuitäts-Helper wie annuity() und capex_annual()).
```

---

## 2. Elektromobilität als eigener Sektor

```
Füge deutschland_v1.py einen neuen Sektor "E-Mobilität" hinzu, analog zur
bestehenden Wärmepumpen-Logik (Link von Strom-Bus zu neuem EV-Bus,
Nachfrage als Load mit Zeitprofil). Implementiere:
- Ein EV-Lastprofil pro Zone (synthetisch, ähnlich _synthetic_base()),
  skalierbar über einen neuen Parameter ev_scale.
- Optionales Smart Charging: ein Store für die EV-Batteriekapazität mit
  Lade-/Entladefenstern, das PyPSA erlaubt, Ladezeiten zu optimieren.
- Einen Kill-Switch (Boolean-Parameter include_ev=False als Default),
  damit der bestehende Modelllauf ohne EV weiterhin unverändert
  funktioniert.
Dokumentiere die neuen Parameter im Docstring von build_network().
```

---

## 3. Demand-Side-Management (Lastverschiebung)

```
Implementiere in deutschland_v1.py eine einfache Demand-Side-Management
(DSM)-Option für die elektrische Grundlast: ein Anteil der Last (Parameter
dsm_share, z.B. 0-20%) soll innerhalb eines Zeitfensters (z.B. +/- 4h)
verschiebbar sein, modelliert über ein Store-Element mit Lade-/Entlade-
Constraints statt einer festen Load. Stelle sicher, dass die Gesamtenergie
pro Tag konstant bleibt (Energieerhaltung). Füge einen Parameter
enable_dsm: bool hinzu, der die Funktion optional aktiviert, ohne
bestehende Läufe zu verändern.
```

---

## 4. Sensitivitätsanalyse / Tornado-Diagramm

```
Erstelle eine neue Funktion run_sensitivity() in deutschland_v1.py, die
das Modell mehrfach mit variierten Einzelparametern (co2_price, gas_price,
discount_pct, load_scale) laufen lässt (jeweils +/-20% vom Basiswert,
andere Parameter konstant) und die Auswirkung auf total_cost() und
re_share() zurückgibt. Ergänze eine Plot-Funktion plot_tornado(), die die
Ergebnisse als horizontales Tornado-Diagramm (matplotlib) darstellt,
sortiert nach Einfluss-Stärke. Binde beides als neuen Tab in
deutschland_gui.py ein, mit einem Button "Sensitivitätsanalyse starten".
```

---

## 5. Validierung gegen reale Erzeugungsdaten

```
Schreibe eine neue Funktion validate_against_real_data() in
deutschland_v1.py, die die Modellergebnisse (model_energy_by_carrier())
mit realen historischen Erzeugungsdaten vergleicht. Nutze dafür zunächst
eine lokale CSV (z.B. data/Referenzdaten/entsoe_2023.csv, Format:
Zeitstempel, Carrier, MWh) als Platzhalter-Datenquelle, falls kein
Internetzugriff verfügbar ist. Berechne Abweichungen je Energieträger in
Prozent und erzeuge einen einfachen Balkenplot Modell vs. Realität.
Kommentiere klar, wo später ein echter ENTSO-E-API-Import ergänzt werden
könnte.
```

---

## 6. Unit-Tests für Kernfunktionen

```
Erstelle eine neue Datei tests/test_deutschland_v1.py mit pytest-Tests für
folgende Funktionen aus deutschland_v1.py: annuity(), capex_annual(),
opex(), total_co2(), re_share(), total_cost(). Nutze einfache, nachvollzieh-
bare Beispielwerte und prüfe auf plausible Grenzfälle (z.B. annuity() mit
Zinssatz 0, capex_annual() mit Lebensdauer 1 Jahr). Füge eine
requirements-dev.txt mit pytest hinzu und ergänze in der DOKUMENTATION.md
einen kurzen Abschnitt "Tests ausführen".
```

---

## 7. Szenario-Vergleichsbericht (mehrere Läufe)

```
Implementiere in deutschland_v1.py eine Funktion compare_scenarios(), die
mehrere vordefinierte Szenarien (z.B. "Basis", "Hohe Elektrifizierung",
"Importabhängig") nacheinander mit run_base() durchrechnet und die
wichtigsten Kennzahlen (total_cost, re_share, total_co2, Import/Export-
Bilanz) in einer zusammenfassenden Tabelle (pandas DataFrame) sowie einem
gruppierten Balkendiagramm gegenüberstellt. Ergänze in make_pdf() einen
optionalen Abschnitt, der diesen Szenarienvergleich ins PDF übernimmt,
falls compare_scenarios() vorher aufgerufen wurde.
```

---

## Hinweise zur Anwendung

- Prompts einzeln an Claude Code übergeben, nicht alle gleichzeitig –
  nach jedem Schritt `python deutschland_v1.py` testen.
- Vor größeren Änderungen einen Git-Branch anlegen
  (`git checkout -b feature/battery-storage`).
- Nach jeder erfolgreichen Erweiterung die `docs/DOKUMENTATION.md`
  entsprechend Abschnitt ergänzen lassen (kann als Zusatz-Prompt an
  Claude Code angehängt werden: "Aktualisiere DOKUMENTATION.md um diesen
  neuen Abschnitt").

---

## Bonus-Prompt: Dashboard-Slider für neue Features

```
Erweitere deutschland_gui.py um folgende neue Sidebar-Elemente in
Streamlit, jeweils mit sinnvollen Tooltips (help=...):
- st.checkbox("🔋 Großbatteriespeicher aktivieren", value=False)
- st.checkbox("🚗 E-Mobilität aktivieren", value=False)
  -> bei Aktivierung: st.slider("EV-Durchdringung (%)", 0, 100, 30)
- st.checkbox("⚡ Lastmanagement (DSM) aktivieren", value=False)
  -> bei Aktivierung: st.slider("Verschiebbarer Lastanteil (%)", 0, 20, 10)
- st.checkbox("🏭 Industriesektor mitmodellieren", value=False)
Reiche alle neuen Werte als Parameter an build_network() weiter und
zeige im Hauptbereich eine kurze Zusammenfassung ("Aktive Module: ...")
oberhalb der Ergebnis-Tabs an.
```
