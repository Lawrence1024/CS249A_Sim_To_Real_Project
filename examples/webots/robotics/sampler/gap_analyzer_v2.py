import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure local imports work regardless of entrypoint
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[3]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import boundary_check  # type: ignore
from logger.log_decoder import LogDecoder  # type: ignore

# Configuration
WAYPOINTS = [
    (-0.32, -0.46),
    (-0.32, 0.36),
    (-1.02, 0.36),
    (-1.02, -0.46),
]


@dataclass
class TrajectoryGapConfig:
    """Tuning knobs for trajectory comparison."""

    use_relative_deltas: bool = False
    trajectory_norm: float = 1.0  # meters; used to clamp trajectory gap to [0, 1]
    boundary_limit_dist: float = 0.3


def _extract_waypoint_hits(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return a list of hit events inferred from target_id transitions."""
    if df.empty or "target_id" not in df.columns:
        return []

    hits: List[Dict[str, Any]] = []
    prev_id = int(df.iloc[0]["target_id"])

    for idx, row in df.iloc[1:].iterrows():
        cur_id = int(row["target_id"])
        if cur_id != prev_id:
            hits.append(
                {
                    "waypoint": prev_id,  # waypoint just hit
                    "index": idx,
                    "timestamp": float(row["timestamp"]),
                    "new_target_id": cur_id,
                }
            )
        prev_id = cur_id

    return hits


def num_waypoints_hit_v2(df: pd.DataFrame, total_wp: int = 4) -> int:
    """
    Waypoint hit count:
      - If waypoint 0 is hit twice (two 0->1 transitions), return total_wp.
      - Otherwise, return the last row's target_id.
    """
    hits = _extract_waypoint_hits(df)
    zero_hits = [h for h in hits if h["waypoint"] == 0]
    if len(zero_hits) >= 2:
        return total_wp + 1 # add 1 to include the second 0->1 transition
    if df.empty:
        return 0
    if df.iloc[-1]["target_id"] == 0:
        return total_wp # add 1 to include the second 0->1 transition
    return int(df.iloc[-1]["target_id"])


def _segment_full_run(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Keep data from the very start up to:
      - The second time waypoint 0 is hit (second 0->1 switch), or
      - The last waypoint hit if WP0 is not hit twice, or
      - The final row if no transitions exist.
    """
    hits_all = _extract_waypoint_hits(df)
    zero_hits = [h for h in hits_all if h["waypoint"] == 0]

    if len(zero_hits) >= 2:
        end_idx = zero_hits[1]["index"]
    elif hits_all:
        end_idx = hits_all[-1]["index"]
    else:
        end_idx = df.index[-1]

    first_idx = df.index[0]
    trimmed_df = df.loc[first_idx:end_idx].copy()
    hits_trimmed = [h for h in hits_all if h["index"] <= end_idx]
    return trimmed_df, hits_trimmed


def _truncate_to_common_hits(
    df_sim: pd.DataFrame,
    hits_sim: List[Dict[str, Any]],
    df_real: pd.DataFrame,
    hits_real: List[Dict[str, Any]],
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Truncate both runs so they end at the same number of waypoint hits.
    If no hits exist in either run, keep the full data.
    """
    common_hits = min(len(hits_sim), len(hits_real))
    if common_hits == 0:
        return df_sim, df_real, hits_sim, hits_real

    end_idx_sim = hits_sim[common_hits - 1]["index"]
    end_idx_real = hits_real[common_hits - 1]["index"]

    df_sim_trunc = df_sim.loc[df_sim.index[0] : end_idx_sim].copy()
    df_real_trunc = df_real.loc[df_real.index[0] : end_idx_real].copy()

    hits_sim_trunc = [h for h in hits_sim if h["index"] <= end_idx_sim]
    hits_real_trunc = [h for h in hits_real if h["index"] <= end_idx_real]

    return df_sim_trunc, df_real_trunc, hits_sim_trunc, hits_real_trunc


def _boundary_violation_exists(
    df: pd.DataFrame, waypoints=WAYPOINTS, limit_dist: float = 0.3
) -> bool:
    """Return True if any point violates the square boundary."""
    for _, row in df.iterrows():
        if boundary_check.check_square_boundary_violation(
            (row["x"], row["y"]), waypoints, limit_dist=limit_dist
        ):
            return True
    return False


def _align_and_interpolate(
    df_ref: pd.DataFrame, df_other: pd.DataFrame
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Align df_other to df_ref's timeline using linear interpolation.
    Timestamps are shifted so each run starts at t=0.
    Returns: (t_ref, x_ref, y_ref, interp_other_xy)
    """
    t_ref = df_ref["timestamp"].to_numpy() - float(df_ref["timestamp"].iloc[0])
    t_other = df_other["timestamp"].to_numpy() - float(df_other["timestamp"].iloc[0])

    end_time = min(t_ref[-1], t_other[-1])
    mask_ref = t_ref <= end_time

    t_ref = t_ref[mask_ref]
    x_ref = df_ref["x"].to_numpy()[mask_ref]
    y_ref = df_ref["y"].to_numpy()[mask_ref]

    x_other = np.interp(t_ref, t_other, df_other["x"].to_numpy())
    y_other = np.interp(t_ref, t_other, df_other["y"].to_numpy())

    return t_ref, x_ref, y_ref, np.stack([x_other, y_other], axis=1)


def compute_trajectory_gap(
    df_sim: pd.DataFrame,
    df_real: pd.DataFrame,
    use_relative_deltas: bool = False,
) -> Dict[str, Any]:
    """
    Compute trajectory gap using either absolute positions or relative deltas.

    Returns:
        {
            "mean_gap": float,
            "segments": int,
            "mode": "relative_deltas" | "absolute",
        }
    """
    if len(df_sim) < 2 or len(df_real) < 2:
        return {"mean_gap": 0.0, "segments": 0, "mode": "relative_deltas" if use_relative_deltas else "absolute"}

    t_ref, x_ref, y_ref, other_xy = _align_and_interpolate(df_sim, df_real)
    x_other, y_other = other_xy[:, 0], other_xy[:, 1]

    if use_relative_deltas:
        dx_ref = np.diff(x_ref)
        dy_ref = np.diff(y_ref)
        dx_other = np.diff(x_other)
        dy_other = np.diff(y_other)
        deltas = np.sqrt((dx_ref - dx_other) ** 2 + (dy_ref - dy_other) ** 2)
    else:
        pos_diff = np.sqrt((x_ref - x_other) ** 2 + (y_ref - y_other) ** 2)
        # Skip the first point to match the "segments = N-1" description
        deltas = pos_diff[1:] if len(pos_diff) > 1 else pos_diff

    segments = len(deltas)
    mean_gap = float(deltas.sum() / segments) if segments > 0 else 0.0

    return {
        "mean_gap": mean_gap,
        "segments": segments,
        "mode": "relative_deltas" if use_relative_deltas else "absolute",
        "aligned_points": len(t_ref),
        "duration": float(t_ref[-1]) if len(t_ref) else 0.0,
    }


def compute_sim_real_gap_v2(
    df_sim: pd.DataFrame,
    df_real: pd.DataFrame,
    config: TrajectoryGapConfig = TrajectoryGapConfig(),
) -> Dict[str, Any]:
    """
    End-to-end gap computation following the new evaluation scheme.
    """
    # 1) Start from the beginning; end when WP0 is hit again (or last hit/row).
    df_sim_span, hits_sim = _segment_full_run(df_sim)
    df_real_span, hits_real = _segment_full_run(df_real)

    # 2) Waypoint counts
    wp_hit_sim = num_waypoints_hit_v2(df_sim_span, len(WAYPOINTS))
    wp_hit_real = num_waypoints_hit_v2(df_real_span, len(WAYPOINTS))
    wp_diff = abs(wp_hit_sim - wp_hit_real)

    # 3) Truncate to common hits, then trim to the shorter time span.
    df_sim_common, df_real_common, hits_sim_common, hits_real_common = _truncate_to_common_hits(
        df_sim_span, hits_sim, df_real_span, hits_real
    )

    if not df_sim_common.empty and not df_real_common.empty:
        end_time = min(
            df_sim_common["timestamp"].iloc[-1] - df_sim_common["timestamp"].iloc[0],
            df_real_common["timestamp"].iloc[-1] - df_real_common["timestamp"].iloc[0],
        )
        # Ensure both are cut to the shorter relative duration
        df_sim_common = df_sim_common[
            (df_sim_common["timestamp"] - df_sim_common["timestamp"].iloc[0]) <= end_time
        ]
        df_real_common = df_real_common[
            (df_real_common["timestamp"] - df_real_common["timestamp"].iloc[0]) <= end_time
        ]

    # 4) Boundary agreement
    violation_sim = _boundary_violation_exists(df_sim_common, limit_dist=config.boundary_limit_dist)
    violation_real = _boundary_violation_exists(df_real_common, limit_dist=config.boundary_limit_dist)
    boundary_match = 1 if violation_sim == violation_real else 0

    # 5) Trajectory gap
    traj_gap = compute_trajectory_gap(
        df_sim_common, df_real_common, use_relative_deltas=config.use_relative_deltas
    )

    return {
        "waypoints_hit_sim": wp_hit_sim,
        "waypoints_hit_real": wp_hit_real,
        "waypoints_diff": wp_diff,
        "hits_considered": min(len(hits_sim_common), len(hits_real_common)),
        "boundary_violation_sim": violation_sim,
        "boundary_violation_real": violation_real,
        "boundary_match": boundary_match,
        "trajectory_gap": traj_gap["mean_gap"],
        "trajectory_mode": traj_gap["mode"],
        "trajectory_segments": traj_gap["segments"],
        "trajectory_aligned_points": traj_gap.get("aligned_points", 0),
        "trajectory_duration": traj_gap.get("duration", 0.0),
        "df_sim_used": df_sim_common,
        "df_real_used": df_real_common,
    }


def visualize_alignment(df_sim: pd.DataFrame, df_real: pd.DataFrame, title: str = "Sim vs Real (v2)") -> None:
    """Quick overlay visualization of the trajectories being compared."""
    plt.figure(figsize=(8, 6))
    plt.plot(df_sim["x"], df_sim["y"], label="Sim", color="blue")
    plt.plot(df_real["x"], df_real["y"], label="Real", color="red")
    plt.scatter([wp[0] for wp in WAYPOINTS], [wp[1] for wp in WAYPOINTS], c="green", marker="o", label="Waypoints")
    plt.axis("equal")
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend()
    plt.grid(True)
    plt.show()


def run_sim_to_real_analysis(
    sim_file: str,
    real_file: str,
    config: TrajectoryGapConfig = TrajectoryGapConfig(),
    do_visualize: bool = False,
) -> Dict[str, Any]:
    """Convenience entrypoint mirroring the original script."""
    df_sim = LogDecoder.decode_df(sim_file)
    df_real = LogDecoder.decode_df(real_file)

    if df_sim is None or df_real is None:
        raise FileNotFoundError("Failed to decode one or both log files.")

    metrics = compute_sim_real_gap_v2(df_sim, df_real, config=config)

    if do_visualize:
        visualize_alignment(metrics["df_sim_used"], metrics["df_real_used"])

    return metrics


if __name__ == "__main__":
    SIM_LOG_FILE = str(ROOT.parent / "log" / "fast_log_1765330653.bin")
    REAL_LOG_FILE = str(ROOT.parent / "log" / "fast_log_1765330805.bin")
    results = run_sim_to_real_analysis(
        SIM_LOG_FILE,
        REAL_LOG_FILE,
        config=TrajectoryGapConfig(use_relative_deltas=False, trajectory_norm=1.0),
        do_visualize=True,
    )
    print(results)

