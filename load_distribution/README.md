# Load Distribution Optimizer

MILP-based load distribution optimizer for paper mill operations. Integrates with the price prediction engine to optimize electricity consumption by scheduling flexible equipment loads based on forecasted prices while maintaining production targets and operational constraints.

## Features

- **Integrated Price Forecasting**: Automatically calls price prediction engine for fresh forecasts
- **AI-Powered Insights**: Natural language explanations of optimization decisions using Claude Sonnet 4.5
- Mixed Integer Linear Programming (MILP) optimization using PuLP
- Configurable constraints for different operational scenarios
- Equipment scheduling: paper machines (ON/OFF), pulper speeds, compressors, wastewater pump
- Inventory management with safety buffers
- Grid stability constraints (ramp rates)
- Environmental compliance (wastewater frequency)

## Installation

```bash
# Install dependencies (includes price prediction engine dependencies)
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your OpenAI API key

# Verify installation
uv run python -m load_distribution.cli --help
```

## AI Insights

The optimizer includes optional AI-powered insights using Claude Sonnet 4.5 that explain optimization decisions in natural language:

- **Executive Summary**: High-level overview of the strategy
- **Key Decisions**: Specific equipment scheduling choices that drove savings
- **Price Strategy**: How the optimizer exploited price patterns
- **Inventory Strategy**: How storage was used to enable load shifting
- **Risk Considerations**: Potential constraints to monitor

### Setup

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Add your Anthropic API key to `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Get your key from: https://console.anthropic.com/settings/keys

### Usage

AI insights are OFF by default. To enable:
```bash
uv run python -m load_distribution.cli optimize --ai-insights ...
```

## Quick Start

Basic optimization with integrated price forecasting:

```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-03-20 06:00" \
  --forecast-horizon 24 \
  --ai-insights
```

The system will:
1. Call the price prediction engine with the specified location and time
2. Generate 24-hour price forecasts using 60 days of historical context
3. Optimize equipment schedule to minimize electricity costs
4. Display savings and detailed schedule

**Result**: Significant cost savings through strategic equipment scheduling and load shifting

---

## Command-Line Options

### Required
- `--location` - Location ID (e.g., HAY2201, BEN2201, OTA2201)
- `--forecast-start` - Start date and time (YYYY-MM-DD HH:MM or YYYY-MM-DD)
- `--production-target` - Total production target for forecast period (tons)

### Forecasting
- `--forecast-horizon` - Hours to forecast (1-168), default: 48

### Initial Conditions
- `--current-inventory` - Current inventory level (hours), default: 5.0

### Production Constraints
- `--min-inventory` - Minimum inventory (hours), default: 2.0
- `--max-inventory` - Maximum inventory (hours), default: 12.0

### AI Insights
- `--ai-insights` - Enable AI-powered insights using Claude (requires ANTHROPIC_API_KEY)

### Operational Constraints
- `--ramp-rate` - Max load change rate (MW/min), default: 0.5
- `--wastewater-frequency` - Wastewater runs every N hours, default: 4
- `--min-compressors` - Minimum compressors ON (1-3), default: 1

### Output
- `--output` - Save schedule to CSV file (optional)

Run `uv run python -m load_distribution.cli optimize --help` for complete list.

---

## Demo Scenarios

All demos use **48-hour horizon** (the default) which provides realistic operational planning timeframes.

**Note**: Production target default is 250 tons for 48h horizon. Adjust proportionally for different horizons or flexibility needs.

### 1. Baseline (Standard Operation)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48
```
**Result**: Uses default 250 tons target, demonstrates baseline equipment scheduling strategy

### 2. Low Production (High Flexibility)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48
```
**Result**: Higher savings potential, more flexibility in equipment scheduling, wider inventory swings

### 3. Large Storage Tank
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --max-inventory 15.0
```
**Result**: Maximum savings potential, large inventory buffer enables aggressive load shifting and equipment scheduling flexibility

### 4. Tight Constraints
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --min-inventory 4.0 \
  --max-inventory 6.0 \
  --ramp-rate 0.3
```
**Result**: Lower savings, narrow inventory range limits flexibility, slower load changes constrain equipment scheduling

### 5. Fast Ramp Rate
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --ramp-rate 1.0
```
**Result**: Faster response to price changes, more aggressive optimization, quicker equipment state transitions

### 6. Strict Environmental Compliance
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --wastewater-frequency 2
```
**Result**: Wastewater runs every 2 hours (more frequent), slightly reduces scheduling flexibility but maintains compliance

### 7. Maximum Flexibility
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 100 \
  --forecast-horizon 48 \
  --min-inventory 1.0 \
  --max-inventory 18.0 \
  --ramp-rate 1.0 \
  --wastewater-frequency 8
```
**Result**: Highest savings potential, wide load/inventory ranges, aggressive equipment scheduling with maximum operational flexibility

### 8. Short Horizon (24h)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 125 \
  --forecast-horizon 24
```
**Result**: Shorter planning window, production target scaled proportionally (125 tons for 24h vs 250 for 48h)

---

## Understanding the Output

Each optimization shows:

1. **Inputs**: Location, date/time, horizon, current state
2. **Configuration**: All constraint settings and their impact
3. **Price Forecast**: Integrated prediction engine results
4. **Results Comparison**: Consolidated table comparing baseline vs proposed strategy
   - Baseline: Naive operator strategy (run equipment from period 0 until target met)
   - Proposed: Price-aware optimization with strategic timing
   - Shows: Total cost, average load, load range, inventory metrics, production
5. **Schedule Comparison**: Side-by-side view of baseline and proposed schedules (first 12 periods)
6. **AI Insights** (if enabled): Natural language explanation comparing strategies

### Baseline vs Proposed Strategy

The optimizer compares two approaches:

**Baseline (Naive Operator)**:
- Run equipment from period 0 at typical settings (PM ON, pulper 100%, 2 compressors)
- Continue until production target is met, then switch to minimal load
- Ignores price signals, focuses only on meeting production requirements
- Represents what an operator would do without price forecasts

**Proposed (Price-Aware)**:
- Strategic timing and equipment scheduling based on price patterns
- Exploits low-price periods for production, reduces load during high prices
- Uses inventory as a buffer to enable load shifting
- Respects all constraints while minimizing cost

### Example AI Insights Output

```
╔══════════════════════════════════════════════════════════════════╗
║                     AI-Powered Insights                          ║
╚══════════════════════════════════════════════════════════════════╝

Executive Summary:
The optimizer recommends a strategy that would achieve 42% savings vs baseline 
by delaying heavy production until off-peak hours. Unlike the baseline which 
runs equipment immediately, the proposed strategy exploits the $50/MWh price 
spread between night and peak periods.

Key Decisions:
  • Unlike baseline which runs at 100% from period 0, recommends delaying 
    heavy production until 2-6am ($45-55/MWh)
  • Proposes turning OFF paper machines during 5-7pm peak ($120+/MWh) to 
    avoid 12MW consumption
  • Builds inventory to 11h during cheap periods to enable 4 hours of 
    reduced operation during expensive periods

Price Strategy:
  Baseline would incur costs during expensive periods by running continuously.
  Proposed strategy concentrates production in the $40-60/MWh window (midnight-6am)
  and minimizes load during $100+/MWh peaks (5-8pm). Exploits $80/MWh price spread.

Inventory Strategy:
  Unlike baseline which maintains constant 5h inventory, the proposed strategy 
  uses inventory as a strategic buffer. Builds to 11h during cheap production 
  (2-6am), then depletes to 2h during expensive periods while paper machines 
  continue running on stored pulp.

⚠ Risk Considerations:
  • Inventory would drop to 2.1 hours at 7pm - at minimum safety buffer
  • Price forecast uncertainty: ±$15/MWh could impact actual savings
```

---

## Key Insights

### Production vs Flexibility Tradeoff
- Lower production targets = more optimization flexibility = higher savings potential
- 150 tons (48h horizon): Higher flexibility in equipment scheduling
- 250 tons (48h horizon): Moderate flexibility with balanced operation
- 400+ tons (48h horizon): Lower flexibility, more continuous operation required

### Storage Capacity Impact
- Larger inventory buffers enable better load shifting and equipment scheduling
- 2-8 hours: Standard flexibility (default)
- 2-15 hours: High flexibility
- 2-20 hours: Maximum flexibility
- 4-6 hours: Constrained operation

### Operational Constraints
- **Ramp Rate**: Faster rates (1.0 MW/min) allow quicker response to prices
- **Wastewater**: Less frequent (every 8 hours) provides more scheduling flexibility
- **Compressors**: Minimum requirements reduce optimization options

### Equipment Scheduling
- **Paper Machines**: 12.0 MW when ON, can be turned OFF during expensive periods
- **Pulper**: 0% (OFF), 60% (conservation), 100% (standard), 120% (high production)
- **Compressors**: 3 units, each 1.0 MW, minimum 1 must be ON
- **Wastewater Pump**: 1.5 MW, must run every N hours

---

## Optimization Problem

The system solves a Mixed Integer Linear Programming (MILP) problem:

**Objective**: Minimize total electricity cost over forecast horizon

**Decision Variables**:
- Paper machines: binary (ON/OFF)
- Pulper speed: 0%, 60%, 100%, or 120% (integer choice)
- Compressor states: 3 binary variables (ON/OFF)
- Wastewater pump: binary variable (ON/OFF)

**State Variable**:
- Inventory level: continuous (hours of pulp in storage)

**Constraints**:
- Inventory bounds: 2 - 8 hours (configurable up to 20h)
- Ramp rate: 0.5 MW/min (configurable)
- Production target: 250 tons for forecast period (configurable)
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

1. Start with baseline (#1) to establish reference point with default settings
2. Show low production (#2) to demonstrate increased equipment scheduling flexibility
3. Compare storage scenarios (#3 vs #4) to show value of larger inventory buffers
4. Demonstrate constraint impact (#5, #6) on optimization flexibility
5. End with maximum flexibility (#7) to show aggressive equipment scheduling
6. Try short horizon (#8) to compare 24h vs 48h planning windows

**Why these demos work well**:
- 48-hour horizon provides realistic operational planning timeframe
- Low production targets (100-150 tons) show clear equipment scheduling flexibility
- Large inventory buffers (15-18h) enable strategic equipment operation timing
- Fast ramp rates (1.0 MW/min) allow quick response to price changes
- Demonstrates full range of equipment control options
