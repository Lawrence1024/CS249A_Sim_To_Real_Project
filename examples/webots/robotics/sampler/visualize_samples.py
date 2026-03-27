"""
Visualization script for sample_data.pkl

Creates a 3D scatter plot showing parameter combinations (forwardSpeed, turnSpeed, waypointThreshold)
color-coded by combined_error (sim-to-real gap).
"""

import pickle
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT.parents[3]))

# Import gap analyzer for computing metrics
import gap_analyzer_v2 as ga_v2
from gap_analyzer_v2 import TrajectoryGapConfig

def load_sample_data(checkpoint_dir: str = None, log_file_path: str = "sample_data.pkl"):
    """
    Load all collected sample data from pickle file.
    """
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


def visualize_samples_3d(
    checkpoint_dir: str = None,
    log_file_path: str = "sample_data.pkl",
    gap_threshold: float = 0.5,
    colormap: str = "RdYlGn_r",  # Red-Yellow-Green reversed (red = high gap, green = low gap)
    figsize: tuple = (10, 8),  # Size for each individual figure
    save_path: str = None
):
    """
    Create 4 separate figures: a 3D scatter plot and 3 additional 2D projection plots of samples with color-coding based on combined_error.
    
    The visualization creates 4 separate figures:
    - Figure 1: 3D plot - forwardSpeed vs turnSpeed vs waypointThreshold
    - Figure 2: 2D plot - forwardSpeed vs waypointThreshold (tolerance)
    - Figure 3: 2D plot - turnSpeed vs waypointThreshold (tolerance)
    - Figure 4: 2D plot - forwardSpeed vs turnSpeed
    
    Args:
        checkpoint_dir: Directory containing the pickle file
        log_file_path: Name of the pickle file
        gap_threshold: Threshold for color coding (points above this are "high gap")
        colormap: Matplotlib colormap name
        figsize: Figure size (width, height) - applies to each individual figure
        save_path: Optional base path to save the figures (will append suffixes like '_3d.png', '_forward_vs_tolerance.png', etc.)
    """
    # Load data
    all_samples = load_sample_data(checkpoint_dir, log_file_path)
    
    if len(all_samples) == 0:
        print("No samples found in pickle file.")
        return
    
    # Extract data
    forward_speeds = []
    turn_speeds = []
    waypoint_thresholds = []
    combined_errors = []
    finished_laps = []
    sample_nums = []
    
    for sample in all_samples:
        params = sample.get('params', {})
        gap_metrics = sample.get('gap_metrics', {})
        
        # Get parameters
        fs = params.get('forwardSpeed')
        ts = params.get('turnSpeed')
        wt = params.get('waypointThreshold')
        
        # Get combined error and finished_lap
        if gap_metrics:
            error = gap_metrics.get('combined_error')
            finished_lap = gap_metrics.get('finished_lap', False)
        else:
            error = None
            finished_lap = False
        
        # Only include samples with all required data
        if fs is not None and ts is not None and wt is not None and error is not None:
            forward_speeds.append(fs)
            turn_speeds.append(ts)
            waypoint_thresholds.append(wt)
            combined_errors.append(error)
            finished_laps.append(finished_lap)
            sample_nums.append(sample.get('sample_num', 0))
    
    if len(forward_speeds) == 0:
        print("No samples with complete data found.")
        return
    
    # Convert to numpy arrays
    forward_speeds = np.array(forward_speeds)
    turn_speeds = np.array(turn_speeds)
    waypoint_thresholds = np.array(waypoint_thresholds)
    combined_errors = np.array(combined_errors)
    finished_laps = np.array(finished_laps)
    
    # Split data into finished_lap = True and False groups
    finished_mask = finished_laps == True
    not_finished_mask = ~finished_mask
    
    # Data for finished_lap = True (circles/spheres)
    fs_finished = forward_speeds[finished_mask]
    ts_finished = turn_speeds[finished_mask]
    wt_finished = waypoint_thresholds[finished_mask]
    errors_finished = combined_errors[finished_mask]
    
    # Data for finished_lap = False (squares/cubes)
    fs_not_finished = forward_speeds[not_finished_mask]
    ts_not_finished = turn_speeds[not_finished_mask]
    wt_not_finished = waypoint_thresholds[not_finished_mask]
    errors_not_finished = combined_errors[not_finished_mask]
    
    # Calculate threshold statistics if needed
    if gap_threshold:
        high_gap_count = np.sum(combined_errors >= gap_threshold)
        low_gap_count = np.sum(combined_errors < gap_threshold)
    
    # Figure 1: 3D plot
    fig1 = plt.figure(figsize=figsize)
    ax_3d = fig1.add_subplot(111, projection='3d')
    
    # Plot finished_lap = True points (circles/spheres)
    if len(fs_finished) > 0:
        scatter_3d_finished = ax_3d.scatter(
            fs_finished,
            ts_finished,
            wt_finished,
            c=errors_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='o',
            label='Finished Lap (True)'
        )
    
    # Plot finished_lap = False points (squares/cubes)
    if len(fs_not_finished) > 0:
        scatter_3d_not_finished = ax_3d.scatter(
            fs_not_finished,
            ts_not_finished,
            wt_not_finished,
            c=errors_not_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='s',
            label='Not Finished Lap (False)'
        )
    
    # Use one of the scatter plots for colorbar
    scatter_3d = scatter_3d_finished if len(fs_finished) > 0 else scatter_3d_not_finished
    
    ax_3d.set_xlabel('forwardSpeed', fontsize=12, fontweight='bold')
    ax_3d.set_ylabel('turnSpeed', fontsize=12, fontweight='bold')
    ax_3d.set_zlabel('waypointThreshold', fontsize=12, fontweight='bold')
    ax_3d.set_title(
        f'3D Parameter Space Visualization\n'
        f'{len(forward_speeds)} samples | Gap range: [{combined_errors.min():.3f}, {combined_errors.max():.3f}]',
        fontsize=14,
        fontweight='bold'
    )
    
    cbar1 = plt.colorbar(scatter_3d, ax=ax_3d, pad=0.1)
    cbar1.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    
    # Add legend - move to upper right to avoid overlap with threshold annotation
    # Customize legend handles to be hollow (no fill color)
    handles, labels = ax_3d.get_legend_handles_labels()
    if handles:
        # Create hollow markers for legend
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        ax_3d.legend(new_handles, labels, loc='upper right', fontsize=9, framealpha=0.9)
    else:
        ax_3d.legend(loc='upper right', fontsize=9, framealpha=0.9)
    
    if gap_threshold:
        # Move threshold annotation lower to avoid overlap with title and legend
        ax_3d.text2D(
            0.02, 0.85,
            f'Threshold: {gap_threshold:.2f}\n'
            f'High gap (≥{gap_threshold:.2f}): {high_gap_count}\n'
            f'Low gap (<{gap_threshold:.2f}): {low_gap_count}',
            transform=ax_3d.transAxes,
            fontsize=9,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7)
        )
    
    # Adjust layout to prevent overlap
    plt.tight_layout(rect=[0, 0, 0.95, 0.95])
    if save_path:
        save_name = save_path.replace('.png', '_3d.png') if save_path.endswith('.png') else save_path + '_3d.png'
        plt.savefig(save_name, dpi=300, bbox_inches='tight')
        print(f"3D plot saved to: {save_name}")
    plt.show()
    
    # Figure 2: forwardSpeed vs waypointThreshold (tolerance)
    fig2 = plt.figure(figsize=figsize)
    ax1 = fig2.add_subplot(111)
    
    # Plot finished_lap = True points (circles)
    if len(fs_finished) > 0:
        scatter1_finished = ax1.scatter(
            fs_finished,
            wt_finished,
            c=errors_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='o',
            label='Finished Lap (True)'
        )
    
    # Plot finished_lap = False points (squares)
    if len(fs_not_finished) > 0:
        scatter1_not_finished = ax1.scatter(
            fs_not_finished,
            wt_not_finished,
            c=errors_not_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='s',
            label='Not Finished Lap (False)'
        )
    
    scatter1 = scatter1_finished if len(fs_finished) > 0 else scatter1_not_finished
    # Customize legend handles to be hollow (no fill color)
    handles, labels = ax1.get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        ax1.legend(new_handles, labels, loc='best', fontsize=9)
    else:
        ax1.legend(loc='best', fontsize=9)
    ax1.set_xlabel('forwardSpeed', fontsize=12, fontweight='bold')
    ax1.set_ylabel('waypointThreshold (tolerance)', fontsize=12, fontweight='bold')
    ax1.set_title(
        f'forwardSpeed vs Tolerance\n'
        f'{len(forward_speeds)} samples | Gap range: [{combined_errors.min():.3f}, {combined_errors.max():.3f}]',
        fontsize=14,
        fontweight='bold'
    )
    ax1.grid(True, alpha=0.3)
    cbar2 = plt.colorbar(scatter1, ax=ax1, pad=0.1)
    cbar2.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    plt.tight_layout()
    if save_path:
        save_name = save_path.replace('.png', '_forward_vs_tolerance.png') if save_path.endswith('.png') else save_path + '_forward_vs_tolerance.png'
        plt.savefig(save_name, dpi=300, bbox_inches='tight')
        print(f"forwardSpeed vs Tolerance plot saved to: {save_name}")
    plt.show()
    
    # Figure 3: turnSpeed vs waypointThreshold (tolerance)
    fig3 = plt.figure(figsize=figsize)
    ax2 = fig3.add_subplot(111)
    
    # Plot finished_lap = True points (circles)
    if len(fs_finished) > 0:
        scatter2_finished = ax2.scatter(
            ts_finished,
            wt_finished,
            c=errors_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='o',
            label='Finished Lap (True)'
        )
    
    # Plot finished_lap = False points (squares)
    if len(fs_not_finished) > 0:
        scatter2_not_finished = ax2.scatter(
            ts_not_finished,
            wt_not_finished,
            c=errors_not_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='s',
            label='Not Finished Lap (False)'
        )
    
    scatter2 = scatter2_finished if len(fs_finished) > 0 else scatter2_not_finished
    # Customize legend handles to be hollow (no fill color)
    handles, labels = ax2.get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        ax2.legend(new_handles, labels, loc='best', fontsize=9)
    else:
        ax2.legend(loc='best', fontsize=9)
    ax2.set_xlabel('turnSpeed', fontsize=12, fontweight='bold')
    ax2.set_ylabel('waypointThreshold (tolerance)', fontsize=12, fontweight='bold')
    ax2.set_title(
        f'turnSpeed vs Tolerance\n'
        f'{len(forward_speeds)} samples | Gap range: [{combined_errors.min():.3f}, {combined_errors.max():.3f}]',
        fontsize=14,
        fontweight='bold'
    )
    ax2.grid(True, alpha=0.3)
    cbar3 = plt.colorbar(scatter2, ax=ax2, pad=0.1)
    cbar3.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    plt.tight_layout()
    if save_path:
        save_name = save_path.replace('.png', '_turn_vs_tolerance.png') if save_path.endswith('.png') else save_path + '_turn_vs_tolerance.png'
        plt.savefig(save_name, dpi=300, bbox_inches='tight')
        print(f"turnSpeed vs Tolerance plot saved to: {save_name}")
    plt.show()
    
    # Figure 4: forwardSpeed vs turnSpeed
    fig4 = plt.figure(figsize=figsize)
    ax3 = fig4.add_subplot(111)
    
    # Plot finished_lap = True points (circles)
    if len(fs_finished) > 0:
        scatter3_finished = ax3.scatter(
            fs_finished,
            ts_finished,
            c=errors_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='o',
            label='Finished Lap (True)'
        )
    
    # Plot finished_lap = False points (squares)
    if len(fs_not_finished) > 0:
        scatter3_not_finished = ax3.scatter(
            fs_not_finished,
            ts_not_finished,
            c=errors_not_finished,
            cmap=colormap,
            vmin=0,
            vmax=1,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5,
            marker='s',
            label='Not Finished Lap (False)'
        )
    
    scatter3 = scatter3_finished if len(fs_finished) > 0 else scatter3_not_finished
    # Customize legend handles to be hollow (no fill color)
    handles, labels = ax3.get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        ax3.legend(new_handles, labels, loc='best', fontsize=9)
    else:
        ax3.legend(loc='best', fontsize=9)
    ax3.set_xlabel('forwardSpeed', fontsize=12, fontweight='bold')
    ax3.set_ylabel('turnSpeed', fontsize=12, fontweight='bold')
    ax3.set_title(
        f'forwardSpeed vs turnSpeed\n'
        f'{len(forward_speeds)} samples | Gap range: [{combined_errors.min():.3f}, {combined_errors.max():.3f}]',
        fontsize=14,
        fontweight='bold'
    )
    ax3.grid(True, alpha=0.3)
    cbar4 = plt.colorbar(scatter3, ax=ax3, pad=0.1)
    cbar4.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    plt.tight_layout()
    if save_path:
        save_name = save_path.replace('.png', '_forward_vs_turn.png') if save_path.endswith('.png') else save_path + '_forward_vs_turn.png'
        plt.savefig(save_name, dpi=300, bbox_inches='tight')
        print(f"forwardSpeed vs turnSpeed plot saved to: {save_name}")
    plt.show()
    
    # Print summary statistics
    print(f"\n{'='*60}")
    print("Summary Statistics:")
    print(f"{'='*60}")
    print(f"Total samples visualized: {len(forward_speeds)}")
    print(f"\nParameter ranges:")
    print(f"  forwardSpeed: [{forward_speeds.min():.2f}, {forward_speeds.max():.2f}]")
    print(f"  turnSpeed: [{turn_speeds.min():.2f}, {turn_speeds.max():.2f}]")
    print(f"  waypointThreshold: [{waypoint_thresholds.min():.4f}, {waypoint_thresholds.max():.4f}]")
    print(f"\nCombined error statistics:")
    print(f"  Min: {combined_errors.min():.4f}")
    print(f"  Max: {combined_errors.max():.4f}")
    print(f"  Mean: {combined_errors.mean():.4f}")
    print(f"  Median: {np.median(combined_errors):.4f}")
    print(f"  Std: {combined_errors.std():.4f}")
    if gap_threshold:
        print(f"\nThreshold analysis (threshold = {gap_threshold:.2f}):")
        print(f"  High gap (≥{gap_threshold:.2f}): {high_gap_count} ({100*high_gap_count/len(combined_errors):.1f}%)")
        print(f"  Low gap (<{gap_threshold:.2f}): {low_gap_count} ({100*low_gap_count/len(combined_errors):.1f}%)")
    print(f"\nFinished lap statistics:")
    print(f"  Finished lap (True): {np.sum(finished_laps)} ({100*np.sum(finished_laps)/len(finished_laps):.1f}%)")
    print(f"  Not finished lap (False): {np.sum(~finished_laps)} ({100*np.sum(~finished_laps)/len(finished_laps):.1f}%)")


def visualize_separate_metrics_3d(
    checkpoint_dir: str = None,
    log_file_path: str = "sample_data.pkl",
    colormap: str = "RdYlGn_r",  # Red-Yellow-Green reversed (red = high gap, green = low gap)
    figsize: tuple = (16, 12),  # Larger figure for 4 subplots
    save_path: str = None,
    trajectory_norm: float = 0.2,  # Same as DEFAULT_TRAJECTORY_NORM in post_processing
    boundary_limit_dist: float = 0.25,
    recompute_metrics: bool = True,  # If True, recompute from raw data; if False, use gap_metrics if available
):
    """
    Create 4 synchronized 3D scatter plots showing separate metrics:
    1. Combined Error (already computed)
    2. Waypoint Gap (waypoints_diff, normalized)
    3. Boundary Gap (1 - boundary_match)
    4. Trajectory Gap (trajectory_gap, normalized)
    
    All 4 plots are synchronized - rotating one will rotate all others.
    
    Note: View synchronization works best when rotating slowly. The synchronization
    is triggered on mouse movement during rotation (left mouse button held down).
    
    Args:
        checkpoint_dir: Directory containing the pickle file
        log_file_path: Name of the pickle file
        colormap: Matplotlib colormap name
        figsize: Figure size (width, height)
        save_path: Optional path to save the figure
        trajectory_norm: Normalization factor for trajectory gap (default: 0.2)
        boundary_limit_dist: Boundary limit distance for violation checking
        recompute_metrics: If True, recompute metrics from df_sim/df_real; if False, use gap_metrics if available
    """
    # Load data
    all_samples = load_sample_data(checkpoint_dir, log_file_path)
    
    if len(all_samples) == 0:
        print("No samples found in pickle file.")
        return
    
    print(f"Loaded {len(all_samples)} samples")
    if recompute_metrics:
        print("Recomputing metrics from raw data (this may take a while)...")
    
    # Extract data and compute metrics
    forward_speeds = []
    turn_speeds = []
    waypoint_thresholds = []
    combined_errors = []
    waypoint_gaps = []
    boundary_gaps = []
    trajectory_gaps = []
    finished_laps = []
    sample_nums = []
    
    config = TrajectoryGapConfig(
        use_relative_deltas=False,
        trajectory_norm=trajectory_norm,
        boundary_limit_dist=boundary_limit_dist,
    )
    
    for idx, sample in enumerate(all_samples):
        params = sample.get('params', {})
        df_sim = sample.get('df_sim')
        df_real = sample.get('df_real')
        gap_metrics = sample.get('gap_metrics', {})
        
        # Get parameters
        fs = params.get('forwardSpeed')
        ts = params.get('turnSpeed')
        wt = params.get('waypointThreshold')
        
        if fs is None or ts is None or wt is None:
            continue
        
        # Compute or retrieve metrics
        if recompute_metrics and df_sim is not None and df_real is not None:
            try:
                raw_metrics = ga_v2.compute_sim_real_gap_v2(df_sim, df_real, config=config)
                
                wp_gap = raw_metrics["waypoints_diff"]
                boundary_gap = 1.0 - raw_metrics["boundary_match"]
                traj_gap_raw = raw_metrics["trajectory_gap"]
                traj_gap = min(1.0, traj_gap_raw / trajectory_norm) if trajectory_norm > 0 else 0.0
                
                # Compute combined_error using the same logic as post_processing.py
                # Use default weights from post_processing if available
                DEFAULT_WEIGHTS = {
                    "waypoint": 0.8,
                    "boundary_wp_diff": 0.2,
                    "boundary": 0.6,
                    "trajectory": 0.4,
                }
                if wp_gap == 0:
                    combined_error = min(
                        1.0,
                        DEFAULT_WEIGHTS.get("boundary", 0.0) * boundary_gap
                        + DEFAULT_WEIGHTS.get("trajectory", 0.0) * traj_gap,
                    )
                else:
                    combined_error = min(
                        1.0,
                        DEFAULT_WEIGHTS.get("waypoint", 0.0) * min(wp_gap / 4.0, 1.0)  # Normalize wp_gap to [0,1]
                        + DEFAULT_WEIGHTS.get("boundary_wp_diff", 0.0) * boundary_gap
                    )
            except Exception as e:
                print(f"Warning: Failed to compute metrics for sample {idx}: {e}")
                continue
        else:
            # Use existing gap_metrics
            if not gap_metrics:
                continue
            
            combined_error = gap_metrics.get('combined_error')
            wp_gap = gap_metrics.get('waypoints_diff', gap_metrics.get('normalized_waypoint_gap', 0))
            boundary_match = gap_metrics.get('boundary_match', 1)
            boundary_gap = 1.0 - boundary_match
            traj_gap_raw = gap_metrics.get('trajectory_gap_raw', gap_metrics.get('normalized_trajectory_gap', 0))
            traj_gap = gap_metrics.get('normalized_trajectory_gap', min(1.0, traj_gap_raw / trajectory_norm) if trajectory_norm > 0 else 0.0)
        
        # Only include samples with all required data
        if (combined_error is not None and wp_gap is not None and 
            boundary_gap is not None and traj_gap is not None):
            forward_speeds.append(fs)
            turn_speeds.append(ts)
            waypoint_thresholds.append(wt)
            combined_errors.append(combined_error)
            waypoint_gaps.append(wp_gap)
            boundary_gaps.append(boundary_gap)
            trajectory_gaps.append(traj_gap)
            finished_laps.append(gap_metrics.get('finished_lap', False))
            sample_nums.append(sample.get('sample_num', 0))
    
    if len(forward_speeds) == 0:
        print("No samples with complete metric data found.")
        return
    
    print(f"Processing {len(forward_speeds)} samples with complete metrics")
    
    # Convert to numpy arrays
    forward_speeds = np.array(forward_speeds)
    turn_speeds = np.array(turn_speeds)
    waypoint_thresholds = np.array(waypoint_thresholds)
    combined_errors = np.array(combined_errors)
    waypoint_gaps = np.array(waypoint_gaps)
    boundary_gaps = np.array(boundary_gaps)
    trajectory_gaps = np.array(trajectory_gaps)
    finished_laps = np.array(finished_laps)
    
    
    # Split data into finished_lap = True and False groups
    finished_mask = finished_laps == True
    not_finished_mask = ~finished_mask
    
    # Data for finished_lap = True (circles)
    fs_finished = forward_speeds[finished_mask]
    ts_finished = turn_speeds[finished_mask]
    wt_finished = waypoint_thresholds[finished_mask]
    
    # Data for finished_lap = False (squares)
    fs_not_finished = forward_speeds[not_finished_mask]
    ts_not_finished = turn_speeds[not_finished_mask]
    wt_not_finished = waypoint_thresholds[not_finished_mask]
    
    # Create figure with 2x2 subplots
    fig = plt.figure(figsize=figsize)
    axes = []
    
    # Create 4 subplots
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    ax2 = fig.add_subplot(2, 2, 2, projection='3d')
    ax3 = fig.add_subplot(2, 2, 3, projection='3d')
    ax4 = fig.add_subplot(2, 2, 4, projection='3d')
    axes = [ax1, ax2, ax3, ax4]
    
    # Metric data and titles
    metric_data = [
        (combined_errors, "Combined Error", (0, 1)),
        (waypoint_gaps, "Waypoint Gap", (0, waypoint_gaps.max())),
        (boundary_gaps, "Boundary Gap", (0, 1)),
        (trajectory_gaps, "Trajectory Gap (normalized)", (0, 1)),
    ]
    
    scatter_objects = []
    
    # Plot each metric
    for ax, (metric_values, title, vrange) in zip(axes, metric_data):
        metric_finished = metric_values[finished_mask]
        metric_not_finished = metric_values[not_finished_mask]
        
        scatters = []
        
        # Plot finished_lap = True points (circles)
        if len(fs_finished) > 0:
            scatter_finished = ax.scatter(
                fs_finished,
                ts_finished,
                wt_finished,
                c=metric_finished,
                cmap=colormap,
                vmin=vrange[0],
                vmax=vrange[1],
                s=100,
                alpha=0.7,
                edgecolors='black',
                linewidths=0.5,
                marker='o',
                label='Finished Lap'
            )
            scatters.append(scatter_finished)
        
        # Plot finished_lap = False points (squares)
        if len(fs_not_finished) > 0:
            scatter_not_finished = ax.scatter(
                fs_not_finished,
                ts_not_finished,
                wt_not_finished,
                c=metric_not_finished,
                cmap=colormap,
                vmin=vrange[0],
                vmax=vrange[1],
                s=100,
                alpha=0.7,
                edgecolors='black',
                linewidths=0.5,
                marker='s',
                label='Not Finished Lap'
            )
            scatters.append(scatter_not_finished)
        
        scatter_objects.append(scatters[0] if scatters else None)
        
        ax.set_xlabel('forwardSpeed', fontsize=10, fontweight='bold')
        ax.set_ylabel('turnSpeed', fontsize=10, fontweight='bold')
        ax.set_zlabel('waypointThreshold', fontsize=10, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold')
        
        # Add colorbar
        if scatters:
            cbar = plt.colorbar(scatters[0], ax=ax, pad=0.1, shrink=0.8)
            cbar.set_label(title, rotation=270, labelpad=15, fontsize=9)
        
        # Add legend (only on first subplot to avoid clutter)
        if ax == ax1:
            ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    
    # Set initial view angles for all axes
    initial_elev = 20
    initial_azim = 45
    
    # Synchronize views - when one axis is rotated, update all others
    # Store the initial view angles
    shared_view = {'elev': initial_elev, 'azim': initial_azim, 'source': None}
    
    def on_mouse_move(event):
        """Update shared view angles when mouse moves during rotation."""
        if event.inaxes in axes and event.button == 1:  # Left mouse button
            source_ax = event.inaxes
            shared_view['source'] = source_ax
            shared_view['elev'] = source_ax.elev
            shared_view['azim'] = source_ax.azim
            
            # Update all other axes to match
            for ax in axes:
                if ax != source_ax:
                    ax.view_init(elev=shared_view['elev'], azim=shared_view['azim'])
            fig.canvas.draw_idle()
    
    def on_button_release(event):
        """Finalize view synchronization on button release."""
        if event.inaxes in axes:
            source_ax = event.inaxes
            shared_view['elev'] = source_ax.elev
            shared_view['azim'] = source_ax.azim
            
            # Update all other axes to match
            for ax in axes:
                if ax != source_ax:
                    ax.view_init(elev=shared_view['elev'], azim=shared_view['azim'])
            fig.canvas.draw_idle()
    
    # Connect events to figure (not individual axes) for better synchronization
    fig.canvas.mpl_connect('motion_notify_event', on_mouse_move)
    fig.canvas.mpl_connect('button_release_event', on_button_release)
    
    # Set initial view for all axes (same as first axis)
    for ax in axes:
        ax.view_init(elev=initial_elev, azim=initial_azim)
    
    # Add overall title
    fig.suptitle(
        f'Separate Metrics Visualization ({len(forward_speeds)} samples)\n'
        f'Rotate any plot to synchronize all views',
        fontsize=14,
        fontweight='bold'
    )
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {save_path}")
    
    # Print summary statistics
    print(f"\n{'='*60}")
    print("Metric Statistics:")
    print(f"{'='*60}")
    print(f"Total samples: {len(forward_speeds)}")
    print(f"\nCombined Error: min={combined_errors.min():.4f}, max={combined_errors.max():.4f}, mean={combined_errors.mean():.4f}")
    print(f"Waypoint Gap: min={waypoint_gaps.min():.0f}, max={waypoint_gaps.max():.0f}, mean={waypoint_gaps.mean():.4f}")
    print(f"Boundary Gap: min={boundary_gaps.min():.4f}, max={boundary_gaps.max():.4f}, mean={boundary_gaps.mean():.4f}")
    print(f"Trajectory Gap: min={trajectory_gaps.min():.4f}, max={trajectory_gaps.max():.4f}, mean={trajectory_gaps.mean():.4f}")
    
    plt.show()


def visualize_samples_2d_projections(
    checkpoint_dir: str = None,
    log_file_path: str = "sample_data.pkl",
    gap_threshold: float = 0.5,
    colormap: str = "RdYlGn_r",
    figsize: tuple = (15, 5),
    save_path: str = None
):
    """
    Create 2D projection plots (three subplots showing different parameter pairs).
    """
    # Load data
    all_samples = load_sample_data(checkpoint_dir, log_file_path)
    
    if len(all_samples) == 0:
        print("No samples found in pickle file.")
        return
    
    # Extract data (same as 3D version)
    forward_speeds = []
    turn_speeds = []
    waypoint_thresholds = []
    combined_errors = []
    finished_laps = []
    
    for sample in all_samples:
        params = sample.get('params', {})
        gap_metrics = sample.get('gap_metrics', {})
        
        fs = params.get('forwardSpeed')
        ts = params.get('turnSpeed')
        wt = params.get('waypointThreshold')
        error = gap_metrics.get('combined_error') if gap_metrics else None
        finished_lap = gap_metrics.get('finished_lap', False) if gap_metrics else False
        
        if fs is not None and ts is not None and wt is not None and error is not None:
            forward_speeds.append(fs)
            turn_speeds.append(ts)
            waypoint_thresholds.append(wt)
            combined_errors.append(error)
            finished_laps.append(finished_lap)
    
    if len(forward_speeds) == 0:
        print("No samples with complete data found.")
        return
    
    forward_speeds = np.array(forward_speeds)
    turn_speeds = np.array(turn_speeds)
    waypoint_thresholds = np.array(waypoint_thresholds)
    combined_errors = np.array(combined_errors)
    finished_laps = np.array(finished_laps)
    
    # Split data into finished_lap = True and False groups
    finished_mask = finished_laps == True
    not_finished_mask = ~finished_mask
    
    # Data for finished_lap = True (circles)
    fs_finished = forward_speeds[finished_mask]
    ts_finished = turn_speeds[finished_mask]
    wt_finished = waypoint_thresholds[finished_mask]
    errors_finished = combined_errors[finished_mask]
    
    # Data for finished_lap = False (squares)
    fs_not_finished = forward_speeds[not_finished_mask]
    ts_not_finished = turn_speeds[not_finished_mask]
    wt_not_finished = waypoint_thresholds[not_finished_mask]
    errors_not_finished = combined_errors[not_finished_mask]
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=figsize)
    
    # Plot 1: forwardSpeed vs turnSpeed
    if len(fs_finished) > 0:
        axes[0].scatter(
            fs_finished, ts_finished,
            c=errors_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='o', label='Finished Lap (True)'
        )
    if len(fs_not_finished) > 0:
        axes[0].scatter(
            fs_not_finished, ts_not_finished,
            c=errors_not_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='s', label='Not Finished Lap (False)'
        )
    axes[0].set_xlabel('forwardSpeed', fontweight='bold')
    axes[0].set_ylabel('turnSpeed', fontweight='bold')
    axes[0].set_title('forwardSpeed vs turnSpeed')
    axes[0].grid(True, alpha=0.3)
    # Customize legend handles to be hollow (no fill color)
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        axes[0].legend(new_handles, labels, loc='best', fontsize=8)
    else:
        axes[0].legend(loc='best', fontsize=8)
    
    # Plot 2: forwardSpeed vs waypointThreshold
    if len(fs_finished) > 0:
        axes[1].scatter(
            fs_finished, wt_finished,
            c=errors_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='o', label='Finished Lap (True)'
        )
    if len(fs_not_finished) > 0:
        axes[1].scatter(
            fs_not_finished, wt_not_finished,
            c=errors_not_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='s', label='Not Finished Lap (False)'
        )
    axes[1].set_xlabel('forwardSpeed', fontweight='bold')
    axes[1].set_ylabel('waypointThreshold', fontweight='bold')
    axes[1].set_title('forwardSpeed vs waypointThreshold')
    axes[1].grid(True, alpha=0.3)
    # Customize legend handles to be hollow (no fill color)
    handles, labels = axes[1].get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        axes[1].legend(new_handles, labels, loc='best', fontsize=8)
    else:
        axes[1].legend(loc='best', fontsize=8)
    
    # Plot 3: turnSpeed vs waypointThreshold
    scatter3 = None
    if len(fs_finished) > 0:
        scatter3 = axes[2].scatter(
            ts_finished, wt_finished,
            c=errors_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='o', label='Finished Lap (True)'
        )
    if len(fs_not_finished) > 0:
        scatter3 = axes[2].scatter(
            ts_not_finished, wt_not_finished,
            c=errors_not_finished, cmap=colormap,
            vmin=0, vmax=1,
            s=100, alpha=0.7, edgecolors='black', linewidths=0.5,
            marker='s', label='Not Finished Lap (False)'
        )
    axes[2].set_xlabel('turnSpeed', fontweight='bold')
    axes[2].set_ylabel('waypointThreshold', fontweight='bold')
    axes[2].set_title('turnSpeed vs waypointThreshold')
    axes[2].grid(True, alpha=0.3)
    # Customize legend handles to be hollow (no fill color)
    handles, labels = axes[2].get_legend_handles_labels()
    if handles:
        new_handles = []
        for handle, label in zip(handles, labels):
            # Determine marker from label (works for both 2D and 3D plots)
            if 'Finished Lap (True)' in label:
                marker = 'o'
            elif 'Not Finished Lap (False)' in label:
                marker = 's'
            else:
                # Try to get marker from handle if possible
                try:
                    marker = handle.get_marker()
                except AttributeError:
                    marker = 'o'  # default fallback
            
            new_handle = Line2D([0], [0], marker=marker, linestyle='None', 
                               markersize=8, markeredgecolor='black', 
                               markerfacecolor='none', markeredgewidth=1.5)
            new_handles.append(new_handle)
        axes[2].legend(new_handles, labels, loc='best', fontsize=8)
    else:
        axes[2].legend(loc='best', fontsize=8)
    
    # Add colorbar (use scatter3 if it exists, otherwise use combined_errors)
    if scatter3 is not None:
        cbar = plt.colorbar(scatter3, ax=axes, pad=0.1)
    else:
        # Fallback: create a dummy scatter for colorbar
        dummy_scatter = axes[0].scatter(forward_speeds, turn_speeds, c=combined_errors, cmap=colormap, vmin=0, vmax=1, s=0)
        cbar = plt.colorbar(dummy_scatter, ax=axes, pad=0.1)
    cbar.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    
    # Add overall title
    fig.suptitle(
        f'Parameter Space 2D Projections ({len(forward_speeds)} samples)',
        fontsize=14, fontweight='bold'
    )
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {save_path}")
    
    plt.show()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize sample data from pickle file')
    parser.add_argument(
        '--checkpoint-dir',
        type=str,
        default=None,
        help='Directory containing sample_data.pkl (default: checkpoints/)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=0.5,
        help='Threshold for gap classification (default: 0.5)'
    )
    parser.add_argument(
        '--colormap',
        type=str,
        default='RdYlGn_r',
        help='Matplotlib colormap name (default: RdYlGn_r)'
    )
    parser.add_argument(
        '--projections',
        action='store_true',
        help='Show 2D projections instead of 3D plot'
    )
    parser.add_argument(
        '--separate-metrics',
        action='store_true',
        help='Show 4 separate 3D plots for different metrics (combined, waypoint, boundary, trajectory)'
    )
    parser.add_argument(
        '--save',
        type=str,
        default=None,
        help='Path to save the figure (optional)'
    )
    parser.add_argument(
        '--no-recompute',
        action='store_true',
        help='Use existing gap_metrics instead of recomputing from raw data (only for --separate-metrics)'
    )
    
    args = parser.parse_args()
    
    if args.separate_metrics:
        visualize_separate_metrics_3d(
            checkpoint_dir=args.checkpoint_dir,
            colormap=args.colormap,
            save_path=args.save,
            recompute_metrics=not args.no_recompute
        )
    elif args.projections:
        visualize_samples_2d_projections(
            checkpoint_dir=args.checkpoint_dir,
            gap_threshold=args.threshold,
            colormap=args.colormap,
            save_path=args.save
        )
    else:
        visualize_samples_3d(
            checkpoint_dir=args.checkpoint_dir,
            gap_threshold=args.threshold,
            colormap=args.colormap,
            save_path=args.save
        )

