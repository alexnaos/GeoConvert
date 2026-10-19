@echo off
rem Запуск локального сервиса GeoConvert на http://127.0.0.1:5050
rem Остановка: закрыть окно или taskkill /IM python.exe /FI "WINDOWTITLE eq *app.py*"
cd /d "%~dp0"
python app.py
pause
