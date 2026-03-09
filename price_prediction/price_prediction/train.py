"""Train price prediction model using AutoGluon TimeSeriesPredictor."""

import sys
import pandas as pd
from autogluon.timeseries import TimeSeriesDataFrame, TimeSeriesPredictor

from .config import (
    GROUND_TRUTH_FILE, MODEL_PATH, TIME_LIMIT, PRESET, EVAL_METRIC, 
    NUM_VAL_WINDOWS, KNOWN_COVARIATES, PREDICTION_LENGTH, HYPERPARAMETERS,
    QUANTILE_LEVELS
)


def train_model():
    """Train AutoML time series model with known covariates and static features."""
    
    print("\n" + "="*70, flush=True)
    print("     NZ ELECTRICITY PRICE PREDICTION - MODEL TRAINING", flush=True)
    print("="*70 + "\n", flush=True)
    
    if not GROUND_TRUTH_FILE.exists():
        print(f"✗ Training data not found: {GROUND_TRUTH_FILE}", flush=True)
        raise FileNotFoundError(f"Training data not found: {GROUND_TRUTH_FILE}")
    
    print("✓ Loading training data...", flush=True)
    df = pd.read_csv(GROUND_TRUTH_FILE)
    train_data = TimeSeriesDataFrame.from_data_frame(
        df,
        id_column='item_id',
        timestamp_column='timestamp'
    )
    
    # Load and attach static features
    static_file = GROUND_TRUTH_FILE.parent / "static_features.csv"
    if static_file.exists():
        static_features = pd.read_csv(static_file)
        static_features = static_features.set_index('item_id')
        train_data.static_features = static_features
        print(f"✓ Loaded static features for {len(static_features)} locations", flush=True)
    
    # Dataset summary
    date_range = f"{train_data.index.get_level_values('timestamp').min()} to {train_data.index.get_level_values('timestamp').max()}"
    
    print("\nDataset Summary:", flush=True)
    print(f"  Total Records: {len(train_data):,}", flush=True)
    print(f"  Locations: {train_data.num_items}", flush=True)
    print(f"  Date Range: {date_range}", flush=True)
    print(f"  Frequency: 30min (half-hourly)", flush=True)
    
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Create predictor with optimized model selection and quantile prediction
    predictor = TimeSeriesPredictor(
        prediction_length=PREDICTION_LENGTH,
        freq='30min',
        path=str(MODEL_PATH),
        target='target',
        eval_metric=EVAL_METRIC,
        known_covariates_names=KNOWN_COVARIATES,
        quantile_levels=QUANTILE_LEVELS  # Enable probabilistic forecasting
    )
    
    # Training configuration
    print("\nTraining Configuration:", flush=True)
    print(f"  Prediction Horizon: {PREDICTION_LENGTH} periods (2 days)", flush=True)
    print(f"  Quantile Levels: {QUANTILE_LEVELS} (P10, P50, P90 for uncertainty)", flush=True)
    print(f"  Known Covariates: {len(KNOWN_COVARIATES)} features", flush=True)
    print(f"    • Time: hour, day_of_week, month, is_weekend, is_holiday", flush=True)
    print(f"    • Weather: temperature, humidity, precipitation, wind_speed, solar_radiation", flush=True)
    print(f"    • Derived: temperature_sq, heating_degree_days, cooling_degree_days", flush=True)
    print(f"  Static Features: Island (NI/SI), PointOfConnection", flush=True)
    print(f"  Models: {', '.join(HYPERPARAMETERS.keys())}", flush=True)
    print(f"  Time Limit: {TIME_LIMIT}s ({TIME_LIMIT/60:.0f} minutes)", flush=True)
    print(f"  Validation: {NUM_VAL_WINDOWS}-window time series CV", flush=True)
    print(f"  Metric: {EVAL_METRIC} (Mean Absolute Error)", flush=True)
    print(f"  Parallel Training: Enabled (statistical models run in parallel)", flush=True)
    
    print("\n⚡ Starting model training...\n", flush=True)
    sys.stdout.flush()
    
    predictor.fit(
        train_data,
        hyperparameters=HYPERPARAMETERS,
        time_limit=TIME_LIMIT,
        num_val_windows=NUM_VAL_WINDOWS,
        enable_ensemble=True,
        verbosity=3
    )
    
    print("\n" + "="*70, flush=True)
    print("                    TRAINING COMPLETE!", flush=True)
    print("="*70 + "\n", flush=True)
    
    # Show validation leaderboard
    print("Validation Leaderboard (Internal CV):", flush=True)
    leaderboard = predictor.leaderboard()
    print(leaderboard, flush=True)
    
    # Evaluate on full dataset to get test scores
    print("\nEvaluating on full dataset...", flush=True)
    test_scores = predictor.evaluate(train_data)
    
    print("\nTest Scores:", flush=True)
    for metric, score in test_scores.items():
        print(f"  {metric}: {score:.4f}", flush=True)
    
    # Show leaderboard with test scores
    print("\nFull Leaderboard (with test scores):", flush=True)
    print(predictor.leaderboard(train_data), flush=True)
    
    print(f"\n✓ Model saved: {MODEL_PATH}", flush=True)
    
    return predictor


if __name__ == "__main__":
    train_model()
