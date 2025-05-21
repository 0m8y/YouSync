@echo off
:: Upgrade pip
python -m pip install --upgrade pip

:: Install requirements
python -m pip install -r requirements.txt

:: Delete old yousync.exe
if exist yousync.exe del /f /q yousync.exe


:: Compile yousync.py to an executable
pyinstaller --onefile --clean --noupx --add-data "gui/assets/images/;gui/assets/images" yousync.py

:: Move the compiled executable to ProgramData
move dist\yousync.exe .

:: Delete temp files
rmdir /s /q dist
rmdir /s /q build

ISCC yousync.iss
