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
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24
```

The system will:
1. Call the price prediction engine with the specified location and time
2. Generate 24-hour price forecasts using 60 days of historical context
3. Optimize equipment schedule to minimize electricity costs
4. Display savings and detailed schedule

**Result**: ~10% cost savings ($14,222 saved on $140,119 baseline)

---

## Command-Line Options

### Required
- `--location` - Location ID (e.g., HAY2201, BEN2201, OTA2201)

### Forecasting
- `--date` - Start date (YYYY-MM-DD), default: 2024-03-07
- `--time` - Start time (HH:MM), default: 00:00
- `--forecast-horizon` - Hours to forecast (1-168), default: 48

### Current State
- `--current-inventory` - Current inventory level (hours), default: 5.0
- `--current-load` - Current load (MW), default: 22.8

### Production Constraints
- `--production-target` - Daily production target (tons), default: 500.0
- `--min-inventory` - Minimum inventory (hours), default: 2.0
- `--max-inventory` - Maximum inventory (hours), default: 8.0

### Operational Constraints
- `--ramp-rate` - Max load change rate (MW/min), default: 0.5
- `--wastewater-frequency` - Wastewater runs every N hours, default: 4
- `--min-compressors` - Minimum compressors ON (1-3), default: 1

### Output
- `--output` - Save schedule to CSV file (optional)

Run `uv run python -m load_distribution.cli optimize --help` for complete list.

---

## Demo Scenarios

All demos use **2024-03-20 06:00** which provides good price variation ($242-270/MWh) and visible equipment scheduling changes.

### 1. Baseline (Standard Operation)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24
```
**Result**: ~10% savings, moderate flexibility

### 2. Low Production (High Flexibility)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300
```
**Result**: ~11% savings, pulper drops to 60% during high prices, inventory swings 2.0-5.0 hours

### 3. Large Storage Tank
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --max-inventory 12.0
```
**Result**: Higher savings, inventory can swing 2.0-12.0 hours, better load shifting

### 4. Tight Constraints
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --min-inventory 4.0 \
  --max-inventory 6.0 \
  --ramp-rate 0.3
```
**Result**: Lower savings, narrow inventory range, slower load changes

### 5. Fast Ramp Rate
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --ramp-rate 1.0
```
**Result**: Faster response to price changes, more aggressive optimization

### 6. Strict Environmental Compliance
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --wastewater-frequency 2
```
**Result**: Wastewater runs every 2 hours, slightly higher costs

### 7. Maximum Flexibility
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --min-inventory 1.0 \
  --max-inventory 12.0 \
  --ramp-rate 1.0 \
  --wastewater-frequency 8
```
**Result**: Highest savings, wide load/inventory ranges, aggressive load shifting

---

## Understanding the Output

Each optimization shows:

1. **Inputs**: Location, date/time, horizon, current state
2. **Configuration**: All constraint settings and their impact
3. **Price Forecast**: Integrated prediction engine results
4. **Optimization Results**: Total cost, baseline cost, savings, solve time
5. **Metrics**: Load ranges, inventory ranges, production totals
6. **Schedule Sample**: First 12 periods with equipment settings, load, inventory, price, cost

---

## Key Insights

### Production vs Flexibility Tradeoff
- Lower production targets = more optimization flexibility = higher savings
- 300 tons/day: ~11% savings (pulper can drop to 60%)
- 500 tons/day: ~10% savings (pulper stays at 100%)

### Storage Capacity Impact
- Larger inventory buffers enable better load shifting
- 2-8 hours: Standard flexibility
- 1-12 hours: Maximum flexibility
- 4-6 hours: Constrained operation

### Operational Constraints
- **Ramp Rate**: Faster rates (1.0 MW/min) allow quicker response to prices
- **Wastewater**: Less frequent (every 8 hours) provides more scheduling flexibility
- **Compressors**: Minimum requirements reduce optimization options

### Equipment Scheduling
- **Pulper**: 60% (conservation), 100% (standard), 120% (high production)
- **Compressors**: 3 units, each 1.5 MW, minimum 1 must be ON
- **Wastewater Pump**: 1.5 MW, must run every N hours

---

## Optimization Problem

The system solves a Mixed Integer Linear Programming (MILP) problem:

**Objective**: Minimize total electricity cost over forecast horizon

**Decision Variables**:
- Pulper speed: 60%, 100%, or 120% (integer choice)
- Compressor states: 3 binary variables (ON/OFF)
- Wastewater pump: binary variable (ON/OFF)

**State Variable**:
- Inventory level: continuous (hours of pulp in storage)

**Constraints**:
- Load bounds: 15.6 - 28.2 MW
- Inventory bounds: 2 - 8 hours (configurable)
- Ramp rate: 0.5 MW/min (configurable)
- Production target: 500 tons/day (configurable)
- Wastewater frequency: every 4 hours (configurable)
- Minimum compressors: 1 must be ON (configurable)

See `OPTIMIZATION_PROBLEM.md` for detailed mathematical formulation.

---

## Comparison of Scenarios

See `RESULTS_COMPARISON.md` for detailed analysis of different constraint scenarios including:
- Production target impact (200 vs 500 tons/day)
- Inventory flexibility (tight vs wide ranges)
- Pulper speed options (1 vs 3 speeds)
- Load shifting capability
- Solve time analysis

---

## Architecture

```
load_distribution/
├── load_distribution/
│   ├── cli.py          # Command-line interface
│   ├── optimizer.py    # Core MILP optimizer
│   ├── models.py       # Pydantic data models
│   └── config.py       # Configuration constants
├── OPTIMIZATION_PROBLEM.md  # Mathematical formulation
├── RESULTS_COMPARISON.md    # Scenario analysis
├── README.md           # This file
└── pyproject.toml      # Dependencies
```

---

## Tips for Demos

1. Start with baseline (#1) to establish reference point
2. Show low production (#2) to demonstrate clear pulper speed changes
3. Compare storage scenarios (#3 vs #4) to show value of larger tanks
4. Demonstrate constraint impact (#5, #6) on optimization
5. End with extremes (#7) to show maximum flexibility

**Why 2024-03-20 06:00 works well**:
- Morning start captures high-price peak hours (6-9 AM)
- Price range: $242-270/MWh (good variation)
- Low production shows clear pulper speed changes
- Inventory drops during high prices
- Visible load-shifting behavior
