# NZ Electricity Price Prediction

Predicts electricity clearing prices at 244 locations across New Zealand up to 48 hours ahead (96 half-hourly periods) using machine learning to optimize bidding strategies in the NZ electricity market.

## Features

- **Temporal Fusion Transformer (TFT)** model for time series forecasting
- **Probabilistic forecasts** with uncertainty quantification (P10, P50, P90)
- **15 features**: time patterns, weather forecasts, location characteristics
- **244 locations** across New Zealand
- **48-hour horizon** (96 half-hourly periods)
- **Integrated with load optimizer** for automated bidding

## Installation

```bash
# Install dependencies
uv sync

# Verify installation
uv run python -m price_prediction.predict --help
```

## Quick Start

Generate 48-hour forecast for a location:

```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --locations HAY2201
```

**Note**: This is a backtesting system that requires actual future data in `ground_truth.csv` for the forecast period.

---

## Workflow

### 1. Download Data
```bash
# Download clearing prices (required)
uv run python download_clearing_prices.py

# Download bid data (optional)
uv run python download_bid_data.py
```

### 2. Prepare Training Data
```bash
uv run python -m price_prediction.prepare_data
```
Creates `evaluation/ground_truth.csv` and `evaluation/static_features.csv`

### 3. Train Model
```bash
uv run python -m price_prediction.train
```
Trains AutoGluon TimeSeriesPredictor (90 minutes, saves to `models/price_predictor/`)

### 4. Evaluate Model
```bash
uv run python -m price_prediction.evaluate
```
Generates comprehensive report in `evaluation/report/EVALUATION_REPORT.md`

### 5. Generate Predictions
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --locations HAY2201
```

---

## Command-Line Options

### Required
- `--date` - Forecast start date (YYYY-MM-DD)

### Optional
- `--time` - Start time (HH:MM), default: 00:00
- `--hours` - Forecast hours (1-48), default: 48
- `--context-days` - Historical context days (1-365), default: 60
- `--locations` - Specific location IDs (can specify multiple), default: all
- `--output` - Save predictions to CSV file

Run `uv run python -m price_prediction.predict --help` for complete list.

---

## Demo Commands

All demos use **HAY2201** (Haywards - major North Island transmission hub). Data available: March 7, 2024 to March 6, 2026.

### 1. Basic 48-Hour Forecast
```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --locations HAY2201
```
Default 60 days context, summer conditions

### 2. Morning Peak (6-9 AM)
```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --time 06:00 \
  --hours 6 \
  --locations HAY2201
```
Captures morning demand ramp-up, highest volatility

### 3. Evening Peak (5-8 PM)
```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --time 17:00 \
  --hours 5 \
  --locations HAY2201
```
Captures evening peak demand

### 4. Long Context (90 Days)
```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --context-days 90 \
  --hours 24 \
  --locations HAY2201
```
More historical data, captures seasonal patterns

### 5. Winter High Demand
```bash
uv run python -m price_prediction.predict \
  --date 2025-07-15 \
  --time 06:00 \
  --hours 24 \
  --locations HAY2201
```
Winter morning peak, higher demand and volatility

### 6. Summer Low Demand
```bash
uv run python -m price_prediction.predict \
  --date 2025-01-15 \
  --time 12:00 \
  --hours 24 \
  --locations HAY2201
```
Typical summer conditions, lower demand, stable prices

### 7. Extreme Price Event
```bash
uv run python -m price_prediction.predict \
  --date 2025-05-07 \
  --time 10:00 \
  --hours 8 \
  --locations HAY2201
```
Extreme price spike (Max $10,541/MWh), tests uncertainty quantification

### 8. Save to File
```bash
uv run python -m price_prediction.predict \
  --date 2025-06-01 \
  --hours 24 \
  --locations HAY2201 \
  --output forecast_june1.csv
```
Saves predictions with all quantiles and actual prices

---

## Model Performance

**Overall Metrics (21-day holdout)**:
- MAE: $53.32/MWh (19% error)
- R²: 75% (explains most price variation)
- Bias: Nearly unbiased
- Volatility capture: 78% of actual market swings

**Works Well On**:
- Typical prices ($150-$300, 87% of data): MAE $53/MWh
- Mid-day hours (11am-3pm): Stable, predictable
- Days 1-5: Most reliable forecasts
- Locations near generation hubs

**Struggles With**:
- Extreme prices (>$300): MAE jumps significantly
- Morning/evening peaks: Highest volatility
- Grid edge locations: Higher errors
- Days 6-14: Forecast degradation

See `evaluation/report/EVALUATION_REPORT.md` for detailed analysis.

---

## Understanding the Output

Each prediction shows:

1. **Forecast Summary**: Date range, locations, periods, mean price, price range
2. **Data Used**: Historical context, future covariates, features included
3. **Forecast Table**: Timestamp, actual price, predicted price, error, P10/P90 quantiles, uncertainty
4. **Visualization**: ASCII chart showing actual vs predicted prices
5. **Performance Metrics**: MAE, RMSE for the forecast period

**Interpreting Uncertainty**:
- **P10**: 10th percentile (conservative low estimate)
- **P50**: Median prediction (most likely)
- **P90**: 90th percentile (conservative high estimate)
- **Uncertainty**: P90 - P10 spread (wider = less confident)

---

## Key Insights

### Time-of-Day Patterns
- **Morning peak (7-9am)**: Highest prices, highest volatility
- **Mid-day (11am-3pm)**: Most stable, best predictions
- **Evening peak (5-8pm)**: High prices, moderate volatility
- **Night (10pm-6am)**: Lowest prices, very stable

### Seasonal Patterns
- **Winter (Jun-Aug)**: Highest prices ($400-500/MWh peaks), 3.6x summer
- **Summer (Dec-Feb)**: Lowest prices ($15-25/MWh), most stable
- **Shoulder (Mar-May, Sep-Nov)**: Moderate prices, transitional

### Location Patterns
- **North Island hubs** (HAY2201, OTA2201): Lower volatility
- **South Island** (BEN2201): Higher volatility, transmission constraints
- **Grid edges**: Highest volatility, worst predictions

### Forecast Horizon
- **Hours 1-12**: Most reliable
- **Hours 13-24**: Good reliability
- **Hours 25-48**: Degrading reliability

---

## Production Recommendations

1. **Use P90 for conservative bidding** - Protects against underestimation
2. **Add 20-30% margins for high-price forecasts** - Model underestimates extremes
3. **Re-forecast daily** - Don't rely on day-old forecasts
4. **Override during weather events** - Model struggles with extreme conditions
5. **Focus on days 1-5** - Reliability drops significantly after day 5
6. **Location-specific corrections** - Apply adjustments for high-volatility sites

---

## Project Structure

```
price_prediction/
├── price_prediction/          # Source code
│   ├── config.py             # Configuration
│   ├── prepare_data.py       # Data preparation
│   ├── train.py              # Model training
│   ├── evaluate.py           # Model evaluation & reporting
│   └── predict.py            # Generate predictions
├── evaluation/               # Data & evaluation outputs
│   ├── ground_truth.csv      # Training data
│   ├── static_features.csv   # Location metadata
│   └── report/               # Evaluation reports & plots
├── models/                   # Trained models
│   └── price_predictor/      # AutoGluon model
├── download_clearing_prices.py  # Data download script
├── download_bid_data.py         # Bid data download script
└── README.md                 # This file
```

---

## Technology Stack

- **AutoGluon 1.5.0**: TimeSeriesPredictor
- **Model**: Temporal Fusion Transformer (TFT)
- **Features**: 15 covariates (time + weather + location)
- **Horizon**: 96 periods (48 hours, half-hourly)
- **Training**: 90 minutes on 2 years of data (8.2M observations)

---

## Tips for Demos

- **Consistent location**: Use HAY2201 for reliable results
- **Data range**: Use dates between 2024-03-07 and 2026-03-06
- **Better context**: Use `--context-days 90` for seasonal patterns
- **Peak hours**: Focus on 6-9 AM and 5-8 PM for highest volatility
- **Save results**: Always use `--output` for important forecasts
- **Check uncertainty**: Wide P10-P90 spread indicates low confidence
