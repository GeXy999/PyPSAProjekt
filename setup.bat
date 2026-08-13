@echo off
setlocal EnableDelayedExpansion
rem ============================================================
rem  Deutschland Energy Model - Ersteinrichtung (Windows)
rem  Macht den Projektordner auf einem NEUEN PC startklar:
rem    1) virtuelle Umgebung (.venv) anlegen
rem    2) Abhaengigkeiten aus requirements.txt installieren
rem    3) Desktop-Verknuepfung mit App-Icon erstellen
rem    4) optional: Ollama + KI-Modell fuer die Ergebnis-Zusammenfassung
rem  Pfad-unabhaengig: nutzt den Ordner dieser Datei (%~dp0).
rem ============================================================
cd /d "%~dp0"
set "PROJ=%CD%"
echo Projekt: %PROJ%
echo.

rem --- [1/4] Python finden (py-Launcher bevorzugt, sonst python) ---
set "PYEXE="
py -3 --version >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    python --version >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [FEHLER] Kein Python gefunden.
    echo          Bitte Python 3.11+ installieren ^(Haken "Add to PATH"^):
    echo          https://www.python.org/downloads/
    pause & exit /b 1
)
echo [1/4] Python: %PYEXE%

rem --- [2/4] venv anlegen (falls noch nicht vorhanden) + Pakete ---
if exist ".venv\Scripts\python.exe" (
    echo [2/4] .venv existiert bereits - ueberspringe Anlegen.
) else (
    echo [2/4] Lege virtuelle Umgebung .venv an ...
    %PYEXE% -m venv .venv || ( echo [FEHLER] venv-Erstellung fehlgeschlagen. & pause & exit /b 1 )
)
echo       Installiere Abhaengigkeiten ^(kann einige Minuten dauern^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt || ( echo [FEHLER] pip install fehlgeschlagen. & pause & exit /b 1 )

rem --- [3/4] Desktop-Verknuepfung erstellen (Icon nur falls vorhanden) ---
echo [3/4] Erstelle Desktop-Verknuepfung ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PROJ%'; $ws=New-Object -ComObject WScript.Shell; $d=[Environment]::GetFolderPath('Desktop'); $l=$ws.CreateShortcut((Join-Path $d 'Deutschland Energy Model.lnk')); $l.TargetPath=(Join-Path $p 'launcher\start_app.bat'); $l.WorkingDirectory=$p; $ico=(Join-Path $p 'assets\app_icon.ico'); if(Test-Path $ico){$l.IconLocation=$ico}; $l.Description='Startet VS Code + die Streamlit-GUI'; $l.WindowStyle=7; $l.Save(); Write-Host ('  -> ' + (Join-Path $d 'Deutschland Energy Model.lnk'))"

rem --- [4/4] Optional: Ollama + lokales KI-Modell (Ergebnis-Zusammenfassung) ---
echo.
set "OLLAMA_EXE="
where ollama >nul 2>nul && set "OLLAMA_EXE=ollama"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

if defined OLLAMA_EXE (
    echo [4/4] Ollama bereits installiert - ueberspringe Installation.
) else (
    echo [4/4] Optionaler KI-Assistent ^(Ollama, lokal, ~2,5 GB Download^):
    echo       fasst nach dem Loesen die Ergebnisse in Fliesstext zusammen.
    echo       Laeuft komplett lokal - keine Daten verlassen den PC, kein Account noetig.
    set /p "INSTALL_OLLAMA=      Jetzt installieren? (j/N): "
    if /i "!INSTALL_OLLAMA!"=="j" (
        where winget >nul 2>nul
        if errorlevel 1 (
            echo       [WARN] winget nicht gefunden. Bitte manuell installieren:
            echo              https://ollama.com
        ) else (
            echo       Installiere Ollama per winget ^(laeuft im Hintergrund^) ...
            winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements
            if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
        )
    ) else (
        echo       Uebersprungen - spaeter jederzeit nachholbar, siehe README.md.
    )
)

if defined OLLAMA_EXE (
    start "" /min "!OLLAMA_EXE!" serve
    timeout /t 4 /nobreak >nul
    echo       Lade KI-Modell llama3.2:3b ^(~2 GB, einmalig, kann einige Minuten dauern^) ...
    "!OLLAMA_EXE!" pull llama3.2:3b
    if errorlevel 1 (
        echo       [WARN] Modell-Download fehlgeschlagen ^(Ollama-Dienst evtl. noch nicht bereit^).
        echo              Ollama einmal ueber das Startmenue oeffnen, dann in einem Terminal:
        echo              ollama pull llama3.2:3b
    )
)

echo.
echo ============================================================
echo  Fertig - der Ordner ist startklar!
echo  App starten: Desktop-Icon "Deutschland Energy Model"
echo               oder  launcher\start_app.bat
echo.
echo  Solver: standardmaessig HiGHS (kostenlos, schon installiert).
echo  Optional schneller mit Gurobi + kostenloser Studi-Lizenz -
echo  Details in README.md (Abschnitt SOLVER).
echo.
echo  Optional fuer echte ERA5-Wetterdaten: atlite + cdsapi lokal
echo  installieren und einen CDS-Key in .env / .cdsapirc hinterlegen
echo  (ohne Key rechnet das Modell mit synthetischem Wetter).
echo.
echo  KI-Zusammenfassung der Ergebnisse (Ollama): siehe Schritt [4/4] oben.
echo  Falls uebersprungen, jederzeit nachholbar - Details in README.md.
echo  Ohne Ollama funktioniert die App unveraendert weiter - der Expander
echo  "KI-Zusammenfassung" bleibt dann einfach inaktiv.
echo ============================================================
pause
