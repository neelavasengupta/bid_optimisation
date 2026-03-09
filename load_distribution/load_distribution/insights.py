"""LLM-powered insights for optimization results using PydanticAI."""

from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel


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

You receive a comprehensive optimization report with:
- Problem setup (location, time, initial state)
- All constraints and configuration
- Complete schedule (every 30-min period with equipment states, loads, inventory, prices)
- Financial results and metrics
- Strategic pattern analysis

Your job is to:
1. Identify the 3-5 most important decisions that drove savings
2. Explain HOW the optimizer exploited price patterns
3. Explain WHY inventory was managed the way it was
4. Identify constraint-driven vs. strategic decisions
5. Note any risks or tight constraints to monitor

Be specific with:
- Times and period numbers
- Equipment states (pulper speeds, compressor counts)
- Prices and costs
- Cause-and-effect relationships

Explain technical concepts simply. Focus on actionable insights, not just descriptions."""
        )
    
    async def generate_insights(self, context: str) -> OptimizationInsight:
        """
        Generate insights from optimization context.
        
        Args:
            context: Complete optimization report as formatted string
            
        Returns:
            Structured insights
        """
        result_obj = await self.agent.run(context)
        return result_obj.data

