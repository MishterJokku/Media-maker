@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
python media_scene_maker.py
pause
