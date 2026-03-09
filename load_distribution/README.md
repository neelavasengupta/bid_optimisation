# Load Distribution Optimizer

MILP-based load distribution optimizer for paper mill operations. Integrates with the price prediction engine to optimize electricity consumption by scheduling flexible equipment loads based on forecasted prices while maintaining production targets and operational constraints.

## Features

- **Integrated Price Forecasting**: Automatically calls price prediction engine for fresh forecasts
- Mixed Integer Linear Programming (MILP) optimization using PuLP
- Configurable constraints for different operational scenarios
- Equipment scheduling: pulper speeds, compressors, wastewater pump
- Inventory management with safety buffers
- Grid stability constraints (ramp rates)
- Environmental compliance (wastewater frequency)

## Architecture

```
User Input (location, timestamp, constraints)
    ↓
Price Prediction Engine (Component 1)
    ↓
Price Forecasts (48 periods for 24 hours)
    ↓
Load Distribution Optimizer (Component 2)
    ↓
Optimized Equipment Schedule + Savings
```

## Installation

```bash
# Install dependencies (includes price prediction engine dependencies)
uv sync

# Verify installation
uv run python -m load_distribution.cli --help
```

## Quick Start

Basic optimization with integrated price forecasting:

```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24
```

The system will:
1. Call the price prediction engine with the specified location and time
2. Generate 24-hour price forecasts using 60 days of historical context
3. Optimize equipment schedule to minimize electricity costs
4. Display savings and detailed schedule

## Configurable Parameters

The optimizer supports extensive configuration to demonstrate how different constraints affect optimization results:

### Production Constraints
- `--production-target`: Daily production target (tons) - affects minimum pulper speed
- `--allow-pulper-60`: Enable 60% pulper speed (conservation mode)
- `--allow-pulper-120`: Enable 120% pulper speed (high production mode)

### Storage Constraints
- `--min-inventory`: Minimum inventory level (hours) - safety buffer
- `--max-inventory`: Maximum inventory level (hours) - tank capacity

### Equipment Constraints
- `--min-load`: Minimum mill load (MW) - equipment constraints
- `--max-load`: Maximum mill load (MW) - equipment capacity
- `--min-compressors`: Minimum compressors that must be ON (1-3)

### Operational Constraints
- `--ramp-rate`: Maximum load change rate (MW/min) - grid stability
- `--wastewater-frequency`: Wastewater must run every N hours - environmental compliance

## Demo Scenarios

### Scenario 1: Baseline (500 tons/day production)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500
```
**Result**: ~10% savings

### Scenario 2: Reduced Production (200 tons/day)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 200
```
**Result**: ~11-12% savings (more flexibility)

### Scenario 3: Limited Operating Modes (no 60% speed)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500 \
  --allow-pulper-60 false
```
**Result**: Similar or slightly worse savings (less flexibility)

### Scenario 4: Tight Inventory Constraints
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500 \
  --min-inventory 4.0 \
  --max-inventory 6.0
```
**Result**: Slightly lower savings (tighter constraints = less flexibility)

### Scenario 5: Aggressive Ramp Rate (faster load changes)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500 \
  --ramp-rate 1.0
```
**Result**: More flexibility to respond to price changes

### Scenario 6: Strict Environmental Compliance (wastewater every 2 hours)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500 \
  --wastewater-frequency 2
```
**Result**: More frequent wastewater runs = higher costs

### Scenario 7: High Production Mode (800 tons/day)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 800 \
  --allow-pulper-120 true
```
**Result**: Higher production = less flexibility = lower savings

### Scenario 8: Different Location
```bash
uv run python -m load_distribution.cli optimize \
  --location BEN2201 \
  --forecast-start "2024-04-01 00:00" \
  --forecast-horizon 24 \
  --production-target 500
```
**Result**: Savings vary by location price patterns

### Scenario 9: Different Time Period
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-05-15 00:00" \
  --forecast-horizon 24 \
  --production-target 500
```
**Result**: Savings vary by seasonal price patterns

### Scenario 10: Legacy Mode (pre-generated CSV)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-horizon 24 \
  --production-target 500 \
  --price-forecast-csv ../price_prediction/evaluation/predictions_20260309_092144.csv
```
**Result**: Uses pre-generated forecasts instead of calling prediction engine

### Scenario 5: Aggressive Ramp Rate (faster load changes)
```bash
uv run python -m load_distribution.cli optimize \
  --price-forecast ../price_prediction/evaluation/predictions_20260309_092144.csv \
  --location HAY2201 \
  --forecast-horizon 24 \
  --production-target 500 \
  --ramp-rate 1.0
```
**Result**: More flexibility to respond to price changes

### Scenario 6: Strict Environmental Compliance (wastewater every 2 hours)
```bash
uv run python -m load_distribution.cli optimize \
  --price-forecast ../price_prediction/evaluation/predictions_20260309_092144.csv \
  --location HAY2201 \
  --forecast-horizon 24 \
  --production-target 500 \
  --wastewater-frequency 2
```
**Result**: More frequent wastewater runs = higher costs

### Scenario 7: High Production Mode (800 tons/day)
```bash
uv run python -m load_distribution.cli optimize \
  --price-forecast ../price_prediction/evaluation/predictions_20260309_092144.csv \
  --location HAY2201 \
  --forecast-horizon 24 \
  --production-target 800 \
  --allow-pulper-120 true
```
**Result**: Higher production = less flexibility = lower savings

## Output

The optimizer provides:

1. **Configuration Summary**: Shows all constraint settings and their impact
2. **Optimization Results**: Total cost, baseline cost, savings, solve time
3. **Metrics**: Load ranges, inventory ranges, production totals
4. **Schedule Sample**: First 12 periods showing equipment settings, load, inventory, prices
5. **Optional CSV Export**: Full schedule for further analysis

## Optimization Problem

The system solves a Mixed Integer Linear Programming (MILP) problem:

- **Objective**: Minimize total electricity cost
- **Decision Variables**: Pulper speed (60/100/120%), compressor states (3x binary), wastewater pump (binary)
- **State Variable**: Inventory level (hours of pulp in storage)
- **Constraints**: 
  - Load bounds (15.6 - 28.2 MW)
  - Inventory bounds (2 - 8 hours)
  - Ramp rate (0.5 MW/min)
  - Production target (500 tons/day)
  - Wastewater frequency (every 4 hours)
  - Minimum compressors (1 must be ON)

See `OPTIMIZATION_PROBLEM.md` for detailed mathematical formulation.

## Architecture

```
load_distribution/
├── load_distribution/
│   ├── cli.py          # Command-line interface
│   ├── optimizer.py    # Core MILP optimizer
│   ├── models.py       # Pydantic data models
│   └── config.py       # Configuration constants
├── OPTIMIZATION_PROBLEM.md  # Problem formulation
├── README.md           # This file
└── pyproject.toml      # Dependencies
```

## Key Insights

1. **Production Flexibility**: Lower production targets allow more optimization flexibility
2. **Operating Modes**: More speed options (60%, 100%, 120%) = better optimization
3. **Storage Capacity**: Larger inventory buffers enable load shifting
4. **Ramp Rates**: Faster ramp rates allow quicker response to price changes
5. **Environmental Constraints**: More frequent wastewater runs reduce optimization flexibility

## Next Steps

1. Integrate with real-time price forecasts from Component 1
2. Add uncertainty handling (robust optimization)
3. Implement rolling horizon optimization
4. Add equipment degradation costs
5. Multi-day optimization with daily production targets
