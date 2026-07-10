# Projektregeln – Deutschland Energy Model

Verbindliche Arbeitsweise für dieses Repo → @docs/claude_rules.md

**Nicht-offensichtlicher Zwang:** `deutschland_v1.py` / `deutschland_gui.py` müssen im
Projekt-Root bleiben – alle Datenpfade sind `SCRIPT_DIR`-relativ (`OUTPUT_DIR`,
`ERA5_DIR`, `REFERENCE_DIR`). Verschieben bricht Cache & Referenzdaten.

## Bestehende Abmachungen (Vorrang, ergänzend zu claude_rules)
- **Doku pflegen:** `docs/DOKUMENTATION.md` bei Code-Änderungen mitziehen und das
  „Stand"-Datum oben aktualisieren (lebendes Dokument).
- **Beleg-Kontext:** Chat knapp halten, aber die **Doku darf ausführlich & lehrreich**
  sein (Dozent will alles nachvollziehen können) – Token-Sparen gilt für den Chat, nicht
  für die Doku-Qualität.
- **Datenschutz:** Referenzdaten (`data/`), Excel und `.env`/Secrets **niemals** ins Repo
  oder in die Git-Historie. Sind gitignored – so lassen.
- **Ehrlichkeit:** Grenzen/Vereinfachungen offen benennen (z. B. synthetisches Wetter,
  literaturbasierte Nachbardaten), keine Schönfärberei.
- **Ergebnistreue:** Änderungen, die „nichts an den Ergebnissen ändern" sollen, vorher
  verhaltensneutral verifizieren (numerisch/Reproduzierbarkeit), bevor committet wird.
- **Commits/Push** nur auf ausdrücklichen Wunsch; sinnvoll gruppieren, deutsche Messages.

## Ruflo / Agenten-Workflow
- Ruflo nur einsetzen, wenn die Aufgabe mehrstufig ist, mehrere Dateien betrifft oder parallele Rollen sinnvoll sind.
- Für kleine Ein-Datei-Änderungen, reine Textkorrekturen oder einfache Debug-Fixes keinen großen Swarm starten.
- Immer klein anfangen: erst 3–4 spezialisierte Agenten, nur bei echtem Bedarf skalieren.
- Rollen klar trennen:
  - Architekt: Projektstruktur, Abhängigkeiten, Vorgehen.
  - Coder: konkrete Implementierung.
  - Tester: Randfälle, Regressionen, Reproduzierbarkeit.
  - Reviewer: Schwachstellen, unnötige Komplexität, Folgerisiken.
- Vor dem Lesen vieler Dateien zuerst die relevante Struktur oder den Graph nutzen, falls verfügbar.
- Danach nur die wirklich betroffenen Dateien oder Codeabschnitte öffnen.
- Ruflo soll Kontext sparen und Arbeit verteilen, nicht unnötige Komplexität erzeugen.
- Memory, Swarms und Zusatzmodule nur dann nutzen, wenn daraus ein klarer Vorteil für diese Aufgabe entsteht.
- Wenn die Aufgabe klar lösbar ist, bevorzuge den einfachsten direkten Weg.