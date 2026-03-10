"""Core MILP optimizer for load distribution."""

import time
from typing import List, Tuple
from datetime import timedelta
import pulp as pl
from pydantic import BaseModel, Field, field_validator

from .models import (
    OptimizationRequest, OptimizationResult, SchedulePeriod,
    EquipmentSettings, MillState, PriceForecast
)
from .config import MILL_CONFIG, OPTIMIZATION_CONFIG


from pydantic import BaseModel, Field, field_validator


class LoadOptimizer(BaseModel):
    """MILP-based load distribution optimizer."""
    
    model_config = {"arbitrary_types_allowed": True}
    
    min_inventory: float = Field(default=2.0, ge=0.0, le=8.0, description="Minimum inventory level (hours)")
    max_inventory: float = Field(default=8.0, ge=2.0, le=10.0, description="Maximum inventory level (hours)")
    production_target: float = Field(default=250.0, ge=0.0, description="Total production target for forecast period (tons)")
    ramp_rate: float = Field(default=0.5, gt=0.0, description="Maximum load change rate (MW/min)")
    wastewater_frequency: int = Field(default=4, ge=1, description="Wastewater must run every N hours")
    min_compressors: int = Field(default=1, ge=1, le=3, description="Minimum compressors that must be ON")
    
    # Loaded from config
    config: dict = Field(default_factory=lambda: MILL_CONFIG, exclude=True)
    opt_config: dict = Field(default_factory=lambda: OPTIMIZATION_CONFIG, exclude=True)
    min_load: float = Field(default_factory=lambda: MILL_CONFIG["min_load"], exclude=True)
    max_load: float = Field(default_factory=lambda: MILL_CONFIG["max_load"], exclude=True)
    
    @field_validator('max_inventory')
    @classmethod
    def validate_inventory_range(cls, v, info):
        """Ensure max_inventory > min_inventory."""
        if 'min_inventory' in info.data and v <= info.data['min_inventory']:
            raise ValueError(f"max_inventory ({v}) must be greater than min_inventory ({info.data['min_inventory']})")
        return v
    
    def optimize(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Optimize load distribution over forecast horizon.
        
        Args:
            request: Optimization request with mill state and price forecast
        
        Returns:
            OptimizationResult with optimal schedule and metrics
        """
        start_time = time.time()
        
        # Extract data
        n_periods = request.forecast_horizon * 2  # 30-min periods
        prices = [pf.price_mean for pf in request.price_forecast[:n_periods]]
        initial_inventory = request.mill_state.inventory_level
        initial_load = request.mill_state.current_load
        
        # Create optimization problem
        prob = pl.LpProblem("Load_Distribution", pl.LpMinimize)
        
        # Time periods
        T = range(n_periods)
        
        # Decision variables
        pulper_speed = pl.LpVariable.dicts(
            "pulper_speed", T,
            cat='Integer',
            lowBound=0,
            upBound=120
        )
        
        compressor_1 = pl.LpVariable.dicts("c1", T, cat='Binary')
        compressor_2 = pl.LpVariable.dicts("c2", T, cat='Binary')
        compressor_3 = pl.LpVariable.dicts("c3", T, cat='Binary')
        wastewater = pl.LpVariable.dicts("ww", T, cat='Binary')
        
        # Auxiliary variables for cubic law (linearization)
        # Since pulper_speed ∈ {0, 60, 100, 120}, we use binary indicators
        speed_0 = pl.LpVariable.dicts("s0", T, cat='Binary')
        speed_60 = pl.LpVariable.dicts("s60", T, cat='Binary')
        speed_100 = pl.LpVariable.dicts("s100", T, cat='Binary')
        speed_120 = pl.LpVariable.dicts("s120", T, cat='Binary')
        
        # Pulper power for each speed option
        pulper_power_map = {
            0: 0.0,                     # OFF
            60: 6.0 * (0.6 ** 3),       # 1.296 MW
            100: 6.0 * (1.0 ** 3),      # 6.0 MW
            120: 6.0 * (1.2 ** 3),      # 10.368 MW
        }
        
        pulper_power = pl.LpVariable.dicts("pulper_power", T, lowBound=0)
        
        # Total load
        load = pl.LpVariable.dicts("load", T, lowBound=self.min_load, upBound=self.max_load)
        
        # Inventory level
        inventory = pl.LpVariable.dicts(
            "inventory", T,
            lowBound=self.min_inventory,
            upBound=self.max_inventory
        )
        
        # Objective: Minimize total cost
        prob += pl.lpSum([
            prices[t] * load[t] * 0.5  # 0.5 hours per period
            for t in T
        ]), "Total_Cost"
        
        # Constraints
        for t in T:
            # Speed selection: exactly one of 0%, 60%, 100%, or 120%
            prob += speed_0[t] + speed_60[t] + speed_100[t] + speed_120[t] == 1, f"Speed_Selection_{t}"
            prob += pulper_speed[t] == 0 * speed_0[t] + 60 * speed_60[t] + 100 * speed_100[t] + 120 * speed_120[t], f"Speed_Value_{t}"
            prob += pulper_power[t] == (
                pulper_power_map[0] * speed_0[t] +
                pulper_power_map[60] * speed_60[t] +
                pulper_power_map[100] * speed_100[t] +
                pulper_power_map[120] * speed_120[t]
            ), f"Pulper_Power_{t}"
            
            # Total load calculation
            prob += load[t] == (
                12.0 +  # Paper machines
                1.3 +   # Critical systems
                pulper_power[t] +  # Pulper
                1.0 * (compressor_1[t] + compressor_2[t] + compressor_3[t]) +  # Compressors
                1.5 * wastewater[t]  # Wastewater
            ), f"Load_Calc_{t}"
            
            # At least min_compressors must be ON
            prob += compressor_1[t] + compressor_2[t] + compressor_3[t] >= self.min_compressors, \
                    f"Min_Compressors_{t}"
            
            # Inventory dynamics
            pulp_production = 5.0 * pulper_speed[t] / 100  # MW equivalent
            pulp_consumption = 5.0  # MW equivalent (constant)
            
            if t == 0:
                prob += inventory[t] == initial_inventory + \
                        (pulp_production - pulp_consumption) * 0.5, \
                        f"Inventory_Initial"
            else:
                prob += inventory[t] == inventory[t-1] + \
                        (pulp_production - pulp_consumption) * 0.5, \
                        f"Inventory_Dynamics_{t}"
            
            # Ramp rate constraint (MW per 30-min period)
            max_ramp = self.ramp_rate * 30  # MW per 30 minutes
            if t == 0:
                prob += load[t] - initial_load <= max_ramp, f"Ramp_Up_Initial"
                prob += initial_load - load[t] <= max_ramp, f"Ramp_Down_Initial"
            else:
                prob += load[t] - load[t-1] <= max_ramp, f"Ramp_Up_{t}"
                prob += load[t-1] - load[t] <= max_ramp, f"Ramp_Down_{t}"
        
        # Wastewater constraint: must run at least once every N hours
        periods_per_cycle = self.wastewater_frequency * 2  # Convert hours to 30-min periods
        for k in range(0, n_periods - periods_per_cycle + 1):
            prob += pl.lpSum([wastewater[t] for t in range(k, k + periods_per_cycle)]) >= 1, \
                    f"Wastewater_Frequency_{k}"
        
        # Production target: total production must meet target
        # Production rate: pulper_speed/100 * 5.0 MW * 0.5h * 10 tons/MWh = tons per period
        # Simplified: pulper_speed * 0.25 = tons per period
        prob += pl.lpSum([pulper_speed[t] * 0.25 for t in T]) >= self.production_target, \
                "Production_Target"
        
        # Calculate maximum possible production for validation
        max_production = n_periods * 120 * 0.25  # All periods at 120%
        if self.production_target > max_production:
            raise ValueError(
                f"Production target {self.production_target} tons exceeds maximum capacity "
                f"{max_production:.1f} tons for {request.forecast_horizon}-hour horizon "
                f"(pulper max speed: 120%)"
            )
        
        # Solve
        solver = pl.PULP_CBC_CMD(
            msg=0,  # Suppress solver output
            timeLimit=self.opt_config["solver_time_limit"],
            gapRel=self.opt_config["mip_gap"]
        )
        
        prob.solve(solver)
        
        solve_time = time.time() - start_time
        
        # Extract solution
        if prob.status != pl.LpStatusOptimal:
            error_msg = f"Solver failed with status: {pl.LpStatus[prob.status]}"
            if prob.status == pl.LpStatusInfeasible:
                error_msg += "\n\nPossible causes:"
                error_msg += f"\n- Production target ({self.production_target} tons/day) may be too high"
                error_msg += f"\n- Inventory range ({self.min_inventory}-{self.max_inventory} hours) may be too narrow"
                error_msg += f"\n- Ramp rate ({self.ramp_rate} MW/min) may be too restrictive"
                error_msg += f"\n- Wastewater frequency ({self.wastewater_frequency} hours) may conflict with other constraints"
            raise RuntimeError(error_msg)
        
        # Build schedule
        schedule = self._build_schedule(
            request, n_periods, pulper_speed, compressor_1, compressor_2,
            compressor_3, wastewater, load, inventory, prices
        )
        
        # Calculate metrics
        total_cost = pl.value(prob.objective)
        baseline_cost = self._calculate_baseline_cost(prices, n_periods)
        
        return OptimizationResult(
            schedule=schedule,
            total_cost=total_cost,
            baseline_cost=baseline_cost,
            savings=baseline_cost - total_cost,
            savings_percent=((baseline_cost - total_cost) / baseline_cost) * 100,
            avg_load=sum(s.expected_load for s in schedule) / len(schedule),
            min_load=min(s.expected_load for s in schedule),
            max_load=max(s.expected_load for s in schedule),
            min_inventory=min(s.expected_inventory for s in schedule),
            max_inventory=max(s.expected_inventory for s in schedule),
            avg_inventory=sum(s.expected_inventory for s in schedule) / len(schedule),
            total_production=self._calculate_production(schedule),
            production_target=self.production_target,
            solve_time=solve_time,
            solver_status=pl.LpStatus[prob.status]
        )
    
    def _build_schedule(
        self, request: OptimizationRequest, n_periods: int,
        pulper_speed, c1, c2, c3, ww, load, inventory, prices
    ) -> List[SchedulePeriod]:
        """Build schedule from solver solution."""
        schedule = []
        
        for t in range(n_periods):
            timestamp = request.mill_state.timestamp + timedelta(minutes=30 * t)
            
            equipment = EquipmentSettings(
                pulper_speed=int(pl.value(pulper_speed[t])),
                compressor_1=bool(pl.value(c1[t])),
                compressor_2=bool(pl.value(c2[t])),
                compressor_3=bool(pl.value(c3[t])),
                wastewater_pump=bool(pl.value(ww[t]))
            )
            
            expected_load = pl.value(load[t])
            expected_inventory = pl.value(inventory[t])
            price = prices[t]
            period_cost = price * expected_load * 0.5
            
            schedule.append(SchedulePeriod(
                timestamp=timestamp,
                equipment=equipment,
                expected_load=expected_load,
                expected_inventory=expected_inventory,
                price=price,
                period_cost=period_cost
            ))
        
        return schedule
    
    def _calculate_baseline_cost(self, prices: List[float], n_periods: int) -> float:
        """Calculate baseline cost at constant 22.8 MW load."""
        return sum(prices) * 22.8 * 0.5
    
    def _calculate_production(self, schedule: List[SchedulePeriod]) -> float:
        """Calculate total production in tons."""
        # 1 MW-hour of pulp production ≈ 10 tons (mill-specific conversion)
        return sum(s.equipment.pulp_production_rate() * 0.5 for s in schedule) * 10
