"""The ETL pipeline: read the raw files, build the district table, write it to data/processed/."""

from pathlib import Path

import pandas as pd

from ev_gap import config
from ev_gap.extract import read_destatis, read_kba, read_register
from ev_gap.transform import build_districts


def run(raw_dir: Path = config.RAW_DIR, target: Path = config.DISTRICTS_FILE) -> pd.DataFrame:
    register_files = sorted(raw_dir.glob(config.BNETZA_GLOB))
    if not register_files:
        raise FileNotFoundError(f"No register CSV in {raw_dir}. Run: python -m ev_gap.download")

    districts = build_districts(
        register=read_register(register_files[-1]),
        kba=read_kba(raw_dir / config.KBA_FZ1_FILE),
        destatis=read_destatis(raw_dir / config.DESTATIS_KREISE_FILE),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    districts.to_csv(target, index=False)
    return districts


def load_districts(path: Path = config.DISTRICTS_FILE) -> pd.DataFrame:
    """Read the processed table. The key must stay text, because it has leading zeros."""
    return pd.read_csv(path, dtype={"key": str})


if __name__ == "__main__":
    result = run()
    print(f"{len(result)} districts written to {config.DISTRICTS_FILE}")
    print(f"BEV {result['bev'].sum():,} | charging points {result['charging_points'].sum():,} "
          f"| BEV per point {result['bev'].sum() / result['charging_points'].sum():.1f}")
