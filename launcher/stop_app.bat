@echo off
rem ===========================================================
rem  Stoppt die versteckt laufende Streamlit-GUI des Modells.
rem ===========================================================
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'streamlit.*deutschland_gui\.py' }; if($p){ $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Write-Host 'Streamlit-GUI gestoppt.' } else { Write-Host 'Keine laufende GUI gefunden.' }"
timeout /t 2 >nul
