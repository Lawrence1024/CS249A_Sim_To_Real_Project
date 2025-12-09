import pandas as pd
import numpy as np
from shapely.geometry import LineString, Polygon
from typing import List, Tuple, Dict
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
import sys
import os


# --- CONFIGURATION ---
# ⚠️ USER CONFIGURATION REQUIRED: DEFINE YOUR WAYPOINTS AND CAR SIZE
# Note: Waypoints are now only used for context/visualization, not for segmentation.
WAYPOINTS = [
    (0.0, 0.0), # WP0 (Start/End)
    (1.0, 0.0), # WP1
    (1.0, 1.0), # WP2
    (0.0, 1.0)  # WP3
]
# Trajectory Buffer Radius (R = Car Width / 2). Used for Polygon Comparison.
BUFFER_RADIUS = 0.05 

# --- CORE FUNCTIONS ---

def segment_laps_and_track_hits(df_log: pd.DataFrame) -> Tuple[pd.DataFrame, List[Dict]]:
    """
    Optimized: Segments the data using the 'target_id' column based on the 0 -> 1 switch.
    The lap is defined from the moment target_id first changes 0 -> 1, up until 
    the moment target_id changes 0 -> 1 for the second time.
    
    Returns: (DataFrame of the first lap, List of hit records for the first lap)
    """
    
    # Target ID switch: Hitting WP0 causes target_id to change from the previous target (WP0, ID=0) to WP1 (ID=1).
    # Find all indices where target_id becomes 1 AND the previous target_id was 0 (or another value).
    
    hit_wp0_indices = df_log[
        (df_log['target_id'] == 1) & (df_log['target_id'].shift(1) == 0)
    ].index.tolist()

    if len(hit_wp0_indices) < 2:
        print("Warning: Failed to find two 0 -> 1 target_id switch events. Cannot segment a full lap.")
        return pd.DataFrame(), []

    # Start index of the lap: First time target_id switches to 1
    start_index = hit_wp0_indices[0]
    
    # End index of the lap: Second time target_id switches to 1 (This row is the start of the next lap)
    end_index = hit_wp0_indices[1] 

    # Extract the first lap DataFrame (inclusive of the start, exclusive of the end point)
    # The lap ends just before the row where the second 0->1 transition occurs.
    first_lap_df = df_log.loc[start_index:end_index].iloc[:-1].copy()
    
    # --- Simplified Hit Records (for Lap Time) ---
    lap_hits = []
    
    lap_target_ids = first_lap_df['target_id'].values
    lap_timestamps = first_lap_df['timestamp'].values
    lap_indices = first_lap_df.index.values

    # Record the *start* of the lap (Hit WP0 -> Target 1 switch)
    lap_hits.append({
        'timestamp': lap_timestamps[0],
        'waypoint_index': 0, # Corresponds to hitting WP0
        'data_index': lap_indices[0]
    })

    # Find subsequent target ID changes (1 -> 2, 2 -> 3, 3 -> 0)
    for i in range(1, len(lap_target_ids)):
        current_id = lap_target_ids[i]
        prev_id = lap_target_ids[i-1]
        
        # Check for a switch to a new target
        if current_id != prev_id:
            # The switch happens at index i.
            # The waypoint hit is the ID *before* the switch (prev_id).
            lap_hits.append({
                'timestamp': lap_timestamps[i],
                'waypoint_index': prev_id, 
                'data_index': lap_indices[i]
            })

    # Record the end of the lap (Hit WP3 -> Target 0 switch)
    # The end time is the timestamp at the 'end_index' in the original df (where the 0->1 switch happens)
    end_lap_timestamp = df_log.loc[end_index, 'timestamp']
    lap_hits.append({
        'timestamp': end_lap_timestamp,
        'waypoint_index': len(WAYPOINTS) - 1, # Corresponds to hitting the last WP (WP3)
        'data_index': end_index
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


def calculate_buffered_area_gap(lap_df: pd.DataFrame, comparison_polygon: Polygon = None) -> Tuple[float, float, Polygon]:
    """
    Calculates the buffered area (Polygon) of the trajectory and compares it 
    with a reference Polygon (e.g., the Sim trajectory).
    """
    trajectory_points = lap_df[['x', 'y']].values
    
    if len(trajectory_points) < 2:
        return 0.0, 0.0, None

    # 1. Generate the buffered Polygon for the current trajectory
    trajectory_line = LineString(trajectory_points)
    current_polygon = trajectory_line.buffer(BUFFER_RADIUS)
    
    if comparison_polygon is None:
        return 0.0, 0.0, current_polygon

    # 2. Compare with the reference Polygon
    union = current_polygon.union(comparison_polygon)
    intersection = current_polygon.intersection(comparison_polygon)

    area_union = union.area
    area_intersection = intersection.area
    
    # 3. Calculate Non-Common Area (Symmetric Difference)
    area_diff = area_union - area_intersection

    # 4. Calculate Difference Ratio (Numerical Metric 1)
    ratio_diff = area_diff / area_union if area_union > 0 else 0.0

    return ratio_diff, area_diff, current_polygon

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

    # --- 2. SEGMENTATION AND LAP TIME ANALYSIS ---
    print("\n--- 2. LAP SEGMENTATION & TIME ANALYSIS ---")
    
    # SIM ANALYSIS
    lap_df_sim, hits_sim = segment_laps_and_track_hits(df_sim)
    total_time_sim, segments_sim = calculate_lap_times(hits_sim)
    
    # REAL ANALYSIS
    lap_df_real, hits_real = segment_laps_and_track_hits(df_real)
    total_time_real, segments_real = calculate_lap_times(hits_real)

    if total_time_sim == 0 or total_time_real == 0:
        print("One or both logs failed to complete the first lap. Cannot calculate lap times.")
        return
    
    # Numerical Metric 2: Lap Time Comparison
    lap_time_gap = (total_time_real - total_time_sim) / total_time_sim * 100

    print(f"\n[TIME METRICS (Units: seconds)]")
    print(f"Sim Total Lap Time: {total_time_sim:.3f}s (WP0->...->WP0)")
    print(f"Real Total Lap Time: {total_time_real:.3f}s (WP0->...->WP0)")
    print(f"-> Numerical Metric 2 (Lap Time Gap): {lap_time_gap:.2f}% (Real relative to Sim)")
    
    # --- 3. POLYGON COMPARISON ANALYSIS ---
    print("\n--- 3. POLYGON COMPARISON ANALYSIS (Trajectory Shape) ---")

    # Step 1: Get Sim reference Polygon
    _, _, polygon_sim = calculate_buffered_area_gap(lap_df_sim)
    
    # Step 2: Compare Real trajectory against Sim Polygon
    ratio_diff, area_diff, polygon_real = calculate_buffered_area_gap(lap_df_real, comparison_polygon=polygon_sim)

    # Numerical Metric 1: Polygon Comparison Ratio
    print(f"Buffer Radius Used (R): {BUFFER_RADIUS:.3f}")
    print(f"Non-Common Area (Area_diff): {area_diff:.4f} sq. units")
    print(f"-> Numerical Metric 1 (Polygon Comparison Ratio): {ratio_diff*100:.2f}% (Non-overlapping path footprint)")

    # --- 4. VISUALIZATION ---
    if do_visualize:
        print("\n--- 4. VISUALIZATION ---")
        visualize_comparison(lap_df_sim, lap_df_real, polygon_sim, polygon_real)

"""up real, down sim"""

def run_sim_to_real_analysis(sim_file: str, real_file: str, do_visualize: bool = False):
    """
    Main function to run the sim-to-real gap analysis.
    
    NOTE: This version is modified to use the hardcoded/simulated data 
    (create_simulated_data) for testing purposes, bypassing file reading.
    """
    print("--- 1. LOADING DATA ---")

    # -------------------------------------------------------------
    # 🔥 FIX: BYPASSING FILE READING AND USING SIMULATED DATA DIRECTLY
    # -------------------------------------------------------------
    try:
        # Use the hardcoded functions defined below to generate test data
        df_sim = create_simulated_data(is_real=False) 
        df_real = create_simulated_data(is_real=True)  
        print("Successfully generated simulated data for Sim and Real.")

        # --- Original file reading code (now commented out) ---
        # try:
        #     from log_decoder import LogDecoder
        # except ImportError:
        #     print("Error: log_decoder.py not found. Ensure it is in the same directory.")
        #     return
        # df_sim = LogDecoder.decode_df(sim_file)
        # df_real = LogDecoder.decode_df(real_file)
        # -----------------------------------------------------

    except NameError:
        print("FATAL ERROR: The function 'create_simulated_data' is not defined in the accessible scope.")
        print("Please ensure you copied the entire 'SIMULATED DATA FOR TESTING' section from the previous response.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during data generation: {e}")
        return

    if df_sim is None or df_real is None:
        print("Analysis stopped because simulated data generation failed.")
        return

    # --- 2. SEGMENTATION AND LAP TIME ANALYSIS ---
    print("\n--- 2. LAP SEGMENTATION & TIME ANALYSIS ---")
    
    # SIM ANALYSIS
    lap_df_sim, hits_sim = segment_laps_and_track_hits(df_sim)
    total_time_sim, segments_sim = calculate_lap_times(hits_sim)
    
    # REAL ANALYSIS
    lap_df_real, hits_real = segment_laps_and_track_hits(df_real)
    total_time_real, segments_real = calculate_lap_times(hits_real)

    if total_time_sim == 0 or total_time_real == 0:
        print("One or both logs failed to complete the first lap. Cannot calculate lap times.")
        return
    
    # Numerical Metric 2: Lap Time Comparison
    lap_time_gap = (total_time_real - total_time_sim) / total_time_sim * 100

    print(f"\n[TIME METRICS (Units: seconds)]")
    print(f"Sim Total Lap Time: {total_time_sim:.3f}s (WP0->...->WP0)")
    print(f"Real Total Lap Time: {total_time_real:.3f}s (WP0->...->WP0)")
    print(f"-> Numerical Metric 2 (Lap Time Gap): {lap_time_gap:.2f}% (Real relative to Sim)")
    
    # --- 3. POLYGON COMPARISON ANALYSIS ---
    print("\n--- 3. POLYGON COMPARISON ANALYSIS (Trajectory Shape) ---")

    # Step 1: Get Sim reference Polygon
    _, _, polygon_sim = calculate_buffered_area_gap(lap_df_sim)
    
    # Step 2: Compare Real trajectory against Sim Polygon
    ratio_diff, area_diff, polygon_real = calculate_buffered_area_gap(lap_df_real, comparison_polygon=polygon_sim)

    # Numerical Metric 1: Polygon Comparison Ratio
    print(f"Buffer Radius Used (R): {BUFFER_RADIUS:.3f}")
    print(f"Non-Common Area (Area_diff): {area_diff:.4f} sq. units")
    print(f"-> Numerical Metric 1 (Polygon Comparison Ratio): {ratio_diff*100:.2f}% (Non-overlapping path footprint)")

    # --- 4. VISUALIZATION ---
    if do_visualize:
        print("\n--- 4. VISUALIZATION ---")
        visualize_comparison(lap_df_sim, lap_df_real, polygon_sim, polygon_real)


# Helper class to mock LogDecoder for testing
class MockLogDecoder:
    @staticmethod
    def decode_df(filename: str):
        if 'sim' in filename:
            return create_simulated_data(is_real=False)
        elif 'real' in filename:
            return create_simulated_data(is_real=True)
        return None



if __name__ == "__main__":
    # ⚠️ USE MOCK FILES FOR DEMONSTRATION 
    SIM_LOG_FILE = 'sim_log.bin'  
    REAL_LOG_FILE = 'real_log.bin' 
    
    # Run the analysis and visualize the results
    run_sim_to_real_analysis(SIM_LOG_FILE, REAL_LOG_FILE, do_visualize=True)