"""
Robotics evaluation script for hybrid simulation + hardware testing with VerifAI-style samplers.

This script implements the workflow:
1. Get parameters from sampler
2. Run Webots simulation
3. Run real Pololu hardware
4. Compare results and compute metric
5. Update sampler with feedback
6. Repeat
"""

import sys
import os
import logging
from pathlib import Path

# Add paths for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import scenic
import scenic.core.external_params
from sampler import MultiArmedBanditSampler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent


def run_robotics_evaluation(
    scenic_file_path: str,
    num_samples: int = 100,
    sampler_params: dict = None,
    webots_world_path: str = None,
    max_retries: int = 5,
    checkpoint_dir: str = None,
    resume_from_checkpoint: bool = False,
    start_sample_num: int = 0,
    pause_before_hardware: bool = True
):
    """
    Run robotics evaluation with hybrid simulation + hardware testing using Multi-Armed Bandit sampler.
    
    Uses MAB sampler for multi-objective optimization of sim-to-real gap:
    - Trajectory out of bounds detection
    - Trajectory difference metric
    - Waypoint timing difference
    
    Args:
        scenic_file_path: Path to the .scenic file with VerifaiRange parameters
        num_samples: Number of parameter samples to test
        sampler_params: Parameters for the MAB sampler (alpha, thres, buckets, exploration_ratio)
        webots_world_path: Path to Webots .wbt world file
        max_retries: Maximum retries for failed simulations
        checkpoint_dir: Directory to save/load checkpoints (enables save/resume)
        resume_from_checkpoint: If True, load sampler state from checkpoint
        start_sample_num: Sample number to start from (for resume)
        pause_before_hardware: If True, pause and wait for user input before hardware run
    """
    if sampler_params is None:
        sampler_params = {
            'alpha': 0.1,
            'thres': 0.5,
            'buckets': 10,
            'exploration_ratio': 2.0
        }
    
    log.info(f"Starting robotics evaluation: {scenic_file_path}")
    log.info(f"Using Multi-Armed Bandit sampler, Num samples: {num_samples}")
    
    ### 1. Initialize scenario and extract parameter domain ###
    log.info("Loading Scenic scenario and extracting parameter domain...")
    scenario = scenic.scenarioFromFile(scenic_file_path, mode2D=True)
    
    param_domain = {}
    for param_name, param_value in scenario.params.items():
        if isinstance(param_value, scenic.core.external_params.VerifaiRange):
            # Extract domain from VerifaiRange
            # VerifaiRange.domain is a verifai.features.Box object
            param_domain[param_name] = param_value.domain
            log.info(f"Found parameter: {param_name} with domain {param_value.domain}")
    
    if not param_domain:
        raise ValueError("No VerifaiRange parameters found in scenario!")
    
    log.info(f"Parameter domain: {param_domain}")
    
    ### 2. Initialize or load MAB sampler ###
    checkpoint_file = None
    results_file = None
    if checkpoint_dir:
        os.makedirs(checkpoint_dir, exist_ok=True)
        checkpoint_file = os.path.join(checkpoint_dir, "sampler_state_mab.pkl")
        results_file = os.path.join(checkpoint_dir, "results.pkl")
    
    if resume_from_checkpoint and checkpoint_file and os.path.exists(checkpoint_file):
        log.info(f"Resuming from checkpoint: {checkpoint_file}")
        sampler = MultiArmedBanditSampler.load_state(checkpoint_file)
        
        # Load previous results if they exist
        if results_file and os.path.exists(results_file):
            import pickle
            with open(results_file, 'rb') as f:
                results = pickle.load(f)
            log.info(f"Loaded {len(results['samples'])} previous samples from checkpoint")
        else:
            results = {
                'samples': [],
                'metrics': [],
                'sim_data': [],
                'hardware_data': [],
                'violations': []
            }
        successful_samples = start_sample_num
    else:
        sampler = create_mab_sampler(param_domain, sampler_params)
        results = {
            'samples': [],
            'metrics': [],
            'sim_data': [],
            'hardware_data': [],
            'violations': []
        }
        successful_samples = 0
    
    ### 3. Sampling loop ###
    retries = 0
    
    while successful_samples < num_samples:
        if retries >= max_retries:
            log.error(f"Exceeded maximum retries ({max_retries}). Stopping evaluation.")
            break
        
        log.info(f"\n{'='*60}")
        log.info(f"Sample {successful_samples + 1}/{num_samples}")
        
        try:
            ### 4a. Generate parameter sample ###
            sample = sampler.getSample()
            params = {}
            param_info = "Sampled parameters: "
            for param_name in param_domain.keys():
                params[param_name] = sample[param_name]
                param_info += f"{param_name}: {sample[param_name]:.3f} "
            log.info(param_info)
            
            ### 4b. Create scenario with sampled parameters ###
            # Note: We need to pass parameters to override VerifaiRange values
            # This requires modifying how we create the scenario
            scenario_with_params = create_scenario_with_params(scenic_file_path, params)
            
            ### 4c. Run Webots simulation ###
            log.info("Running Webots simulation...")
            sim_result = run_webots_simulation(scenario_with_params, webots_world_path, params)
            if sim_result is None:
                log.warning("Simulation failed. Retrying...")
                retries += 1
                continue
            
            ### 4d. Run real hardware ###
            if pause_before_hardware:
                log.info("Ready to run real Pololu hardware...")
                log.info("Press Enter when hardware is ready, or Ctrl+C to pause (checkpoint will be saved)...")
                try:
                    input()
                except KeyboardInterrupt:
                    log.info("\nPausing evaluation...")
                    # Save checkpoint before exiting
                    if checkpoint_dir and checkpoint_file:
                        sampler.save_state(checkpoint_file)
                        if results_file:
                            import pickle
                            with open(results_file, 'wb') as f:
                                pickle.dump(results, f)
                        log.info(f"Checkpoint saved. Resume with resume_from_checkpoint=True, start_sample_num={successful_samples}")
                    raise
            
            log.info("Running real Pololu hardware...")
            hardware_result = run_pololu_hardware(params)
            if hardware_result is None:
                log.warning("Hardware run failed. Retrying...")
                retries += 1
                continue
            
            ### 4e. Compare results and compute multi-objective metric ###
            log.info("Comparing simulation and hardware results...")
            # Multi-objective metric aggregates:
            # 1. Trajectory out of bounds
            # 2. Trajectory difference
            # 3. Waypoint timing difference
            metric = compute_multi_objective_metric(sim_result, hardware_result)
            log.info(f"Computed multi-objective metric: {metric:.4f}")
            
            ### 4f. Store results ###
            results['samples'].append(sample)
            results['metrics'].append(metric)
            results['sim_data'].append(sim_result)
            results['hardware_data'].append(hardware_result)
            
            ### 4g. Update MAB sampler ###
            # MAB sampler updates based on aggregated error value
            # Higher metric = larger sim-to-real gap (what we want to find)
            error_value = metric  # Multi-objective metric is already normalized as error (0-1 range)
            sampler.update(sample, error_value, log=log)
            log.info(f"Updated MAB sampler with error value: {error_value:.4f}")
            
            successful_samples += 1
            retries = 0
            
            ### 4h. Save checkpoint periodically ###
            if checkpoint_dir and checkpoint_file:
                # Save every sample, or adjust frequency as needed
                sampler.save_state(checkpoint_file)
                if results_file:
                    import pickle
                    with open(results_file, 'wb') as f:
                        pickle.dump(results, f)
                log.info(f"Checkpoint saved at sample {successful_samples}")
            
        except Exception as e:
            log.error(f"Error in evaluation loop: {e}", exc_info=True)
            retries += 1
            continue
    
    ### 5. Final checkpoint save ###
    if checkpoint_dir and checkpoint_file:
        sampler.save_state(checkpoint_file)
        if results_file:
            import pickle
            with open(results_file, 'wb') as f:
                pickle.dump(results, f)
        log.info(f"Final checkpoint saved")
    
    ### 6. Print summary ###
    log.info(f"\n{'='*60}")
    log.info("Evaluation complete!")
    log.info(f"Successful samples: {successful_samples}/{num_samples}")
    if results['metrics']:
        avg_metric = sum(results['metrics']) / len(results['metrics'])
        max_metric = max(results['metrics'])
        min_metric = min(results['metrics'])
        log.info(f"Metric statistics:")
        log.info(f"  Average: {avg_metric:.4f}")
        log.info(f"  Min: {min_metric:.4f}")
        log.info(f"  Max: {max_metric:.4f}")
    
    return results


def create_mab_sampler(param_domain: dict, params: dict):
    """Create a Multi-Armed Bandit sampler for multi-objective optimization."""
    return MultiArmedBanditSampler(
        param_domain,
        alpha=params.get('alpha', 0.1),
        thres=params.get('thres', 0.5),
        buckets=params.get('buckets', 10),
        exploration_ratio=params.get('exploration_ratio', 2.0)
    )


def create_scenario_with_params(scenic_file_path: str, params: dict):
    """
    Create a Scenic scenario with concrete parameter values.
    
    Since VerifaiRange is a distribution used in behavior constructors (not a global param),
    we need to replace it with concrete values. We do this by:
    1. Reading the .scenic file
    2. Replacing VerifaiRange calls with concrete values
    3. Compiling the modified scenario
    
    For example:
        forwardSpeed=VerifaiRange(50, 100) -> forwardSpeed=75.0
    """
    import re
    import tempfile
    
    # Read the original scenario file
    with open(scenic_file_path, 'r') as f:
        content = f.read()
    
    modified_content = content
    
    # Replace VerifaiRange calls with concrete values for each parameter
    # Pattern matches: param_name=VerifaiRange(low, high) or param_name=VerifaiRange(...)
    # Handles spaces around = and different formatting
    for param_name, param_value in params.items():
        # Match: param_name = VerifaiRange(...) or param_name=VerifaiRange(...)
        # The pattern captures the parameter name and replaces the entire VerifaiRange call
        pattern = rf'({param_name})\s*=\s*VerifaiRange\([^)]+\)'
        replacement = rf'\1={param_value}'
        modified_content = re.sub(pattern, replacement, modified_content)
        
        # Verify replacement happened (warn if not found)
        if pattern in content and replacement not in modified_content:
            log.warning(f"Could not find pattern to replace for parameter {param_name}")
    
    # Write to temporary file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.scenic', delete=False, encoding='utf-8')
    temp_file.write(modified_content)
    temp_file.close()
    
    try:
        # Compile the modified scenario
        scenario = scenic.scenarioFromFile(temp_file.name, mode2D=True)
        return scenario
    except Exception as e:
        log.error(f"Failed to compile modified scenario: {e}")
        log.debug(f"Modified content:\n{modified_content}")
        raise
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file.name)
        except:
            pass


def run_webots_simulation(scenario, webots_world_path: str, params: dict):
    """
    Run Webots simulation with given parameters.
    
    TODO: Implement Webots simulation execution
    Options:
    1. Use subprocess to launch Webots in headless mode
    2. Use Webots Python API directly
    3. Use Scenic's WebotsSimulator if available externally
    
    Returns:
        dict: Simulation results (trajectory, metrics, etc.)
    """
    # Placeholder implementation
    log.warning("run_webots_simulation not yet implemented")
    
    # Expected return format:
    return {
        'trajectory': [],  # List of (x, y, heading) tuples over time
        'waypoints_reached': [],  # Which waypoints were reached
        'final_position': None,
        'duration': None,
        'success': False
    }


def run_pololu_hardware(params: dict):
    """
    Run real Pololu robot with given parameters.
    
    TODO: Implement hardware interface
    Options:
    1. Use BLE interface to send commands to robot
    2. Use motion capture system to track position
    3. Record trajectory data
    
    Returns:
        dict: Hardware results (trajectory, metrics, etc.)
    """
    # Placeholder implementation
    log.warning("run_pololu_hardware not yet implemented")
    
    # Expected return format:
    return {
        'trajectory': [],  # List of (x, y, heading) tuples over time
        'waypoints_reached': [],  # Which waypoints were reached
        'final_position': None,
        'duration': None,
        'success': False
    }


def compute_multi_objective_metric(sim_result: dict, hardware_result: dict):
    """
    Compute multi-objective metric comparing simulation and hardware results.
    
    This function aggregates three objectives for sim-to-real gap analysis:
    1. Trajectory out of bounds: Binary penalty if hardware trajectory goes out of bounds
    2. Trajectory difference: Continuous metric quantifying path difference (e.g., DTW distance)
    3. Waypoint timing difference: Continuous metric for timing differences at waypoints
    
    The metric should be normalized to [0, 1] range where:
    - Lower values = simulation and hardware are more similar (good digital twin)
    - Higher values = larger sim-to-real gap (bad digital twin, what we want to find)
    
    NOTE: This function should be implemented to compute the actual metrics.
    For now, returns a placeholder value.
    
    Args:
        sim_result: Simulation results dictionary containing:
            - 'trajectory': List of (x, y, heading) tuples over time
            - 'waypoint_times': List of times when waypoints were reached
            - 'out_of_bounds': Boolean indicating if trajectory went out of bounds
        hardware_result: Hardware results dictionary with same structure
    
    Returns:
        float: Aggregated multi-objective metric in [0, 1] range
    """
    # TODO: Implement multi-objective metric computation
    # This should aggregate the three objectives:
    # 1. Check if hardware trajectory is out of bounds
    # 2. Compute trajectory difference (DTW, Euclidean, etc.)
    # 3. Compute waypoint timing differences
    
    # Placeholder: return maximum error if data is missing
    if not sim_result.get('trajectory') or not hardware_result.get('trajectory'):
        log.warning("Missing trajectory data, returning maximum error")
        return 1.0
    
    # Placeholder implementation - should be replaced with actual multi-objective aggregation
    # Example structure:
    #   out_of_bounds_penalty = 1.0 if hardware_result.get('out_of_bounds') else 0.0
    #   traj_diff = compute_trajectory_difference(sim_result['trajectory'], hardware_result['trajectory'])
    #   timing_diff = compute_waypoint_timing_difference(sim_result['waypoint_times'], hardware_result['waypoint_times'])
    #   aggregated = weights['bounds'] * out_of_bounds_penalty + weights['traj'] * traj_diff + weights['timing'] * timing_diff
    
    log.warning("compute_multi_objective_metric using placeholder - implement actual computation")
    return 0.5  # Placeholder


if __name__ == "__main__":
    # Example usage
    scenic_file = os.path.join(ROOT.parent, "pololu_verifai.scenic")
    webots_world = os.path.join(ROOT.parent, "webots_data/worlds/pololu_verifai.wbt")
    checkpoint_dir = os.path.join(ROOT, "checkpoints")
    
    results = run_robotics_evaluation(
        scenic_file_path=scenic_file,
        num_samples=10,  # Start with small number for testing
        sampler_params={
            'alpha': 0.1,
            'thres': 0.5,
            'buckets': 10,
            'exploration_ratio': 2.0
        },
        webots_world_path=webots_world,
        max_retries=5,
        checkpoint_dir=checkpoint_dir,
        resume_from_checkpoint=False,  # Set to True to resume from checkpoint
        start_sample_num=0,
        pause_before_hardware=True  # Pause before each hardware run
    )
    
    print("\nEvaluation complete!")
    print(f"Processed {len(results['samples'])} samples")

