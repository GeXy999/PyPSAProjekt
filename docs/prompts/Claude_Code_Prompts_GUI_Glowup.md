# Claude Code Prompts – GUI "richtig geil" machen 🔥

> Sammlung von Prompts für alle in der letzten Ideenrunde besprochenen
> Features. Jeder Prompt ist einzeln nutzbar – probier aus, was dir
> gefällt, und wirf den Rest einfach weg. Am besten in einem eigenen
> Branch testen (`git checkout -b feature/gui-glowup`).

---



---

## 3. Konfetti/Erfolgs-Animation bei guten Ergebnissen

```
Füge in deutschland_gui.py direkt nach der Berechnung der KPIs (co2, ee,
total_cost) eine Erfolgs-Logik hinzu: Wenn ee > 80, rufe st.balloons()
auf und zeige st.success("🌱 Exzellenter EE-Anteil! Über 80% erneuerbare
Erzeugung erreicht."). Wenn co2 < co2_budget_mt * 0.7 (CO2 deutlich unter
Budget), rufe st.snow() auf und zeige eine passende Erfolgsmeldung. Stelle
sicher, dass diese Effekte nur einmal pro neuem Solve-Ergebnis ausgelöst
werden (nicht bei jedem Streamlit-Rerun), indem du einen Hash/Zeitstempel
des aktuellen Ergebnisses mit st.session_state.last_celebrated
vergleichst.
```

---

## 4. Dynamisches Hero-Banner je Szenario-Ergebnis

```
Passe in deutschland_gui.py den bestehenden .de-hero CSS-Block und das
zugehörige st.markdown so an, dass der Hintergrund-Gradient des Headers
sich nach dem Solve dynamisch an den EE-Anteil (ee) anpasst: Bei ee > 70
ein grünliches Gradient (z.B. #0a4023 -> #123a5c), bei ee zwischen 40-70
das bestehende Blau, bei ee < 40 ein wärmeres/rötliches Gradient
(#4a1e12 -> #123a5c). Baue die Farbwerte als Python-f-string direkt in
den style="..."-Attribut des <div class="de-hero">-Blocks ein, statt sie
fix im <style>-Block zu setzen. Der Effekt soll erst nach dem ersten
erfolgreichen Solve aktiv werden; vor dem ersten Lauf bleibt das
Standard-Blau erhalten.
```

---

## 5. Szenario-Challenge-Modus

```
Füge deutschland_gui.py einen neuen Sidebar-Bereich "🎯 Challenge" hinzu
mit einem Dropdown zur Auswahl vordefinierter Ziele, z.B.:
- "90% EE bei unter 60 Mrd €/a"
- "CO2 unter 50 Mt/a bei unter 70 Mrd €/a"
- "Kostenoptimum ohne CO2-Limit"
Nach jedem Solve prüfe automatisch, ob das gewählte Challenge-Ziel
erreicht wurde (Vergleich der KPIs mit den im Dropdown hinterlegten
Grenzwerten, als Dictionary CHALLENGES = {...} am Skriptanfang definiert).
Zeige bei Erfolg eine Erfolgsbox mit Badge-Emoji (🏆) und bei Misserfolg
eine Hinweisbox, wie weit das Ergebnis vom Ziel entfernt ist (z.B. "EE-
Anteil um 8 Prozentpunkte zu niedrig").
```

---

## 6. Live-Vorschau bei Slider-Bewegung

```
Ergänze in deutschland_gui.py neben dem CO2-Preis-Slider und dem
Gaspreis-Slider in der Sidebar eine leichte Heuristik-Vorschau (ohne
den vollen Solver aufzurufen): Berechne anhand einfacher Faustformeln
(z.B. linearer Zusammenhang aus den letzten 3-5 gespeicherten Läufen in
st.session_state.runs via numpy.polyfit) eine grobe Schätzung, wie sich
eine Slider-Änderung auf total_cost und ee auswirken könnte. Zeige diese
Schätzung als kleinen st.caption-Text direkt unter dem jeweiligen
Slider, z.B. "→ geschätzt: +3.2 Mrd €/a, +5% EE (Schätzung, kein
tatsächlicher Solve)". Wenn zu wenige historische Läufe vorhanden sind,
zeige stattdessen "Noch keine Schätzung möglich – bitte erst mehrfach
optimieren".
```

---

## 7. Vorher/Nachher-Vergleichsslider auf der Karte

```
Implementiere in deutschland_gui.py einen neuen Tab "🔄 Vorher/Nachher",
der zwei gespeicherte Läufe aus st.session_state.runs per Dropdown
auswählen lässt (Lauf A und Lauf B). Zeige darunter zwei Karten
nebeneinander (st.columns([1,1])) mit den jeweiligen
Kapazitäts-/Auslastungsdaten, sowie eine Delta-Tabelle darunter, die
die Unterschiede in Gesamtkosten, CO2, EE-Anteil und installierter
Leistung je Zone zwischen den beiden Läufen zeigt (mit +/- Vorzeichen
und Farbkennzeichnung: grün bei Verbesserung, rot bei Verschlechterung).
```

---

## 8. 3D-Kapazitäts-Visualisierung

```
Erweitere den Kapazitäten-Tab in deutschland_gui.py um eine zusätzliche
3D-Visualisierung mit go.Bar3d oder go.Surface: Zeige die installierte
Kapazität je Energieträger (x-Achse) und je Zone (y-Achse) als
Höhenwert (z-Achse) in einem interaktiven 3D-Balkendiagramm. Nutze die
bestehende FARBEN-Palette für die Einfärbung der Energieträger. Platziere
die 3D-Ansicht als optionalen Expander "🧊 3D-Ansicht" unterhalb der
bestehenden 2D-Kapazitätscharts, damit die Standardansicht unverändert
bleibt.
```




## 11. Zeitreise-Modus (Zeitraffer über das Jahr)

```
Füge im Dispatch-Tab von deutschland_gui.py eine Zeitraffer-Funktion
hinzu: Ein Play/Pause-Button (st.button mit Session-State-Flag) und ein
st.slider "Stunde im Jahr" (0-8760), der bei aktivem Play-Modus über
eine Schleife mit time.sleep(0.05) und st.rerun() automatisch
weiterläuft und dabei sowohl den Dispatch-Chart als auch die
Kartenansicht (Leitungsauslastung zum jeweiligen Zeitschritt) synchron
aktualisiert. Baue eine Geschwindigkeitsauswahl (1x/5x/20x Stunden pro
Schritt) ein. Achte darauf, dass der Play-Modus über einen expliziten
Stop-Button beendet werden kann, um Endlosschleifen zu vermeiden.
```

---

## 12. Vergleichs-Badge-System für gespeicherte Läufe

```
Erweitere den "Läufe"-Vergleichstab in deutschland_gui.py (falls noch
nicht vorhanden, zuerst anlegen wie im GUI-Polish-Prompt beschrieben) um
ein automatisches Badge-System: Vergib für die Liste der gespeicherten
Läufe in st.session_state.runs automatisch Abzeichen als Text/Emoji-
Spalte in der Vergleichstabelle: "🏆 Günstigster" (niedrigste total_cost),
"🌱 Grünster" (höchster ee-Wert), "⚡ Meiste Erzeugung" (höchster
erz_twh). Zeige die Badges sowohl in der Tabelle als auch als separate
st.metric-Kacheln oberhalb der Tabelle mit Verweis auf den jeweiligen
Lauf-Zeitstempel.
```


## Hinweise zur Anwendung

- Bitte NICHT alle 13 Prompts gleichzeitig einsetzen – wähle 2-3 Favoriten
  aus und teste sie einzeln, damit du bei Problemen genau weißt, welche
  Änderung den Fehler verursacht hat.
- Empfehlung für den größten Sofort-Effekt bei vertretbarem Aufwand:
  Prompt 2 (Sparklines), Prompt 3 (Konfetti/Erfolg) und Prompt 10
  ("Ergebnis erklären") zuerst ausprobieren.
- Aufwendigere/experimentelle Prompts (1, 9, 11) eher für später, wenn
  die Basis-Features stabil laufen – diese können performance-kritisch
  sein (viele Rerun-Zyklen) und erfordern ggf. Nachjustierung.
- Immer in einem eigenen Branch testen:
  `git checkout -b feature/gui-glowup`.
