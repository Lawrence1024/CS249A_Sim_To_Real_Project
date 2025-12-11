import pandas as pd
import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize
from typing import List, Tuple, Dict, Any
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import sys
import os
import logging
from logger import boundary_check

# Configuration
WAYPOINTS = [
    (-0.32,-0.46), (-0.32,0.36), (-1.02,0.36), (-1.02,-0.46)
]
BUFFER_RADIUS = 0.05 

log = logging.getLogger(__name__)

def segment_laps_and_track_hits(df_log: pd.DataFrame, use_initial_zero_span: bool = False) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Segment a lap from the log.

    Modes:
      - use_initial_zero_span=False (default): lap is from first 0->1 switch up to
        the second 0->1 switch (existing behavior).
      - use_initial_zero_span=True: lap is from the very first row to the last row
        whose target_id is 0 before it updates to 1 for the first time.
    
    Returns: (DataFrame of the lap, List of hit records for the lap)
    """

    if use_initial_zero_span:
        # We want from the very first point to the last 0 before target_id switches back to 1.
        # Find the first index where target_id == 1 AND previous target_id == 0 (the reappearance of 1).
        zero_to_one_idx_list = df_log[(df_log["target_id"] == 1) & (df_log["target_id"].shift(1) == 0)].index.tolist()

        if len(zero_to_one_idx_list) == 0:
            # print("Warning: No 0->1 transition found. Cannot segment initial zero span.")
            return pd.DataFrame(), []

        switch_idx = zero_to_one_idx_list[0]  # first time 0->1 happens
        end_index = switch_idx - 1  # last 0 before 1 reappears

        if end_index < df_log.index.min():
            # print("Warning: Invalid 0->1 transition indices. Cannot segment initial zero span.")
            return pd.DataFrame(), []

        start_index = df_log.index.min()
        first_lap_df = df_log.loc[start_index:end_index].copy()

        lap_hits = [{
            'timestamp': first_lap_df.iloc[0]['timestamp'],
            'waypoint_index': 0,
            'data_index': first_lap_df.index[0]
        }, {
            'timestamp': first_lap_df.iloc[-1]['timestamp'],
            'waypoint_index': 0,
            'data_index': first_lap_df.index[-1]
        }]
    else:
        # Target ID switch: Hitting WP0 causes target_id to change from the previous target (WP0, ID=0) to WP1 (ID=1).
        # Find all indices where target_id becomes 1 AND the previous target_id was 0 (or another value).
        
        hit_wp0_indices = df_log[
            (df_log['target_id'] == 1) & (df_log['target_id'].shift(1) == 0)
        ].index.tolist()

        if len(hit_wp0_indices) < 2:
            # print("Warning: Failed to find one 0 -> 1 target_id switch events. Cannot segment a full lap.")
            return pd.DataFrame(), []

        
        # End index of the lap: First time target_id switches to 1 (This row is the start of the next lap)
        start_index,end_index = hit_wp0_indices[0], hit_wp0_indices[1]

        # Extract the first lap DataFrame (inclusive of the start, exclusive of the end point)
        # The lap ends just before the row where the second 0->1 transition occurs.
        first_lap_df = df_log.loc[start_index:end_index].iloc[:-1].copy()
    
    # --- Simplified Hit Records (for Lap Time) ---
    lap_hits = []
    
    lap_target_ids = first_lap_df['target_id'].values
    lap_timestamps = first_lap_df['timestamp'].values
    lap_indices = first_lap_df.index.values

    # Record the start of the lap
    lap_hits.append({
        'timestamp': lap_timestamps[0],
        'waypoint_index': 0, # Corresponds to hitting WP0
        'data_index': lap_indices[0]
    })

    # Find subsequent target ID changes (only in default mode where switches exist)
    if not use_initial_zero_span:
        for i in range(1, len(lap_target_ids)):
            current_id = lap_target_ids[i]
            prev_id = lap_target_ids[i-1]
            
            if current_id != prev_id:
                lap_hits.append({
                    'timestamp': lap_timestamps[i],
                    'waypoint_index': prev_id, 
                    'data_index': lap_indices[i]
                })

    # Record the end of the lap
    lap_hits.append({
        'timestamp': lap_timestamps[-1],
        'waypoint_index': lap_target_ids[-1] if len(lap_target_ids) else 0,
        'data_index': lap_indices[-1]
    })

    return first_lap_df, lap_hits

def calculate_lap_times(first_lap_hits: List[Dict]) -> Tuple[float, Dict[str, float]]:
    """
    Calculates the total lap time and individual segment times (time between waypoints).
    Uses the timestamp of the target_id switch.
    """
    if len(first_lap_hits) < 2:
        return 0.0, {}
        
    # Total Lap Time: Time difference between the first and last recorded hit (WP0 to next WP0)
    # The last hit records the moment target_id switched back to 1.
    total_lap_time = first_lap_hits[-1]['timestamp'] - first_lap_hits[0]['timestamp']
    
    segment_times = {}
    
    # Calculate time for each segment
    for i in range(len(first_lap_hits) - 1):
        start_hit = first_lap_hits[i]
        end_hit = first_lap_hits[i+1]
        
        # Waypoint Index Logic: WP hit is the ID *before* the target_id switch
        if i == 0:
             # First segment: from start (target_id=1) to target_id=2 switch (hit WP1)
             start_wp_id = 0 
             end_wp_id = 1
        elif i == len(first_lap_hits) - 2:
             # Last segment: from last WP hit (target_id=final ID) to end (target_id=1 switch)
             start_wp_id = len(WAYPOINTS) - 1
             end_wp_id = 0
        else:
             # Middle segments: target_id switching from X to X+1 means WP X was hit
             # The index here represents the ID *being targeted* after the previous switch
             start_wp_id = end_hit['waypoint_index'] - 1 if end_hit['waypoint_index'] > 1 else 0
             end_wp_id = end_hit['waypoint_index']
        
        segment_id = f"WP{start_wp_id}->WP{end_wp_id}"
        segment_time = end_hit['timestamp'] - start_hit['timestamp']
        segment_times[segment_id] = segment_time
        
    return total_lap_time, segment_times


def calculate_buffered_area_gap(lap_df: pd.DataFrame, comparison_polygon: Polygon = None, waypoints=WAYPOINTS) -> Tuple[float, float, Polygon]:
    """
    Calculates the area enclosed by the trajectory (as a Polygon) and compares it
    with a reference Polygon (e.g., the Sim trajectory).
    """
    trajectory_points = lap_df[['x', 'y']].values
    
    if len(trajectory_points) < 3:
        return 0.0, 0.0, None

    # Build polygon from trajectory path (enclosed area). If invalid/degenerate, use convex hull.
    current_polygon = Polygon(trajectory_points)
    if (not current_polygon.is_valid) or current_polygon.area == 0:
        # Try to fix self-intersections while preserving concavities
        fixed = current_polygon.buffer(0)
        if fixed.is_valid and fixed.area > 0:
            current_polygon = fixed
        else:
            # Fallback: polygonize the linestring to capture concave parts if possible
            ls = LineString(trajectory_points)
            polys = list(polygonize(ls))
            if polys:
                current_polygon = max(polys, key=lambda p: p.area)
            else:
                current_polygon = current_polygon.convex_hull
    
    if comparison_polygon is None:
        return 0.0, 0.0, current_polygon

    # Compare with the reference Polygon
    union = current_polygon.union(comparison_polygon)
    intersection = current_polygon.intersection(comparison_polygon)

    area_union = union.area
    area_intersection = intersection.area
    
    # Non-Common Area (Symmetric Difference)
    area_diff = area_union - area_intersection
    waypoint_polygon_area = Polygon(waypoints).area if waypoints else 0.0
    if waypoint_polygon_area > 0:
        sqrt_ratio_diff = max(0.0, min(1.0, np.sqrt(area_diff / waypoint_polygon_area)))
    else:
        sqrt_ratio_diff = max(0.0, min(1.0, np.sqrt(area_diff / area_union)))
    # Difference Ratio (Numerical Metric 1)
    return sqrt_ratio_diff, area_diff, current_polygon


def boundary_violation_exists(lap_df: pd.DataFrame, waypoints=WAYPOINTS, limit_dist: float = 0.3) -> bool:
    """Return True if any point in the lap trajectory violates the boundary."""
    for _, row in lap_df.iterrows():
        if boundary_check.check_square_boundary_violation(
            (row["x"], row["y"]), waypoints, limit_dist=limit_dist
        ):
            return True
    return False


def compute_gap_objectives(
    lap_df_sim: pd.DataFrame,
    lap_df_real: pd.DataFrame,
    sqrt_ratio_diff: float,
    area_diff: float,
    total_time_sim: float,
    total_time_real: float,
    waypoints=WAYPOINTS,
    boundary_limit_dist: float = 0.3,
) -> Dict[str, float]:
    """
    Compute normalized objectives for sim-to-real gap:
      - boundary_gap: 1 if exactly one run violates the boundary, else 0.
      - normalized_area_gap: non-overlap area normalized by waypoint polygon area (fallback to ratio_diff).
      - normalized_time_gap: (real - sim) / sim, clamped to [0,1].
    Also returns raw ratios for transparency.
    """
    # Boundary objective
    violation_sim = boundary_violation_exists(lap_df_sim, waypoints=waypoints, limit_dist=boundary_limit_dist)
    violation_real = boundary_violation_exists(lap_df_real, waypoints=waypoints, limit_dist=boundary_limit_dist)
    boundary_gap = 1.0 if (violation_sim != violation_real) else 0.0

    # Area objective normalized by waypoint polygon area
    normalized_area_gap = sqrt_ratio_diff

    # Time objective normalized
    raw_time_gap_ratio = (total_time_real - total_time_sim) / total_time_sim if total_time_sim else 0.0
    normalized_time_gap = max(0.0, min(1.0, raw_time_gap_ratio))

    lap_time_gap_pct = raw_time_gap_ratio * 100.0

    return {
        "boundary_gap": boundary_gap,
        "boundary_violation_sim": violation_sim,
        "boundary_violation_real": violation_real,
        "normalized_area_gap": normalized_area_gap,
        "normalized_time_gap": normalized_time_gap,
        "time_gap_ratio": raw_time_gap_ratio,
        "lap_time_gap_pct": lap_time_gap_pct,
    }

def get_num_waypoints_hit(df: pd.DataFrame, num_waypoints: int = 4) -> int:
    """Calculate the number of waypoints hit based on target_id transitions."""
    if df.empty:
        return 0
    
    # Check if target 0 is sought after at least twice
    changes = df['target_id'].ne(df['target_id'].shift()).cumsum()
    unique_sequence = df.groupby(changes)['target_id'].first()
    zero_blocks = (unique_sequence == 0).sum()
    
    if zero_blocks >= 2:
        return num_waypoints
    else:
        # Return the last target_id if a full lap wasn't completed
        return int(df.iloc[-1]['target_id'])

def compute_sim_real_gap(df_sim: pd.DataFrame, df_real: pd.DataFrame, waypoints=WAYPOINTS) -> Dict[str, Any]:
    """
    Compute comprehensive sim-to-real gap metrics from dataframes.
    Handles both partial and full lap scenarios.
    """
    # 1. Calculate Waypoints Hit (Partial Lap Logic)
    num_hits_sim = get_num_waypoints_hit(df_sim, len(waypoints))
    num_hits_real = get_num_waypoints_hit(df_real, len(waypoints))
    waypoints_diff = abs(num_hits_sim - num_hits_real)

    # 2. Check for Partial Lap (if hits < total waypoints)
    if num_hits_sim < len(waypoints) or num_hits_real < len(waypoints):
        # Compute simplified metric for partial laps
        
        # Use whatever data we have for boundary check
        lap_df_sim, _ = segment_laps_and_track_hits(df_sim)
        if lap_df_sim.empty: lap_df_sim = df_sim
        
        lap_df_real, _ = segment_laps_and_track_hits(df_real)
        if lap_df_real.empty: lap_df_real = df_real

        violation_sim = boundary_violation_exists(lap_df_sim, waypoints=waypoints)
        violation_real = boundary_violation_exists(lap_df_real, waypoints=waypoints)
        boundary_gap = 1.0 if (violation_sim != violation_real) else 0.0

        # Weighted sum: 0.6 * diff + 0.4 * boundary
        combined_error = min(1.0, 0.6 * waypoints_diff + 0.4 * boundary_gap)

        return {
            "combined_error": combined_error,
            "boundary_gap": boundary_gap,
            "waypoints_diff": waypoints_diff,
            "waypoints_hit_sim": num_hits_sim,
            "waypoints_hit_real": num_hits_real,
            "boundary_violation_sim": violation_sim,
            "boundary_violation_real": violation_real,
            "lap_time_sim": 0.0,
            "lap_time_real": 0.0,
            "lap_time_gap_pct": 0.0,
            "area_diff": 0.0,
            "ratio_diff": 0.0,
            "normalized_area_gap": 0.0,
            "normalized_time_gap": 0.0,
            "time_gap_ratio": 0.0,
        }

    # 3. Full Lap Logic
    lap_df_sim, hits_sim = segment_laps_and_track_hits(df_sim)
    lap_df_real, hits_real = segment_laps_and_track_hits(df_real)

    if lap_df_sim.empty or lap_df_real.empty:
        # Should be caught by partial logic, but safety fallback
        return {"combined_error": 1.0, "error": "Unable to segment lap despite waypoint counts"}

    total_time_sim, _ = calculate_lap_times(hits_sim)
    total_time_real, _ = calculate_lap_times(hits_real)

    if total_time_sim == 0 or total_time_real == 0:
        return {"combined_error": 1.0, "error": "Zero lap time"}

    _, _, polygon_sim = calculate_buffered_area_gap(lap_df_sim)
    sqrt_ratio_diff, area_diff, polygon_real = calculate_buffered_area_gap(
        lap_df_real, comparison_polygon=polygon_sim
    )

    objectives = compute_gap_objectives(
        lap_df_sim,
        lap_df_real,
        sqrt_ratio_diff,
        area_diff,
        total_time_sim,
        total_time_real,
        waypoints=waypoints,
    )

    combined_error = min(
        1.0,
        0.4 * objectives["boundary_gap"]
        + 0.35 * objectives["normalized_area_gap"]
        + 0.25 * objectives["normalized_time_gap"],
    )

    return {
        "combined_error": combined_error,
        "boundary_gap": objectives["boundary_gap"],
        "waypoints_diff": waypoints_diff,
        "waypoints_hit_sim": num_hits_sim,
        "waypoints_hit_real": num_hits_real,
        "boundary_violation_sim": objectives["boundary_violation_sim"],
        "boundary_violation_real": objectives["boundary_violation_real"],
        "lap_time_sim": total_time_sim,
        "lap_time_real": total_time_real,
        "lap_time_gap_pct": objectives["lap_time_gap_pct"],
        "area_diff": area_diff,
        "ratio_diff": sqrt_ratio_diff,
        "normalized_area_gap": objectives["normalized_area_gap"],
        "normalized_time_gap": objectives["normalized_time_gap"],
        "time_gap_ratio": objectives["time_gap_ratio"],
    }

def visualize_comparison(lap_df_sim: pd.DataFrame, lap_df_real: pd.DataFrame, polygon_sim: Polygon, polygon_real: Polygon):
    """
    Visualizes the Sim and Real trajectories, including their buffered areas.
    """
    plt.figure(figsize=(12, 8))
    
    # 1. Plot trajectories (center line)
    plt.plot(lap_df_sim['x'], lap_df_sim['y'], 'b-', linewidth=1.5, label='Sim Trajectory (Center Line)', alpha=0.8)
    plt.plot(lap_df_real['x'], lap_df_real['y'], 'r-', linewidth=1.5, label='Real Trajectory (Center Line)', alpha=0.8)
    
    # 2. Plot Waypoints
    wp_x = [wp[0] for wp in WAYPOINTS]
    wp_y = [wp[1] for wp in WAYPOINTS]
    plt.plot(wp_x, wp_y, 'go', markersize=7, label='Waypoints')

    # 3. Plot Buffered Polygons (filled area)
    # Sim unique area (Sim - Real)
    sim_diff = polygon_sim.difference(polygon_real)
    if sim_diff.geom_type == 'Polygon':
        coords = np.array(sim_diff.exterior.coords)
        plt.fill(coords[:, 0], coords[:, 1], 'b', alpha=0.2, label='Sim Unique Area')
    
    # Real unique area (Real - Sim)
    real_diff = polygon_real.difference(polygon_sim)
    if real_diff.geom_type == 'Polygon':
        coords = np.array(real_diff.exterior.coords)
        plt.fill(coords[:, 0], coords[:, 1], 'r', alpha=0.2, label='Real Unique Area')

    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.title(f'Sim-to-Real Trajectory Comparison (Buffer R={BUFFER_RADIUS} units)')
    plt.legend()
    plt.axis('equal')
    plt.grid(True)
    plt.show()


# -------------------------------------------------------------
# SIMULATED DATA FOR TESTING (Replace your actual file reading)
# -------------------------------------------------------------
def create_simulated_data(is_real=False):
    """Creates a sample DataFrame mimicking a full lap and more."""
    data = []
    timestamp = 0.0
    num_wp = len(WAYPOINTS)
    
    # Create the path points (Example: a square loop with 4 WP)
    path_points = [
        (0.0, 0.0), (0.2, 0.0), (0.4, 0.0), (0.6, 0.0), (0.8, 0.0), (1.0, 0.0), # WP0 -> WP1
        (1.0, 0.2), (1.0, 0.4), (1.0, 0.6), (1.0, 0.8), (1.0, 1.0), # WP1 -> WP2
        (0.8, 1.0), (0.6, 1.0), (0.4, 1.0), (0.2, 1.0), (0.0, 1.0), # WP2 -> WP3
        (0.0, 0.8), (0.0, 0.6), (0.0, 0.4), (0.0, 0.2), (0.0, 0.0)  # WP3 -> WP0
    ]

    # Repeat the path for two laps
    target_id = 0
    for lap in range(3):
        for i, (x, y) in enumerate(path_points):
            # Simulate target_id change when hitting a WP
            if i % (len(path_points) // num_wp) == 0 and i > 0:
                target_id = (target_id % num_wp) + 1 # 1 -> 2 -> 3 -> 0 -> 1...
            
            # Add noise for "real" data
            noise_x, noise_y = (np.random.randn(2) * 0.01) if is_real else (0, 0)
            
            # Simulate a slightly different path/speed for real data
            if is_real and lap == 1:
                x += 0.05 
                y += 0.05
                timestamp += 0.02 # Real is slower

            data.append([
                timestamp, i, x + noise_x, y + noise_y, 0, 0, 0, 0, 0, target_id
            ])
            timestamp += 0.01 # Simulate time progression

    df = pd.DataFrame(data, columns=['timestamp', 'step_count', 'x', 'y', 'z', 'heading', 'targetHeading', 'effectiveHHeading', 'angle', 'target_id'])
    
    # Correct target_id: Target_id=0 for the last few points aiming for WP0 
    # and Target_id=1 for the first points aiming for WP1, etc.
    # The moment we hit WP_i, target_id switches to i+1 (or 1 if looping)
    
    # Since the log structure implies the controller *updates* target_id AFTER hitting the WP,
    # we need to simulate that transition: target_id 0 -> 1 when starting/hitting last WP
    target_id_list = [1, 2, 3, 0] * 3 # Simplified target ID sequence based on path points length
    target_id_per_segment = len(path_points) // num_wp
    
    # -------------------------------------------------------------
    # 修复后的 target_id 修正部分 (基于目标 ID: 0, 1, 2, 3)
    # -------------------------------------------------------------
    
    total_path_points = len(path_points)
    num_wp = len(WAYPOINTS) # 4
    segment_points_count = total_path_points // num_wp # 20 // 4 = 5 points per segment

    final_ids = []
    for lap in range(3):
        # Target ID Sequence: 1, 2, 3, 0 (Aiming for WP1, WP2, WP3, WP0)
        target_sequence = [1, 2, 3, 0]
        
        for target_id in target_sequence:
            final_ids.extend([target_id] * segment_points_count)
            
    # Use NumPy array, and fill/trim to match df length (robust calculation)
    final_ids_np = np.array(final_ids)
    
    if len(final_ids_np) < len(df):
         # If simulation generated fewer points than intended, pad with the last target ID (0)
         last_id = 0
         padding = np.full(len(df) - len(final_ids_np), last_id)
         final_ids_np = np.concatenate((final_ids_np, padding))
    
    df['target_id'] = final_ids_np[:len(df)]
    return df


def run_sim_to_real_analysis(sim_file: str, real_file: str, do_visualize: bool = False):
    """
    Main function to run the sim-to-real gap analysis.
    """
    print("--- 1. LOADING DATA ---")
    try:
        from log_decoder import LogDecoder
    except ImportError:
        print("Error: log_decoder.py not found. Ensure it is in the same directory.")
        return

    df_sim = LogDecoder.decode_df(sim_file)
    df_real = LogDecoder.decode_df(real_file)

    if df_sim is None or df_real is None:
        print("Analysis stopped due to file loading errors.")
        return

    # --- 2. COMPUTE METRICS ---
    print("\n--- 2. COMPUTING METRICS ---")
    metrics = compute_sim_real_gap(df_sim, df_real)
    
    if "error" in metrics:
        print(f"Error computing metrics: {metrics['error']}")
        return

    print(f"\n[METRICS]")
    print(f"Combined Error: {metrics['combined_error']:.4f}")
    if metrics["lap_time_sim"] > 0:
        print(f"Lap Time Gap: {metrics['lap_time_gap_pct']:.2f}%")
        print(f"Area Ratio Diff: {metrics['ratio_diff']:.4f}")
    else:
        print(f"Waypoints Hit: Sim={metrics['waypoints_hit_sim']}, Real={metrics['waypoints_hit_real']}")
        print(f"Partial Lap Detected - Metrics based on waypoint diff and boundary violation.")

    # --- 3. VISUALIZATION ---
    if do_visualize and metrics["lap_time_sim"] > 0:
        print("\n--- 3. VISUALIZATION ---")
        # Re-compute polygons for visualization (since we abstracted them away)
        lap_df_sim, _ = segment_laps_and_track_hits(df_sim)
        lap_df_real, _ = segment_laps_and_track_hits(df_real)
        _, _, polygon_sim = calculate_buffered_area_gap(lap_df_sim)
        _, _, polygon_real = calculate_buffered_area_gap(lap_df_real, comparison_polygon=polygon_sim)
        visualize_comparison(lap_df_sim, lap_df_real, polygon_sim, polygon_real)

if __name__ == "__main__":
    # ⚠️ USE MOCK FILES FOR DEMONSTRATION 
    SIM_LOG_FILE = './examples/webots/robotics/log/fast_log_1765330653.bin'  
    REAL_LOG_FILE = './examples/webots/robotics/log/fast_log_1765330805.bin' 
    
    # Run the analysis and visualize the results
    run_sim_to_real_analysis(SIM_LOG_FILE, REAL_LOG_FILE, do_visualize=True)
