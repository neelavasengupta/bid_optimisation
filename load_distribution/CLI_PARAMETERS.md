# CLI Parameters Reference

## Required Parameters

### `--location`
- **Type**: String
- **Required**: Yes
- **Description**: Location ID for price forecasting
- **Examples**: `HAY2201`, `BEN2201`, `OTA2201`

### `--forecast-start`
- **Type**: DateTime
- **Required**: Yes
- **Format**: `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`
- **Description**: Start date and time for forecast
- **Example**: `--forecast-start "2024-03-20 06:00"`

### `--production-target`
- **Type**: Float
- **Required**: Yes
- **Range**: ≥ 0.0 tons
- **Description**: Total production target for the entire forecast period (not per day)
- **Soft Constraint**: Optimizer can deviate with penalties (100 $/ton over, 200 $/ton under)
- **Scaling**: Adjust proportionally with horizon (e.g., 125 tons for 24h, 250 tons for 48h, 500 tons for 96h)
- **Example**: `--production-target 250`

---

## Optional Parameters

### Forecasting

#### `--forecast-horizon`
- **Type**: Integer
- **Default**: `48`
- **Range**: 1-168 hours
- **Description**: Forecast horizon in hours
- **Example**: `--forecast-horizon 24`

---

### Initial State

#### `--current-inventory`
- **Type**: Float
- **Default**: `5.0`
- **Range**: 2.0-20.0 hours
- **Description**: Current inventory level in hours of pulp
- **Example**: `--current-inventory 6.5`

---

### Production Constraints

#### `--min-inventory`
- **Type**: Float
- **Default**: `2.0`
- **Range**: 0.0-10.0 hours
- **Description**: Minimum inventory level (safety buffer to prevent paper machine starvation)
- **Example**: `--min-inventory 3.0`

#### `--max-inventory`
- **Type**: Float
- **Default**: `12.0`
- **Range**: 2.0-20.0 hours
- **Description**: Maximum inventory level (tank capacity physical limit)
- **Note**: Must be greater than `min-inventory`
- **Example**: `--max-inventory 15.0`

---

### Operational Constraints

#### `--ramp-rate`
- **Type**: Float
- **Default**: `0.5`
- **Range**: ≥ 0.1 MW/min
- **Description**: Maximum load change rate for grid stability and equipment protection
- **Calculation**: Converted to MW per 30-min period (default: 0.5 × 30 = 15 MW/period)
- **Example**: `--ramp-rate 1.0`

#### `--wastewater-frequency`
- **Type**: Integer
- **Default**: `4`
- **Range**: ≥ 1 hours
- **Description**: Wastewater pump must run at least once every N hours (environmental compliance)
- **Example**: `--wastewater-frequency 8`

#### `--min-compressors`
- **Type**: Integer
- **Default**: `1`
- **Range**: 1-3
- **Description**: Minimum number of compressors that must be ON (process requirements)
- **Example**: `--min-compressors 2`

---

### Output Options

#### `--output`
- **Type**: File path
- **Default**: None (no file saved)
- **Description**: Save optimized schedule to CSV file
- **Example**: `--output schedule.csv`

#### `--ai-insights`
- **Type**: Flag (boolean)
- **Default**: `False` (disabled)
- **Description**: Generate AI-powered insights using Claude Sonnet 4.5
- **Requires**: `ANTHROPIC_API_KEY` environment variable
- **Example**: `--ai-insights`

---

## Parameter Relationships

### Production Target vs Horizon
The production target is for the **entire forecast period**, not per day:
- 24h horizon → ~125 tons (if maintaining ~500 tons/day rate)
- 48h horizon → ~250 tons (default)
- 72h horizon → ~375 tons

### Inventory Range Impact
Wider inventory ranges enable more load shifting:
- **Tight** (4-6h): Limited flexibility, lower savings
- **Standard** (2-8h): Balanced operation (default)
- **Wide** (2-15h): High flexibility, higher savings potential
- **Maximum** (2-20h): Maximum flexibility

### Ramp Rate Impact
- **Slow** (0.3 MW/min): Gradual changes, smoother operation
- **Standard** (0.5 MW/min): Balanced (default)
- **Fast** (1.0 MW/min): Quick response to price changes

### Current Load Considerations
- **Minimum** (1.3 MW): Critical systems only (all equipment OFF)
- **Low** (5-10 MW): Paper machines OFF, minimal operation
- **Standard** (22.8 MW): Typical operation (default)
- **Maximum** (28.2 MW): All equipment at maximum

---

## Equipment Power Consumption Reference

For context on load values:

| Equipment | State | Power (MW) |
|-----------|-------|------------|
| Critical Systems | Always ON | 1.3 |
| Paper Machines | ON | 12.0 |
| Paper Machines | OFF | 0.0 |
| Pulper | 0% (OFF) | 0.0 |
| Pulper | 60% | 1.296 |
| Pulper | 100% | 6.0 |
| Pulper | 120% | 10.368 |
| Compressor (each) | ON | 1.0 |
| Wastewater Pump | ON | 1.5 |

**Load Range**: 1.3 MW (minimum) to 28.2 MW (maximum)

---

## Examples

### Minimal Command (Required Only)
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-03-20 06:00" \
  --production-target 250
```

### Standard Operation
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-03-20 06:00" \
  --production-target 250 \
  --forecast-horizon 48
```

### High Flexibility Scenario
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-03-20 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --min-inventory 1.0 \
  --max-inventory 18.0 \
  --ramp-rate 1.0 \
  --wastewater-frequency 8
```

### With AI Insights and Output
```bash
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2024-03-20 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --ai-insights \
  --output schedule.csv
```

---

## Validation Rules

1. `max-inventory` must be > `min-inventory`
2. `production-target` must not exceed maximum capacity: `horizon × 2 periods/h × 120% × production_factor`
3. `current-inventory` must be within `[min-inventory, max-inventory]`
4. `current-load` must be within equipment capability range [1.3, 28.2] MW

---

## Tips

1. **Start with defaults** to understand baseline behavior
2. **Adjust production target** to see flexibility impact (lower = more savings potential)
3. **Widen inventory range** to enable more aggressive load shifting
4. **Increase ramp rate** for faster response to price changes
5. **Use AI insights** to understand optimization decisions
6. **Save output** for detailed analysis and record-keeping
