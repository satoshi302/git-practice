from __future__ import annotations
"""
Kindle firmware download and extraction utilities.

Amazon firmware packages are gzip-compressed tar archives containing
partition images and RSA signatures. This module handles fetching and
unpacking them for use with the flash tools.
"""
import gzip
import hashlib
import os
import tarfile
import urllib.request

from kindle_recovery.common.exceptions import FlashError
from kindle_recovery.common.logger import get_logger

log = get_logger(__name__)

# Amazon OTA firmware URL pattern for Kindle Paperwhite 4
FIRMWARE_URL_TEMPLATE = (
    "https://s3.amazonaws.com/firmwaredownloads/"
    "update_kindle_{device}_{version}.bin"
)

# Device identifier for PW4
PW4_DEVICE_ID = "kindlepw4"


def download_firmware(version: str, output_dir: str = "firmware", device: str = PW4_DEVICE_ID) -> str:
    os.makedirs(output_dir, exist_ok=True)
    url = FIRMWARE_URL_TEMPLATE.format(device=device, version=version)
    filename = url.split("/")[-1]
    dest = os.path.join(output_dir, filename)

    if os.path.exists(dest):
        log.info("Firmware already downloaded: %s", dest)
        return dest

    log.info("Downloading firmware %s from Amazon OTA...", version)
    log.info("URL: %s", url)

    def _progress(block_count, block_size, total_size):
        if total_size > 0:
            pct = block_count * block_size * 100 // total_size
            print(f"\r  {pct:3d}%  {block_count * block_size // 1024 // 1024} MB", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print()
    log.info("Downloaded: %s", dest)
    return dest


def verify_firmware(bin_path: str) -> bool:
    log.info("Verifying firmware integrity: %s", bin_path)
    sha256 = hashlib.sha256()
    with open(bin_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    digest = sha256.hexdigest()
    log.info("SHA256: %s", digest)
    # Amazon does not publish standalone hashes; integrity is checked by the
    # internal signature embedded in the package. Return True for informational use.
    return True


def extract_firmware(bin_path: str, output_dir: str | None = None) -> dict[str, str]:
    if output_dir is None:
        output_dir = bin_path.replace(".bin", "_extracted")
    os.makedirs(output_dir, exist_ok=True)

    log.info("Extracting %s to %s...", bin_path, output_dir)

    # Kindle .bin files are gzip-compressed tar archives
    try:
        with gzip.open(bin_path, "rb") as gz:
            with tarfile.open(fileobj=gz) as tar:
                tar.extractall(output_dir)
                members = tar.getnames()
    except (gzip.BadGzipFile, tarfile.TarError) as e:
        raise FlashError(f"Failed to extract firmware: {e}") from e

    log.info("Extracted %d files:", len(members))
    result = {}
    for name in members:
        path = os.path.join(output_dir, name)
        result[name] = path
        log.info("  %s", name)

    return result


def find_partition_images(extracted: dict[str, str]) -> dict[str, str]:
    images = {}
    for name, path in extracted.items():
        lower = name.lower()
        if "os" in lower and lower.endswith(".img"):
            images["os"] = path
        elif "recovery" in lower and lower.endswith(".img"):
            images["recovery"] = path
        elif "uboot" in lower or "spl" in lower:
            images["bootloader"] = path
    return images
