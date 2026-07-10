@echo off
rem ===========================================================
rem  Programm-Update: holt die neueste Version via git pull
rem  (nur Fast-Forward - lokale Aenderungen werden NIE ueberschrieben)
rem  und aktualisiert danach die Python-Abhaengigkeiten.
rem ===========================================================
cd /d "%~dp0.."

echo === Update: git pull ===
git pull --ff-only
if errorlevel 1 (
    echo.
    echo [HINWEIS] Update nicht moeglich - vermutlich lokale Aenderungen
    echo oder keine Internetverbindung. Nichts wurde ueberschrieben.
    pause & exit /b 1
)

echo.
echo === Abhaengigkeiten aktualisieren ===
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
) else (
    echo .venv fehlt - bitte einmal setup.bat ausfuehren.
)

echo.
echo Fertig. Laufende App neu starten, damit das Update wirkt
echo (launcher\stop_app.bat, dann Desktop-Icon).
pause
