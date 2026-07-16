@echo off
rem ===========================================================
rem  Zeigt den Fortschritt der ERA5-Downloads:
rem   - 11 Nachbarlaender (Kreis 1)
rem   - 13 weitere europaeische Laender (Kreis 2)
rem   - 11 restliche ENTSO-E-Laender (Kreis 3)
rem  Zaehlt die erwarteten Cutout-Dateien in era5_data\.
rem ===========================================================
cd /d "%~dp0.."

powershell -NoProfile -ExecutionPolicy Bypass -Command "$n=[ordered]@{FR='0.0_44.0';BE='3.0_50.0';LU='5.7_49.4';NL='4.0_51.5';DK='8.0_55.0';PL='15.0_51.0';CZ='13.0_49.0';AT='10.0_46.5';CH='6.0_46.0';SE='12.0_56.0';NO='6.0_58.0'}; $e=[ordered]@{ES='-8.5_36.5';PT='-9.5_37.0';IT='8.0_38.0';GB='-5.5_50.5';IE='-10.0_51.5';FI='21.0_60.0';SK='17.0_47.8';HU='16.0_45.8';SI='13.5_45.4';HR='13.5_42.5';RO='20.5_43.5';BG='22.5_41.0';GR='20.0_35.0'}; $k3=[ordered]@{EE='22.0_57.5';LV='21.0_55.7';LT='21.0_53.9';RS='18.8_42.2';BA='15.7_42.5';ME='18.4_41.8';MK='20.4_40.8';AL='19.2_39.6';XK='20.0_41.8';MD='26.6_45.4';UA='22.1_44.3'}; function Show($m,$t){ $d=0; Write-Host (''); Write-Host ('  -- ' + $t + ' --') -ForegroundColor Yellow; foreach($k in $m.Keys){ $f=Join-Path 'era5_data' ('de_'+$m[$k]+'_2023.nc'); if(Test-Path $f){ $mb=[math]::Round((Get-Item $f).Length/1MB,1); $d++; Write-Host ('  {0}  OK  {1} MB' -f $k,$mb) -ForegroundColor Green } else { Write-Host ('  {0}  --' -f $k) -ForegroundColor DarkGray } }; return $d }; $d1=Show $n 'Kreis 1: Nachbarn (11)'; $d2=Show $e 'Kreis 2: weitere Laender (13)'; $d3=Show $k3 'Kreis 3: restliches Europa (11)'; Write-Host ''; Write-Host ('  ==> Kreis 1 ' + $d1 + '/11   |   Kreis 2 ' + $d2 + '/13   |   Kreis 3 ' + $d3 + '/11') -ForegroundColor Cyan"

echo.
pause
