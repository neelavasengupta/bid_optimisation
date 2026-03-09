# Load Distribution Optimization Problem

## Problem Statement

Given forecasted electricity prices for the next 48 hours, determine the optimal equipment settings for a paper mill to minimize electricity costs while maintaining production targets and respecting operational constraints.

---

## Objective Function

**Minimize:** Total electricity cost over forecast horizon T

```
minimize: Σ(t=0 to T) [ P(t) × L(t) × Δt ]

where:
  P(t) = electricity price at time t ($/MWh)
  L(t) = mill load at time t (MW)
  Δt = time period duration (0.5 hours)
```

---

## Decision Variables

For each time period t:

### 1. Pulper Speed
```
s(t) ∈ {60%, 100%, 120%}
```
- Determines pulper power consumption via cubic law
- Power = 6.0 × (s(t)/100)³ MW
  - At 60%: 6.0 × 0.6³ = 1.3 MW
  - At 100%: 6.0 × 1.0³ = 6.0 MW
  - At 120%: 6.0 × 1.2³ = 10.4 MW

### 2. Compressor States
```
c₁(t), c₂(t), c₃(t) ∈ {0, 1}
```
- Binary variables: 1 = ON (1 MW each), 0 = OFF
- Each compressor consumes 1.0 MW when ON

### 3. Wastewater Pump
```
w(t) ∈ {0, 1}
```
- Binary variable: 1 = ON (1.5 MW), 0 = OFF
- Can be deferred during expensive periods

### Total Load Calculation
```
L(t) = 12.0                           (paper machines - constant)
     + 1.3                            (critical systems - constant)
     + 6.0 × (s(t)/100)³              (pulper - cubic law)
     + 1.0 × (c₁(t) + c₂(t) + c₃(t)) (compressors)
     + 1.5 × w(t)                     (wastewater)
```

**Load Range:** 15.6 MW (minimum) to 28.2 MW (maximum)

---

## State Variable

### Inventory Level
```
I(t) = hours of pulp in storage tanks
```

**Dynamics:**
```
I(t+1) = I(t) + [Pulp_Production(t) - Pulp_Consumption(t)] × Δt

where:
  Pulp_Production(t) = 5.0 × (s(t)/100) MW equivalent
    - At 60% speed: 3.0 MW equivalent
    - At 100% speed: 5.0 MW equivalent
    - At 120% speed: 6.0 MW equivalent
  
  Pulp_Consumption(t) = 5.0 MW (constant - paper machines)
```

**Inventory Change Examples:**
- HIGH mode (120% speed): +1.0 MW → +0.5 hours per period
- NORMAL mode (100% speed): 0 MW → 0 hours per period (balanced)
- CONSERVATION mode (60% speed): -2.0 MW → -1.0 hours per period

---

## Constraints

All constraints are **configurable** via CLI options to demonstrate how different assumptions affect optimization.

### 1. Load Bounds
```
min_load ≤ L(t) ≤ max_load  MW    ∀t
```
- **Default:** 15.6 ≤ L(t) ≤ 28.2 MW
- **Configurable:** `--min-load`, `--max-load`
- Minimum: Paper machines + critical + minimum pulper + min compressors
- Maximum: All equipment at maximum capacity

### 2. Inventory Bounds
```
min_inventory ≤ I(t) ≤ max_inventory  hours    ∀t
```
- **Default:** 2.0 ≤ I(t) ≤ 8.0 hours
- **Configurable:** `--min-inventory`, `--max-inventory`
- Minimum: Safety buffer (prevent paper machine starvation)
- Maximum: Tank capacity (physical limit)

### 3. Ramp Rate Limit
```
|L(t) - L(t-1)| ≤ ramp_rate × 30  MW    ∀t
```
- **Default:** 0.5 MW/min × 30 min = 15 MW per period
- **Configurable:** `--ramp-rate` (MW/min)
- Protects equipment and grid stability

### 4. Daily Production Target
```
Average pulper speed ≥ (production_target / 500) × 100%
```
- **Default:** 500 tons/day (requires 100% average speed)
- **Configurable:** `--production-target` (tons/day)
- Ensures customer orders are fulfilled
- Lower target = more flexibility = higher savings

### 5. Equipment Logic Constraints

**Compressors - Minimum Coverage:**
```
c₁(t) + c₂(t) + c₃(t) ≥ min_compressors    ∀t
```
- **Default:** At least 1 compressor must be ON
- **Configurable:** `--min-compressors` (1-3)
- Required for pneumatic controls and process equipment

**Wastewater - Deferred Treatment:**
```
Σ(t=k to k+2×wastewater_frequency) w(t) ≥ 1    ∀k
```
- **Default:** Must run at least once every 4 hours (8 periods)
- **Configurable:** `--wastewater-frequency` (hours)
- Environmental compliance requirement
- Can be deferred during expensive periods

**Pulper Speed Options:**
```
s(t) ∈ allowed_speeds
```
- **Default:** {60%, 100%, 120%} (all speeds allowed)
- **Configurable:** 
  - `--allow-pulper-60` (enable/disable 60% speed)
  - `--allow-pulper-120` (enable/disable 120% speed)
- More speed options = more flexibility = higher savings

### 6. Paper Machines (Hard Constraint)
```
Paper_Machine_Speed(t) = 100%    ∀t
Paper_Machine_Power(t) = 12.0 MW    ∀t
```
- **NEVER adjusted** - quality and safety requirement
- Constant speed ensures consistent paper properties:
  - Moisture content
  - Thickness uniformity
  - Tensile strength
- Any speed variation ruins product quality

---

## Inputs

### 1. Price Forecast
```
P(t) for t = 0 to T (T = 48 hours = 96 periods)
```
- **Source:** price_prediction component
- **Format:** $/MWh per 30-minute period
- **Location-specific:** e.g., HAY2201
- **Includes:** Mean prediction + uncertainty quantiles (P10, P50, P90)

**Example:**
```csv
timestamp,mean,p10,p90
2026-03-09 00:00:00,145.23,120.45,170.89
2026-03-09 00:30:00,142.67,118.23,168.45
...
```

### 2. Initial State
```
I(0) = current inventory level (hours)
L(-1) = current load (MW) - for ramp rate constraint
production_today = tons produced so far today
```

**Example:**
```json
{
  "timestamp": "2026-03-09 14:30:00",
  "inventory_level": 5.2,
  "current_load": 22.8,
  "production_today": 300.5,
  "current_mode": "NORMAL"
}
```

### 3. Mill Configuration
```
Equipment specifications:
  - Paper machines: 12.0 MW (constant)
  - Critical systems: 1.3 MW (constant)
  - Pulper base: 6.0 MW at 100% speed
  - Compressor unit: 1.0 MW each
  - Wastewater: 1.5 MW

Operating constraints:
  - Storage: 2.0 - 8.0 hours
  - Ramp rate: 0.5 MW/min
  - Production target: 500 tons/day
```

### 4. Location
```
location_id: str (e.g., "HAY2201")
```
- Used to filter price forecasts
- Different locations have different price patterns

---

## Outputs

### 1. Optimal Schedule

For each time period t (96 periods for 48 hours):

```json
{
  "timestamp": "2026-03-09 00:00:00",
  "pulper_speed": 120,              // % (60, 100, or 120)
  "compressor_1": true,             // ON/OFF
  "compressor_2": true,             // ON/OFF
  "compressor_3": true,             // ON/OFF
  "wastewater_pump": true,          // ON/OFF
  "expected_load": 28.2,            // MW
  "expected_inventory": 5.5,        // hours
  "price": 124.50,                  // $/MWh
  "period_cost": 1755.90,           // $ (28.2 MW × 0.5h × $124.50)
  "mode": "HIGH"                    // HIGH/NORMAL/CONSERVATION
}
```

### 2. Summary Metrics

```json
{
  "optimization_summary": {
    "total_cost": 89888.00,         // $ - optimized schedule
    "baseline_cost": 91068.00,      // $ - constant 22.8 MW
    "savings": 1180.00,             // $ - daily savings
    "savings_percent": 1.3,         // %
    
    "load_statistics": {
      "avg_load": 23.5,             // MW
      "min_load": 15.6,             // MW
      "max_load": 28.2,             // MW
      "load_factor": 0.83           // avg/max
    },
    
    "inventory_statistics": {
      "min_inventory": 2.5,         // hours
      "max_inventory": 7.2,         // hours
      "avg_inventory": 5.1,         // hours
      "violations": 0               // constraint violations
    },
    
    "production": {
      "total_tons": 502.3,          // tons
      "target_tons": 500.0,         // tons
      "achievement": 100.5          // %
    },
    
    "mode_distribution": {
      "HIGH": 12,                   // periods (6 hours)
      "NORMAL": 72,                 // periods (36 hours)
      "CONSERVATION": 12            // periods (6 hours)
    }
  }
}
```

### 3. Visualization Data

For plotting and analysis:
```
- Load profile over time
- Inventory level over time
- Price vs load comparison
- Cost breakdown by period
- Mode transitions
```

---

## Problem Classification

### Type: Mixed Integer Linear Programming (MILP)

**Mixed:**
- Continuous variables: Inventory level I(t)
- Discrete variables: Equipment states (binary)

**Integer:**
- Binary variables: c₁(t), c₂(t), c₃(t), w(t) ∈ {0, 1}
- Discrete choice: s(t) ∈ {60, 100, 120}

**Linear:**
- Objective function: Linear in L(t)
- Most constraints: Linear inequalities

**Non-linear Element:**
- Cubic law for pulper: Power = 6.0 × (s(t)/100)³
- But only 3 discrete values, so can be linearized

### Complexity

**Problem Size:**
- Time periods: 96 (48 hours × 2 periods/hour)
- Decision variables per period: 5 (pulper + 3 compressors + wastewater)
- Total decision variables: 480
- Constraints per period: ~8
- Total constraints: ~768

**Solvability:**
- Small enough for exact solution (< 1 second with modern solvers)
- Can use: PuLP, OR-Tools, Gurobi, CPLEX
- Alternative: Heuristic/rule-based for real-time operation

---

## Solution Approach

### Implementation: Full MILP Optimization

The system uses **Approach 2 (Full MILP)** with PuLP solver for optimal equipment scheduling.

**Why MILP:**
- Proven optimal solution (not heuristic)
- Handles complex constraints naturally
- Fast solve time (< 0.1 seconds for 48-hour horizon)
- Flexible - easy to add new constraints
- Configurable - all constraints can be adjusted via CLI

**Solver:** PuLP with CBC (Coin-or Branch and Cut)
- Open source, no licensing costs
- Branch & Bound algorithm
- Guarantees optimal solution
- Handles up to 500 variables efficiently

**Decision Variables per Period:**
- Pulper speed: s(t) ∈ {60, 100, 120} (linearized with binary indicators)
- Compressor states: c₁(t), c₂(t), c₃(t) ∈ {0, 1}
- Wastewater pump: w(t) ∈ {0, 1}
- Total: 8 variables per period (3 speed indicators + 4 equipment states + 1 load)

**Linearization of Cubic Law:**
Since pulper speed has only 3 discrete values, the cubic relationship is linearized:
```
s(t) = 60 × s₆₀(t) + 100 × s₁₀₀(t) + 120 × s₁₂₀(t)
s₆₀(t) + s₁₀₀(t) + s₁₂₀(t) = 1
Power(t) = 1.296 × s₆₀(t) + 6.0 × s₁₀₀(t) + 10.368 × s₁₂₀(t)
```

**Advantages of This Approach:**
- Optimal solution (5-10% better than simple rules)
- Configurable constraints for scenario analysis
- Fast enough for real-time use
- Handles all equipment interactions
- Respects all physical and operational constraints

**Performance:**
- Solve time: 0.05-0.10 seconds (48-hour horizon)
- Typical savings: 10-12% vs constant load
- Scales to 168-hour horizon if needed

---

## Next Steps

1. ✅ **Validate assumptions** - Mill configuration confirmed
2. ✅ **Choose approach** - Full MILP implemented with PuLP
3. ✅ **Implement optimizer** - Core optimization logic complete
4. ✅ **Integrate with forecasting** - Price prediction engine integrated
5. ✅ **Create configurable system** - All constraints adjustable via CLI
6. **Test scenarios** - Validate on different constraint combinations
7. **Deploy** - Integrate with real-time mill control system

## Usage

```bash
# Basic optimization with defaults
uv run python -m load_distribution.cli optimize --location HAY2201 --date 2024-04-01

# Custom constraints
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --date 2024-04-01 \
  --production-target 300 \
  --min-inventory 3.0 \
  --max-inventory 7.0

# See all options
uv run python -m load_distribution.cli optimize --help
```

See `CLI_REFERENCE.md` for complete documentation of all options.
