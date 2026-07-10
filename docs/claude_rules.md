# CLAUDE.md

## Mission
Arbeite in diesem Repository so **effektiv, präzise und tokensparend** wie möglich.
Der Fokus liegt auf **Python**, **PyPSA**, **VS Code** und einem bereits eingebauten **Graphify**-Workflow.

## Arbeitsprinzipien
- Antworte standardmäßig knapp, technisch und lösungsorientiert.
- Vermeide Wiederholungen der Aufgabenstellung oder des bereits bekannten Kontexts.
- Lies nicht unnötig viele Dateien vollständig.
- Arbeite bevorzugt **diff-orientiert** statt vollständige Dateien neu auszugeben.
- Stelle nur dann Rückfragen, wenn ohne sie ein hohes Fehlerrisiko besteht.
- Wenn eine Aufgabe komplex ist, beginne mit einem sehr kurzen Plan mit maximal 5 Punkten.
- Nach einer abgeschlossenen Teilaufgabe: Status knapp komprimieren in „erledigt / offen / nächster Schritt“.

## Priorität: Graphify zuerst nutzen
Wenn Graphify-Daten vorhanden sind, nutze **zuerst Graphify** zur Orientierung, bevor rohe Dateisuche erfolgt.

### Reihenfolge der Kontextbeschaffung
1. Prüfe, ob `graphify-out/GRAPH_REPORT.md` existiert.
2. Lies zuerst `graphify-out/GRAPH_REPORT.md` für Architektur, Communities, zentrale Knoten und überraschende Verbindungen.
3. Nutze danach, wenn nötig, Graphify-Abfragen für präzise Navigation.
4. Greife erst danach zu rohen Dateioperationen wie breit angelegtem Grep/Glob/Read.
5. Öffne anschließend nur die wirklich relevanten Dateien oder Codeabschnitte.

### Graphify-Regeln
- Verwende Graphify bevorzugt für:
  - Architekturverständnis
  - Auffinden zentraler Module/Funktionen
  - Abhängigkeits- und Aufrufketten
  - Einstieg in unbekannte Teilbereiche
  - Refactoring über mehrere Dateien
  - Lokalisierung von Seiteneffekten
- Wenn Graphify einen klaren Pfad oder Zielknoten zeigt, lies zuerst diese Dateien statt breit im Repository zu suchen.
- Nutze `GRAPH_REPORT.md` als Primärübersicht und Rohdateien erst als Verifikation oder für konkrete Änderungen.
- Wenn Graphify veraltet wirkt und viele Dateien seitdem geändert wurden, schlage ein Graph-Update vor, bevor große Architekturentscheidungen getroffen werden.

## Graphify effektiv einsetzen
Wenn verfügbar, arbeite bevorzugt mit diesen Denkregeln:
- „Erst Struktur, dann Dateien.“
- „Erst zentrale Knoten, dann abhängige Details.“
- „Erst Communities prüfen, dann Einzeldateien öffnen.“
- „Nicht das ganze Repo lesen, wenn der Graph die relevanten Bereiche schon eingrenzt.“

Wenn ein Graph vorhanden ist, vermeide:
- blindes Grep über das ganze Repository,
- das Öffnen vieler ähnlicher Dateien auf Verdacht,
- Volltextlesen großer Verzeichnisse ohne vorherige strukturelle Orientierung.

## Python- und PyPSA-spezifische Regeln
- Bevorzuge kleine, präzise Änderungen an bestehenden Funktionen statt großflächiger Umschreibungen.
- Bei PyPSA-Aufgaben zuerst verstehen:
  - welche `Network`-Objekte betroffen sind,
  - welche Komponenten verändert werden (`buses`, `loads`, `generators`, `links`, `stores`, `storage_units`, `lines`, `transformers`),
  - ob das Problem in Datenvorbereitung, Netzaufbau, Optimierung oder Auswertung liegt.
- Bei PyPSA-Fehlern zuerst prüfen:
  - Index-/Spaltennamen,
  - Snapshots,
  - Carrier-Zuordnungen,
  - Einheiten und Vorzeichen,
  - `p_nom` / `e_nom` / Limits,
  - fehlende Zeitreihen,
  - Konsistenz der Komponentenbeziehungen.
- Bei DataFrame- oder Zeitreihenproblemen zuerst Form, Index, dtypes, NaNs und Beispielzeilen prüfen, statt ganze Dateien auszugeben.
- Bei Solver-/Optimierungsproblemen zuerst die kleinste reproduzierbare Ursache isolieren.

## VS Code Arbeitsstil
- Arbeite so, als ob Dateilesen teuer ist.
- Öffne nur die betroffenen Dateien und möglichst nur relevante Abschnitte.
- Wenn mehrere Dateien ähnlich aussehen, identifiziere zuerst die wahrscheinlich führende Datei oder den zentralen Einstiegspunkt.
- Nutze vorhandene Struktur im Projekt: `src/`, `scripts/`, `notebooks/`, `config/`, `data/`, `results/`, `tests/`.
- Bevorzuge Änderungen, die mit bestehenden Mustern, Imports und Projektkonventionen konsistent sind.

## Token-Sparregeln
- Keine langen Einleitungen.
- Keine Wiederholung des User-Prompts.
- Keine vollständige Ausgabe großer Dateien.
- Keine langen Logs vollständig zitieren; nur relevante Ausschnitte nutzen.
- Keine unnötigen Alternativen ausformulieren, wenn eine Option klar besser ist.
- Keine Erklärung von Basiswissen, außer wenn ausdrücklich gewünscht.
- Wenn dieselbe Aufgabe mit weniger Kontext lösbar ist, wähle die kleinere Kontexteinheit.
- Komprimiere Zwischenergebnisse aktiv.

## Modellverhalten
Nutze hohe Denktiefe nur bei echter Notwendigkeit.

### Hohe Denktiefe nur für
- Architekturentscheidungen
- komplexe PyPSA-Debuggingfälle
- Refactoring mit mehreren Abhängigkeiten
- Performance- oder Modellierungs-Trade-offs
- finale Qualitätsprüfung

### Niedrige bis mittlere Denktiefe für
- mechanische Codeänderungen
- einfache Refactors
- gezielte Bugfixes
- Umbenennungen
- Formatierung
- Tests, kleine Hilfsfunktionen, Boilerplate

## Vorgehen bei Aufgaben
1. Ziel in 1–2 Sätzen präzisieren.
2. Zuerst Graphify-Bericht bzw. strukturelle Hinweise nutzen, falls vorhanden.
3. Nur relevante Dateien oder Abschnitte lesen.
4. Bestehende Muster im Code erkennen.
5. Minimal-invasive Änderung umsetzen.
6. Ergebnis knapp prüfen.
7. Antwort kompakt halten: Änderung, Grund, nächster Schritt.

## Antwortformat
Bei Implementierungen:
- Was geändert wurde
- Warum diese Änderung passend ist
- Welche Datei(en) betroffen sind
- Nächster sinnvoller Prüf- oder Testschritt

Bei Debugging:
- Wahrscheinlichste Ursache zuerst
- Kleinster sinnvoller Fix oder Test zuerst
- Nur dann mehrere Hypothesen nennen, wenn die Lage wirklich unklar ist

Bei Architekturfragen:
- Erst Graphify-Zusammenhang nennen, dann konkrete Dateien/Funktionen
- Trade-offs kurz, nicht essayartig

## Umgang mit langen Sessions
Wenn der Verlauf lang wird:
- Erzeuge aktiv eine kompakte Zusammenfassung mit:
  - Ziel
  - aktueller Stand
  - betroffene Dateien
  - wichtige Entscheidungen
  - offene Probleme
  - nächster Schritt
- Arbeite danach auf Basis dieser Zusammenfassung weiter.

## Umgang mit Logs, Tabellen und Daten
- Analysiere zuerst nur die relevanten Fehlermeldungen oder Schlüsselspalten.
- Bei CSV/Parquet/JSON nur Struktur, Kopfzeilen, Spaltentypen und wenige Beispielzeilen prüfen.
- Bei Notebooks nicht das ganze Notebook ausgeben; nur relevante Zellen oder Funktionen betrachten.
- Bei Ergebnisauswertung zuerst Kennzahlen und Anomalien zusammenfassen.

## Was vermieden werden soll
- Blindes Lesen vieler Dateien trotz vorhandenem Graphify-Graph.
- Großflächige Umschreibungen ohne klaren Grund.
- Vollständige Neuerstellung bestehender Dateien bei kleinen Änderungen.
- Lange theoretische Erklärungen statt konkreter Umsetzung.
- Unnötig breite Suche im gesamten Repository.
- Wiederholung bekannter Projektregeln in jeder Antwort.

## Bevorzugte interne Leitfragen
- Gibt es schon Graphify-Hinweise auf die relevanten Knoten oder Communities?
- Welche kleinste Kontexteinheit reicht zur Lösung?
- Welche Datei ist der wahrscheinlichste Einstiegspunkt?
- Ist ein gezielter Patch besser als eine komplette Umschreibung?
- Reicht eine kurze technische Antwort statt einer langen Erklärung?

## Kompaktvorlage für neue Sessions
```md
Ziel:

Aktueller Stand:

Graphify-Hinweise:

Betroffene Dateien:

Wichtige Entscheidungen:

Offene Probleme:

Nächster Schritt:
```

## Optionales Verhalten bei vorhandenem Graphify-Setup
Wenn `graphify-out/GRAPH_REPORT.md` oder andere Graphify-Artefakte vorhanden sind, behandle sie als bevorzugte Navigationshilfe für Architektur- und Repo-Verständnis.
Wenn sie fehlen oder veraltet sind, weise knapp darauf hin und arbeite dann mit minimal nötiger Dateisuche weiter.
