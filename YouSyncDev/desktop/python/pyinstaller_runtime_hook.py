"""PyInstaller runtime hook for YouSync macOS worker.

This runs before yousync_worker.py imports the app code. It sets a usable CA
bundle so urllib, requests, pytubefix and yt-dlp can validate HTTPS certificates
inside the packaged macOS app.
"""

from pathlib import Path
import os
import sys


def _is_file(path_value: str | None) -> bool:
    if not path_value:
        return False

    try:
        return Path(path_value).is_file()
    except Exception:
        return False


def _candidate_certificates() -> list[Path]:
    candidates: list[Path] = []

    try:
        import certifi

        candidates.append(Path(certifi.where()))
    except Exception:
        pass

    bundle_dir = getattr(sys, "_MEIPASS", "")
    if bundle_dir:
        bundle_path = Path(bundle_dir)
        candidates.extend(
            [
                bundle_path / "certifi" / "cacert.pem",
                bundle_path / "certifi" / "cacert.pemc",
                bundle_path / "cacert.pem",
            ]
        )

    candidates.extend(
        [
            Path("/etc/ssl/cert.pem"),
            Path("/private/etc/ssl/cert.pem"),
        ]
    )

    return candidates


def _configure_ssl_certificates() -> None:
    current_ssl_cert = os.environ.get("SSL_CERT_FILE")
    current_requests_bundle = os.environ.get("REQUESTS_CA_BUNDLE")

    if _is_file(current_ssl_cert) and _is_file(current_requests_bundle):
        return

    for candidate in _candidate_certificates():
        if candidate.is_file():
            cert_path = str(candidate)
            os.environ["SSL_CERT_FILE"] = cert_path
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path
            os.environ["CURL_CA_BUNDLE"] = cert_path
            return


_configure_ssl_certificates()
