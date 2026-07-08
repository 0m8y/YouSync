$ErrorActionPreference = "Stop"

function Print-Help {
    Write-Host "YouSync Windows installer builder"
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\build-windows-installer.ps1              Clean then build Windows installer"
    Write-Host "  .\build-windows-installer.ps1 --install    Clean, build, then launch installer"
    Write-Host "  .\build-windows-installer.ps1 --version 1.0.1 --install"
    Write-Host "  .\build-windows-installer.ps1 -version 1.0.1 --install"
    Write-Host "  .\build-windows-installer.ps1 -v 1.0.1 --install"
    Write-Host "  .\build-windows-installer.ps1 --clean      Clean only"
    Write-Host "  .\build-windows-installer.ps1 -c           Clean only"
    Write-Host "  .\build-windows-installer.ps1 --no-clean   Build without cleaning"
    Write-Host "  .\build-windows-installer.ps1 --msi        Build MSI instead of NSIS EXE"
    Write-Host "  .\build-windows-installer.ps1 --all-bundles"
    Write-Host "  .\build-windows-installer.ps1 --help       Show help"
    Write-Host ""
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $Encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

function Validate-Version {
    param([Parameter(Mandatory = $true)][string]$Version)

    if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
        throw "Invalid version: $Version. Expected SemVer format: MAJOR.MINOR.PATCH, for example 1.0.1"
    }
}

function Read-Version {
    if (!(Test-Path $VersionFile)) {
        throw "VERSION file not found: $VersionFile. Create it with a SemVer value, for example: 1.0.0"
    }

    $Version = (Get-Content $VersionFile -Raw -Encoding UTF8).Trim()
    Validate-Version $Version
    return $Version
}

function Set-VersionFile {
    param([Parameter(Mandatory = $true)][string]$Version)

    Validate-Version $Version
    Write-Utf8NoBom -Path $VersionFile -Content ($Version + [Environment]::NewLine)
}

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (!(Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Command,
        [Parameter(Mandatory = $true)][string]$ErrorMessage
    )

    $OldErrorActionPreference = $ErrorActionPreference
    $ExitCode = 0

    try {
        # Windows PowerShell 5.1 can treat native stderr as PowerShell errors.
        # We do not want warnings from npm/PyInstaller/Tauri to abort the script when the native exit code is 0.
        $global:ErrorActionPreference = "Continue"
        & $Command
        $ExitCode = $LASTEXITCODE
    } finally {
        $global:ErrorActionPreference = $OldErrorActionPreference
    }

    if ($ExitCode -ne 0) {
        throw "$ErrorMessage Exit code: $ExitCode"
    }
}

function Sync-ProjectVersions {
    param([Parameter(Mandatory = $true)][string]$Version)

    Validate-Version $Version

    Write-Host ""
    Write-Host "Synchronizing project version..." -ForegroundColor Cyan
    Write-Host "Version: $Version"

    $PackageJsonPath = Join-Path $DesktopDir "package.json"
    $PackageLockPath = Join-Path $DesktopDir "package-lock.json"
    $TauriConfigPath = Join-Path $TauriDir "tauri.conf.json"
    $CargoTomlPath = Join-Path $TauriDir "Cargo.toml"

    if (!(Test-Path $PackageJsonPath)) { throw "package.json not found: $PackageJsonPath" }
    if (!(Test-Path $PackageLockPath)) { throw "package-lock.json not found: $PackageLockPath" }
    if (!(Test-Path $TauriConfigPath)) { throw "tauri.conf.json not found: $TauriConfigPath" }
    if (!(Test-Path $CargoTomlPath)) { throw "Cargo.toml not found: $CargoTomlPath" }

    Set-Location $DesktopDir

    # Do not parse package-lock.json with Windows PowerShell 5.1.
    # npm handles package.json + package-lock.json correctly, including the root package key "".
    Invoke-Checked -ErrorMessage "npm version failed." -Command {
        & npm.cmd version $Version --no-git-tag-version --allow-same-version | Out-Host
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $DesktopDir "build") | Out-Null

    $NodeScriptPath = Join-Path $DesktopDir "build\sync-tauri-version-windows.cjs"
    $NodeScriptContent = @'
const fs = require("fs");

const version = process.argv[2];
const file = "src-tauri/tauri.conf.json";
const data = JSON.parse(fs.readFileSync(file, "utf8"));

data.version = version;

if (!data.build) {
  data.build = {};
}

// The Windows installer script builds the Windows worker before Tauri.
// Do not keep the macOS worker command here, otherwise Windows builds fail.
data.build.beforeBuildCommand = "npm run build";

fs.writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
'@

    Write-Utf8NoBom -Path $NodeScriptPath -Content ($NodeScriptContent + [Environment]::NewLine)

    Invoke-Checked -ErrorMessage "Failed to update tauri.conf.json." -Command {
        & node.exe $NodeScriptPath $Version
    }

    $CargoToml = Get-Content $CargoTomlPath -Raw -Encoding UTF8
    $UpdatedCargoToml = [regex]::Replace(
        $CargoToml,
        '(?ms)(^\[package\]\s*.*?^version\s*=\s*")[^"]+(")',
        "`${1}$Version`${2}",
        1
    )

    $VersionRegex = [regex]::Escape($Version)
    if ($UpdatedCargoToml -eq $CargoToml -and $CargoToml -notmatch ('version\s*=\s*"' + $VersionRegex + '"')) {
        throw "Could not update [package] version in Cargo.toml"
    }

    Write-Utf8NoBom -Path $CargoTomlPath -Content $UpdatedCargoToml
}

function Clean-Outputs {
    Write-Host ""
    Write-Host "Cleaning previous frontend build..." -ForegroundColor Yellow
    Remove-Item (Join-Path $DesktopDir "dist") -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "Cleaning previous Tauri Windows bundles..." -ForegroundColor Yellow
    Remove-Item (Join-Path $TauriDir "target\release\bundle") -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "Cleaning previous Windows installer output..." -ForegroundColor Yellow
    Remove-Item $WindowsInstallerDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "Cleaning previous PyInstaller Windows worker build cache..." -ForegroundColor Yellow
    Remove-Item $WorkerBuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $WorkerSpecBuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $PyinstallerCacheDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "Cleaning previous Windows worker sidecar..." -ForegroundColor Yellow
    if (Test-Path $BinariesDir) {
        Get-ChildItem -Path $BinariesDir -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -like "*x86_64-pc-windows-msvc*" -or
                $_.Name -eq "yousync-worker.exe" -or
                $_.Name -eq "yousync_worker.exe"
            } |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "Clean completed." -ForegroundColor Green
}

function Write-WindowsWorkerSpec {
    $SpecPath = Join-Path $DesktopDir "python\yousync_worker_windows.spec"

    $SpecContent = @'
# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


spec_dir = Path(SPECPATH).resolve()
project_root = spec_dir.parents[1]
desktop_dir = project_root / "desktop"
worker_entry = desktop_dir / "python" / "yousync_worker.py"

hiddenimports = [
    "core.CentralManager",
    "core.utils",
    "core.storage.AudioDataStore",
    "core.storage.AudioMetadata",
    "core.storage.PlaylistData",
    "core.storage.PlaylistDataStore",
    "core.audio_managers.IAudioManager",
    "core.audio_managers.YoutubeAudioManager",
    "core.audio_managers.SpotifyAudioManager",
    "core.audio_managers.AppleAudioManager",
    "core.audio_managers.DeezerAudioManager",
    "core.playlist_managers.IPlaylistManager",
    "core.playlist_managers.YoutubePlaylistManager",
    "core.playlist_managers.SpotifyPlaylistManager",
    "core.playlist_managers.ApplePlaylistManager",
    "core.playlist_managers.DeezerPlaylistManager",
    "requests",
    "bs4",
    "lxml",
    "PIL",
    "eyed3",
    "moviepy.audio.io.AudioFileClip",
    "numpy._core._exceptions",
    "pytubefix",
    "selenium",
    "youtube_search",
    "yt_dlp",
    "certifi",
]

hiddenimports += collect_submodules("pytubefix")
hiddenimports += collect_submodules("yt_dlp")

datas = []
datas += collect_data_files("certifi")
datas += collect_data_files("yt_dlp")
datas += collect_data_files("pytubefix")
datas += copy_metadata("imageio")
datas += copy_metadata("imageio-ffmpeg")
datas += copy_metadata("moviepy")

a = Analysis(
    [str(worker_entry)],
    pathex=[str(project_root), str(desktop_dir / "python")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(desktop_dir / "python" / "pyinstaller_runtime_hook.py")],
    excludes=["customtkinter", "tkinter"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="yousync-worker-x86_64-pc-windows-msvc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
)
'@

    Write-Utf8NoBom -Path $SpecPath -Content ($SpecContent + [Environment]::NewLine)
    return $SpecPath
}

function Build-PythonWorker {
    Write-Host ""
    Write-Host "Building Python worker sidecar..." -ForegroundColor Cyan

    if (!(Test-Path $PythonBin)) {
        throw "Python virtualenv not found at $PythonBin"
    }

    Set-Location $ProjectDir

    Write-Host "Checking Python syntax..." -ForegroundColor Yellow

    Invoke-Checked -ErrorMessage "Python syntax check failed." -Command {
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
    }

    Write-Host "Python syntax OK" -ForegroundColor Green

    Write-Host "Checking PyInstaller..." -ForegroundColor Yellow

    $OldErrorActionPreference = $ErrorActionPreference
    $PyInstallerCheckExitCode = 0
    try {
        $global:ErrorActionPreference = "Continue"
        & $PythonBin -c "import PyInstaller, sys; print(PyInstaller.__version__)"
        $PyInstallerCheckExitCode = $LASTEXITCODE
    } finally {
        $global:ErrorActionPreference = $OldErrorActionPreference
    }

    if ($PyInstallerCheckExitCode -ne 0) {
        Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
        Invoke-Checked -ErrorMessage "Failed to install PyInstaller." -Command {
            & $PythonBin -m pip install pyinstaller
        }
    }

    New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null
    New-Item -ItemType Directory -Force -Path $WorkerBuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $WorkerSpecBuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PyinstallerCacheDir | Out-Null

    Write-Host "Cleaning previous worker build..." -ForegroundColor Yellow
    Remove-Item $WorkerBuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $WorkerSpecBuildDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item $PyinstallerCacheDir -Recurse -Force -ErrorAction SilentlyContinue

    New-Item -ItemType Directory -Force -Path $WorkerBuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $WorkerSpecBuildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $PyinstallerCacheDir | Out-Null

    Write-Host "Cleaning previous Windows worker binary..." -ForegroundColor Yellow
    Get-ChildItem -Path $BinariesDir -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like "*x86_64-pc-windows-msvc*" -or
            $_.Name -eq "yousync-worker.exe" -or
            $_.Name -eq "yousync_worker.exe"
        } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYINSTALLER_CONFIG_DIR = $PyinstallerCacheDir
    $env:PYTHONPATH = "$ProjectDir;$DesktopDir\python"

    $SpecPath = Write-WindowsWorkerSpec

    Write-Host "Worker spec: $SpecPath"
    Write-Host "Building with PyInstaller..." -ForegroundColor Yellow

    Set-Location $DesktopDir

    Invoke-Checked -ErrorMessage "PyInstaller worker build failed." -Command {
        & $PythonBin -m PyInstaller `
            --clean `
            --noconfirm `
            --distpath $BinariesDir `
            --workpath $WorkerBuildDir `
            $SpecPath
    }

    if (!(Test-Path $ExpectedWorkerPath)) {
        Write-Host "Expected worker not found. Searching candidate..." -ForegroundColor Yellow

        $Candidate = Get-ChildItem -Path $BinariesDir -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -like "yousync-worker*" -or
                $_.Extension -eq ".exe"
            } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if ($null -eq $Candidate) {
            throw "No generated worker binary found in $BinariesDir"
        }

        Copy-Item -Path $Candidate.FullName -Destination $ExpectedWorkerPath -Force
    }

    if (!(Test-Path $ExpectedWorkerPath)) {
        throw "No Windows sidecar binary found at $ExpectedWorkerPath"
    }

    $WorkerFile = Get-Item $ExpectedWorkerPath
    if ($WorkerFile.Length -lt 1000000) {
        throw "Worker binary looks too small: $($WorkerFile.Length) bytes"
    }

    Write-Host ""
    Write-Host "Python sidecar binaries:" -ForegroundColor Cyan
    Get-ChildItem -Path $BinariesDir -File |
        Where-Object { $_.Name -like "yousync-worker*" } |
        ForEach-Object {
            Write-Host $_.FullName
            Get-Item $_.FullName | Format-List Name, Length, LastWriteTime
            Get-FileHash $_.FullName -Algorithm SHA256 | Format-List Algorithm, Hash
        }

    Write-Host "Python worker sidecar built." -ForegroundColor Green
}

function Copy-BuildOutputs {
    Write-Host ""
    Write-Host "Collecting Windows installer outputs..." -ForegroundColor Cyan

    New-Item -ItemType Directory -Force -Path $WindowsInstallerDir | Out-Null

    $BundleRoot = Join-Path $TauriDir "target\release\bundle"

    if (!(Test-Path $BundleRoot)) {
        throw "Bundle output folder not found: $BundleRoot"
    }

    $Installers = Get-ChildItem -Path $BundleRoot -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -eq ".exe" -or $_.Extension -eq ".msi" } |
        Sort-Object LastWriteTime -Descending

    if ($Installers.Count -eq 0) {
        throw "No Windows installer found under $BundleRoot"
    }

    $CopiedOutputs = @()
    $ExeCount = 0
    $MsiCount = 0

    foreach ($Installer in $Installers) {
        $ParentName = Split-Path (Split-Path $Installer.FullName -Parent) -Leaf

        if ($Installer.Extension -eq ".msi") {
            $MsiCount++
            if ($MsiCount -eq 1) {
                $DestName = "YouSyncInstaller-Windows-v$Version-x64.msi"
            } else {
                $DestName = "YouSyncInstaller-Windows-v$Version-x64-$ParentName-$MsiCount.msi"
            }
        } else {
            $ExeCount++
            if ($ExeCount -eq 1) {
                $DestName = "YouSyncInstaller-Windows-v$Version-x64.exe"
            } else {
                $DestName = "YouSyncInstaller-Windows-v$Version-x64-$ParentName-$ExeCount.exe"
            }
        }

        $DestPath = Join-Path $WindowsInstallerDir $DestName
        Copy-Item -Path $Installer.FullName -Destination $DestPath -Force
        $CopiedOutputs += $DestPath
    }

    Write-Host ""
    Write-Host "Windows installer outputs:" -ForegroundColor Green

    foreach ($Output in $CopiedOutputs) {
        Write-Host $Output
        Get-Item $Output | Format-List Name, Length, LastWriteTime
        Get-FileHash $Output -Algorithm SHA256 | Format-List Algorithm, Hash
    }

    return $CopiedOutputs
}

$CleanOnly = $false
$SkipClean = $false
$InstallApp = $false
$RequestedVersion = ""
$BundleTarget = "nsis"

for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        "--clean" { $CleanOnly = $true }
        "-c" { $CleanOnly = $true }
        "--no-clean" { $SkipClean = $true }
        "--install" { $InstallApp = $true }
        "--version" {
            if ($i + 1 -ge $args.Count) { throw "Missing version value after --version" }
            $i++
            $RequestedVersion = $args[$i]
        }
        "-version" {
            if ($i + 1 -ge $args.Count) { throw "Missing version value after -version" }
            $i++
            $RequestedVersion = $args[$i]
        }
        "-v" {
            if ($i + 1 -ge $args.Count) { throw "Missing version value after -v" }
            $i++
            $RequestedVersion = $args[$i]
        }
        "--msi" { $BundleTarget = "msi" }
        "--all-bundles" { $BundleTarget = "all" }
        "--help" {
            Print-Help
            exit 0
        }
        "-h" {
            Print-Help
            exit 0
        }
        default {
            throw "Unknown option: $($args[$i])"
        }
    }
}

if ($CleanOnly -and $SkipClean) {
    throw "You cannot use --clean and --no-clean together."
}

Write-Host "==============================" -ForegroundColor Cyan
Write-Host " YouSync Windows installer build" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

if ($env:OS -ne "Windows_NT") {
    throw "This script must be run on Windows."
}

if ($env:PROCESSOR_ARCHITECTURE -ne "AMD64" -and $env:PROCESSOR_ARCHITEW6432 -ne "AMD64") {
    throw "This script builds x64 Windows installers only. Current architecture: $env:PROCESSOR_ARCHITECTURE"
}

$RootDir = if ($PSScriptRoot) {
    (Resolve-Path $PSScriptRoot).Path
} else {
    (Resolve-Path (Split-Path -Parent $MyInvocation.MyCommand.Path)).Path
}

$ProjectDir = Join-Path $RootDir "YouSyncDev"
$DesktopDir = Join-Path $ProjectDir "desktop"
$TauriDir = Join-Path $DesktopDir "src-tauri"
$VersionFile = Join-Path $RootDir "VERSION"

$PythonBin = Join-Path $ProjectDir ".venv\Scripts\python.exe"

$InstallerRoot = Join-Path $RootDir "installer"
$WindowsInstallerDir = Join-Path $InstallerRoot "YouSyncInstaller-Windows"

$BinariesDir = Join-Path $TauriDir "binaries"
$WorkerBuildDir = Join-Path $DesktopDir "build\yousync_worker_windows"
$WorkerSpecBuildDir = Join-Path $DesktopDir "build\pyinstaller-spec-windows"
$PyinstallerCacheDir = Join-Path $DesktopDir "build\pyinstaller-cache-windows"
$ExpectedWorkerPath = Join-Path $BinariesDir "yousync-worker-x86_64-pc-windows-msvc.exe"

$BuildLog = Join-Path $DesktopDir "build\tauri-build-windows.log"

if (!(Test-Path $DesktopDir)) {
    throw "Desktop folder not found: $DesktopDir"
}

if ($RequestedVersion -ne "") {
    Validate-Version $RequestedVersion
}

Assert-Command "npm.cmd"
Assert-Command "node.exe"
Assert-Command "cargo.exe"
Assert-Command "rustc.exe"

if (!$SkipClean) {
    Clean-Outputs
}

if ($CleanOnly) {
    exit 0
}

New-Item -ItemType Directory -Force -Path $WindowsInstallerDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DesktopDir "build") | Out-Null

if ($RequestedVersion -ne "") {
    Set-VersionFile $RequestedVersion
}

$Version = Read-Version
Sync-ProjectVersions $Version

Write-Host ""
Write-Host "Root:         $RootDir"
Write-Host "Project:      $ProjectDir"
Write-Host "Desktop:      $DesktopDir"
Write-Host "Version:      $Version"
Write-Host "Architecture: x64"
Write-Host "Bundle:       $BundleTarget"
Write-Host "Install app:  $InstallApp"
Write-Host "Output:       $WindowsInstallerDir"
Write-Host ""

Write-Host "Stopping running YouSync/dev processes..." -ForegroundColor Yellow
Get-Process -Name YouSync,yousync,node,cargo,rustc -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

Build-PythonWorker

Write-Host ""
Write-Host "Building Tauri Windows installer..." -ForegroundColor Cyan
Write-Host "Command: npm run tauri -- build --bundles $BundleTarget"
Write-Host "Build log: $BuildLog"
Write-Host ""

Set-Location $DesktopDir

$OldErrorActionPreference = $ErrorActionPreference
$TauriExitCode = 0

try {
    $global:ErrorActionPreference = "Continue"
    & npm.cmd run tauri -- build --bundles $BundleTarget 2>&1 | Tee-Object -FilePath $BuildLog
    $TauriExitCode = $LASTEXITCODE
} finally {
    $global:ErrorActionPreference = $OldErrorActionPreference
}

if ($TauriExitCode -ne 0) {
    Write-Host ""
    Write-Host "Tauri Windows build failed." -ForegroundColor Red
    Write-Host "Build log:"
    Write-Host $BuildLog
    exit 1
}

Write-Host ""
Write-Host "Worker inside Tauri release/bundle outputs:" -ForegroundColor Cyan
Get-ChildItem -Path (Join-Path $TauriDir "target\release") -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "worker|x86_64|yousync" } |
    Select-Object FullName, Length, LastWriteTime |
    Format-Table -AutoSize

$CopiedOutputs = Copy-BuildOutputs

if ($InstallApp) {
    $InstallerToRun = $CopiedOutputs |
        Where-Object { $_ -like "*.exe" } |
        Select-Object -First 1

    if ($null -eq $InstallerToRun) {
        $InstallerToRun = $CopiedOutputs |
            Where-Object { $_ -like "*.msi" } |
            Select-Object -First 1
    }

    if ($null -eq $InstallerToRun) {
        throw "No installer available to run."
    }

    Write-Host ""
    Write-Host "Running installer:" -ForegroundColor Cyan
    Write-Host $InstallerToRun

    if ($InstallerToRun -like "*.msi") {
        Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$InstallerToRun`"" -Wait
    } else {
        Start-Process -FilePath $InstallerToRun -Wait
    }

    Write-Host ""
    Write-Host "Installer finished." -ForegroundColor Green
}

Write-Host ""
Write-Host "Windows installer build completed!" -ForegroundColor Green
Write-Host ""
Write-Host "Output folder:"
Write-Host $WindowsInstallerDir
Write-Host ""
Write-Host "Main expected installer:"
Write-Host (Join-Path $WindowsInstallerDir "YouSyncInstaller-Windows-v$Version-x64.exe")
Write-Host ""
