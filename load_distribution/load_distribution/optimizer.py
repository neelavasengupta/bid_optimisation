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
    
    # All parameters configured via CLI - no defaults here
    min_inventory: float = Field(ge=0.0, le=10.0, description="Minimum inventory level (hours)")
    max_inventory: float = Field(ge=2.0, le=20.0, description="Maximum inventory level (hours)")
    production_target: float = Field(ge=0.0, description="Total production target for forecast period (tons)")
    ramp_rate: float = Field(gt=0.0, description="Maximum load change rate (MW/min)")
    wastewater_frequency: int = Field(ge=1, description="Wastewater must run every N hours")
    min_compressors: int = Field(ge=1, le=3, description="Minimum compressors that must be ON")
    
    # Loaded from config
    config: dict = Field(default_factory=lambda: MILL_CONFIG, exclude=True)
    opt_config: dict = Field(default_factory=lambda: OPTIMIZATION_CONFIG, exclude=True)
    
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
        max_pulper_speed = max(self.config["pulper_speeds"])
        pulper_speed = pl.LpVariable.dicts(
            "pulper_speed", T,
            cat='Integer',
            lowBound=0,
            upBound=max_pulper_speed
        )
        
        compressor_1 = pl.LpVariable.dicts("c1", T, cat='Binary')
        compressor_2 = pl.LpVariable.dicts("c2", T, cat='Binary')
        compressor_3 = pl.LpVariable.dicts("c3", T, cat='Binary')
        wastewater = pl.LpVariable.dicts("ww", T, cat='Binary')
        paper_machines = pl.LpVariable.dicts("pm", T, cat='Binary')  # NEW: Paper machines ON/OFF
        
        # Auxiliary variables for cubic law (linearization)
        # Since pulper_speed ∈ {0, 60, 100, 120}, we use binary indicators
        speed_0 = pl.LpVariable.dicts("s0", T, cat='Binary')
        speed_60 = pl.LpVariable.dicts("s60", T, cat='Binary')
        speed_100 = pl.LpVariable.dicts("s100", T, cat='Binary')
        speed_120 = pl.LpVariable.dicts("s120", T, cat='Binary')
        
        # Pulper power for each speed option
        pulper_power_map = {
            speed: self.config["pulper_base"] * (speed / 100) ** 3
            for speed in self.config["pulper_speeds"]
        }
        
        pulper_power = pl.LpVariable.dicts("pulper_power", T, lowBound=0)
        
        # Total load (no artificial bounds - determined by equipment states)
        load = pl.LpVariable.dicts("load", T, lowBound=0)
        
        # Inventory level
        inventory = pl.LpVariable.dicts(
            "inventory", T,
            lowBound=self.min_inventory,
            upBound=self.max_inventory
        )
        
        # Objective: Minimize total cost + penalties for deviation from target
        # We penalize BOTH overproduction and underproduction
        overproduction = pl.LpVariable("overproduction", lowBound=0)
        underproduction = pl.LpVariable("underproduction", lowBound=0)
        
        overproduction_penalty = self.opt_config["overproduction_penalty"]
        underproduction_penalty = self.opt_config["underproduction_penalty"]
        
        period_duration = self.config["period_duration"]  # 0.5 hours
        
        prob += pl.lpSum([
            prices[t] * load[t] * period_duration  # Electricity cost
            for t in T
        ]) + overproduction_penalty * overproduction + underproduction_penalty * underproduction, \
            "Total_Cost_Plus_Production_Penalties"
        
        # Define production deviation from target
        # Conversion: speed % * period_duration * tons_per_mwh / base_speed = tons per period
        # At 100% speed: 100 * 0.5 * 10 * 5.0 / 100 = 25 tons per period
        speeds = self.config["pulper_speeds"]  # [0, 60, 100, 120]
        base_speed = speeds[2]  # 100% - the reference speed for normalization
        production_factor = period_duration * self.config["tons_per_mwh"] * self.config["pulp_consumption_rate"] / base_speed
        total_production = pl.lpSum([pulper_speed[t] * production_factor for t in T])
        prob += overproduction >= total_production - self.production_target, "Overproduction_Definition"
        prob += underproduction >= self.production_target - total_production, "Underproduction_Definition"
        
        # Constraints
        speeds = self.config["pulper_speeds"]  # [0, 60, 100, 120]
        for t in T:
            # Speed selection: exactly one allowed speed
            prob += speed_0[t] + speed_60[t] + speed_100[t] + speed_120[t] == 1, f"Speed_Selection_{t}"
            # Pulper speed value (0*speed_0 term omitted since it's always 0)
            prob += pulper_speed[t] == speeds[1] * speed_60[t] + speeds[2] * speed_100[t] + speeds[3] * speed_120[t], f"Speed_Value_{t}"
            prob += pulper_power[t] == (
                pulper_power_map[speeds[0]] * speed_0[t] +
                pulper_power_map[speeds[1]] * speed_60[t] +
                pulper_power_map[speeds[2]] * speed_100[t] +
                pulper_power_map[speeds[3]] * speed_120[t]
            ), f"Pulper_Power_{t}"
            
            # Total load calculation
            prob += load[t] == (
                self.config["paper_machines"] * paper_machines[t] +  # NOW CONTROLLABLE
                self.config["critical_systems"] +
                pulper_power[t] +
                self.config["compressor_unit"] * (compressor_1[t] + compressor_2[t] + compressor_3[t]) +
                self.config["wastewater"] * wastewater[t]
            ), f"Load_Calc_{t}"
            
            # At least min_compressors must be ON
            prob += compressor_1[t] + compressor_2[t] + compressor_3[t] >= self.min_compressors, \
                    f"Min_Compressors_{t}"
            
            # Inventory dynamics
            pulp_production = self.config["pulp_consumption_rate"] * pulper_speed[t] / speeds[2]  # MW equivalent (normalized to 100%)
            pulp_consumption = self.config["pulp_consumption_rate"] * paper_machines[t]  # MW equivalent (only when paper machines ON)
            
            if t == 0:
                prob += inventory[t] == initial_inventory + \
                        (pulp_production - pulp_consumption) * period_duration, \
                        f"Inventory_Initial"
            else:
                prob += inventory[t] == inventory[t-1] + \
                        (pulp_production - pulp_consumption) * period_duration, \
                        f"Inventory_Dynamics_{t}"
            
            # Ramp rate constraint (MW per period)
            minutes_per_period = period_duration * 60  # Convert hours to minutes
            max_ramp = self.ramp_rate * minutes_per_period  # MW per period
            if t == 0:
                prob += load[t] - initial_load <= max_ramp, f"Ramp_Up_Initial"
                prob += initial_load - load[t] <= max_ramp, f"Ramp_Down_Initial"
            else:
                prob += load[t] - load[t-1] <= max_ramp, f"Ramp_Up_{t}"
                prob += load[t-1] - load[t] <= max_ramp, f"Ramp_Down_{t}"
        
        # Wastewater constraint: must run at least once every N hours
        periods_per_hour = int(1 / period_duration)  # 2 periods per hour (for 0.5h periods)
        periods_per_cycle = self.wastewater_frequency * periods_per_hour  # Convert hours to periods
        for k in range(0, n_periods - periods_per_cycle + 1):
            prob += pl.lpSum([wastewater[t] for t in range(k, k + periods_per_cycle)]) >= 1, \
                    f"Wastewater_Frequency_{k}"
        
        # Production target: REMOVED - now handled as soft constraint in objective
        # The old hard constraint forced minimum production, preventing pulper from going to 0%
        # Now the solver can choose to underproduce if inventory constraints require it
        
        # Calculate maximum possible production for validation
        max_speed = max(self.config["pulper_speeds"])
        max_production = n_periods * max_speed * production_factor
        if self.production_target > max_production:
            raise ValueError(
                f"Production target {self.production_target} tons exceeds maximum capacity "
                f"{max_production:.1f} tons for {request.forecast_horizon}-hour horizon "
                f"(pulper max speed: {max_speed}%)"
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
                error_msg += f"\n- Production target ({self.production_target} tons) may be too high for horizon"
                error_msg += f"\n- Inventory range ({self.min_inventory}-{self.max_inventory} hours) may be too narrow"
                error_msg += f"\n- Ramp rate ({self.ramp_rate} MW/min) may be too restrictive"
                error_msg += f"\n- Wastewater frequency ({self.wastewater_frequency} hours) may conflict with other constraints"
            raise RuntimeError(error_msg)
        
        # Build schedule
        schedule = self._build_schedule(
            request, n_periods, pulper_speed, compressor_1, compressor_2,
            compressor_3, wastewater, paper_machines, load, inventory, prices
        )
        
        # Calculate metrics
        total_cost = pl.value(prob.objective)
        baseline_metrics = self._calculate_baseline_metrics(prices, n_periods, request.mill_state.inventory_level)
        
        return OptimizationResult(
            schedule=schedule,
            baseline_schedule_sample=baseline_metrics['baseline_schedule_sample'],
            total_cost=total_cost,
            baseline_cost=baseline_metrics['baseline_cost'],
            baseline_avg_load=baseline_metrics['baseline_avg_load'],
            baseline_min_load=baseline_metrics['baseline_min_load'],
            baseline_max_load=baseline_metrics['baseline_max_load'],
            baseline_avg_inventory=baseline_metrics['baseline_avg_inventory'],
            baseline_min_inventory=baseline_metrics['baseline_min_inventory'],
            baseline_max_inventory=baseline_metrics['baseline_max_inventory'],
            savings=baseline_metrics['baseline_cost'] - total_cost,
            savings_percent=((baseline_metrics['baseline_cost'] - total_cost) / baseline_metrics['baseline_cost']) * 100,
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
        pulper_speed, c1, c2, c3, ww, pm, load, inventory, prices
    ) -> List[SchedulePeriod]:
        """Build schedule from solver solution."""
        schedule = []
        period_duration = self.config["period_duration"]
        
        for t in range(n_periods):
            timestamp = request.mill_state.timestamp + timedelta(minutes=30 * t)
            
            equipment = EquipmentSettings(
                pulper_speed=int(pl.value(pulper_speed[t])),
                compressor_1=bool(pl.value(c1[t])),
                compressor_2=bool(pl.value(c2[t])),
                compressor_3=bool(pl.value(c3[t])),
                wastewater_pump=bool(pl.value(ww[t])),
                paper_machines=bool(pl.value(pm[t]))  # NEW
            )
            
            expected_load = pl.value(load[t])
            expected_inventory = pl.value(inventory[t])
            price = prices[t]
            period_cost = price * expected_load * period_duration
            
            schedule.append(SchedulePeriod(
                timestamp=timestamp,
                equipment=equipment,
                expected_load=expected_load,
                expected_inventory=expected_inventory,
                price=price,
                period_cost=period_cost
            ))
        
        return schedule
    
    def _calculate_baseline_metrics(self, prices: List[float], n_periods: int, initial_inventory: float) -> dict:
        """
        Calculate baseline metrics using naive strategy:
        - Run equipment from period 0 onwards (no price optimization)
        - Respects production target but ignores price signals
        - Uses typical equipment configuration: pulper 100%, PM ON, 2 compressors, periodic wastewater
        
        This represents what an operator would do without price forecasts:
        just run equipment to meet production needs starting immediately.
        
        Returns:
            dict with baseline_cost, baseline_avg_load, baseline_min_load, baseline_max_load,
            baseline_avg_inventory, baseline_min_inventory, baseline_max_inventory, baseline_schedule_sample
        """
        period_duration = self.config["period_duration"]
        tons_per_mwh = self.config["tons_per_mwh"]
        
        # Baseline equipment configuration (typical operation)
        # PM ON, pulper 100%, 2 compressors, wastewater every 4 hours
        pm_load = self.config["paper_machines"]
        critical_load = self.config["critical_systems"]
        pulper_load = self.config["pulper_base"] * (100 / 100) ** 3  # 100% speed
        compressor_load = 2 * self.config["compressor_unit"]  # 2 compressors
        wastewater_load = self.config["wastewater"]
        
        # Production and consumption rates
        production_rate_per_period = self.config["pulp_consumption_rate"] * period_duration * tons_per_mwh  # tons
        consumption_rate_per_period = self.config["pulp_consumption_rate"] * period_duration  # MW-hours converted to hours of inventory
        
        # Calculate how many periods needed to meet production target
        if production_rate_per_period > 0:
            periods_needed = self.production_target / production_rate_per_period
            periods_needed = min(int(periods_needed) + 1, n_periods)  # Round up
        else:
            periods_needed = n_periods
        
        # Simulate baseline schedule
        baseline_cost = 0.0
        loads = []
        inventories = []
        schedule_sample = []  # Store first 12 periods for display
        current_inventory = initial_inventory
        
        for i in range(n_periods):
            if i < periods_needed:
                # Full production mode
                load = pm_load + critical_load + pulper_load + compressor_load
                has_wastewater = (i % 8 == 0)
                if has_wastewater:
                    load += wastewater_load
                
                # Inventory change: production - consumption
                # Production: pulper at 100% produces consumption_rate_per_period hours of inventory
                # Consumption: PM ON consumes consumption_rate_per_period hours of inventory
                # Net: 0 (balanced)
                inventory_change = 0.0
                
                # Store schedule info for first 12 periods
                if i < 12:
                    schedule_sample.append({
                        'period': i,
                        'pm': 'ON',
                        'pulper': 100,
                        'compressors': 2,
                        'wastewater': 'ON' if has_wastewater else 'OFF',
                        'load': load,
                        'inventory': current_inventory,
                        'price': prices[i],
                        'cost': prices[i] * load * period_duration
                    })
            else:
                # Minimal mode after production target met
                # Just critical systems + 1 compressor, no production, no consumption
                load = critical_load + self.config["compressor_unit"]
                inventory_change = 0.0
                
                # Store schedule info for first 12 periods
                if i < 12:
                    schedule_sample.append({
                        'period': i,
                        'pm': 'OFF',
                        'pulper': 0,
                        'compressors': 1,
                        'wastewater': 'OFF',
                        'load': load,
                        'inventory': current_inventory,
                        'price': prices[i],
                        'cost': prices[i] * load * period_duration
                    })
            
            current_inventory += inventory_change
            
            baseline_cost += prices[i] * load * period_duration
            loads.append(load)
            inventories.append(current_inventory)
        
        return {
            'baseline_cost': baseline_cost,
            'baseline_avg_load': sum(loads) / len(loads),
            'baseline_min_load': min(loads),
            'baseline_max_load': max(loads),
            'baseline_avg_inventory': sum(inventories) / len(inventories),
            'baseline_min_inventory': min(inventories),
            'baseline_max_inventory': max(inventories),
            'baseline_schedule_sample': schedule_sample
        }
    
    def _calculate_production(self, schedule: List[SchedulePeriod]) -> float:
        """Calculate total production in tons."""
        period_duration = self.config["period_duration"]
        tons_per_mwh = self.config["tons_per_mwh"]
        return sum(s.equipment.pulp_production_rate() * period_duration for s in schedule) * tons_per_mwh
