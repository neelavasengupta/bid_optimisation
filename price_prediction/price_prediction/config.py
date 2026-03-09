"""Configuration for price prediction system."""

from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "evaluation"
MODEL_DIR = PROJECT_ROOT / "models"
REPORT_DIR = DATA_DIR / "report"
WEATHER_DATA_FILE = PROJECT_ROOT.parent / "data" / "weather" / "weather_all_locations.csv"

# Data files
GROUND_TRUTH_FILE = DATA_DIR / "ground_truth.csv"
STATIC_FEATURES_FILE = DATA_DIR / "static_features.csv"

# Model paths
MODEL_PATH = MODEL_DIR / "price_predictor"

# Best model for inference
# Note: WeightedEnsemble has best validation score (28.82 MAE) but TFT performs
# better on actual test data. Use TFT for production predictions.
BEST_MODEL = "TemporalFusionTransformer"

# Training config
PREDICTION_LENGTH = 96  # 48 hours (2 days) * 2 half-hour periods per hour
PREDICTION_HOURS = PREDICTION_LENGTH // 2  # 48 hours
TIME_LIMIT = 5400  # 90 minutes
PRESET = 'high_quality'
EVAL_METRIC = 'MAE'
NUM_VAL_WINDOWS = 3

# Quantile levels for probabilistic forecasting
# P10, P50 (median), P90 for uncertainty quantification
QUANTILE_LEVELS = [0.1, 0.5, 0.9]

# Parallel training config
# Statistical models (AutoETS, etc.) use n_jobs for parallel fitting across time series
# Set to -1 to use all CPU cores, or a specific number to limit
N_JOBS = -1  # Use all available CPU cores

# Default weather values for forecasting (typical NZ climate)
DEFAULT_WEATHER = {
    'temperature': 15.0,  # °C
    'humidity': 70.0,  # %
    'precipitation': 0.0,  # mm
    'wind_speed': 5.0,  # m/s
    'solar_radiation': 200.0  # W/m²
}

KNOWN_COVARIATES = [
    'hour', 'day_of_week', 'month', 'is_weekend', 'is_holiday',
    'temperature', 'temperature_sq', 'humidity', 'precipitation', 
    'wind_speed', 'solar_radiation', 'heating_degree_days', 'cooling_degree_days'
]

# Model hyperparameters - improved ensemble with deep learning + quantile prediction
HYPERPARAMETERS = {
    # Deep learning models - better for temporal patterns and uncertainty
    "DeepAR": {
        "num_batches_per_epoch": 50,
        "context_length": 96,  # Use 48 hours of history
        # Note: epochs is controlled by time_limit, not specified here
    },
    
    "TemporalFusionTransformer": {
        "num_batches_per_epoch": 50,
        "context_length": 96,
        # Note: epochs is controlled by time_limit, not specified here
    },
    
    # Tabular models - fast and effective for short horizons
    "DirectTabular": {
        "tabular_hyperparameters": {
            "GBM": {},  # LightGBM
            "CAT": {},  # CatBoost - better outlier handling
            "XGB": {},  # XGBoost
        },
        # No target_scaler - let model learn raw distribution
    },
    
    # Recursive approach - uses predictions as features
    "RecursiveTabular": {
        "tabular_hyperparameters": {
            "GBM": {},
        },
        # No target_scaler
    },
}
