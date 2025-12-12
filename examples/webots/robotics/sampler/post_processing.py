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
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from log_decoder import LogDecoder  # type: ignore
import gap_analyzer_v2 as ga_v2            # type: ignore

log = logging.getLogger(__name__)


class GapComputationError(Exception):
    """Raised when gap metric computation fails."""


LOG_DIR_CANDIDATES = (
    ROOT.parent / "log",   # Expected default: .../robotics/log
    ROOT.parent / "logs",  # Alternate naming
)

DEFAULT_WEIGHTS: Dict[str, float] = {
    "waypoint": 0.8,
    "boundary_wp_diff": 0.2,
    "boundary": 0.6,
    "trajectory": 0.4,
}
DEFAULT_TRAJECTORY_NORM = 0.2


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


def compute_gap_metric(
    sim_log_file: str,
    real_log_file: str,
    do_visualize: bool = False,
    use_relative_deltas: bool = False,
    weights: Optional[Dict[str, float]] = None,
    trajectory_norm: float = DEFAULT_TRAJECTORY_NORM,
    boundary_limit_dist: float = 0.25,
) -> Dict[str, Any]:
    """
    Compute sim-to-real gap metrics from two binary log files.

    Returns a dictionary containing:
        - waypoints_hit_sim/real and absolute difference
        - boundary agreement (1 match, 0 mismatch)
        - trajectory_gap (raw) and normalized value
        - combined_error in [0, 1]
    """
    for path in (sim_log_file, real_log_file):
        if not path or not os.path.exists(path):
            raise GapComputationError(f"Log file not found: {path}")

    df_sim = LogDecoder.decode_df(sim_log_file)
    df_real = LogDecoder.decode_df(real_log_file)

    if df_sim is None or df_real is None:
        raise GapComputationError("Failed to decode one or both log files using LogDecoder.")

    cfg = ga_v2.TrajectoryGapConfig(
        use_relative_deltas=use_relative_deltas,
        trajectory_norm=trajectory_norm,
        boundary_limit_dist=boundary_limit_dist,
    )
    raw_metrics = ga_v2.compute_sim_real_gap_v2(df_sim, df_real, config=cfg)

    wp_gap = raw_metrics["waypoints_diff"] # / float(len(ga_v2.WAYPOINTS)))
    boundary_gap = 1.0 - raw_metrics["boundary_match"]
    norm_val = trajectory_norm if trajectory_norm > 0 else DEFAULT_TRAJECTORY_NORM
    raw_metrics["trajectory_gap"] = min(1.0, raw_metrics["trajectory_gap"] / norm_val) if norm_val else 0.0
    traj_gap = raw_metrics["trajectory_gap"]

    applied_weights = weights or DEFAULT_WEIGHTS
    if wp_gap == 0:
        combined_error = min(
            1.0,
            + applied_weights.get("boundary", 0.0) * boundary_gap
            + applied_weights.get("trajectory", 0.0) * traj_gap,
        )
    else:
        combined_error = min(
            1.0,
            applied_weights.get("waypoint", 0.0) * wp_gap
            + applied_weights.get("boundary_wp_diff", 0.0) * boundary_gap
        )

    metrics: Dict[str, Any] = {
        "waypoints_hit_sim": raw_metrics["waypoints_hit_sim"],
        "waypoints_hit_real": raw_metrics["waypoints_hit_real"],
        "waypoints_diff": raw_metrics["waypoints_diff"],
        "boundary_violation_sim": raw_metrics["boundary_violation_sim"],
        "boundary_violation_real": raw_metrics["boundary_violation_real"],
        "boundary_match": raw_metrics["boundary_match"],
        "trajectory_gap_raw": raw_metrics["trajectory_gap"],
        "trajectory_mode": raw_metrics["trajectory_mode"],
        "trajectory_segments": raw_metrics["trajectory_segments"],
        "trajectory_aligned_points": raw_metrics["trajectory_aligned_points"],
        "trajectory_duration": raw_metrics["trajectory_duration"],
        "normalized_waypoint_gap": wp_gap,
        "normalized_boundary_gap": boundary_gap,
        "normalized_trajectory_gap": traj_gap,
        "combined_error": combined_error,
        "weights": applied_weights,
    }

    log.info(
        "Gap metrics v2 -> wp_diff: %d | boundary_match: %d | traj_gap: %.4f (%s) | combined_error: %.4f",
        raw_metrics["waypoints_diff"],
        raw_metrics["boundary_match"],
        raw_metrics["trajectory_gap"],
        raw_metrics["trajectory_mode"],
        combined_error,
    )

    if do_visualize:
        ga_v2.visualize_alignment(raw_metrics["df_sim_used"], raw_metrics["df_real_used"])
    print("Trajectory gap:", metrics["normalized_trajectory_gap"])

    return metrics


__all__ = ["compute_gap_metric", "GapComputationError", "get_latest_log_pair"]

