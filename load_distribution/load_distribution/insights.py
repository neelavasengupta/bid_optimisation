"""LLM-powered insights for optimization results using PydanticAI."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel


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


def _load_system_prompt() -> str:
    """Load system prompt from markdown file."""
    prompt_path = Path(__file__).parent / "prompts" / "insights_system.md"
    return prompt_path.read_text()


class InsightGenerator:
    """Generate natural language insights from optimization results using Claude."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize insight generator.
        
        Args:
            api_key: Anthropic API key. If None, will use ANTHROPIC_API_KEY env var
        """
        model = AnthropicModel('claude-3-5-sonnet-20241022', api_key=api_key)
        system_prompt = _load_system_prompt()
        
        self.agent = Agent(
            model=model,
            result_type=OptimizationInsight,
            system_prompt=system_prompt
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

