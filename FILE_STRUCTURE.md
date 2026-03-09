# File Structure and Path References

This document maps key files and their dependencies to help understand the project structure.

## Data Dependencies

### Analysis Module
- **analysis/clearing_price_analysis.py**
  - Reads: `data/raw/clearings/*.csv` (clearing price files)
  - Writes: `analysis/outputs/clearing_fig*.png`, `analysis/outputs/clearing_price_summary.json`
  - Referenced by: `analysis/Complete_Analysis.md`

### Price Prediction Module
- **price_prediction/download_bid_data.py**
  - Downloads to: `data/raw/bids/*.csv`
  
- **price_prediction/download_clearing_prices.py**
  - Downloads to: `data/raw/clearings/*.csv`

- **price_prediction/price_prediction/prepare_data.py**
  - Reads: `data/raw/clearings/*.csv`, `data/weather/weather_all_locations.csv`
  - Writes: `price_prediction/evaluation/ground_truth.csv`, `price_prediction/evaluation/static_features.csv`

- **price_prediction/price_prediction/train.py**
  - Reads: `price_prediction/evaluation/ground_truth.csv`
  - Writes: `price_prediction/models/price_predictor/` (trained model)

- **price_prediction/price_prediction/predict.py**
  - Reads: `price_prediction/models/price_predictor/` (trained model)
  - Reads: `price_prediction/evaluation/ground_truth.csv` (for context data)
  - Outputs: Predictions to stdout or file

- **price_prediction/price_prediction/evaluate.py**
  - Reads: `price_prediction/models/price_predictor/` (trained model)
  - Reads: `price_prediction/evaluation/ground_truth.csv`
  - Reads: `data/weather/weather_all_locations.csv`
  - Writes: `price_prediction/evaluation/report/*.png`, `price_prediction/evaluation/report/EVALUATION_REPORT.md`

### Load Distribution Module
- **load_distribution/load_distribution/optimizer.py**
  - Reads: Price predictions (from price_prediction module via CLI)
  - Writes: Optimization results to stdout

## Path Configuration Files

All paths are configured in these files:

1. **price_prediction/price_prediction/config.py**
   - `DATA_DIR`: `price_prediction/evaluation/`
   - `MODEL_DIR`: `price_prediction/models/`
   - `REPORT_DIR`: `price_prediction/evaluation/report/`
   - `WEATHER_DATA_FILE`: `data/weather/weather_all_locations.csv`
   - `GROUND_TRUTH_FILE`: `price_prediction/evaluation/ground_truth.csv`
   - `STATIC_FEATURES_FILE`: `price_prediction/evaluation/static_features.csv`
   - `MODEL_PATH`: `price_prediction/models/price_predictor/`

2. **load_distribution/load_distribution/config.py**
   - `DATA_DIR`: `load_distribution/data/`
   - `OUTPUT_DIR`: `load_distribution/outputs/`

3. **analysis/clearing_price_analysis.py**
   - `DATA_DIR`: `data/raw/clearings/`
   - `OUTPUT_DIR`: `analysis/outputs/`

## Data Not in Repository

The following directories are excluded via `.gitignore`:
- `data/` - All raw data files (5.3GB)
- `models/` - Trained models (large binary files)
- `.venv/` - Python virtual environments

To set up data:
1. Run `price_prediction/download_clearing_prices.py` to download clearing prices
2. Run `price_prediction/download_bid_data.py` to download bid data (optional)
3. Download weather data separately (not automated)

## Workflow

```
1. Download Data
   ├── download_clearing_prices.py → data/raw/clearings/
   └── download_bid_data.py → data/raw/bids/

2. Prepare Training Data
   └── prepare_data.py → evaluation/ground_truth.csv

3. Train Model
   └── train.py → models/price_predictor/

4. Evaluate Model
   └── evaluate.py → evaluation/report/

5. Make Predictions
   └── predict.py (uses trained model)

6. Optimize Load Distribution
   └── load_distribution CLI (uses predictions)
```

## Important Notes

- All paths use `Path(__file__).parent` for relative resolution
- No hardcoded absolute paths
- Data directory structure must match expected layout
- Models directory is created automatically during training
