"""Pydantic models for load optimization."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


class MillState(BaseModel):
    """Current state of the paper mill."""
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime
    inventory_level: float = Field(ge=2.0, le=8.0, description="Hours of pulp in storage")
    current_load: float = Field(ge=15.6, le=28.2, description="Current power consumption (MW)")
    production_today: float = Field(ge=0, description="Tons produced so far today")
    current_pulper_speed: int = Field(description="Current pulper speed (%)")
    
    @field_validator('current_pulper_speed')
    @classmethod
    def validate_pulper_speed(cls, v):
        if v not in [60, 100, 120]:
            raise ValueError(f"Pulper speed must be 60, 100, or 120, got {v}")
        return v


class PriceForecast(BaseModel):
    """Price forecast for a single time period."""
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime
    price_mean: float = Field(gt=0, description="Mean price forecast ($/MWh)")
    price_p10: Optional[float] = Field(default=None, description="10th percentile")
    price_p90: Optional[float] = Field(default=None, description="90th percentile")


class EquipmentSettings(BaseModel):
    """Equipment settings for a single time period."""
    model_config = ConfigDict(frozen=True)
    
    pulper_speed: int = Field(description="Pulper speed (%)")
    compressor_1: bool = Field(description="Compressor 1 state")
    compressor_2: bool = Field(description="Compressor 2 state")
    compressor_3: bool = Field(description="Compressor 3 state")
    wastewater_pump: bool = Field(description="Wastewater pump state")
    
    @field_validator('pulper_speed')
    @classmethod
    def validate_pulper_speed(cls, v):
        if v not in [60, 100, 120]:
            raise ValueError(f"Pulper speed must be 60, 100, or 120, got {v}")
        return v
    
    def total_load(self) -> float:
        """Calculate total mill load for these settings."""
        from .config import MILL_CONFIG
        
        # Paper machines + critical (constant)
        load = MILL_CONFIG["paper_machines"] + MILL_CONFIG["critical_systems"]
        
        # Pulper (cubic law)
        load += MILL_CONFIG["pulper_base"] * (self.pulper_speed / 100) ** 3
        
        # Compressors
        load += sum([self.compressor_1, self.compressor_2, self.compressor_3]) * MILL_CONFIG["compressor_unit"]
        
        # Wastewater
        load += MILL_CONFIG["wastewater"] if self.wastewater_pump else 0.0
        
        return load
    
    def pulp_production_rate(self) -> float:
        """Calculate pulp production rate (MW equivalent)."""
        from .config import MILL_CONFIG
        return MILL_CONFIG["pulp_consumption_rate"] * (self.pulper_speed / 100)


class SchedulePeriod(BaseModel):
    """Optimized schedule for a single time period."""
    model_config = ConfigDict(frozen=True)
    
    timestamp: datetime
    equipment: EquipmentSettings
    expected_load: float = Field(description="Expected power consumption (MW)")
    expected_inventory: float = Field(description="Expected inventory level (hours)")
    price: float = Field(description="Electricity price ($/MWh)")
    period_cost: float = Field(description="Cost for this period ($)")


class OptimizationResult(BaseModel):
    """Complete optimization result."""
    model_config = ConfigDict(frozen=True)
    
    schedule: List[SchedulePeriod]
    total_cost: float = Field(description="Total cost ($)")
    baseline_cost: float = Field(description="Baseline cost at constant load ($)")
    savings: float = Field(description="Cost savings ($)")
    savings_percent: float = Field(description="Savings percentage")
    
    avg_load: float = Field(description="Average load (MW)")
    min_load: float = Field(description="Minimum load (MW)")
    max_load: float = Field(description="Maximum load (MW)")
    
    min_inventory: float = Field(description="Minimum inventory (hours)")
    max_inventory: float = Field(description="Maximum inventory (hours)")
    avg_inventory: float = Field(description="Average inventory (hours)")
    
    total_production: float = Field(description="Total production (tons)")
    production_target: float = Field(description="Production target (tons)")
    
    solve_time: float = Field(description="Solver time (seconds)")
    solver_status: str = Field(description="Solver status")


class OptimizationRequest(BaseModel):
    """Request for load optimization."""
    model_config = ConfigDict(frozen=True, validate_assignment=True)
    
    mill_state: MillState
    price_forecast: List[PriceForecast]
    location: str = Field(description="Location ID (e.g., HAY2201)")
    forecast_horizon: int = Field(default=48, ge=1, le=168, description="Hours to optimize")
    
    @field_validator('price_forecast', mode='after')
    @classmethod
    def validate_forecast_length(cls, v, info):
        """Ensure forecast covers the horizon."""
        # Get forecast_horizon from context, or infer from price_forecast length
        horizon = info.data.get('forecast_horizon')
        if horizon is None:
            # Infer from price forecast length (periods / 2 = hours)
            horizon = len(v) // 2
        
        required_periods = horizon * 2  # 30-min periods
        if len(v) < required_periods:
            raise ValueError(
                f"Price forecast must have at least {required_periods} periods "
                f"for {horizon}-hour horizon, got {len(v)}"
            )
        return v
