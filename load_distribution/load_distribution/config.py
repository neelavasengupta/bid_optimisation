"""Configuration for load distribution optimization system."""

from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Mill equipment specifications (used in load calculations)
MILL_CONFIG = {
    # Power consumption (MW)
    "paper_machines": 12.0,        # Constant load
    "critical_systems": 1.3,       # Constant load
    "pulper_base": 6.0,            # At 100% speed (cubic law applies)
    "compressor_unit": 1.0,        # Per compressor
    "wastewater": 1.5,             # When running
    
    # Production parameters
    "pulp_consumption_rate": 5.0,  # MW equivalent - paper machines consume continuously
    "pulper_speeds": [0, 60, 100, 120],  # Allowed speed percentages
    
    # Baseline for comparison
    "baseline_load": 22.8,         # MW - typical constant operation
    "default_initial_load": 20.0,  # MW - assumed starting load for ramp rate constraint
    
    # Time and conversion factors
    "period_duration": 0.5,        # Hours per optimization period (30 minutes)
    "tons_per_mwh": 10.0,          # Mill-specific conversion: pulp production
}

# Optimization solver parameters
OPTIMIZATION_CONFIG = {
    # Solver settings
    "solver_time_limit": 60,       # Seconds - max time for solver
    "mip_gap": 0.01,               # 1% - acceptable optimality gap
    
    # Production target penalties ($/ton)
    "overproduction_penalty": 100.0,   # Cost for producing above target
    "underproduction_penalty": 200.0,  # Cost for producing below target (higher priority)
}
