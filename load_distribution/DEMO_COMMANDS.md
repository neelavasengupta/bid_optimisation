# Load Distribution Optimizer - Demo Commands

This document provides ready-to-run demo commands showcasing different optimization scenarios.

All demos use **2024-03-20 06:00** as the start time, which provides good price variation and visible pulper speed changes.

## Quick Start

### 1. Baseline Optimization
Standard 24-hour optimization with default settings:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24
```

**What to observe:**
- Total cost vs baseline cost
- Savings percentage (~10%)
- Load and inventory ranges
- Equipment scheduling patterns

---

## Production Scenarios

### 2. Low Production Day (High Flexibility)
Reduced production target allows more flexibility:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300
```

**What to observe:**
- Higher savings percentage (~11%)
- Pulper drops to 60% during high-price morning hours
- Inventory drops from 4.0 → 2.0 hours
- Load range: 16.6 - 21.8 MW
- Clear load-shifting behavior

### 3. High Production Day (Low Flexibility)
Higher production target constrains optimization:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 500
```

**What to observe:**
- Lower savings percentage (~10%)
- Pulper stuck at 100% (no speed variation)
- Inventory flat at 5.0 hours (no variation)
- Narrower load range (20.3 - 21.8 MW)
- Less flexibility to avoid high prices

---

## Storage Scenarios

### 4. Large Storage Tank
Bigger tank provides more load-shifting capability:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --max-inventory 12.0
```

**What to observe:**
- Higher savings (more storage flexibility)
- Inventory can swing from 2.0 to 12.0 hours
- Better ability to build inventory during low-price periods
- More aggressive load shifting

### 5. Small Storage Tank
Limited storage constrains optimization:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --min-inventory 4.0 \
  --max-inventory 6.0
```

**What to observe:**
- Lower savings (less storage flexibility)
- Inventory stays in narrow 4.0-6.0 hour range
- Less ability to shift load
- Pulper speed changes less frequently

---

## Operational Constraints

### 6. Strict Environmental Compliance
Wastewater must run more frequently:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --wastewater-frequency 2
```

**What to observe:**
- Wastewater pump runs every 2 hours (vs default 4)
- Slightly higher costs due to more frequent pump operation
- Less flexibility in scheduling
- Pump may run during high-price periods

### 7. Relaxed Environmental Compliance
Wastewater can run less frequently:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --wastewater-frequency 8
```

**What to observe:**
- Wastewater pump runs every 8 hours
- More flexibility to avoid high-price periods
- Potentially higher savings
- Pump scheduled during low-price periods

### 8. Fast Ramp Rate
Equipment can change load quickly:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --ramp-rate 1.0
```

**What to observe:**
- Faster response to price changes
- More aggressive load shifting
- Pulper can change speeds more quickly
- Potentially higher savings

### 9. Slow Ramp Rate
Equipment must change load gradually:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --ramp-rate 0.2
```

**What to observe:**
- Slower, smoother load transitions
- Less aggressive optimization
- Lower savings due to ramp constraints
- More gradual pulper speed changes

---

## Combined Scenarios

### 10. Maximum Flexibility
All constraints relaxed for highest savings:
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

**What to observe:**
- Highest savings percentage
- Wide load range (16.6 - 28.2 MW possible)
- Wide inventory range (1.0 - 12.0 hours)
- Aggressive load shifting
- Full use of all flexibility options

### 11. Constrained Operation
All constraints tightened to show impact:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 500 \
  --min-inventory 4.0 \
  --max-inventory 6.0 \
  --ramp-rate 0.3 \
  --wastewater-frequency 2 \
  --min-compressors 2
```

**What to observe:**
- Lower savings percentage
- Narrow load and inventory ranges
- Less flexibility to respond to prices
- More conservative operation

---

## Tips for Demos

1. **Start with baseline** (Demo #1) to establish reference point
2. **Show low production** (Demo #2) to demonstrate clear pulper speed changes
3. **Compare production scenarios** (#2 vs #3) to show production-flexibility tradeoff
4. **Show storage impact** (#4 vs #5) to demonstrate value of larger tanks
5. **Demonstrate constraints** (#6-9) to show how operational limits affect optimization
6. **End with extremes** (#10 vs #11) to show maximum vs minimum flexibility

## Understanding the Output

Each demo shows:
- **Optimization Inputs**: Location, date/time, horizon, context days, inventory, load
- **Configuration**: All constraint settings and their impact
- **Results**: Total cost, baseline cost, savings percentage
- **Metrics**: Load ranges, inventory ranges, production totals
- **Schedule Sample**: First 12 periods with pulper %, compressors, wastewater, load, inventory, price, cost

## Key Insights

**Why 2024-03-20 06:00 works well:**
- Morning start captures high-price peak hours (6-9 AM)
- Price range: $242-270/MWh (good variation)
- Low production target (300 tons) shows clear pulper speed changes
- Inventory drops from 4.0 → 2.0 hours during high prices
- Pulper runs at 60% during expensive morning hours

**Production capacity limits:**
- Maximum: 600 tons/day (120% pulper continuously)
- Baseline: 500 tons/day (100% pulper continuously)
- Minimum: 300 tons/day (60% pulper continuously)

## Saving Results

Add `--output schedule.csv` to any command to save the full schedule:
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-03-20 \
  --time 06:00 \
  --forecast-horizon 24 \
  --production-target 300 \
  --output results/low_production_schedule.csv
```
