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
from log_decoder import LogDecoder  # type: ignore

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
    boundary_limit_dist: float = 0.25


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
    if df.empty or len(hits) == 0:
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
        end_idx = df.index[-1]  # Use final row if no transitions exist

    first_idx = df.index[0]
    trimmed_df = df.loc[first_idx:end_idx].copy()
    hits_trimmed = [h for h in hits_all if h["index"] <= end_idx]
    return trimmed_df, hits_trimmed

def _truncate_for_trajectory_comparison(
    df_sim: pd.DataFrame,
    hits_sim: List[Dict[str, Any]],
    df_real: pd.DataFrame,
    hits_real: List[Dict[str, Any]],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Truncate both runs for trajectory comparison:
    1. Start from the first data point (index 0)
    2. End at the same last waypoint hit (based on common_hits)
    
    This ensures trajectory comparison starts from the very beginning of the log.
    For trajectory comparison, we allow common_hits >= 1 (unlike boundary checking which needs >= 2).
    """
    common_hits = min(len(hits_sim), len(hits_real))
    
    # If no hits at all, use full span
    if common_hits == 0:
        return df_sim.copy(), df_real.copy()
    
    # Determine end indices based on common hits
    # If common_hits == 5, waypoint 0 has been hit twice (full lap completed)
    if common_hits == 5:
        zero_hits_sim = [i for i, h in enumerate(hits_sim) if h["waypoint"] == 0]
        if len(zero_hits_sim) >= 2:
            last_hit_idx_sim = hits_sim[zero_hits_sim[1]]["index"]
        else:
            last_hit_idx_sim = hits_sim[-1]["index"]
        
        zero_hits_real = [i for i, h in enumerate(hits_real) if h["waypoint"] == 0]
        if len(zero_hits_real) >= 2:
            last_hit_idx_real = hits_real[zero_hits_real[1]]["index"]
        else:
            last_hit_idx_real = hits_real[-1]["index"]
    else:
        last_hit_idx_sim = hits_sim[common_hits - 1]["index"]
        last_hit_idx_real = hits_real[common_hits - 1]["index"]

    # Truncate from index 0 (start) to last hit (inclusive)
    df_sim_trunc = df_sim.loc[df_sim.index[0] : last_hit_idx_sim].copy()
    df_real_trunc = df_real.loc[df_real.index[0] : last_hit_idx_real].copy()

    return df_sim_trunc, df_real_trunc

def _truncate_to_common_hits(
    df_sim: pd.DataFrame,
    hits_sim: List[Dict[str, Any]],
    df_real: pd.DataFrame,
    hits_real: List[Dict[str, Any]],
) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Truncate both runs so they:
    1. Start from the first waypoint hit
    2. End at the same number of waypoint hits (min_hits)
    
    If no hits exist in either run or less than 2 hits, return empty dataframes.
    """
    common_hits = min(len(hits_sim), len(hits_real))
    if common_hits == 0 or common_hits < 2:
        # Return empty dataframes if insufficient hits
        return pd.DataFrame(), pd.DataFrame(), [], []

    # Get first and last hit indices for both
    first_hit_idx_sim = hits_sim[0]["index"]
    
    # If common_hits == 5, waypoint 0 has been hit twice (full lap completed)
    # Truncate at the second time waypoint 0 is hit
    if common_hits == 5:
        # Find the second occurrence of waypoint 0 being hit
        zero_hits_sim = [i for i, h in enumerate(hits_sim) if h["waypoint"] == 0]
        if len(zero_hits_sim) >= 2:
            last_hit_idx_sim = hits_sim[zero_hits_sim[1]]["index"]
        else:
            last_hit_idx_sim = hits_sim[-1]["index"]
    else:
        last_hit_idx_sim = hits_sim[common_hits - 1]["index"]
    
    first_hit_idx_real = hits_real[0]["index"]
    
    # If common_hits == 5, waypoint 0 has been hit twice (full lap completed)
    # Truncate at the second time waypoint 0 is hit
    if common_hits == 5:
        # Find the second occurrence of waypoint 0 being hit
        zero_hits_real = [i for i, h in enumerate(hits_real) if h["waypoint"] == 0]
        if len(zero_hits_real) >= 2:
            last_hit_idx_real = hits_real[zero_hits_real[1]]["index"]
        else:
            last_hit_idx_real = hits_real[-1]["index"]
    else:
        last_hit_idx_real = hits_real[common_hits - 1]["index"]

    # Truncate from first hit to last hit (inclusive)
    df_sim_trunc = df_sim.loc[first_hit_idx_sim : last_hit_idx_sim].copy()
    df_real_trunc = df_real.loc[first_hit_idx_real : last_hit_idx_real].copy()

    hits_sim_trunc = [h for h in hits_sim[:common_hits]]
    hits_real_trunc = [h for h in hits_real[:common_hits]]

    return df_sim_trunc, df_real_trunc, hits_sim_trunc, hits_real_trunc


def _boundary_violation_exists(
    df: pd.DataFrame, waypoints=WAYPOINTS, limit_dist: float = 0.2 #Modify post_processing instead!!!
) -> bool:
    """Return True if any point violates the square boundary.
    CHECKS THE ENTIRE DATAFRAME FOR BOUNDARY VIOLATIONS, SO DO TRUNCATE FIRST!!!
    """
    if df.empty:
        return False
    
    
    # If no waypoint hits, check the entire trajectory
    # Check boundary violations only in the filtered range
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
        return {
            "mean_gap": 0.0,
            "median_gap": 0.0,
            "max_gap": 0.0,
            "p95_gap": 0.0,
            "segments": 0,
            "mode": "relative_deltas" if use_relative_deltas else "absolute",
            "gap_times": [],
            "gap_series": [],
        }

    t_ref, x_ref, y_ref, other_xy = _align_and_interpolate(df_sim, df_real)
    x_other, y_other = other_xy[:, 0], other_xy[:, 1]

    if use_relative_deltas:
        dx_ref = np.diff(x_ref)
        dy_ref = np.diff(y_ref)
        dx_other = np.diff(x_other)
        dy_other = np.diff(y_other)
        deltas = np.sqrt((dx_ref - dx_other) ** 2 + (dy_ref - dy_other) ** 2)
        gap_times = t_ref[1:] if len(t_ref) > 1 else np.array([])
    else:
        pos_diff = np.sqrt((x_ref - x_other) ** 2 + (y_ref - y_other) ** 2)
        # Skip the first point to match the "segments = N-1" description
        deltas = pos_diff[1:] if len(pos_diff) > 1 else pos_diff
        gap_times = t_ref[1:] if len(t_ref) > 1 else t_ref

    segments = len(deltas)
    if segments > 0:
        mean_gap = float(np.mean(deltas))
        median_gap = float(np.median(deltas))
        max_gap = float(np.max(deltas))
        p95_gap = float(np.percentile(deltas, 95))
    else:
        mean_gap = median_gap = max_gap = p95_gap = 0.0

    return {
        "mean_gap": mean_gap,
        "median_gap": median_gap,
        "max_gap": max_gap,
        "p95_gap": p95_gap,
        "segments": segments,
        "mode": "relative_deltas" if use_relative_deltas else "absolute",
        "aligned_points": len(t_ref),
        "duration": float(t_ref[-1]) if len(t_ref) else 0.0,
        "gap_times": gap_times.tolist(),
        "gap_series": deltas.tolist(),
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
    wp_hit_sim = num_waypoints_hit_v2(df_sim, len(WAYPOINTS))
    wp_hit_real = num_waypoints_hit_v2(df_real, len(WAYPOINTS))
    wp_diff = abs(wp_hit_sim - wp_hit_real)

    if wp_hit_sim == wp_hit_real == 0:
        # Return zero gap with compatible structure
        return {
            "waypoints_hit_sim": 0,
            "waypoints_hit_real": 0,
            "waypoints_diff": 0,
            "hits_considered": 0,
            "boundary_violation_sim": False,
            "boundary_violation_real": False,
            "boundary_match": 1,  # Both have no violations, so they match
            "trajectory_gap": 0.0,
            "trajectory_mode": "relative_deltas" if config.use_relative_deltas else "absolute",
            "trajectory_segments": 0,
            "trajectory_aligned_points": 0,
            "trajectory_duration": 0.0,
            "df_sim_used": pd.DataFrame(),
            "df_real_used": pd.DataFrame(),
        } 

    # 3) Truncate to common hits: start from first waypoint hit, end at same last waypoint hit
    df_sim_common, df_real_common, hits_sim_common, hits_real_common = _truncate_to_common_hits(
        df_sim_span, hits_sim, df_real_span, hits_real
    )

    # 4) Boundary agreement
    violation_sim = _boundary_violation_exists(df_sim_common, limit_dist=config.boundary_limit_dist)
    violation_real = _boundary_violation_exists(df_real_common, limit_dist=config.boundary_limit_dist)
    boundary_match = 1 if violation_sim == violation_real else 0

    
    # 5) Trajectory gap - start from first data point, end at same last waypoint hit
    df_sim_traj, df_real_traj = _truncate_for_trajectory_comparison(
        df_sim_span, hits_sim, df_real_span, hits_real
    )
    traj_gap = compute_trajectory_gap(
        df_sim_traj, df_real_traj, use_relative_deltas=config.use_relative_deltas
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


def visualize_alignment(
    df_sim: pd.DataFrame, 
    df_real: pd.DataFrame, 
    title: str = "Sim vs Real (v2)",
    limit_dist: float = 0.25,
    show_boundaries: bool = True,
    already_truncated: bool = False
) -> None:
    """Quick overlay visualization of the trajectories being compared.
    Shows only the truncated segments used for boundary violation comparison
    (as defined in _truncate_to_common_hits: first hit to last hit).
    
    Args:
        df_sim: Simulation trajectory dataframe
        df_real: Real trajectory dataframe
        title: Plot title
        limit_dist: Boundary limit distance for violation checking
        show_boundaries: Whether to draw boundary rectangles
        already_truncated: If True, assumes dataframes are already truncated (from metrics)
    """
    plt.figure(figsize=(10, 8))
    
    # Get truncated segments (same logic as metrics)
    if already_truncated:
        # Dataframes are already truncated (e.g., from metrics), use as-is
        df_sim_compare = df_sim
        df_real_compare = df_real
    else:
        # 1) Segment full run (trajectories from start to last waypoint hit)
        df_sim_span, hits_sim = _segment_full_run(df_sim)
        df_real_span, hits_real = _segment_full_run(df_real)
        
        # 2) Truncate to common hits (segments used for comparison)
        df_sim_compare, df_real_compare, hits_sim_compare, hits_real_compare = _truncate_to_common_hits(
            df_sim_span, hits_sim, df_real_span, hits_real
        )
        
        # If comparison segments are empty, use full span (but warn)
        if df_sim_compare.empty or df_real_compare.empty:
            print("Warning: Truncation resulted in empty dataframes, showing full span")
            df_sim_compare = df_sim_span
            df_real_compare = df_real_span
    
    # Separate violating and non-violating points in the comparison segments
    sim_violations = []
    sim_safe = []
    real_violations = []
    real_safe = []
    
    for _, row in df_sim_compare.iterrows():
        pos = (row["x"], row["y"])
        is_violation = boundary_check.check_square_boundary_violation(
            pos, WAYPOINTS, limit_dist=limit_dist
        )
        if is_violation:
            sim_violations.append(pos)
        else:
            sim_safe.append(pos)
    
    for _, row in df_real_compare.iterrows():
        pos = (row["x"], row["y"])
        is_violation = boundary_check.check_square_boundary_violation(
            pos, WAYPOINTS, limit_dist=limit_dist
        )
        if is_violation:
            real_violations.append(pos)
        else:
            real_safe.append(pos)
    
    # Plot safe trajectories (only comparison segments)
    if sim_safe:
        sim_safe_arr = np.array(sim_safe)
        plt.plot(sim_safe_arr[:, 0], sim_safe_arr[:, 1], label="Sim (safe)", color="blue", alpha=0.6, linewidth=1.5)
    if real_safe:
        real_safe_arr = np.array(real_safe)
        plt.plot(real_safe_arr[:, 0], real_safe_arr[:, 1], label="Real (safe)", color="red", alpha=0.6, linewidth=1.5)
    
    # Plot violations (only on comparison segments)
    if sim_violations:
        sim_viol_arr = np.array(sim_violations)
        plt.scatter(sim_viol_arr[:, 0], sim_viol_arr[:, 1], c="orange", marker="x", s=50, 
                   label=f"Sim violations ({len(sim_violations)})", zorder=5, linewidths=2)
    
    if real_violations:
        real_viol_arr = np.array(real_violations)
        plt.scatter(real_viol_arr[:, 0], real_viol_arr[:, 1], c="magenta", marker="x", s=50, 
                   label=f"Real violations ({len(real_violations)})", zorder=5, linewidths=2)
    
    # Plot waypoints
    plt.scatter([wp[0] for wp in WAYPOINTS], [wp[1] for wp in WAYPOINTS], c="green", marker="o", s=100, label="Waypoints", zorder=6)
    
    # Draw boundaries if requested
    if show_boundaries:
        _draw_boundaries(plt, limit_dist)
    
    plt.axis("equal")
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()


def _draw_boundaries(plt, limit_dist: float = 0.25):
    """Helper function to draw inner and outer boundaries."""
    from matplotlib.patches import Rectangle
    import matplotlib.patches as mpatches
    
    # Calculate bounding box of waypoints
    wp_x = [wp[0] for wp in WAYPOINTS]
    wp_y = [wp[1] for wp in WAYPOINTS]
    min_x, max_x = min(wp_x), max(wp_x)
    min_y, max_y = min(wp_y), max(wp_y)
    
    # Calculate rectangle dimensions
    width = max_x - min_x
    height = max_y - min_y
    
    # Outer boundary (red, dashed)
    outer_rect = Rectangle(
        (min_x - limit_dist, min_y - limit_dist),
        width + 2 * limit_dist,
        height + 2 * limit_dist,
        linewidth=2, edgecolor='red', facecolor='none', linestyle='--', alpha=0.7, label=f'Outer boundary (±{limit_dist}m)'
    )
    plt.gca().add_patch(outer_rect)
    
    # Inner boundary (blue, dashed)
    inner_rect = Rectangle(
        (min_x + limit_dist, min_y + limit_dist),
        width - 2 * limit_dist,
        height - 2 * limit_dist,
        linewidth=2, edgecolor='blue', facecolor='none', linestyle='--', alpha=0.7, label=f'Inner boundary (±{limit_dist}m)'
    )
    # Only draw inner if it's valid (positive dimensions)
    if width > 2 * limit_dist and height > 2 * limit_dist:
        plt.gca().add_patch(inner_rect)


def visualize_interpolated_alignment(
    df_sim: pd.DataFrame,
    df_real: pd.DataFrame,
    use_relative_deltas: bool = False,
    title: str = "Interpolated Trajectory Comparison",
    limit_dist: float = 0.25,
    show_boundaries: bool = True,
) -> None:
    """
    Visualize trajectories after aligning df_real to df_sim's timeline via interpolation.
    Shows only the truncated segments used for boundary violation comparison
    (as defined in _truncate_to_common_hits: first hit to last hit).
    """
    if len(df_sim) < 2 or len(df_real) < 2:
        print("Not enough points to visualize interpolation.")
        return

    # 1) Segment full run (trajectories from start to last waypoint hit)
    df_sim_span, hits_sim = _segment_full_run(df_sim)
    df_real_span, hits_real = _segment_full_run(df_real)
    
    # 2) Truncate to common hits (segments used for comparison)
    df_sim_compare, df_real_compare, hits_sim_compare, hits_real_compare = _truncate_to_common_hits(
        df_sim_span, hits_sim, df_real_span, hits_real
    )
    
    # If comparison segments are empty, use full span (but warn)
    if df_sim_compare.empty or df_real_compare.empty:
        print("Warning: Truncation resulted in empty dataframes, using full span")
        df_sim_compare = df_sim_span
        df_real_compare = df_real_span

    # Align and interpolate the comparison segments
    t_ref, x_ref, y_ref, other_xy = _align_and_interpolate(df_sim_compare, df_real_compare)
    x_other, y_other = other_xy[:, 0], other_xy[:, 1]

    # Separate violating and non-violating points in interpolated comparison data
    sim_violations = []
    sim_safe = []
    real_violations = []
    real_safe = []
    
    for i in range(len(x_ref)):
        sim_pos = (x_ref[i], y_ref[i])
        real_pos = (x_other[i], y_other[i])
        
        # Check sim
        sim_is_violation = boundary_check.check_square_boundary_violation(
            sim_pos, WAYPOINTS, limit_dist=limit_dist
        )
        if sim_is_violation:
            sim_violations.append(sim_pos)
        else:
            sim_safe.append(sim_pos)
        
        # Check real
        real_is_violation = boundary_check.check_square_boundary_violation(
            real_pos, WAYPOINTS, limit_dist=limit_dist
        )
        if real_is_violation:
            real_violations.append(real_pos)
        else:
            real_safe.append(real_pos)

    plt.figure(figsize=(10, 8))
    
    # Plot safe interpolated trajectories (only comparison segments)
    if sim_safe:
        sim_safe_arr = np.array(sim_safe)
        plt.plot(sim_safe_arr[:, 0], sim_safe_arr[:, 1], label="Sim (interpolated, safe)", color="blue", alpha=0.7, linewidth=1.5)
    if real_safe:
        real_safe_arr = np.array(real_safe)
        plt.plot(real_safe_arr[:, 0], real_safe_arr[:, 1], label="Real (interpolated, safe)", color="magenta", alpha=0.7, linewidth=1.5)
    
    # Mark violations only on interpolated comparison segments
    if sim_violations:
        sim_viol_arr = np.array(sim_violations)
        plt.scatter(sim_viol_arr[:, 0], sim_viol_arr[:, 1], c="orange", marker="x", s=50, 
                   label=f"Sim violations ({len(sim_violations)})", zorder=5, linewidths=2)
    if real_violations:
        real_viol_arr = np.array(real_violations)
        plt.scatter(real_viol_arr[:, 0], real_viol_arr[:, 1], c="magenta", marker="x", s=50, 
                   label=f"Real violations ({len(real_violations)})", zorder=5, linewidths=2)
    
    plt.scatter([wp[0] for wp in WAYPOINTS], [wp[1] for wp in WAYPOINTS], c="green", marker="o", s=100, label="Waypoints", zorder=6)
    
    # Draw boundaries if requested
    if show_boundaries:
        _draw_boundaries(plt, limit_dist)
    
    plt.axis("equal")
    plt.title(f"{title} | mode={'relative' if use_relative_deltas else 'absolute'} | points={len(t_ref)}")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
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
        # Pass original dataframes so visualization can show full trajectories
        # but mark violations only on the comparison segments
        visualize_alignment(
            df_sim, 
            df_real,
            limit_dist=config.boundary_limit_dist,
            already_truncated=False
        )

    return metrics


if __name__ == "__main__":
    SIM_LOG_FILE = str(ROOT.parent / "log" / "fast_log_1765495926.bin")
    REAL_LOG_FILE = str(ROOT.parent / "log" / "fast_log_1765495955.bin")
    results = run_sim_to_real_analysis(
        SIM_LOG_FILE,
        REAL_LOG_FILE,
        config=TrajectoryGapConfig(use_relative_deltas=False, trajectory_norm=0.2),
        do_visualize=True,
    )
    print(results)

