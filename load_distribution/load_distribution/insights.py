"""LLM-powered insights for optimization results using PydanticAI."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

from .models import OptimizationResult, SchedulePeriod


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

Focus on:
- WHY decisions were made (price patterns, constraints, trade-offs)
- WHAT the key strategies were (load shifting, inventory management)
- HOW much value was created (savings, efficiency gains)

Be specific with numbers, times, and equipment states. Avoid jargon - explain technical concepts simply.
Keep insights concise but insightful."""
        )
    
    async def generate_insights(
        self,
        result: OptimizationResult,
        location: str,
        forecast_start: datetime
    ) -> OptimizationInsight:
        """
        Generate insights from optimization results.
        
        Args:
            result: Optimization result with schedule and metrics
            location: Location ID
            forecast_start: Start time of forecast
            
        Returns:
            Structured insights
        """
        # Prepare context for LLM
        context = self._prepare_context(result, location, forecast_start)
        
        # Generate insights
        result_obj = await self.agent.run(context)
        return result_obj.data
    
    def _prepare_context(
        self,
        result: OptimizationResult,
        location: str,
        forecast_start: datetime
    ) -> str:
        """Prepare optimization context for LLM analysis."""
        
        # Find key periods
        schedule = result.schedule
        prices = [p.price for p in schedule]
        loads = [p.expected_load for p in schedule]
        inventories = [p.expected_inventory for p in schedule]
        
        # Price statistics
        min_price_idx = prices.index(min(prices))
        max_price_idx = prices.index(max(prices))
        avg_price = sum(prices) / len(prices)
        
        # Load statistics
        max_load_idx = loads.index(max(loads))
        min_load_idx = loads.index(min(loads))
        
        # Inventory statistics
        max_inv_idx = inventories.index(max(inventories))
        min_inv_idx = inventories.index(min(inventories))
        
        # Equipment patterns
        pulper_speeds = [p.equipment.pulper_speed for p in schedule]
        pulper_60_count = pulper_speeds.count(60)
        pulper_100_count = pulper_speeds.count(100)
        pulper_120_count = pulper_speeds.count(120)
        
        # Build context
        context = f"""Analyze this paper mill load optimization result:

LOCATION: {location}
FORECAST START: {forecast_start.strftime('%Y-%m-%d %H:%M')}
HORIZON: {len(schedule) // 2} hours ({len(schedule)} periods)

FINANCIAL RESULTS:
- Total Cost: ${result.total_cost:,.2f}
- Baseline Cost: ${result.baseline_cost:,.2f}
- Savings: ${result.savings:,.2f} ({result.savings_percent:.1f}%)

LOAD PROFILE:
- Average: {result.avg_load:.1f} MW
- Range: {result.min_load:.1f} - {result.max_load:.1f} MW
- Peak load at: {schedule[max_load_idx].timestamp.strftime('%I:%M %p')} ({loads[max_load_idx]:.1f} MW)
- Min load at: {schedule[min_load_idx].timestamp.strftime('%I:%M %p')} ({loads[min_load_idx]:.1f} MW)

INVENTORY MANAGEMENT:
- Average: {result.avg_inventory:.1f} hours
- Range: {result.min_inventory:.1f} - {result.max_inventory:.1f} hours
- Peak inventory at: {schedule[max_inv_idx].timestamp.strftime('%I:%M %p')} ({inventories[max_inv_idx]:.1f} hours)
- Min inventory at: {schedule[min_inv_idx].timestamp.strftime('%I:%M %p')} ({inventories[min_inv_idx]:.1f} hours)

PRICE PATTERNS:
- Average price: ${avg_price:.2f}/MWh
- Lowest price: ${prices[min_price_idx]:.2f}/MWh at {schedule[min_price_idx].timestamp.strftime('%I:%M %p')}
- Highest price: ${prices[max_price_idx]:.2f}/MWh at {schedule[max_price_idx].timestamp.strftime('%I:%M %p')}
- Price range: ${min(prices):.2f} - ${max(prices):.2f}/MWh

EQUIPMENT STRATEGY:
- Pulper at 60%: {pulper_60_count} periods ({pulper_60_count/len(schedule)*100:.0f}%)
- Pulper at 100%: {pulper_100_count} periods ({pulper_100_count/len(schedule)*100:.0f}%)
- Pulper at 120%: {pulper_120_count} periods ({pulper_120_count/len(schedule)*100:.0f}%)

PRODUCTION:
- Total: {result.total_production:.1f} tons
- Target: {result.production_target:.1f} tons
- Status: {'✓ Met' if result.total_production >= result.production_target else '✗ Below target'}

KEY PERIODS (first 6 hours):
"""
        
        # Add sample periods
        for i in range(min(12, len(schedule))):
            p = schedule[i]
            eq = p.equipment
            comp_count = sum([eq.compressor_1, eq.compressor_2, eq.compressor_3])
            context += f"\n{p.timestamp.strftime('%I:%M %p')}: Pulper {eq.pulper_speed}%, {comp_count} compressors, "
            context += f"Load {p.expected_load:.1f}MW, Inv {p.expected_inventory:.1f}h, Price ${p.price:.2f}/MWh"
        
        return context
