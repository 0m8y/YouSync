@echo off
setlocal

:: Check if a commit message is provided
if "%~1"=="" (
    echo ❌ Please provide a commit message.
    echo Usage: build_and_push.bat "Your commit message here"
    exit /b 1
)

:: Store the commit message
set "msg=%~1"

:: Go to the build directory
cd YouSyncDev

:: Run the build script
call yousync_build.bat

:: Go back to the root directory
cd ..

:: Add the generated installer to Git
git add YouSyncInstaller.exe

:: Commit with the provided message
git commit -m "%msg%"

:: Push to the remote repository
git push

echo ✅ Build and push completed successfully.
