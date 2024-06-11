@echo off
:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Installing Python...
    :: Download and install Python
    powershell -Command "Start-Process 'https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait"
)

:: Upgrade pip
python -m pip install --upgrade pip

:: Install requirements
python -m pip install -r requirements.txt

:: Compile yousync.py to an executable
pyinstaller --onefile --add-data "gui/assets/images/;gui/assets/images" --noconsole yousync.py

:: Move the compiled executable to ProgramData
move dist\yousync.exe .
rm dist\
