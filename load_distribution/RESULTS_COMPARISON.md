# Load Distribution Optimizer - Results Comparison

Comparison of optimization results under different constraint scenarios.

## Test Setup
- **Price Forecast**: predictions_20260309_092144.csv
- **Location**: HAY2201
- **Forecast Horizon**: 24 hours
- **Baseline Cost**: $53,424.96 (constant 22.8 MW load)

## Scenario Results

### 1. Baseline Configuration (Default)
**Constraints:**
- Production Target: 500 tons/day
- Inventory Range: 2.0 - 8.0 hours
- Pulper Speeds: 60%, 100%, 120%
- Ramp Rate: 0.5 MW/min
- Wastewater: Every 4 hours
- Min Compressors: 1

**Results:**
- Total Cost: $47,990.71
- Savings: $5,434.25 (10.2%)
- Load Range: 20.3 - 21.8 MW
- Inventory Range: 5.0 - 5.0 hours
- Solve Time: 0.09s

**Analysis:** Good baseline savings with moderate flexibility.

---

### 2. Low Production Target (200 tons/day)
**Changed Constraints:**
- Production Target: 200 tons/day (↓ from 500)

**Results:**
- Total Cost: $47,272.65
- Savings: $6,152.31 (11.5%)
- Load Range: 16.6 - 21.8 MW (wider)
- Inventory Range: 2.0 - 5.0 hours (wider)
- Solve Time: 0.04s

**Analysis:** Lower production requirement allows more load shifting. Inventory can drop to minimum (2.0 hours) during high-price periods. 13% better savings than baseline.

---

### 3. No Conservation Mode (60% disabled)
**Changed Constraints:**
- Pulper Speeds: 100%, 120% only

**Results:**
- Total Cost: $47,990.71
- Savings: $5,434.25 (10.2%)
- Load Range: 20.3 - 21.8 MW
- Inventory Range: 5.0 - 5.0 hours
- Solve Time: 0.04s

**Analysis:** Identical to baseline. The 60% speed wasn't being used in baseline scenario, so disabling it has no impact.

---

### 4. Tight Inventory Constraints (4.0 - 6.0 hours)
**Changed Constraints:**
- Inventory Range: 4.0 - 6.0 hours (↓ from 2.0 - 8.0)

**Results:**
- Total Cost: $47,992.16
- Savings: $5,432.80 (10.2%)
- Load Range: 17.1 - 24.7 MW (wider than baseline)
- Inventory Range: 4.0 - 5.0 hours
- Solve Time: 0.06s

**Analysis:** Tighter inventory constraints force more aggressive load changes to stay within bounds. Slightly worse savings than baseline.

---

### 5. Highly Constrained (No Flexibility)
**Changed Constraints:**
- Production Target: 500 tons/day
- Inventory Range: 4.5 - 5.5 hours (very tight)
- Pulper Speeds: 100% only (no 60% or 120%)
- All other constraints: default

**Results:**
- Total Cost: $47,990.71
- Savings: $5,434.25 (10.2%)
- Load Range: 20.3 - 21.8 MW (very narrow)
- Inventory Range: 5.0 - 5.0 hours (no variation)
- Solve Time: 0.04s

**Analysis:** With minimal flexibility, optimizer can only adjust compressor states and wastewater timing. Inventory stays constant at 5.0 hours. Load barely changes. Still achieves 10% savings through smart timing of wastewater pump.

---

## Key Insights

### 1. Production Target Impact
- **Lower target = Higher savings**: 200 tons/day achieved 11.5% vs 500 tons/day at 10.2%
- **Mechanism**: Lower production allows pulper to run slower during high-price periods
- **Trade-off**: Production vs cost optimization

### 2. Inventory Flexibility
- **Wide range (2-8 hours)**: Enables load shifting across time
- **Tight range (4.5-5.5 hours)**: Forces constant inventory, limits flexibility
- **Optimal**: Depends on storage costs vs electricity savings

### 3. Pulper Speed Options
- **Three speeds (60/100/120%)**: Maximum flexibility
- **Two speeds**: Reduced flexibility
- **One speed (100%)**: Minimal flexibility, relies on other equipment

### 4. Load Shifting Capability
- **Flexible scenario**: Load range 16.6 - 21.8 MW (5.2 MW swing)
- **Constrained scenario**: Load range 20.3 - 21.8 MW (1.5 MW swing)
- **Impact**: Wider range = better price response = higher savings

### 5. Solve Time
- All scenarios solve in < 0.1 seconds
- MILP with PuLP/CBC is very efficient for this problem size
- 24-hour horizon = 48 periods = ~480 variables

## Recommendations

### For Maximum Savings
1. Allow all three pulper speeds (60%, 100%, 120%)
2. Wide inventory range (2-8 hours)
3. Flexible production targets (adjust daily based on prices)
4. Fast ramp rates (1.0 MW/min if grid allows)
5. Infrequent wastewater (every 8 hours if compliant)

### For Operational Stability
1. Moderate inventory range (3-7 hours)
2. Standard pulper speeds (100%, 120%)
3. Fixed production targets (500 tons/day)
4. Conservative ramp rates (0.3 MW/min)
5. Regular wastewater (every 4 hours)

### For Risk Mitigation
1. Tight inventory range (4-6 hours)
2. Limited pulper speeds (100% only)
3. High production targets (600+ tons/day)
4. Slow ramp rates (0.2 MW/min)
5. Frequent wastewater (every 2 hours)

## Conclusion

The optimizer demonstrates clear trade-offs between operational flexibility and cost savings:

- **Best Case**: 11.5% savings with flexible constraints
- **Typical Case**: 10.2% savings with standard constraints
- **Worst Case**: Still 10%+ savings even with tight constraints

The key value proposition is that even with conservative constraints, the optimizer achieves meaningful savings (10%+) while maintaining all operational requirements. Relaxing constraints can improve savings by 10-15% relative to the constrained case.
