@echo off
setlocal
rem ============================================================
rem  Deutschland Energy Model - Ersteinrichtung (Windows)
rem  Macht den Projektordner auf einem NEUEN PC startklar:
rem    1) virtuelle Umgebung (.venv) anlegen
rem    2) Abhaengigkeiten aus requirements.txt installieren
rem    3) Desktop-Verknuepfung mit App-Icon erstellen
rem  Pfad-unabhaengig: nutzt den Ordner dieser Datei (%~dp0).
rem ============================================================
cd /d "%~dp0"
set "PROJ=%CD%"
echo Projekt: %PROJ%
echo.

rem --- [1/3] Python finden (py-Launcher bevorzugt, sonst python) ---
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
echo [1/3] Python: %PYEXE%

rem --- [2/3] venv anlegen (falls noch nicht vorhanden) + Pakete ---
if exist ".venv\Scripts\python.exe" (
    echo [2/3] .venv existiert bereits - ueberspringe Anlegen.
) else (
    echo [2/3] Lege virtuelle Umgebung .venv an ...
    %PYEXE% -m venv .venv || ( echo [FEHLER] venv-Erstellung fehlgeschlagen. & pause & exit /b 1 )
)
echo       Installiere Abhaengigkeiten ^(kann einige Minuten dauern^) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt || ( echo [FEHLER] pip install fehlgeschlagen. & pause & exit /b 1 )

rem --- [3/3] Desktop-Verknuepfung erstellen (Icon nur falls vorhanden) ---
echo [3/3] Erstelle Desktop-Verknuepfung ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PROJ%'; $ws=New-Object -ComObject WScript.Shell; $d=[Environment]::GetFolderPath('Desktop'); $l=$ws.CreateShortcut((Join-Path $d 'Deutschland Energy Model.lnk')); $l.TargetPath=(Join-Path $p 'launcher\start_app.bat'); $l.WorkingDirectory=$p; $ico=(Join-Path $p 'assets\app_icon.ico'); if(Test-Path $ico){$l.IconLocation=$ico}; $l.Description='Startet VS Code + die Streamlit-GUI'; $l.WindowStyle=7; $l.Save(); Write-Host ('  -> ' + (Join-Path $d 'Deutschland Energy Model.lnk'))"

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
echo ============================================================
pause
