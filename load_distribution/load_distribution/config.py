"""Configuration for load distribution optimization system."""

from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Mill configuration
MILL_CONFIG = {
    "paper_machines": 12.0,
    "critical_systems": 1.3,
    "pulper_base": 6.0,
    "compressor_unit": 1.0,
    "wastewater": 1.5,
    "min_load": 15.6,
    "max_load": 28.2,
    "normal_load": 22.8,
    "pulper_speeds": [60, 100, 120],
    "storage_min": 2.0,
    "storage_max": 8.0,
    "storage_target": 5.0,
    "ramp_rate": 0.5,
    "production_target": 500,
    "pulp_consumption_rate": 5.0,
}

# Price thresholds
PRICE_THRESHOLDS = {
    "cheap": 150,
    "expensive": 200,
    "extreme": 300,
}

# Optimization parameters
OPTIMIZATION_CONFIG = {
    "forecast_horizon": 48,
    "time_step": 0.5,
    "solver": "PULP_CBC_CMD",
    "solver_time_limit": 60,
    "mip_gap": 0.01,
}
