"""Download the three raw source files into data/raw/. Safe to run again."""

import re
from pathlib import Path

import requests

from ev_gap import config


def find_bnetza_csv_url() -> str:
    """The register file name contains its date, so read the current link from the BNetzA page."""
    page = requests.get(config.BNETZA_PAGE, headers=config.HEADERS, timeout=60)
    page.raise_for_status()
    match = re.search(config.BNETZA_CSV_PATTERN, page.text)
    if match is None:
        raise RuntimeError("No Ladesaeulenregister CSV link found on the BNetzA page.")
    return match.group(0)


def download_file(url: str, target: Path) -> Path:
    """Download url to target. Skips the download if the file already exists."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f"skip   {target.name} (already there)")
        return target

    # Write to a temp name first so a failed download never leaves a half-written file.
    tmp = target.with_suffix(target.suffix + ".part")
    with requests.get(url, headers=config.HEADERS, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    tmp.rename(target)
    print(f"saved  {target.name} ({target.stat().st_size / 1e6:.1f} MB)")
    return target


def download_all(raw_dir: Path = config.RAW_DIR) -> dict[str, Path]:
    bnetza_url = find_bnetza_csv_url()
    return {
        "bnetza": download_file(bnetza_url, raw_dir / bnetza_url.rsplit("/", 1)[-1]),
        "kba": download_file(config.KBA_FZ1_URL, raw_dir / config.KBA_FZ1_FILE),
        "destatis": download_file(config.DESTATIS_KREISE_URL, raw_dir / config.DESTATIS_KREISE_FILE),
        "boundaries": download_file(config.BOUNDARIES_URL, raw_dir / config.BOUNDARIES_FILE),
    }


if __name__ == "__main__":
    download_all()
