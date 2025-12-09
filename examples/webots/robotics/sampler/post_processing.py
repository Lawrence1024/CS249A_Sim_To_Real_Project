"""
Combined post-processing utilities for the Webots robotics sampler.

This module links the manual parameter sampling loop with the gap analysis
logic so we can automatically compute a sim-to-real error metric from the
binary log files produced by Webots (sim) and hardware (real), and then feed
that metric back to the sampler.

Typical flow:
1) Run a sample (manual_robotics_eval updates the Scenic files).
2) Manually execute Webots and the hardware run to produce two log binaries.
3) Call compute_gap_metric(sim_log_file, real_log_file) to get the combined
   error metric and detailed sub-metrics.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure the project root (Scenic/) is importable so logger.gap_analyzer works
ROOT = Path(__file__).resolve().parent  # .../examples/webots/robotics/sampler
PROJECT_ROOT = ROOT.parents[3]          # .../Scenic
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from logger.log_decoder import LogDecoder  # type: ignore
from logger import gap_analyzer as ga      # type: ignore

log = logging.getLogger(__name__)


class GapComputationError(Exception):
    """Raised when gap metric computation fails."""


LOG_DIR_CANDIDATES = (
    ROOT.parent / "log",   # Expected default: .../robotics/log
    ROOT.parent / "logs",  # Alternate naming
)


def _resolve_log_dir(log_dir: Optional[str] = None) -> Path:
    """Resolve the log directory path."""
    if log_dir:
        candidate = Path(log_dir)
        if candidate.is_dir():
            return candidate
        raise GapComputationError(f"Specified log directory does not exist: {log_dir}")

    for candidate in LOG_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate

    raise GapComputationError(
        f"No log directory found. Tried: {', '.join(str(p) for p in LOG_DIR_CANDIDATES)}"
    )


def get_latest_log_pair(log_dir: Optional[str] = None, extension: str = ".bin") -> tuple[Path, Path]:
    """
    Return the two most recent log files (older = sim, newer = real) from the log directory.
    """
    base_dir = _resolve_log_dir(log_dir)
    files = [p for p in base_dir.iterdir() if p.is_file() and p.suffix == extension]

    if len(files) < 2:
        raise GapComputationError(
            f"Not enough log files in {base_dir}. Need at least 2 with extension '{extension}'."
        )

    files.sort(key=lambda p: p.stat().st_mtime)
    sim_file, real_file = files[-2], files[-1]
    return sim_file, real_file


def _normalize_lap_time_gap(lap_time_gap_pct: float) -> float:
    """Convert lap time gap percent into [0, 1] with a soft cap."""
    return min(1.0, abs(lap_time_gap_pct) / 100.0)


def _normalize_area_gap(ratio_diff: float) -> float:
    """Ensure area gap ratio is clamped to [0, 1]."""
    return max(0.0, min(1.0, ratio_diff))


def compute_gap_metric(
    sim_log_file: str,
    real_log_file: str,
    do_visualize: bool = False,
) -> Dict[str, Any]:
    """
    Compute sim-to-real gap metrics from two binary log files.

    Returns a dictionary containing:
        - lap_time_sim, lap_time_real
        - lap_time_gap_pct
        - normalized_time_gap
        - normalized_area_gap
        - combined_error (averaged normalized_time_gap & normalized_area_gap)
        - area_diff
        - ratio_diff
    """
    for path in (sim_log_file, real_log_file):
        if not path or not os.path.exists(path):
            raise GapComputationError(f"Log file not found: {path}")

    df_sim = LogDecoder.decode_df(sim_log_file)
    df_real = LogDecoder.decode_df(real_log_file)

    if df_sim is None or df_real is None:
        raise GapComputationError("Failed to decode one or both log files using LogDecoder.")

    lap_df_sim, hits_sim = ga.segment_laps_and_track_hits(df_sim)
    lap_df_real, hits_real = ga.segment_laps_and_track_hits(df_real)

    if lap_df_sim.empty or lap_df_real.empty:
        raise GapComputationError("Unable to segment a full lap from the provided logs.")

    total_time_sim, _ = ga.calculate_lap_times(hits_sim)
    total_time_real, _ = ga.calculate_lap_times(hits_real)

    if total_time_sim == 0 or total_time_real == 0:
        raise GapComputationError("Lap times could not be computed; check target_id transitions.")

    lap_time_gap_pct = (total_time_real - total_time_sim) / total_time_sim * 100.0

    _, _, polygon_sim = ga.calculate_buffered_area_gap(lap_df_sim)
    ratio_diff, area_diff, polygon_real = ga.calculate_buffered_area_gap(
        lap_df_real, comparison_polygon=polygon_sim
    )

    normalized_time_gap = _normalize_lap_time_gap(lap_time_gap_pct)
    normalized_area_gap = _normalize_area_gap(ratio_diff)
    combined_error = min(1.0, 0.5 * normalized_time_gap + 0.5 * normalized_area_gap)

    metrics: Dict[str, Any] = {
        "lap_time_sim": total_time_sim,
        "lap_time_real": total_time_real,
        "lap_time_gap_pct": lap_time_gap_pct,
        "normalized_time_gap": normalized_time_gap,
        "normalized_area_gap": normalized_area_gap,
        "combined_error": combined_error,
        "area_diff": area_diff,
        "ratio_diff": ratio_diff,
    }

    log.info(
        "Gap metrics -> lap_time_gap_pct: %.2f%% | area_ratio: %.4f | combined_error: %.4f",
        lap_time_gap_pct,
        ratio_diff,
        combined_error,
    )

    if do_visualize:
        ga.visualize_comparison(lap_df_sim, lap_df_real, polygon_sim, polygon_real)

    return metrics


__all__ = ["compute_gap_metric", "GapComputationError", "get_latest_log_pair"]

