@echo off
:: Upgrade pip
python -m pip install --upgrade pip

:: Install requirements
python -m pip install -r requirements.txt

:: Compile yousync.py to an executable
pyinstaller --onefile --clean --noupx --add-data "gui/assets/images/;gui/assets/images" yousync.py

:: Move the compiled executable to ProgramData
move dist\yousync.exe .

:: Delete temp files
rmdir /s /q dist
rmdir /s /q build

:: Create installer
ISCC yousync.iss

:: Delete final exe after packaging
if exist yousync.exe del /f /q yousync.exe
