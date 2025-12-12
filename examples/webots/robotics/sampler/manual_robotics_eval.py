"""
Manual robotics evaluation script - alternative to VerifAI.

This script manages the sampler and automatically updates scenic files with parameter values.
You manually run Webots and hardware, then provide the metric.

Workflow:
1. Script defines parameter ranges directly (independent of VerifAI)
2. Get parameters from sampler
3. Automatically update pololu.scenic and pololu_hardware.scenic with parameter values
4. Wait for user to run Webots + hardware manually
5. User provides metric
6. Update sampler with metric
7. Repeat
"""

import sys
import os
import logging
from pathlib import Path
import re
from datetime import datetime
import pickle

# Add paths for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sampler import MultiArmedBanditSampler
from verifai.features import Box
from post_processing import compute_gap_metric, GapComputationError, get_latest_log_pair

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent


def save_sample_data(
    checkpoint_dir: str,
    sample_num: int,
    params: dict,
    df_sim=None,
    df_real=None,
    gap_metrics: dict = None,
    log_file_path: str = "sample_data.pkl"
):
    """
    Save sample data to a running pickle file.
    Each entry contains parameters and both dataframes for one sample.
    
    Args:
        checkpoint_dir: Directory to save the pickle file
        sample_num: Sample number
        params: Dictionary of parameters used
        df_sim: Pandas DataFrame from simulation log (optional)
        df_real: Pandas DataFrame from real hardware log (optional)
        gap_metrics: Dictionary of computed gap metrics (optional)
        log_file_path: Name of the pickle file to save
    """
    data_file = os.path.join(checkpoint_dir, log_file_path)
    
    # Load existing data or create new list
    if os.path.exists(data_file):
        try:
            with open(data_file, 'rb') as f:
                all_samples = pickle.load(f)
        except Exception as e:
            log.warning(f"Failed to load existing sample data: {e}. Starting fresh.")
            all_samples = []
    else:
        all_samples = []
    
    # Create new entry
    sample_entry = {
        'sample_num': sample_num,
        'params': params.copy(),
        'df_sim': df_sim.copy() if df_sim is not None else None,
        'df_real': df_real.copy() if df_real is not None else None,
        'gap_metrics': gap_metrics.copy() if gap_metrics else None,
        'timestamp': datetime.now().isoformat()
    }
    
    # Append and save
    all_samples.append(sample_entry)
    with open(data_file, 'wb') as f:
        pickle.dump(all_samples, f)
    
    log.info(f"Sample data saved to: {data_file} (total samples: {len(all_samples)})")


def load_sample_data(checkpoint_dir: str, log_file_path: str = "sample_data.pkl"):
    """
    Load all collected sample data from pickle file.
    
    Args:
        checkpoint_dir: Directory containing the pickle file
        log_file_path: Name of the pickle file to load
        
    Returns:
        List of sample entries, each containing params, dataframes, and metrics
    """
    data_file = os.path.join(checkpoint_dir, log_file_path)
    if os.path.exists(data_file):
        try:
            with open(data_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            log.error(f"Failed to load sample data: {e}")
            return []
    return []


def update_scenic_file(scenic_file_path: str, params: dict):
    """
    Update a scenic file with concrete parameter values.
    
    Replaces both VerifaiRange calls and regular numeric values with concrete values.
    Also adds missing parameters to the SquareTrackBehavior call if needed.
    
    For example: 
        forwardSpeed=VerifaiRange(50, 100) -> forwardSpeed=75.0
        forwardSpeed=80 -> forwardSpeed=75.0
    
    Args:
        scenic_file_path: Path to the .scenic file to update
        params: Dictionary of parameter names to values
    
    Returns:
        bool: True if file was updated, False otherwise
    """
    # Read the scenic file
    with open(scenic_file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace parameter values for each parameter
    for param_name, param_value in params.items():
        # Pattern 1: Replace VerifaiRange calls
        # Match: param_name = VerifaiRange(...) or param_name=VerifaiRange(...)
        pattern1 = rf'({param_name})\s*=\s*VerifaiRange\([^)]+\)'
        replacement = rf'\1={param_value}'
        content = re.sub(pattern1, replacement, content)
        
        # Pattern 2: Replace regular numeric values (handles cases like forwardSpeed=80)
        # Match: param_name = number followed by comma, closing paren, or newline
        # This ensures we match complete parameter assignments, not parts of other numbers
        pattern2 = rf'({param_name})\s*=\s*(\d+\.?\d*)(?=\s*[,\)\n])'
        content = re.sub(pattern2, rf'\1={param_value}', content)
    
    # Add missing parameters to SquareTrackBehavior if they don't exist
    # Find the SquareTrackBehavior call (handles multi-line)
    behavior_pattern = r'(SquareTrackBehavior\s*\([^)]*)(\))'
    match = re.search(behavior_pattern, content, re.DOTALL)
    if match:
        behavior_start_part = match.group(1)  # Everything up to and including the opening paren and args
        closing_paren = match.group(2)  # The closing paren
        behavior_start = match.start()
        behavior_end = match.end()
        
        # Extract just the arguments part (between parens)
        args_match = re.search(r'SquareTrackBehavior\s*\((.*?)\)', content, re.DOTALL)
        if args_match:
            behavior_args = args_match.group(1)
            
            # Check which parameters are missing
            missing_params = []
            for param_name in params.keys():
                # Check if parameter exists in the args (as a complete parameter assignment)
                param_pattern = rf'\b{param_name}\s*='
                if not re.search(param_pattern, behavior_args):
                    missing_params.append(param_name)
            
            # Add missing parameters before the closing parenthesis
            if missing_params:
                # Build the new parameter list
                new_params = []
                for param_name in missing_params:
                    new_params.append(f"{param_name}={params[param_name]}")
                
                # Determine indentation from existing args (look for the line with the first param)
                lines = behavior_args.split('\n')
                indent = "        "  # Default indent
                for line in lines:
                    if line.strip() and '=' in line.strip():
                        # Found a parameter line, extract its indentation
                        indent = len(line) - len(line.lstrip())
                        indent = " " * indent
                        break
                
                # Add them to the behavior call (before the closing paren)
                if behavior_args.strip():
                    # Has existing args, add comma and new params on new lines
                    new_behavior_args = behavior_args.rstrip() + ",\n" + indent + (",\n" + indent).join(new_params)
                else:
                    # No existing args, just add new params
                    new_behavior_args = indent + (",\n" + indent).join(new_params)
                
                # Reconstruct the behavior call
                new_behavior_call = f"SquareTrackBehavior({new_behavior_args}\n    )"
                content = content[:behavior_start] + new_behavior_call + content[behavior_end:]
    
    # Only write if content changed
    if content != original_content:
        with open(scenic_file_path, 'w') as f:
            f.write(content)
        log.info(f"Updated {scenic_file_path} with parameter values")
        return True
    else:
        log.warning(f"No changes made to {scenic_file_path} - parameters may not be found")
        return False


def manual_robotics_evaluation(
    webots_scenic_file: str = None,
    hardware_scenic_file: str = None,
    num_samples: int = 100,
    sampler_params: dict = None,
    checkpoint_dir: str = None,
    resume_from_checkpoint: bool = True,
    start_sample_num: int = 0,
    param_ranges: dict = None,
    reset_sampler: bool = False,
    random_seed: int = None
):
    """
    Manual robotics evaluation loop - alternative to VerifAI.
    
    This script works independently of VerifAI. It defines parameter ranges directly
    and updates scenic files with sampled parameter values.
    
    For each iteration:
    1. Get parameters from sampler (within defined ranges)
    2. Automatically update scenic files with parameter values
    3. Wait for user to run Webots + hardware manually
    4. User provides metric
    5. Update sampler with metric
    6. Repeat
    
    Args:
        webots_scenic_file: Path to pololu.scenic file to update for Webots simulation
        hardware_scenic_file: Path to pololu_hardware.scenic file to update for hardware
        num_samples: Number of parameter samples to test
        sampler_params: Parameters for the MAB sampler
        checkpoint_dir: Directory to save/load checkpoints
        resume_from_checkpoint: If True, load sampler state from checkpoint
        start_sample_num: Sample number to start from (for resume)
        param_ranges: Dictionary mapping parameter names to (min, max) tuples.
                     Defaults to: {
                         'forwardSpeed': (50, 100),
                         'turnSpeed': (40, 80),
                         'waypointThreshold': (0.05, 0.2)
                     }
        reset_sampler: If True, reset the sampler to initial state (even if loading from checkpoint)
        random_seed: Random seed for reproducibility. If None, no seed is set.
    """
    if sampler_params is None:
        sampler_params = {
            'alpha': 0.1,
            'thres': 0.5,
            'buckets': 10,
            'exploration_ratio': 2.0
        }
    
    # Define parameter ranges (default values)
    if param_ranges is None:
        param_ranges = {
            'forwardSpeed': (50, 100),
            'turnSpeed': (40, 80),
            'waypointThreshold': (0.05, 0.2)
        }
    
    # Set default paths if not provided
    if webots_scenic_file is None:
        webots_scenic_file = os.path.join(ROOT.parent, "pololu.scenic")
    if hardware_scenic_file is None:
        hardware_scenic_file = os.path.join(ROOT.parent, "pololu_hardware.scenic")
    
    log.info(f"Starting manual robotics evaluation (independent of VerifAI)")
    log.info(f"  Webots scenario: {webots_scenic_file}")
    log.info(f"  Hardware scenario: {hardware_scenic_file}")
    
    # Seed random number generator for reproducibility
    if random_seed is not None:
        import numpy as np
        np.random.seed(random_seed)
        log.info(f"Random seed set to: {random_seed}")
    
    # Create parameter domain from ranges (for VerifAI sampler format)
    # The sampler expects a dictionary of parameter names to Box domains
    # Box takes intervals as arguments, so for 1D: Box((min, max))
    param_domain = {}
    for param_name, (min_val, max_val) in param_ranges.items():
        # Create a Box domain: Box((min, max)) creates a 1D box with one interval
        param_domain[param_name] = Box((min_val, max_val))
        log.info(f"Parameter: {param_name} range: [{min_val}, {max_val}]")
    
    # Initialize or load sampler
    checkpoint_file = None
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_file = os.path.join(checkpoint_dir, "sampler_state_mab.pkl")
    
    if resume_from_checkpoint and checkpoint_file and os.path.exists(checkpoint_file):
        log.info(f"Resuming from checkpoint: {checkpoint_file}")
        sampler = MultiArmedBanditSampler.load_state(checkpoint_file)
        if reset_sampler:
            log.info("Resetting sampler to initial state...")
            sampler.reset()
            successful_samples = 0
        else:
            successful_samples = start_sample_num
    else:
        sampler = MultiArmedBanditSampler(
            param_domain,
            alpha=sampler_params.get('alpha', 0.1),
            thres=sampler_params.get('thres', 0.5),
            buckets=sampler_params.get('buckets', 10),
            exploration_ratio=sampler_params.get('exploration_ratio', 2.0)
        )
        successful_samples = 0
    
    # Manual loop
    while successful_samples < num_samples:
        log.info(f"\n{'='*60}")
        log.info(f"Sample {successful_samples + 1}/{num_samples}")
        
        # Get parameters from sampler
        sample = sampler.getSample()
        
        # Display parameters
        print(f"\n{'='*60}")
        print(f"Sample {successful_samples + 1}/{num_samples}")
        print(f"\nSampled parameters:")
        for param_name in sorted(param_domain.keys()):
            value = sample[param_name]
            print(f"  {param_name}: {value:.4f}")
        
        # Update scenic files with parameter values
        print(f"\nUpdating scenic files...")
        webots_updated = update_scenic_file(webots_scenic_file, sample)
        hardware_updated = update_scenic_file(hardware_scenic_file, sample)
        
        if webots_updated and hardware_updated:
            print(f"✓ Updated {os.path.basename(webots_scenic_file)}")
            print(f"✓ Updated {os.path.basename(hardware_scenic_file)}")
        else:
            print(f"⚠ Some files may not have been updated correctly")
        
        # Optionally write parameters to file for reference
        if checkpoint_dir:
            params_file = os.path.join(checkpoint_dir, f"sample_{successful_samples + 1}_params.txt")
            with open(params_file, 'w') as f:
                f.write(f"Sample {successful_samples + 1}/{num_samples}\n\n")
                f.write("Parameters used:\n")
                for param_name in sorted(param_domain.keys()):
                    value = sample[param_name]
                    f.write(f"  {param_name}: {value:.4f}\n")
            log.info(f"Parameters saved to: {params_file}")
        
        print(f"\n{'='*60}")
        print(f"Next steps:")
        print(f"1. Run Webots simulation (using {os.path.basename(webots_scenic_file)})")
        print(f"2. Run hardware (using {os.path.basename(hardware_scenic_file)})")
        print(f"3. Compute multi-objective metric:")
        print(f"   - Difference in number of waypoints reached")
        print(f"   - Trajectory out of bounds difference")
        print(f"   - Trajectory difference")
        print(f"4. Enter metric below (0-1, higher = larger sim-to-real gap)")
        print(f"{'='*60}")
        
        # Wait for user to provide metric
        try:
            metric_input = input(
                "\nEnter metric value (0-1), press Enter to compute from logs, "
                "'q' to quit, 's' to skip: "
            ).strip()
            
            if metric_input.lower() == 'q':
                log.info("User quit. Saving checkpoint...")
                if checkpoint_dir and checkpoint_file:
                    sampler.save_state(checkpoint_file)
                break
            
            if metric_input.lower() == 's':
                log.info("Skipping this sample...")
                continue

            if metric_input == '':
                # Auto-compute metric from the most recent log files in the robotics log folder
                try:
                    sim_log_path, real_log_path = get_latest_log_pair()
                    print("\nAuto-selected log files:")
                    print(f"  sim : {sim_log_path}")
                    print(f"  real: {real_log_path}")
                    
                    # Decode dataframes for saving
                    from log_decoder import LogDecoder
                    df_sim = LogDecoder.decode_df(str(sim_log_path))
                    df_real = LogDecoder.decode_df(str(real_log_path))
                    
                    if df_sim is None or df_real is None:
                        raise GapComputationError("Failed to decode log files")
                    
                    # Compute metrics
                    gap_metrics = compute_gap_metric(str(sim_log_path), str(real_log_path))
                    metric = gap_metrics["combined_error"]
                    print("\nComputed sim-to-real gap metric:")
                    print(f"  combined_error: {metric:.4f}")
                    print(f"\n  Waypoint metrics:")
                    print(f"    waypoints_hit_sim: {gap_metrics['waypoints_hit_sim']}")
                    print(f"    waypoints_hit_real: {gap_metrics['waypoints_hit_real']}")
                    print(f"    waypoints_diff: {gap_metrics['waypoints_diff']}")
                    print(f"    normalized_waypoint_gap: {gap_metrics['normalized_waypoint_gap']:.4f}")
                    print(f"\n  Boundary metrics:")
                    print(f"    boundary_violation_sim: {gap_metrics['boundary_violation_sim']}")
                    print(f"    boundary_violation_real: {gap_metrics['boundary_violation_real']}")
                    print(f"    boundary_match: {gap_metrics['boundary_match']}")
                    print(f"    normalized_boundary_gap: {gap_metrics['normalized_boundary_gap']:.4f}")
                    print(f"\n  Trajectory metrics:")
                    print(f"    trajectory_gap_raw: {gap_metrics['trajectory_gap_raw']:.4f}")
                    print(f"    normalized_trajectory_gap: {gap_metrics['normalized_trajectory_gap']:.4f}")
                    print(f"    trajectory_mode: {gap_metrics['trajectory_mode']}")
                    print(f"    trajectory_segments: {gap_metrics['trajectory_segments']}")
                    print(f"    trajectory_aligned_points: {gap_metrics['trajectory_aligned_points']}")
                    print(f"    trajectory_duration: {gap_metrics['trajectory_duration']:.2f}s")
                    
                    # Append gap metrics to params file
                    if checkpoint_dir:
                        params_file = os.path.join(checkpoint_dir, f"sample_{successful_samples + 1}_params.txt")
                        with open(params_file, 'a') as f:
                            f.write("\n" + "=" * 60 + "\n")
                            f.write("Gap Metrics Results\n")
                            f.write("=" * 60 + "\n\n")
                            # Summary line matching log format
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                            f.write(f"{timestamp} - INFO - Gap metrics v2 -> wp_diff: {gap_metrics['waypoints_diff']} | boundary_match: {gap_metrics['boundary_match']} | traj_gap: {gap_metrics['trajectory_gap_raw']:.4f} ({gap_metrics['trajectory_mode']}) | combined_error: {metric:.4f}\n\n")
                            f.write("Log files used:\n")
                            f.write(f"  sim : {sim_log_path}\n")
                            f.write(f"  real: {real_log_path}\n\n")
                            f.write("Computed sim-to-real gap metric:\n")
                            f.write(f"  combined_error: {metric:.4f}\n\n")
                            f.write("Waypoint metrics:\n")
                            f.write(f"  waypoints_hit_sim: {gap_metrics['waypoints_hit_sim']}\n")
                            f.write(f"  waypoints_hit_real: {gap_metrics['waypoints_hit_real']}\n")
                            f.write(f"  waypoints_diff: {gap_metrics['waypoints_diff']}\n")
                            f.write(f"  normalized_waypoint_gap: {gap_metrics['normalized_waypoint_gap']:.4f}\n\n")
                            f.write("Boundary metrics:\n")
                            f.write(f"  boundary_violation_sim: {gap_metrics['boundary_violation_sim']}\n")
                            f.write(f"  boundary_violation_real: {gap_metrics['boundary_violation_real']}\n")
                            f.write(f"  boundary_match: {gap_metrics['boundary_match']}\n")
                            f.write(f"  normalized_boundary_gap: {gap_metrics['normalized_boundary_gap']:.4f}\n\n")
                            f.write("Trajectory metrics:\n")
                            f.write(f"  trajectory_gap_raw: {gap_metrics['trajectory_gap_raw']:.4f}\n")
                            f.write(f"  normalized_trajectory_gap: {gap_metrics['normalized_trajectory_gap']:.4f}\n")
                            f.write(f"  trajectory_mode: {gap_metrics['trajectory_mode']}\n")
                            f.write(f"  trajectory_segments: {gap_metrics['trajectory_segments']}\n")
                            f.write(f"  trajectory_aligned_points: {gap_metrics['trajectory_aligned_points']}\n")
                            f.write(f"  trajectory_duration: {gap_metrics['trajectory_duration']:.2f}s\n")
                        log.info(f"Gap metrics appended to: {params_file}")
                        
                        # Save dataframes and parameters to pickle file
                        save_sample_data(
                            checkpoint_dir,
                            successful_samples + 1,
                            sample,  # The parameters dict
                            df_sim,
                            df_real,
                            gap_metrics
                        )
                except GapComputationError as e:
                    log.error(f"Gap computation failed: {e}")
                    continue
            else:
                metric = float(metric_input)
                
                # Validate metric range
                if metric < 0 or metric > 1:
                    log.warning(f"Metric {metric} outside [0,1] range, clamping...")
                    metric = max(0.0, min(1.0, metric))
                
                # Append manually entered metric to params file
                if checkpoint_dir:
                    params_file = os.path.join(checkpoint_dir, f"sample_{successful_samples + 1}_params.txt")
                    with open(params_file, 'a') as f:
                        f.write("\n" + "=" * 60 + "\n")
                        f.write("Gap Metrics Results\n")
                        f.write("=" * 60 + "\n\n")
                        f.write("Metric manually entered by user:\n")
                        f.write(f"  combined_error: {metric:.4f}\n")
                        f.write("\nNote: Detailed gap metrics not computed (metric entered manually)\n")
                    log.info(f"Gap metrics appended to: {params_file}")
                    
                    # Save parameters (but no dataframes since metric was manually entered)
                    save_sample_data(
                        checkpoint_dir,
                        successful_samples + 1,
                        sample,  # The parameters dict
                        df_sim=None,
                        df_real=None,
                        gap_metrics={'combined_error': metric, 'note': 'manually_entered'}
                    )
            
            # Update sampler
            sampler.update(sample, metric, log=log)
            log.info(f"Updated sampler with metric: {metric:.4f}")
            
            # Save checkpoint
            if checkpoint_dir and checkpoint_file:
                sampler.save_state(checkpoint_file)
                log.info(f"Checkpoint saved")
            
            successful_samples += 1
            
        except ValueError:
            log.error("Invalid metric value. Please enter a number between 0 and 1, 'q' to quit, or 's' to skip.")
            continue
        except KeyboardInterrupt:
            log.info("\nInterrupted. Saving checkpoint...")
            if checkpoint_dir and checkpoint_file:
                sampler.save_state(checkpoint_file)
            break
    
    log.info(f"\n{'='*60}")
    log.info("Evaluation complete!")
    log.info(f"Processed {successful_samples}/{num_samples} samples")


if __name__ == "__main__":
    webots_file = os.path.join(ROOT.parent, "pololu.scenic")
    hardware_file = os.path.join(ROOT.parent, "pololu_hardware.scenic")
    checkpoint_dir = os.path.join(ROOT, "checkpoints")
    
    # Define parameter ranges directly (no need for VerifAI scenic file)
    param_ranges = {
        'forwardSpeed': (30, 70),      # Percent Throttle
        'turnSpeed': (20, 40),          # Turn speed units
        'waypointThreshold': (0.08, 0.12)  # Distance threshold in meters
    }
    
    manual_robotics_evaluation(
        webots_scenic_file=webots_file,
        hardware_scenic_file=hardware_file,
        num_samples=100,
        sampler_params={
            'alpha': 0.1,
            'thres': 0.5,
            'buckets': 10,
            'exploration_ratio': 2.0
        },
        checkpoint_dir=checkpoint_dir,
        resume_from_checkpoint=True,
        start_sample_num=0,
        param_ranges=param_ranges,
        reset_sampler=False,
        random_seed=24  # Set to None for no seeding
    )

