"""The ETL pipeline: read the raw files, build the district table, write it to data/processed/."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ev_gap import config
from ev_gap.extract import read_destatis, read_kba, read_register
from ev_gap.transform import build_districts

DATA_INFO_FILE = config.PROCESSED_DIR / "data_info.json"


def file_date(path: Path) -> str:
    """The reference date in a raw file name, for example 2026-11-12."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", path.name)
    if match is None:
        raise ValueError(f"No date in the file name {path.name}")
    return match.group(0)


def data_dates(register_file: Path, kba_file: Path, destatis_file: Path) -> dict:
    """Reference dates of the three sources, and when the pipeline ran."""
    return {
        "charging_register": file_date(register_file),
        "kba_car_stock": file_date(kba_file),
        "destatis_population": file_date(destatis_file),
        "pipeline_run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run(raw_dir: Path = config.RAW_DIR, target: Path = config.DISTRICTS_FILE) -> pd.DataFrame:
    register_files = sorted(raw_dir.glob(config.BNETZA_GLOB))
    if not register_files:
        raise FileNotFoundError(f"No register CSV in {raw_dir}. Run: python -m ev_gap.download")
    kba_file = raw_dir / config.KBA_FZ1_FILE
    destatis_file = raw_dir / config.DESTATIS_KREISE_FILE

    districts = build_districts(
        register=read_register(register_files[-1]),
        kba=read_kba(kba_file),
        destatis=read_destatis(destatis_file),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    districts.to_csv(target, index=False)
    # The dates travel with the results, so the service can say how old its data is.
    info = data_dates(register_files[-1], kba_file, destatis_file)
    (target.parent / DATA_INFO_FILE.name).write_text(json.dumps(info, indent=2), encoding="utf-8")
    return districts


def load_districts(path: Path = config.DISTRICTS_FILE) -> pd.DataFrame:
    """Read the processed table. The key must stay text, because it has leading zeros."""
    return pd.read_csv(path, dtype={"key": str})


if __name__ == "__main__":
    result = run()
    print(f"{len(result)} districts written to {config.DISTRICTS_FILE}")
    print(f"BEV {result['bev'].sum():,} | charging points {result['charging_points'].sum():,} "
          f"| BEV per point {result['bev'].sum() / result['charging_points'].sum():.1f}")
