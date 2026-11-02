@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting Desktop Viewer Server...
python server.py
pause
