"""
Interactive trajectory comparison visualization for sim-to-real gap analysis.

This script loads sample data from sample_data.pkl, finds specific configurations,
and creates an interactive visualization with a slider to manually control
the progression through time-aligned trajectories.
"""

import pickle
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT.parents[3]))

from gap_analyzer_v2 import _align_and_interpolate, WAYPOINTS
import gap_analyzer_v2 as ga_v2


def load_sample_data(checkpoint_dir: str = None, log_file_path: str = "sample_data.pkl"):
    """Load all collected sample data from pickle file."""
    if checkpoint_dir is None:
        checkpoint_dir = os.path.join(ROOT, "checkpoints")
    
    data_file = os.path.join(checkpoint_dir, log_file_path)
    if os.path.exists(data_file):
        try:
            with open(data_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Failed to load sample data: {e}")
            return []
    else:
        print(f"File not found: {data_file}")
        return []


def find_sample_by_params(all_samples, forwardSpeed, turnSpeed, waypointThreshold, tolerance=1e-6):
    """Find a sample entry by parameter values with tolerance."""
    for sample in all_samples:
        params = sample.get('params', {})
        if (abs(params.get('forwardSpeed', 0) - forwardSpeed) < tolerance and
            abs(params.get('turnSpeed', 0) - turnSpeed) < tolerance and
            abs(params.get('waypointThreshold', 0) - waypointThreshold) < tolerance):
            return sample
    return None


def visualize_interactive_trajectory_comparison(
    df_sim,
    df_real,
    title="Sim vs Real Trajectory Comparison",
    sample_label=""
):
    """
    Create an interactive visualization with a slider to control trajectory progression.
    
    Uses the same interpolation method as gap_analyzer_v2 to align trajectories.
    """
    if df_sim is None or df_real is None:
        print(f"Error: Missing data for {sample_label}")
        return
    
    if len(df_sim) < 2 or len(df_real) < 2:
        print(f"Error: Not enough points to visualize {sample_label}")
        return
    
    # Align and interpolate using the same method as gap_analyzer_v2
    t_ref, x_ref, y_ref, other_xy = _align_and_interpolate(df_sim, df_real)
    x_other, y_other = other_xy[:, 0], other_xy[:, 1]
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 10))
    plt.subplots_adjust(bottom=0.15)
    
    # Plot waypoints
    waypoint_x = [wp[0] for wp in WAYPOINTS]
    waypoint_y = [wp[1] for wp in WAYPOINTS]
    ax.scatter(waypoint_x, waypoint_y, c="green", marker="o", s=100, 
               label="Waypoints", zorder=6, edgecolors='black', linewidths=1)
    
    # Plot full trajectories (lightly)
    ax.plot(x_ref, y_ref, 'b-', alpha=0.2, linewidth=1, label='Sim (full)', zorder=1)
    ax.plot(x_other, y_other, 'r-', alpha=0.2, linewidth=1, label='Real (full, interpolated)', zorder=1)
    
    # Initialize plots for animated parts (up to current time)
    sim_line, = ax.plot([], [], 'b-', linewidth=2.5, label='Sim (current)', zorder=3)
    real_line, = ax.plot([], [], 'r-', linewidth=2.5, label='Real (current, interpolated)', zorder=3)
    
    # Current position markers
    sim_marker, = ax.plot([], [], 'bo', markersize=12, zorder=5, label='Sim (now)')
    real_marker, = ax.plot([], [], 'ro', markersize=12, zorder=5, label='Real (now)')
    
    # Connection line between sim and real at current time
    connection_line, = ax.plot([], [], 'k--', linewidth=1, alpha=0.5, zorder=4, label='Gap')
    
    ax.set_xlabel('X (m)', fontsize=12)
    ax.set_ylabel('Y (m)', fontsize=12)
    ax.set_title(f'{title}\n{sample_label}', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.axis('equal')
    
    # Add text annotation for current time
    time_text = ax.text(0.02, 0.98, '', transform=ax.transAxes, 
                       fontsize=11, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Add gap distance text
    gap_text = ax.text(0.02, 0.92, '', transform=ax.transAxes,
                      fontsize=11, verticalalignment='top',
                      bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    def update_plot(time_index):
        """Update the plot based on the current time index."""
        if time_index < 0:
            time_index = 0
        if time_index >= len(t_ref):
            time_index = len(t_ref) - 1
        
        idx = int(time_index)
        
        # Update trajectory lines up to current time
        sim_line.set_data(x_ref[:idx+1], y_ref[:idx+1])
        real_line.set_data(x_other[:idx+1], y_other[:idx+1])
        
        # Update current position markers
        if idx < len(x_ref):
            sim_marker.set_data([x_ref[idx]], [y_ref[idx]])
            real_marker.set_data([x_other[idx]], [y_other[idx]])
            
            # Update connection line
            connection_line.set_data([x_ref[idx], x_other[idx]], 
                                    [y_ref[idx], y_other[idx]])
            
            # Calculate gap distance
            gap_dist = np.sqrt((x_ref[idx] - x_other[idx])**2 + (y_ref[idx] - y_other[idx])**2)
            
            # Update text annotations
            current_time = t_ref[idx]
            time_text.set_text(f'Time: {current_time:.2f} s\nIndex: {idx}/{len(t_ref)-1}')
            gap_text.set_text(f'Gap: {gap_dist:.4f} m')
        
        fig.canvas.draw_idle()
    
    # Create slider
    ax_slider = plt.axes([0.15, 0.02, 0.7, 0.03])
    slider = Slider(ax_slider, 'Time', 0, len(t_ref)-1, valinit=0, valfmt='%d')
    
    def update_slider(val):
        update_plot(val)
    
    slider.on_changed(update_slider)
    
    # Initialize plot
    update_plot(0)
    
    # Set axis limits with some padding
    all_x = np.concatenate([x_ref, x_other, waypoint_x])
    all_y = np.concatenate([y_ref, y_other, waypoint_y])
    x_margin = (all_x.max() - all_x.min()) * 0.1
    y_margin = (all_y.max() - all_y.min()) * 0.1
    ax.set_xlim(all_x.min() - x_margin, all_x.max() + x_margin)
    ax.set_ylim(all_y.min() - y_margin, all_y.max() + y_margin)
    
    plt.tight_layout()
    plt.show()
    
    return fig


def main():
    """Main function to load data and create visualizations."""
    checkpoint_dir = os.path.join(ROOT, "checkpoints")
    
    # Load all samples
    print("Loading sample data...")
    all_samples = load_sample_data(checkpoint_dir)
    
    if not all_samples:
        print("No sample data found!")
        return
    
    print(f"Loaded {len(all_samples)} samples")
    
    # Check data structure
    if len(all_samples) > 0:
        sample = all_samples[0]
        print(f"\nSample structure keys: {list(sample.keys())}")
        if 'params' in sample:
            print(f"Sample 0 params: {sample['params']}")
        if 'df_sim' in sample:
            print(f"Sample 0 has df_sim: {sample['df_sim'] is not None}")
        if 'df_real' in sample:
            print(f"Sample 0 has df_real: {sample['df_real'] is not None}")
        if 'gap_metrics' in sample:
            print(f"Sample 0 has gap_metrics: {sample['gap_metrics'] is not None}")
            if sample['gap_metrics']:
                print(f"Sample 0 combined_error: {sample['gap_metrics'].get('combined_error', 'N/A')}")
    
    # Target parameter values (user specified)
    # High Sim To Real Gap (Row 8):
    params_high = {
        'forwardSpeed': 67.27,
        'turnSpeed': 33.53,
        'waypointThreshold': 0.085
    }
    
    # Low Sim To Real Gap (Row 41):
    params_low = {
        'forwardSpeed': 35.944127,
        'turnSpeed': 25.614439,
        'waypointThreshold': 0.119377
    }
    
    print("\n" + "="*60)
    print("Searching for samples...")
    print("="*60)
    
    # Try to find by parameters first
    sample_high = find_sample_by_params(
        all_samples,
        params_high['forwardSpeed'],
        params_high['turnSpeed'],
        params_high['waypointThreshold'],
        tolerance=0.01  # More lenient tolerance
    )
    
    sample_low = find_sample_by_params(
        all_samples,
        params_low['forwardSpeed'],
        params_low['turnSpeed'],
        params_low['waypointThreshold'],
        tolerance=0.01
    )
    
    # If not found by parameters, try by index (Row 8 = index 7, Row 41 = index 40)
    if not sample_high and len(all_samples) > 7:
        print("\nTrying to find Row 8 by index (index 7)...")
        sample_high = all_samples[7]
        print(f"  Found sample at index 7: {sample_high.get('params', {})}")
    
    if not sample_low and len(all_samples) > 40:
        print("\nTrying to find Row 41 by index (index 40)...")
        sample_low = all_samples[40]
        print(f"  Found sample at index 40: {sample_low.get('params', {})}")
    
    # Also check if user meant sample_num instead of row
    if not sample_high:
        for s in all_samples:
            if s.get('sample_num') == 8:
                sample_high = s
                print(f"\nFound sample_num=8: {s.get('params', {})}")
                break
    
    if not sample_low:
        for s in all_samples:
            if s.get('sample_num') == 41:
                sample_low = s
                print(f"\nFound sample_num=41: {s.get('params', {})}")
                break
    
    if sample_high:
        print(f"\n✓ Found HIGH gap sample")
        print(f"  Sample number: {sample_high.get('sample_num', 'N/A')}")
        print(f"  Params: {sample_high.get('params', {})}")
        if sample_high.get('gap_metrics'):
            print(f"  Combined error: {sample_high['gap_metrics'].get('combined_error', 'N/A')}")
    else:
        print("\n✗ HIGH gap sample (Row 8) NOT FOUND")
        print(f"  Looking for: {params_high}")
        print(f"  Available samples: {len(all_samples)}")
    
    if sample_low:
        print(f"\n✓ Found LOW gap sample")
        print(f"  Sample number: {sample_low.get('sample_num', 'N/A')}")
        print(f"  Params: {sample_low.get('params', {})}")
        if sample_low.get('gap_metrics'):
            print(f"  Combined error: {sample_low['gap_metrics'].get('combined_error', 'N/A')}")
    else:
        print("\n✗ LOW gap sample (Row 41) NOT FOUND")
        print(f"  Looking for: {params_low}")
        print(f"  Available samples: {len(all_samples)}")
    
    # Create visualizations
    print("\n" + "="*60)
    print("Creating visualizations...")
    print("="*60)
    
    if sample_high and sample_high.get('df_sim') is not None and sample_high.get('df_real') is not None:
        print("\nCreating visualization for HIGH gap sample...")
        params = sample_high.get('params', {})
        fs = params.get('forwardSpeed', 0)
        ts = params.get('turnSpeed', 0)
        wt = params.get('waypointThreshold', 0)
        label = f"High Gap Sample - forwardSpeed={fs:.4f}, turnSpeed={ts:.4f}, waypointThreshold={wt:.4f}"
        if sample_high.get('gap_metrics'):
            ce = sample_high['gap_metrics'].get('combined_error', 0)
            label += f"\nCombined Error: {ce:.4f}"
        visualize_interactive_trajectory_comparison(
            sample_high['df_sim'],
            sample_high['df_real'],
            title="High Sim-To-Real Gap Comparison",
            sample_label=label
        )
    else:
        print("\n✗ Cannot visualize HIGH gap sample: missing data")
    
    if sample_low and sample_low.get('df_sim') is not None and sample_low.get('df_real') is not None:
        print("\nCreating visualization for LOW gap sample...")
        params = sample_low.get('params', {})
        fs = params.get('forwardSpeed', 0)
        ts = params.get('turnSpeed', 0)
        wt = params.get('waypointThreshold', 0)
        label = f"Low Gap Sample - forwardSpeed={fs:.4f}, turnSpeed={ts:.4f}, waypointThreshold={wt:.4f}"
        if sample_low.get('gap_metrics'):
            ce = sample_low['gap_metrics'].get('combined_error', 0)
            label += f"\nCombined Error: {ce:.4f}"
        visualize_interactive_trajectory_comparison(
            sample_low['df_sim'],
            sample_low['df_real'],
            title="Low Sim-To-Real Gap Comparison",
            sample_label=label
        )
    else:
        print("\n✗ Cannot visualize LOW gap sample: missing data")


if __name__ == "__main__":
    main()

