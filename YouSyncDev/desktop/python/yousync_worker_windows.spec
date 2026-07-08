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
