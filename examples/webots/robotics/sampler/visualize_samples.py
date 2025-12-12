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
    figsize: tuple = (12, 10),
    save_path: str = None
):
    """
    Create a 3D scatter plot of samples with color-coding based on combined_error.
    
    Args:
        checkpoint_dir: Directory containing the pickle file
        log_file_path: Name of the pickle file
        gap_threshold: Threshold for color coding (points above this are "high gap")
        colormap: Matplotlib colormap name
        figsize: Figure size (width, height)
        save_path: Optional path to save the figure
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
    sample_nums = []
    
    for sample in all_samples:
        params = sample.get('params', {})
        gap_metrics = sample.get('gap_metrics', {})
        
        # Get parameters
        fs = params.get('forwardSpeed')
        ts = params.get('turnSpeed')
        wt = params.get('waypointThreshold')
        
        # Get combined error
        if gap_metrics:
            error = gap_metrics.get('combined_error')
        else:
            error = None
        
        # Only include samples with all required data
        if fs is not None and ts is not None and wt is not None and error is not None:
            forward_speeds.append(fs)
            turn_speeds.append(ts)
            waypoint_thresholds.append(wt)
            combined_errors.append(error)
            sample_nums.append(sample.get('sample_num', 0))
    
    if len(forward_speeds) == 0:
        print("No samples with complete data found.")
        return
    
    # Convert to numpy arrays
    forward_speeds = np.array(forward_speeds)
    turn_speeds = np.array(turn_speeds)
    waypoint_thresholds = np.array(waypoint_thresholds)
    combined_errors = np.array(combined_errors)
    
    # Create figure
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection='3d')
    
    # Create scatter plot with color-coding
    scatter = ax.scatter(
        forward_speeds,
        turn_speeds,
        waypoint_thresholds,
        c=combined_errors,
        cmap=colormap,
        s=100,
        alpha=0.7,
        edgecolors='black',
        linewidths=0.5
    )
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, pad=0.1)
    cbar.set_label('Combined Error (Sim-to-Real Gap)', rotation=270, labelpad=20)
    
    # Set labels
    ax.set_xlabel('forwardSpeed', fontsize=12, fontweight='bold')
    ax.set_ylabel('turnSpeed', fontsize=12, fontweight='bold')
    ax.set_zlabel('waypointThreshold', fontsize=12, fontweight='bold')
    
    # Set title
    ax.set_title(
        f'Parameter Space Visualization\n'
        f'{len(forward_speeds)} samples | Gap range: [{combined_errors.min():.3f}, {combined_errors.max():.3f}]',
        fontsize=14,
        fontweight='bold'
    )
    
    # Add threshold line/annotation if needed
    if gap_threshold:
        # Find samples above threshold
        high_gap_count = np.sum(combined_errors >= gap_threshold)
        low_gap_count = np.sum(combined_errors < gap_threshold)
        
        # Add text annotation
        ax.text2D(
            0.02, 0.98,
            f'Threshold: {gap_threshold:.2f}\n'
            f'High gap (≥{gap_threshold:.2f}): {high_gap_count}\n'
            f'Low gap (<{gap_threshold:.2f}): {low_gap_count}',
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        )
    
    # Improve layout
    plt.tight_layout()
    
    # Save if requested
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"Figure saved to: {save_path}")
    
    # Show plot
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
    
    for sample in all_samples:
        params = sample.get('params', {})
        gap_metrics = sample.get('gap_metrics', {})
        
        fs = params.get('forwardSpeed')
        ts = params.get('turnSpeed')
        wt = params.get('waypointThreshold')
        error = gap_metrics.get('combined_error') if gap_metrics else None
        
        if fs is not None and ts is not None and wt is not None and error is not None:
            forward_speeds.append(fs)
            turn_speeds.append(ts)
            waypoint_thresholds.append(wt)
            combined_errors.append(error)
    
    if len(forward_speeds) == 0:
        print("No samples with complete data found.")
        return
    
    forward_speeds = np.array(forward_speeds)
    turn_speeds = np.array(turn_speeds)
    waypoint_thresholds = np.array(waypoint_thresholds)
    combined_errors = np.array(combined_errors)
    
    # Create figure with 3 subplots
    fig, axes = plt.subplots(1, 3, figsize=figsize)
    
    # Plot 1: forwardSpeed vs turnSpeed
    scatter1 = axes[0].scatter(
        forward_speeds, turn_speeds,
        c=combined_errors, cmap=colormap,
        s=100, alpha=0.7, edgecolors='black', linewidths=0.5
    )
    axes[0].set_xlabel('forwardSpeed', fontweight='bold')
    axes[0].set_ylabel('turnSpeed', fontweight='bold')
    axes[0].set_title('forwardSpeed vs turnSpeed')
    axes[0].grid(True, alpha=0.3)
    
    # Plot 2: forwardSpeed vs waypointThreshold
    scatter2 = axes[1].scatter(
        forward_speeds, waypoint_thresholds,
        c=combined_errors, cmap=colormap,
        s=100, alpha=0.7, edgecolors='black', linewidths=0.5
    )
    axes[1].set_xlabel('forwardSpeed', fontweight='bold')
    axes[1].set_ylabel('waypointThreshold', fontweight='bold')
    axes[1].set_title('forwardSpeed vs waypointThreshold')
    axes[1].grid(True, alpha=0.3)
    
    # Plot 3: turnSpeed vs waypointThreshold
    scatter3 = axes[2].scatter(
        turn_speeds, waypoint_thresholds,
        c=combined_errors, cmap=colormap,
        s=100, alpha=0.7, edgecolors='black', linewidths=0.5
    )
    axes[2].set_xlabel('turnSpeed', fontweight='bold')
    axes[2].set_ylabel('waypointThreshold', fontweight='bold')
    axes[2].set_title('turnSpeed vs waypointThreshold')
    axes[2].grid(True, alpha=0.3)
    
    # Add colorbar
    cbar = plt.colorbar(scatter1, ax=axes, pad=0.1)
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

