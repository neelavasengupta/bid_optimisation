# Load Distribution Optimization Problem

## Problem Statement

Given forecasted electricity prices for the next 48 hours, determine the optimal equipment settings for a paper mill to minimize electricity costs while maintaining production targets and respecting operational constraints.

---

## Objective Function

**Minimize:** Total electricity cost + production deviation penalties

```
minimize: Σ(t=0 to T) [ P(t) × L(t) × Δt ] + α × Q⁺ + β × Q⁻

where:
  P(t) = electricity price at time t ($/MWh)
  L(t) = mill load at time t (MW)
  Δt = time period duration (0.5 hours)
  Q⁺ = overproduction (tons above target)
  Q⁻ = underproduction (tons below target)
  α = 100 $/ton (overproduction penalty)
  β = 200 $/ton (underproduction penalty)
```

---

## Decision Variables

For each time period t:

### 1. Paper Machine State
```
pm(t) ∈ {0, 1}
```
- Binary variable: 1 = ON (12.0 MW), 0 = OFF
- Controls both power consumption and pulp consumption
- When OFF: No pulp consumption, allowing inventory buildup

### 2. Pulper Speed
```
s(t) ∈ {0%, 60%, 100%, 120%}
```
- Determines pulper power consumption via cubic law
- Power = 6.0 × (s(t)/100)³ MW
  - At 0%: 0 MW (OFF)
  - At 60%: 6.0 × 0.6³ = 1.296 MW
  - At 100%: 6.0 × 1.0³ = 6.0 MW
  - At 120%: 6.0 × 1.2³ = 10.368 MW

### 3. Compressor States
```
c₁(t), c₂(t), c₃(t) ∈ {0, 1}
```
- Binary variables: 1 = ON (1 MW each), 0 = OFF
- Each compressor consumes 1.0 MW when ON

### 4. Wastewater Pump
```
w(t) ∈ {0, 1}
```
- Binary variable: 1 = ON (1.5 MW), 0 = OFF
- Can be deferred during expensive periods

### Total Load Calculation
```
L(t) = 12.0 × pm(t)                   (paper machines - controllable)
     + 1.3                            (critical systems - constant)
     + 6.0 × (s(t)/100)³              (pulper - cubic law)
     + 1.0 × (c₁(t) + c₂(t) + c₃(t)) (compressors)
     + 1.5 × w(t)                     (wastewater)
```

**Load Range:** 1.3 MW (minimum - all OFF) to 28.2 MW (maximum - all ON)

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
    - At 0% speed: 0 MW equivalent (OFF)
    - At 60% speed: 3.0 MW equivalent
    - At 100% speed: 5.0 MW equivalent
    - At 120% speed: 6.0 MW equivalent
  
  Pulp_Consumption(t) = 5.0 × pm(t) MW equivalent
    - When paper machines ON: 5.0 MW equivalent
    - When paper machines OFF: 0 MW equivalent
```

**Inventory Change Examples:**
- Paper machines OFF, pulper at 100%: +5.0 MW → +2.5 hours per period
- Paper machines ON, pulper at 120%: +1.0 MW → +0.5 hours per period
- Paper machines ON, pulper at 100%: 0 MW → 0 hours per period (balanced)
- Paper machines ON, pulper at 60%: -2.0 MW → -1.0 hours per period
- Paper machines ON, pulper OFF: -5.0 MW → -2.5 hours per period

---

## Constraints

All constraints are **configurable** via CLI options to demonstrate how different assumptions affect optimization.

### 1. Inventory Bounds
```
min_inventory ≤ I(t) ≤ max_inventory  hours    ∀t
```
- **Default:** 2.0 ≤ I(t) ≤ 8.0 hours
- **Configurable:** `--min-inventory`, `--max-inventory`
- Minimum: Safety buffer (prevent paper machine starvation)
- Maximum: Tank capacity (physical limit)

### 2. Ramp Rate Limit
```
|L(t) - L(t-1)| ≤ ramp_rate × 30  MW    ∀t
```
- **Default:** 0.5 MW/min × 30 min = 15 MW per period
- **Configurable:** `--ramp-rate` (MW/min)
- Protects equipment and grid stability

### 3. Production Target (Soft Constraint)
```
Total_Production = Σ(t=0 to T) [s(t) × production_factor]
Overproduction = max(0, Total_Production - production_target)
Underproduction = max(0, production_target - Total_Production)

Objective includes penalties:
  + 100 $/ton × Overproduction
  + 200 $/ton × Underproduction
```
- **Default:** 250 tons for 48-hour horizon
- **Configurable:** `--production-target` (tons for forecast period)
- Soft constraint allows flexibility when inventory constraints conflict
- Higher penalty for underproduction encourages meeting target
- Optimizer balances production penalties against electricity costs

### 4. Equipment Logic Constraints

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
```

**Example:**
```json
{
  "timestamp": "2026-03-09 14:30:00",
  "inventory_level": 5.2,
  "production_today": 300.5,
  "current_mode": "NORMAL"
}
```

**Note**: Initial load for ramp rate constraint is set to a reasonable default (20 MW) internally.

### 3. Mill Configuration

See Decision Variables and Constraints sections for equipment specifications and operating constraints.

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
  "paper_machines": true,           // ON/OFF
  "pulper_speed": 120,              // % (0, 60, 100, or 120)
  "compressor_1": true,             // ON/OFF
  "compressor_2": true,             // ON/OFF
  "compressor_3": true,             // ON/OFF
  "wastewater_pump": true,          // ON/OFF
  "expected_load": 28.2,            // MW
  "expected_inventory": 5.5,        // hours
  "price": 124.50,                  // $/MWh
  "period_cost": 1755.90,           // $ (28.2 MW × 0.5h × $124.50)
  "mode": "HIGH"                    // HIGH/NORMAL/CONSERVATION/OFF
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
      "OFF": 44,                    // periods (22 hours)
      "CONSERVATION": 8,            // periods (4 hours)
      "NORMAL": 32,                 // periods (16 hours)
      "HIGH": 12                    // periods (6 hours)
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
- Binary variables: pm(t), c₁(t), c₂(t), c₃(t), w(t) ∈ {0, 1}
- Discrete choice: s(t) ∈ {0, 60, 100, 120}

**Linear:**
- Objective function: Linear in L(t) plus linear penalties
- Most constraints: Linear inequalities

**Non-linear Element:**
- Cubic law for pulper: Power = 6.0 × (s(t)/100)³
- But only 4 discrete values, so can be linearized

### Complexity

**Problem Size:**
- Time periods: 96 (48 hours × 2 periods/hour)
- Decision variables per period: 6 (paper machines + pulper + 3 compressors + wastewater)
- Binary indicators for pulper speed: 4 per period (0%, 60%, 100%, 120%)
- Total decision variables: ~960
- Constraints per period: ~10
- Total constraints: ~960

**Solvability:**
- Small enough for exact solution (< 1 second with modern solvers)
- Can use: PuLP, OR-Tools, Gurobi, CPLEX
- Alternative: Heuristic/rule-based for real-time operation

---

## Solution Approach

The system uses full MILP optimization with PuLP solver and CBC (Coin-or Branch and Cut).

**Why MILP:**
- Proven optimal solution
- Handles complex constraints naturally
- Fast solve time (< 0.15 seconds for 48-hour horizon)
- Flexible and configurable

**Linearization of Cubic Law:**
Since pulper speed has only 4 discrete values, the cubic relationship is linearized using binary indicators:
```
s(t) = 0 × s₀(t) + 60 × s₆₀(t) + 100 × s₁₀₀(t) + 120 × s₁₂₀(t)
s₀(t) + s₆₀(t) + s₁₀₀(t) + s₁₂₀(t) = 1
Power(t) = 0 × s₀(t) + 1.296 × s₆₀(t) + 6.0 × s₁₀₀(t) + 10.368 × s₁₂₀(t)
```

**Performance:**
- Solve time: 0.05-0.15 seconds (48-hour horizon)
- Typical savings: 50-85% vs constant load
- Scales to 168-hour horizon if needed

---

## Next Steps

1. ✅ Validate assumptions - Mill configuration confirmed
2. ✅ Choose approach - Full MILP implemented with PuLP
3. ✅ Implement optimizer - Core optimization logic complete
4. ✅ Integrate with forecasting - Price prediction engine integrated
5. ✅ Create configurable system - All constraints adjustable via CLI
6. ✅ Add paper machine control - Paper machines now controllable (ON/OFF)
7. Test scenarios - Validate on different constraint combinations
8. Deploy - Integrate with real-time mill control system

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
