@echo off
cd /d "%~dp0"

echo Installing build requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt

echo Building portable Windows EXE...
python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "Media Scene Maker" ^
  media_scene_maker.py

echo.
echo Build complete.
echo Your app is here:
echo dist\Media Scene Maker\Media Scene Maker.exe
echo.
pause
