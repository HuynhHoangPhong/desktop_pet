@echo off
echo Installing required packages...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building executable...
pyinstaller --noconfirm --windowed --onefile ^
--name CuteDesktopPet ^
--add-data "emotion;emotion" ^
main.py

echo.
echo Build complete! Your executable is located in the "dist" folder.
pause
