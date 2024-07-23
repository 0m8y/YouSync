@echo off
setlocal

REM Verify if FFmpeg is already installed
where ffmpeg >nul 2>nul
if not errorlevel 1 (
    echo FFmpeg is already installed.
    exit /b 0
)

REM Define the download URL and target directory
set "FFMPEG_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z"
set "TARGET_DIR=%USERPROFILE%\ffmpeg"

REM Create the target directory if it does not exist
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

REM Download the FFmpeg archive
echo Downloading FFmpeg...
powershell -Command "(New-Object Net.WebClient).DownloadFile('%FFMPEG_URL%', '%TARGET_DIR%\ffmpeg.7z')"

REM Check if 7z command is available, if not, install 7-Zip
where 7z >nul 2>nul
if errorlevel 1 (
    echo 7-Zip could not be found, installing 7-Zip...
    powershell -Command "Invoke-WebRequest -Uri https://www.7-zip.org/a/7z1900-x64.msi -OutFile %TARGET_DIR%\7z.msi"
    msiexec /i "%TARGET_DIR%\7z.msi" /quiet
    set "PATH=%PATH%;C:\Program Files\7-Zip"
)

REM Extract the FFmpeg archive
echo Extracting FFmpeg...
7z x "%TARGET_DIR%\ffmpeg.7z" -o"%TARGET_DIR%"

REM Clean up the archive file
del "%TARGET_DIR%\ffmpeg.7z"

REM Get the extracted folder name
for /d %%i in ("%TARGET_DIR%\ffmpeg-*") do set "FFMPEG_BIN_DIR=%%i\bin"

REM Add FFmpeg to the PATH using PowerShell to avoid truncation
powershell -Command "[System.Environment]::SetEnvironmentVariable('PATH', [System.Environment]::GetEnvironmentVariable('PATH', 'Machine') + ';%FFMPEG_BIN_DIR%', 'Machine')"

endlocal
pause
