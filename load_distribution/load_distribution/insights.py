"""LLM-powered insights for optimization results using PydanticAI."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from .models import OptimizationResult, SchedulePeriod, OptimizationRequest


class OptimizationInsight(BaseModel):
    """Structured insights from optimization results."""
    
    executive_summary: str = Field(
        description="2-3 sentence summary of the optimization strategy and key results"
    )
    
    key_decisions: List[str] = Field(
        description="3-5 bullet points explaining the most important decisions that drove savings"
    )
    
    price_strategy: str = Field(
        description="How the optimizer exploited price patterns (peak avoidance, valley loading, etc.)"
    )
    
    inventory_strategy: str = Field(
        description="How inventory was used as a buffer to enable load shifting"
    )
    
    risk_considerations: Optional[List[str]] = Field(
        default=None,
        description="Potential risks or tight constraints to monitor (optional)"
    )


class InsightGenerator:
    """Generate natural language insights from optimization results."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize insight generator.
        
        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY env var
        """
        # Use GPT-4o-mini for fast, cost-effective insights
        model = OpenAIModel('gpt-4o-mini', api_key=api_key)
        
        self.agent = Agent(
            model=model,
            result_type=OptimizationInsight,
            system_prompt="""You are an expert energy analyst specializing in industrial load optimization.

Your role is to explain optimization results in clear, actionable language that operations managers can understand.

You have access to:
- The complete optimization schedule (every 30-min period)
- Equipment states (pulper speed, compressors, wastewater pump)
- Price forecasts and actual costs
- Inventory levels throughout the horizon
- Constraint settings (ramp rates, inventory limits, production targets)

Focus on:
- WHY decisions were made (price patterns, constraints, trade-offs)
- WHAT the key strategies were (load shifting, inventory management, equipment cycling)
- HOW much value was created (savings, efficiency gains)
- WHEN critical decisions happened (specific times and prices)

Be specific with numbers, times, and equipment states. Explain the cause-and-effect relationships.
Identify patterns like:
- Building inventory during cheap periods to enable load reduction during expensive periods
- Cycling equipment to match price patterns
- Constraint-driven decisions (ramp rates, inventory limits)
- Trade-offs between production, cost, and operational constraints

Keep insights concise but insightful. Avoid jargon - explain technical concepts simply."""
        )
    
    async def generate_insights(
        self,
        result: OptimizationResult,
        request: OptimizationRequest,
        optimizer_config: dict
    ) -> OptimizationInsight:
        """
        Generate insights from optimization results.
        
        Args:
            result: Optimization result with schedule and metrics
            request: Original optimization request with constraints
            optimizer_config: Optimizer configuration (constraints, bounds)
            
        Returns:
            Structured insights
        """
        # Prepare rich context for LLM
        context = self._prepare_rich_context(result, request, optimizer_config)
        
        # Generate insights
        result_obj = await self.agent.run(context)
        return result_obj.data
    
    def _prepare_rich_context(
        self,
        result: OptimizationResult,
        request: OptimizationRequest,
        optimizer_config: dict
    ) -> str:
        """Prepare comprehensive optimization context for LLM analysis."""
        
        schedule = result.schedule
        
        # Analyze price patterns
        prices = [p.price for p in schedule]
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        price_spread = max_price - min_price
        
        # Find key periods
        min_price_periods = [i for i, p in enumerate(prices) if p == min_price]
        max_price_periods = [i for i, p in enumerate(prices) if p == max_price]
        
        # Analyze load patterns
        loads = [p.expected_load for p in schedule]
        max_load_periods = [i for i, l in enumerate(loads) if l >= max(loads) - 0.5]
        min_load_periods = [i for i, l in enumerate(loads) if l <= min(loads) + 0.5]
        
        # Analyze inventory patterns
        inventories = [p.expected_inventory for p in schedule]
        max_inv_idx = inventories.index(max(inventories))
        min_inv_idx = inventories.index(min(inventories))
        
        # Equipment patterns
        pulper_speeds = [p.equipment.pulper_speed for p in schedule]
        pulper_changes = sum(1 for i in range(1, len(pulper_speeds)) if pulper_speeds[i] != pulper_speeds[i-1])
        
        compressor_counts = [
            sum([p.equipment.compressor_1, p.equipment.compressor_2, p.equipment.compressor_3])
            for p in schedule
        ]
        
        # Identify strategic periods
        high_load_low_price = [
            i for i in range(len(schedule))
            if loads[i] > avg_price and prices[i] < avg_price
        ]
        
        low_load_high_price = [
            i for i in range(len(schedule))
            if loads[i] < result.avg_load and prices[i] > avg_price
        ]
        
        # Build comprehensive context
        context = f"""# OPTIMIZATION ANALYSIS REQUEST

## PROBLEM SETUP

Location: {request.location}
Start Time: {request.mill_state.timestamp.strftime('%Y-%m-%d %H:%M')}
Horizon: {request.forecast_horizon} hours ({len(schedule)} periods)

Initial State:
- Inventory: {request.mill_state.inventory_level:.1f} hours
- Current Load: {request.mill_state.current_load:.1f} MW
- Production Today: {request.mill_state.production_today:.1f} tons

## CONSTRAINTS & CONFIGURATION

Inventory Limits: {optimizer_config['min_inventory']:.1f} - {optimizer_config['max_inventory']:.1f} hours
Load Limits: {optimizer_config['min_load']:.1f} - {optimizer_config['max_load']:.1f} MW
Production Target: {optimizer_config['production_target']:.1f} tons/day
Ramp Rate Limit: {optimizer_config['ramp_rate']:.1f} MW/min
Wastewater Frequency: Every {optimizer_config['wastewater_frequency']} hours
Min Compressors: {optimizer_config['min_compressors']}
Allowed Pulper Speeds: {[60, 100, 120] if optimizer_config.get('allow_pulper_60') and optimizer_config.get('allow_pulper_120') else [100]}%

## OPTIMIZATION RESULTS

Financial:
- Total Cost: ${result.total_cost:,.2f}
- Baseline Cost: ${result.baseline_cost:,.2f}
- Savings: ${result.savings:,.2f} ({result.savings_percent:.1f}%)
- Solve Time: {result.solve_time:.2f}s

Load Profile:
- Average: {result.avg_load:.1f} MW
- Range: {result.min_load:.1f} - {result.max_load:.1f} MW
- High load periods: {len(max_load_periods)} ({len(max_load_periods)/len(schedule)*100:.0f}%)
- Low load periods: {len(min_load_periods)} ({len(min_load_periods)/len(schedule)*100:.0f}%)

Inventory Management:
- Average: {result.avg_inventory:.1f} hours
- Range: {result.min_inventory:.1f} - {result.max_inventory:.1f} hours
- Peak at: {schedule[max_inv_idx].timestamp.strftime('%I:%M %p')} ({inventories[max_inv_idx]:.1f} hours)
- Trough at: {schedule[min_inv_idx].timestamp.strftime('%I:%M %p')} ({inventories[min_inv_idx]:.1f} hours)
- Inventory swing: {max(inventories) - min(inventories):.1f} hours

Production:
- Total: {result.total_production:.1f} tons
- Target: {result.production_target:.1f} tons
- Status: {'✓ Met' if result.total_production >= result.production_target else '✗ Below target'}

## PRICE PATTERNS

Price Statistics:
- Average: ${avg_price:.2f}/MWh
- Range: ${min_price:.2f} - ${max_price:.2f}/MWh
- Spread: ${price_spread:.2f}/MWh ({price_spread/avg_price*100:.0f}% of average)
- Lowest price periods: {min_price_periods[:3]} (indices)
- Highest price periods: {max_price_periods[:3]} (indices)

## EQUIPMENT STRATEGY

Pulper:
- Speed changes: {pulper_changes} times
- 60% usage: {pulper_speeds.count(60)} periods ({pulper_speeds.count(60)/len(schedule)*100:.0f}%)
- 100% usage: {pulper_speeds.count(100)} periods ({pulper_speeds.count(100)/len(schedule)*100:.0f}%)
- 120% usage: {pulper_speeds.count(120)} periods ({pulper_speeds.count(120)/len(schedule)*100:.0f}%)

Compressors:
- Average active: {sum(compressor_counts)/len(compressor_counts):.1f}
- 1 compressor: {compressor_counts.count(1)} periods
- 2 compressors: {compressor_counts.count(2)} periods
- 3 compressors: {compressor_counts.count(3)} periods

## STRATEGIC PATTERNS

High Load + Low Price: {len(high_load_low_price)} periods (good - loading during cheap periods)
Low Load + High Price: {len(low_load_high_price)} periods (good - reducing during expensive periods)

## COMPLETE SCHEDULE (All {len(schedule)} periods)

"""
        
        # Add complete schedule
        for i, p in enumerate(schedule):
            eq = p.equipment
            comp_count = sum([eq.compressor_1, eq.compressor_2, eq.compressor_3])
            ww = "ON" if eq.wastewater_pump else "OFF"
            
            # Calculate changes from previous period
            if i > 0:
                prev = schedule[i-1]
                load_change = p.expected_load - prev.expected_load
                inv_change = p.expected_inventory - prev.expected_inventory
                price_change = p.price - prev.price
                change_str = f" | ΔLoad: {load_change:+.1f}MW, ΔInv: {inv_change:+.1f}h, ΔPrice: ${price_change:+.2f}"
            else:
                change_str = ""
            
            context += f"\nPeriod {i:3d} | {p.timestamp.strftime('%m/%d %I:%M%p')} | "
            context += f"Pulper: {eq.pulper_speed:3d}% | Comp: {comp_count}/3 | WW: {ww:3s} | "
            context += f"Load: {p.expected_load:5.1f}MW | Inv: {p.expected_inventory:4.1f}h | "
            context += f"Price: ${p.price:6.2f}/MWh | Cost: ${p.period_cost:7.2f}{change_str}"
        
        context += f"""

## ANALYSIS INSTRUCTIONS

Based on this complete optimization data:

1. Identify the 3-5 most important decisions that drove the ${result.savings:,.2f} savings
2. Explain HOW the optimizer exploited the ${price_spread:.2f}/MWh price spread
3. Explain WHY inventory swung from {result.min_inventory:.1f} to {result.max_inventory:.1f} hours
4. Identify any periods where constraints were binding or decisions were forced
5. Note any risks (tight inventory, binding ramp rates, near-constraint violations)

Be specific with period numbers, times, prices, and equipment states."""
        
        return context
