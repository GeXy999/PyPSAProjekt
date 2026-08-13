# 🇩🇪 Deutschland Energy Model

**Kostenminimales Stromsystem für Deutschland – PyPSA + Streamlit**

Dieses Projekt rechnet ein kostenoptimales Stromsystem für Deutschland
(5 Zonen + Offshore, Sektorkopplung Wärme/H₂, CO₂-Budget, optionale
Kopplung von 11 Nachbarländern sowie – als 2. Ausbaustufe – ganz Europa)
und zeigt die Ergebnisse in einem interaktiven Dashboard (Streamlit).

---

## 🚀 Schnellstart auf einem neuen PC

> **Voraussetzung:** Windows + Python 3.11 oder neuer
> (bei der Installation den Haken *„Add Python to PATH"* setzen) —
> Download: <https://www.python.org/downloads/>

1. Diesen Ordner auf den PC kopieren (oder per `git clone`).
2. Datei **`setup.bat`** doppelklicken. Das Skript:
   - legt die virtuelle Umgebung `.venv` an,
   - installiert alle Abhängigkeiten (`requirements.txt`),
   - erstellt eine Desktop-Verknüpfung mit App-Icon.

   *(dauert beim ersten Mal einige Minuten)*
3. Fertig. Die App per Desktop-Icon **„Deutschland Energy Model"** starten –
   es öffnen sich VS Code und das Dashboard im Browser.

---

## ▶️ App starten / stoppen

**Starten**
- Desktop-Icon **„Deutschland Energy Model"** *(empfohlen)*
- oder `launcher\start_app.bat`
- oder manuell: `.venv\Scripts\streamlit.exe run deutschland_gui.py`

Das Dashboard öffnet sich automatisch im Browser (i. d. R. <http://localhost:8501>).

**Stoppen**
- `launcher\stop_app.bat`
- beim manuellen Start: Streamlit-Fenster schließen bzw. im Terminal `Strg+C`

---

## 📂 Ordnerüberblick

| Pfad | Inhalt |
|------|--------|
| `deutschland_v1.py` | Modell (Kern) — **muss im Root bleiben** (feste Pfade) |
| `deutschland_gui.py` | Streamlit-Dashboard — **muss im Root bleiben** |
| `setup.bat` | Ersteinrichtung (siehe oben) |
| `requirements.txt` | Python-Abhängigkeiten |
| `launcher\` | `start_app` / `stop_app` / `update_app` / `check_download` |
| `assets\` | App-Icon |
| `data\` | Eingangsdaten *(nur lokal, nicht im Repo)* |
| `era5_data\` | ERA5-Wettercache |
| `output\` | erzeugte Plots & PDF-Bericht |
| `docs\` | ausführliche Dokumentation (`DOKUMENTATION.md`) |
| `.vscode\` | VS-Code-Tasks & Einstellungen |

---

## 🌦️ Wetterdaten (ERA5) — optional

Standardmäßig rechnet das Modell mit **synthetischem Wetter** und läuft damit
sofort auf jedem PC.

Für echte ERA5-Wetterdaten zusätzlich nötig:
- Pakete: `pip install atlite cdsapi`
- ein CDS-API-Key (kostenlos), hinterlegt in `.env` / `.cdsapirc`

Der erste Lauf lädt die Wetterdaten dann herunter (dauert).

---

## 🧠 KI-Zusammenfassung (Ollama) — optional

Im Dashboard fasst optional ein **lokales, kostenloses KI-Modell** (via
[Ollama](https://ollama.com)) die Kennzahlen eines Laufs in Fließtext
zusammen (Zusammenfassung + grober Plausibilitäts-Check). Läuft komplett
**offline auf diesem PC** — keine Daten verlassen den Rechner, **kein
API-Key und kein Ollama-Account nötig**.

**Automatisch:** `setup.bat` bietet Schritt **[4/4]** an, Ollama +
Modell (`llama3.2:3b`, ~2,5 GB) direkt per `winget` zu installieren —
einfach mit `j` bestätigen. Kann jederzeit übersprungen werden.

**Manuell nachholen:**
1. Ollama installieren: <https://ollama.com>
2. Einmalig ein Modell laden (Terminal): `ollama pull llama3.2:3b`
   (~2 GB, danach offline nutzbar)
3. Im Dashboard nach dem Lösen den Expander **„🧠 KI-Zusammenfassung"**
   öffnen (unterhalb der Kennzahlen-Kacheln).

Ohne Ollama läuft die App **unverändert vollständig** weiter — der Expander
zeigt dann nur einen Hinweis statt der Zusammenfassung.

---

## ⚙️ Solver: HiGHS (Standard) oder Gurobi (optional, schneller)

**Standard: HiGHS** — kostenlos, wird von `setup.bat` automatisch installiert
(Paket `highspy`) und braucht **keine Lizenz**. Es ist nichts zu tun; das Modell
läuft sofort. *(HiGHS rechnet mit einem Zeitlimit von 900 s pro Optimierung.)*

**Optional schneller: Gurobi.** Für Studierende gibt es eine **kostenlose
akademische Lizenz** – lohnt sich v. a. bei großen Läufen (z. B. Kopplung der
Nachbarländer). So aktivieren:

1. Mit Uni-/Hochschul-E-Mail registrieren und eine *„Academic WLS License"*
   anlegen: <https://portal.gurobi.com/>
2. `gurobipy` ist bereits in `requirements.txt` enthalten (nach `setup.bat`
   schon installiert — nichts extra nötig).
3. Die drei Lizenz-Werte in eine Datei `.env` im Projekt-Root eintragen
   (eine Zeile je Wert):
   ```env
   GRB_WLSACCESSID=deine-access-id
   GRB_WLSSECRET=dein-secret
   GRB_LICENSEID=1234567
   ```

Beim nächsten Start nutzt das Modell automatisch Gurobi. Ohne (gültige) Lizenz
fällt es **stillschweigend auf HiGHS** zurück – es geht also nie etwas kaputt.

> ℹ️ Die Datei `.env` enthält Geheimnisse und ist bewusst gitignored
> (landet nicht im Repo).

---

## 📖 Mehr Details

Ausführliche Erklärung von Modell, Annahmen, Formeln und GUI:
👉 [`docs/DOKUMENTATION.md`](docs/DOKUMENTATION.md)
