@echo off
cd /d "%~dp0"
venv\Scripts\python.exe tests\run_tests.py %*
