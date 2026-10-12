@echo off
cd /d "%~dp0"
set BANK_BACKEND=sqlite
echo Starting Bank Orderly browser demo using SQLite.
echo Open http://127.0.0.1:5000 in Edge or Chrome.
echo Keep this window open. Press Ctrl+C to stop the server.
python web_app.py
pause
