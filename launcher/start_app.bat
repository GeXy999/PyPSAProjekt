@echo off
rem ===========================================================
rem  Deutschland Energy Model - Starter
rem  Oeffnet VS Code auf dem Projekt und startet die Streamlit-GUI.
rem  Es bleiben KEINE Konsolenfenster offen: Streamlit laeuft
rem  versteckt im Hintergrund, dieses Fenster schliesst sich selbst.
rem  Zum Stoppen der GUI: stop_app.bat
rem ===========================================================
cd /d "%~dp0.."
set "ROOT=%CD%"

powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$r='%ROOT%'; $vsc=Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\Code.exe'; if(-not (Test-Path $vsc)){$vsc=(Get-Command code -ErrorAction SilentlyContinue).Source}; if($vsc){Start-Process -FilePath $vsc -ArgumentList $r}; Start-Process -WindowStyle Hidden -FilePath (Join-Path $r '.venv\Scripts\streamlit.exe') -ArgumentList 'run','deutschland_gui.py' -WorkingDirectory $r"

exit
