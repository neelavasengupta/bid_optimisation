# Load Distribution Optimizer - CLI Reference

Complete reference for all command-line options.

## Basic Usage

```bash
uv run python -m load_distribution.cli optimize [OPTIONS]
```

## Required Options

### `--location` (required)
- **Type**: String
- **Example**: `HAY2201`, `BEN2201`, `OTA2201`
- **Description**: NZ electricity market location ID where the mill is located
- **Impact**: Different locations have different price patterns

## Forecasting Options

### `--date`
- **Type**: String (YYYY-MM-DD)
- **Default**: `2024-03-07`
- **Example**: `2024-04-01`
- **Description**: Start date for price forecast and optimization
- **Impact**: Determines which historical data is used for forecasting

### `--time`
- **Type**: String (HH:MM)
- **Default**: `00:00`
- **Example**: `14:30`
- **Description**: Start time for price forecast and optimization
- **Impact**: Optimization starts from this time of day

### `--forecast-horizon`
- **Type**: Integer (hours)
- **Default**: `48`
- **Range**: 1-168 hours
- **Example**: `24`
- **Description**: How many hours ahead to forecast and optimize
- **Impact**: Longer horizons allow better planning but take more time to solve

### `--context-days`
- **Type**: Integer (days)
- **Default**: `60`
- **Range**: 1-365 days
- **Example**: `90`
- **Description**: Days of historical data used by price prediction model
- **Impact**: More context can improve forecast accuracy but increases computation time

## Mill State Options

### `--current-inventory`
- **Type**: Float (hours)
- **Default**: `5.0`
- **Range**: 2.0-8.0 hours
- **Example**: `4.5`
- **Description**: Current pulp inventory level in hours of production
- **Impact**: Starting point for inventory optimization

### `--current-load`
- **Type**: Float (MW)
- **Default**: `22.8`
- **Range**: 15.6-28.2 MW
- **Example**: `20.0`
- **Description**: Current mill power consumption
- **Impact**: Starting point for load optimization (affects ramp rate constraints)

### `--production-today`
- **Type**: Float (tons)
- **Default**: `0.0`
- **Example**: `150.0`
- **Description**: Tons of paper already produced today
- **Impact**: Affects remaining production target for the day

## Production Constraints

### `--production-target`
- **Type**: Float (tons/day)
- **Default**: `500.0`
- **Range**: 0-600 tons/day (max capacity with 120% pulper speed)
- **Example**: `200.0`, `400.0`, `600.0`
- **Description**: Daily production target in tons
- **Impact**: 
  - Lower target = more flexibility = higher savings
  - Higher target = less flexibility = lower savings
  - Determines minimum average pulper speed
  - Maximum 600 tons/day (requires 120% pulper continuously)
  - Maximum 500 tons/day if `--allow-pulper-120 false`

### `--allow-pulper-60`
- **Type**: Boolean
- **Default**: `true`
- **Example**: `false`
- **Description**: Allow pulper to run at 60% speed (conservation mode)
- **Impact**: 
  - `true`: Can reduce load during high prices
  - `false`: Less flexibility, potentially lower savings

### `--allow-pulper-120`
- **Type**: Boolean
- **Default**: `true`
- **Example**: `false`
- **Description**: Allow pulper to run at 120% speed (high production mode)
- **Impact**: 
  - `true`: Can increase production during low prices
  - `false`: Less flexibility, potentially lower savings

## Storage Constraints

### `--min-inventory`
- **Type**: Float (hours)
- **Default**: `2.0`
- **Example**: `3.0`, `4.0`
- **Description**: Minimum pulp inventory level (safety buffer)
- **Impact**: 
  - Lower = more flexibility to reduce production during high prices
  - Higher = safer but less optimization flexibility

### `--max-inventory`
- **Type**: Float (hours)
- **Default**: `8.0`
- **Example**: `6.0`, `10.0`
- **Description**: Maximum pulp inventory level (tank capacity)
- **Impact**: 
  - Higher = more flexibility to build inventory during low prices
  - Lower = less storage capacity for load shifting

## Equipment Constraints

### `--min-load`
- **Type**: Float (MW)
- **Default**: `15.6`
- **Example**: `16.0`
- **Description**: Minimum mill power consumption (equipment constraints)
- **Impact**: Lower bound on how much load can be reduced

### `--max-load`
- **Type**: Float (MW)
- **Default**: `28.2`
- **Example**: `30.0`
- **Description**: Maximum mill power consumption (equipment capacity)
- **Impact**: Upper bound on how much load can be increased

### `--min-compressors`
- **Type**: Integer
- **Default**: `1`
- **Range**: 1-3
- **Example**: `2`
- **Description**: Minimum number of compressors that must be running
- **Impact**: 
  - Higher = higher base load = less flexibility
  - Lower = more flexibility to reduce load

## Operational Constraints

### `--ramp-rate`
- **Type**: Float (MW/min)
- **Default**: `0.5`
- **Example**: `0.3`, `1.0`
- **Description**: Maximum rate of load change (grid stability requirement)
- **Impact**: 
  - Lower = slower response to price changes
  - Higher = faster response but may stress equipment

### `--wastewater-frequency`
- **Type**: Integer (hours)
- **Default**: `4`
- **Example**: `2`, `8`
- **Description**: Wastewater pump must run at least once every N hours
- **Impact**: 
  - Lower = more frequent runs = higher costs
  - Higher = less frequent runs = more flexibility

## Output Options

### `--output`
- **Type**: File path
- **Default**: None (display only)
- **Example**: `schedule.csv`
- **Description**: Save optimized schedule to CSV file
- **Impact**: Allows saving results for further analysis

## Example Commands

### Minimal (uses all defaults)
```bash
uv run python -m load_distribution.cli optimize --location HAY2201
```

### Typical usage
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --forecast-horizon 24
```

### Low production scenario
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --production-target 200
```

### Maximum production scenario
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --production-target 600
```

### Constrained operation
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --min-inventory 4.0 \
  --max-inventory 6.0 \
  --allow-pulper-60 false
```

### Save results
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --output optimized_schedule.csv
```

## Understanding the Output

The CLI displays:

1. **Optimization Configuration**: Shows all constraint settings
2. **Price Forecasting**: Progress and results from prediction engine
3. **Optimization Results**: Total cost, baseline cost, savings percentage
4. **Metrics**: Load ranges, inventory ranges, production totals
5. **Schedule Sample**: First 12 periods showing equipment settings

## Tips

- Start with defaults to understand baseline behavior
- Adjust one constraint at a time to see its impact
- Lower production targets generally yield higher savings
- Wider inventory ranges provide more optimization flexibility
- Compare different dates to see seasonal price pattern effects
