$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopDir = (Resolve-Path (Join-Path $ScriptDir "..")).Path
$ProjectDir = (Resolve-Path (Join-Path $DesktopDir "..")).Path

$PythonBin = Join-Path $ProjectDir ".venv\Scripts\python.exe"

$TargetTriple = "x86_64-pc-windows-msvc"
$WorkerBaseName = "yousync-worker-$TargetTriple"
$ExpectedExeName = "$WorkerBaseName.exe"

$BinariesDir = Join-Path $DesktopDir "src-tauri\binaries"
$BuildDir = Join-Path $DesktopDir "build\yousync_worker_windows"
$SpecDir = Join-Path $DesktopDir "build\pyinstaller-spec-windows"
$PyinstallerCacheDir = Join-Path $DesktopDir "build\pyinstaller-cache-windows"
$ExpectedExePath = Join-Path $BinariesDir $ExpectedExeName

Write-Host "==============================" -ForegroundColor Cyan
Write-Host " YouSync Python worker build" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "Project: $ProjectDir"
Write-Host "Desktop: $DesktopDir"
Write-Host "Python:  $PythonBin"
Write-Host "Target:  $TargetTriple"
Write-Host "Output:  $ExpectedExePath"
Write-Host ""

if ($env:OS -ne "Windows_NT") {
    throw "The Windows worker sidecar can only be built on Windows."
}

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64" -and $env:PROCESSOR_ARCHITEW6432 -ne "AMD64") {
    throw "This script builds x86_64-pc-windows-msvc only. Current architecture: $env:PROCESSOR_ARCHITECTURE"
}

if (!(Test-Path $PythonBin)) {
    throw "Python virtualenv not found at $PythonBin"
}

Set-Location $ProjectDir

Write-Host "Checking Python syntax..." -ForegroundColor Yellow

& $PythonBin -m py_compile `
    core\utils.py `
    core\CentralManager.py `
    core\playlist_managers\IPlaylistManager.py `
    core\playlist_managers\YoutubePlaylistManager.py `
    core\playlist_managers\SpotifyPlaylistManager.py `
    core\playlist_managers\ApplePlaylistManager.py `
    core\playlist_managers\DeezerPlaylistManager.py `
    core\audio_managers\IAudioManager.py `
    core\audio_managers\YoutubeAudioManager.py `
    core\audio_managers\SpotifyAudioManager.py `
    core\audio_managers\AppleAudioManager.py `
    core\audio_managers\DeezerAudioManager.py `
    desktop\python\yousync_bridge.py `
    desktop\python\yousync_worker.py

if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed."
}

Write-Host "Python syntax OK" -ForegroundColor Green
Write-Host ""

Write-Host "Checking PyInstaller..." -ForegroundColor Yellow

& $PythonBin -m PyInstaller --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    & $PythonBin -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller."
    }
}

Write-Host ""

New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null
New-Item -ItemType Directory -Force -Path $PyinstallerCacheDir | Out-Null

Write-Host "Cleaning previous worker build..." -ForegroundColor Yellow

Remove-Item $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $SpecDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $PyinstallerCacheDir -Recurse -Force -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $SpecDir | Out-Null
New-Item -ItemType Directory -Force -Path $PyinstallerCacheDir | Out-Null

Write-Host "Cleaning previous Windows worker binaries..." -ForegroundColor Yellow

Get-ChildItem -Path $BinariesDir -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -like "yousync-worker*x86_64-pc-windows-msvc*" -or
        $_.Name -eq "yousync-worker.exe" -or
        $_.Name -eq "yousync_worker.exe"
    } |
    Remove-Item -Force

$env:PYINSTALLER_CONFIG_DIR = $PyinstallerCacheDir
$env:PYTHONPATH = "$ProjectDir;$DesktopDir\python"

Write-Host "Building Python worker sidecar..." -ForegroundColor Yellow
Write-Host ""

Set-Location $DesktopDir

$PyInstallerArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--clean",
    "--noconfirm",
    "--name", $WorkerBaseName,
    "--distpath", $BinariesDir,
    "--workpath", $BuildDir,
    "--specpath", $SpecDir,
    "--paths", $ProjectDir,
    "--paths", (Join-Path $DesktopDir "python"),
    "python\yousync_worker.py"
)

& $PythonBin @PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "Files generated in binaries dir:" -ForegroundColor Cyan
Get-ChildItem -Path $BinariesDir -File | Sort-Object LastWriteTime -Descending | Format-Table Name, Length, LastWriteTime -AutoSize

if (!(Test-Path $ExpectedExePath)) {
    Write-Host ""
    Write-Host "Exact expected file not found. Searching generated worker candidate..." -ForegroundColor Yellow

    $Candidates = Get-ChildItem -Path $BinariesDir -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq $WorkerBaseName -or
            $_.Name -eq $ExpectedExeName -or
            $_.Name -like "$WorkerBaseName*" -or
            $_.Name -like "yousync-worker*"
        } |
        Sort-Object LastWriteTime -Descending

    if ($Candidates.Count -eq 0) {
        throw "No generated worker binary found in $BinariesDir"
    }

    $Candidate = $Candidates[0]
    Write-Host "Candidate found: $($Candidate.FullName)" -ForegroundColor Yellow

    if (Test-Path $ExpectedExePath) {
        Remove-Item $ExpectedExePath -Force
    }

    Copy-Item -Path $Candidate.FullName -Destination $ExpectedExePath -Force
}

if (!(Test-Path $ExpectedExePath)) {
    throw "No x86_64-pc-windows-msvc sidecar binary found at $ExpectedExePath"
}

Write-Host ""
Write-Host "Final sidecar:" -ForegroundColor Cyan
Get-Item $ExpectedExePath | Format-List FullName, Length, LastWriteTime
Get-FileHash $ExpectedExePath -Algorithm SHA256 | Format-List Algorithm, Hash

Write-Host ""
Write-Host "Windows Python worker sidecar built successfully." -ForegroundColor Green