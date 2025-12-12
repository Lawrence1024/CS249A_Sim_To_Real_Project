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
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

# Add paths for imports
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

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
        '--save',
        type=str,
        default=None,
        help='Path to save the figure (optional)'
    )
    
    args = parser.parse_args()
    
    if args.projections:
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

