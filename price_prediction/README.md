# NZ Electricity Price Prediction

Predicts electricity clearing prices at 244 locations across New Zealand for 14 days ahead (672 half-hourly periods) to optimize bidding strategies in the NZ electricity market.

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
└── main.py                   # Entry point
```

## Workflow

### 1. Prepare Data
```bash
uv run python -m price_prediction.prepare_data
```
Prepares training data with weather features and static location metadata.

### 2. Train Model
```bash
uv run python -m price_prediction.train
```
Trains AutoGluon TimeSeriesPredictor with:
- DirectTabular and RecursiveTabular models
- 13 known covariates (time + weather features)
- Static features (Island, PointOfConnection)
- 14-day forecast horizon (672 periods)
- 90-minute time limit

### 3. Evaluate Model
```bash
uv run python -m price_prediction.evaluate
```
Generates comprehensive evaluation report with:
- 7 detailed visualizations
- Performance metrics by time, location, price range
- Forecast horizon analysis
- Extreme price behavior analysis
- Actionable recommendations

Output: `evaluation/report/EVALUATION_REPORT.md` + plots

### 4. Generate Predictions
```bash
uv run python -m price_prediction.predict
```
Generates 14-day price forecasts for all 244 locations.

## Model Performance

**Overall Metrics:**
- MAE: $53.32/MWh
- RMSE: $69.27/MWh
- R²: -0.45
- Systematic bias: -$42.79/MWh (underestimation)

**Strengths:**
- Typical prices ($0-$150): Acceptable performance (87% of data)
- Days 1-5: Most reliable forecasts
- Mid-day hours (11am-3pm): Best performance

**Weaknesses:**
- Extreme prices (>$200): Catastrophic errors
- Morning peak (7-9am): MAE $85.61/MWh
- Volatility capture: Only 55% of actual
- Forecast degradation: +31.7% from day 1 to day 14

## Key Findings

1. **Systematic Underestimation**: Model underestimates by $42.79/MWh on average
2. **Extreme Price Failure**: Model "gives up" on prices >$200/MWh
3. **Time-of-Day Sensitivity**: Morning peaks show 2-3x worse performance
4. **Location Variability**: FHL0331 is worst (MAE $77.91), volatile locations struggle
5. **Horizon Degradation**: Reliability drops significantly after day 5

## Recommendations for Bidding

1. Apply +$42.79/MWh bias correction to all predictions
2. DO NOT trust predictions >$100/MWh without safety margins
3. Add +$30-40/MWh margin for morning peak hours (7-9am)
4. Focus optimization on days 1-5 only
5. Use location-specific corrections for high-volatility sites

See `evaluation/report/EVALUATION_REPORT.md` for detailed analysis and recommendations.

## Technology Stack

- **AutoGluon 1.5.0**: TimeSeriesPredictor with tabular models
- **Models**: DirectTabular (GBM, CAT, XGB) + RecursiveTabular
- **Features**: 13 known covariates + 2 static features
- **Horizon**: 672 periods (14 days, half-hourly)
