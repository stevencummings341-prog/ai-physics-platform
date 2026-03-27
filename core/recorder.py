"""Standardized per-step data recording with downsampling and export."""

from __future__ import annotations

import logging
import os
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


class DataRecorder:
    """Collects per-step measurements and exports to CSV or Parquet."""

    def __init__(self, out_dir: str, downsample: int = 1):
        self.out_dir = out_dir
        self.downsample = max(1, downsample)
        self._rows: list[dict[str, Any]] = []
        self._step_counter = 0

    def record(self, row: dict[str, Any]) -> None:
        self._step_counter += 1
        if self._step_counter % self.downsample == 0:
            self._rows.append(row)

    def clear(self) -> None:
        self._rows.clear()
        self._step_counter = 0

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self._rows)

    def save_csv(self, filename: str = "timeseries.csv") -> str:
        path = os.path.join(self.out_dir, filename)
        self.to_dataframe().to_csv(path, index=False)
        log.info("Saved %d rows to %s", len(self._rows), path)
        return path

    def save_parquet(self, filename: str = "timeseries.parquet") -> str:
        path = os.path.join(self.out_dir, filename)
        self.to_dataframe().to_parquet(path, index=False)
        log.info("Saved %d rows to %s", len(self._rows), path)
        return path

    def __len__(self) -> int:
        return len(self._rows)
