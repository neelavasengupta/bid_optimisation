# Price Prediction Demo Commands

Useful command variations to showcase the forecasting system.

**Note:** All demos use HAY2201 (Haywards - major North Island transmission hub) for consistency. Data available from March 7, 2024 to March 6, 2026.

## Basic Usage

### 1. Simple 48-hour forecast (default)
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --locations HAY2201
```
- Uses default 60 days of context
- 48 hours ahead (96 periods)
- Summer conditions

### 2. Specific time of day - afternoon peak
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --time 14:30 --hours 12 --locations HAY2201
```
- Starts forecast at 2:30 PM
- 12-hour forecast (24 periods)
- Captures afternoon/evening demand

### 3. Morning peak hours
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --time 06:00 --hours 6 --locations HAY2201
```
- Captures morning demand ramp-up (6 AM - 12 PM)
- 6-hour forecast

### 4. Evening peak hours
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --time 17:00 --hours 5 --locations HAY2201
```
- Captures evening peak demand (5 PM - 10 PM)
- 5-hour forecast

## Context Variations

### 5. Short context (30 days)
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 30 --hours 24 --locations HAY2201
```
- Uses only 1 month of history
- Faster execution
- More responsive to recent patterns

### 6. Long context (90 days)
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 90 --hours 24 --locations HAY2201
```
- Uses 3 months of history
- Captures seasonal patterns
- More stable predictions

## Interesting Dates & Events

### 7. High volatility day (Dec 12, 2024)
```bash
uv run python -m price_prediction.predict --date 2024-12-12 --time 08:00 --hours 12 --locations HAY2201
```
- Extreme price volatility day
- Mean: $2,673/MWh, Max: $4,559/MWh
- Tests model on extreme conditions

### 8. Price spike event (May 7, 2025)
```bash
uv run python -m price_prediction.predict --date 2025-05-07 --time 10:00 --hours 8 --locations HAY2201
```
- Extreme price spike: Max $10,541/MWh
- Rare event testing
- Shows uncertainty quantification

### 9. Summer day - low demand (Jan 15, 2025)
```bash
uv run python -m price_prediction.predict --date 2025-01-15 --time 12:00 --hours 24 --locations HAY2201
```
- Typical summer conditions
- Lower demand, stable prices
- Good baseline performance

### 10. Winter day - high demand (July 15, 2025)
```bash
uv run python -m price_prediction.predict --date 2025-07-15 --time 06:00 --hours 24 --locations HAY2201
```
- Winter morning peak
- Higher demand, price volatility
- Tests cold weather patterns

### 11. Autumn transition (April 15, 2025)
```bash
uv run python -m price_prediction.predict --date 2025-04-15 --time 00:00 --hours 48 --locations HAY2201
```
- Seasonal transition period
- Moderate demand
- Stable pricing patterns

### 12. Spring conditions (October 15, 2024)
```bash
uv run python -m price_prediction.predict --date 2024-10-15 --time 00:00 --hours 48 --locations HAY2201
```
- Spring weather patterns
- Moderate demand
- Good for baseline testing

## Save Output

### 13. Save predictions to file
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --hours 24 --locations HAY2201 --output forecast_haywards_june1.csv
```
- Saves predictions to CSV
- Easy to analyze in Excel/Python
- Includes all quantiles and actual prices

### 14. Full 48-hour forecast with output
```bash
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 90 --locations HAY2201 --output full_forecast_june1.csv
```
- 48-hour forecast
- 90 days context
- Saved to CSV

## Quick Comparisons

### 15. Compare context lengths (same date)
```bash
# 30 days
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 30 --locations HAY2201

# 60 days (default)
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 60 --locations HAY2201

# 90 days
uv run python -m price_prediction.predict --date 2025-06-01 --context-days 90 --locations HAY2201
```

### 16. Compare different times of day
```bash
# Morning
uv run python -m price_prediction.predict --date 2025-06-01 --time 06:00 --hours 6 --locations HAY2201

# Afternoon
uv run python -m price_prediction.predict --date 2025-06-01 --time 14:00 --hours 6 --locations HAY2201

# Evening
uv run python -m price_prediction.predict --date 2025-06-01 --time 18:00 --hours 6 --locations HAY2201
```

### 17. Compare seasons (same time, different dates)
```bash
# Summer (January)
uv run python -m price_prediction.predict --date 2025-01-15 --time 12:00 --hours 12 --locations HAY2201

# Autumn (April)
uv run python -m price_prediction.predict --date 2025-04-15 --time 12:00 --hours 12 --locations HAY2201

# Winter (July)
uv run python -m price_prediction.predict --date 2025-07-15 --time 12:00 --hours 12 --locations HAY2201

# Spring (October)
uv run python -m price_prediction.predict --date 2024-10-15 --time 12:00 --hours 12 --locations HAY2201
```

## Pro Tips

- **Consistent location**: All demos use HAY2201 for reliable results
- **Data range**: Use dates between 2024-03-07 and 2026-03-06
- **Better context**: Use `--context-days 90` for seasonal patterns
- **Peak hours**: Focus on 6-9 AM and 5-8 PM for highest volatility
- **Save results**: Always use `--output` for important forecasts
- **Uncertainty**: Check P10-P90 spread and "Uncert." column to gauge prediction confidence
- **Error analysis**: Green errors (<$5) are good, yellow (<$20) acceptable, red (≥$20) need investigation

## About HAY2201 (Haywards)

- **Location**: Haywards, Lower Hutt (Wellington region)
- **Type**: Major transmission hub in North Island
- **Significance**: Key interconnection point for North Island grid
- **Data Quality**: Complete coverage across entire dataset
- **Price Characteristics**: Reflects North Island wholesale market dynamics

