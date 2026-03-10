"""LLM-powered insights for optimization results using PydanticAI."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent


class OptimizationInsight(BaseModel):
    """Structured insights from optimization recommendations."""
    
    executive_summary: str = Field(
        description="2-3 sentence summary of the RECOMMENDED optimization strategy and PROJECTED results"
    )
    
    key_decisions: List[str] = Field(
        description="3-5 bullet points explaining the most important RECOMMENDED decisions that would drive savings"
    )
    
    price_strategy: str = Field(
        description="How the optimizer PROPOSES to exploit price patterns (peak avoidance, valley loading, etc.)"
    )
    
    inventory_strategy: str = Field(
        description="How inventory SHOULD BE used as a buffer to enable load shifting"
    )
    
    risk_considerations: Optional[List[str]] = Field(
        default=None,
        description="Potential risks or tight constraints to monitor IF THIS STRATEGY IS IMPLEMENTED (optional)"
    )


def _load_system_prompt() -> str:
    """Load system prompt from markdown file."""
    prompt_path = Path(__file__).parent / "prompts" / "insights_system.md"
    return prompt_path.read_text()


class InsightGenerator:
    """Generate natural language insights from optimization results using Claude."""
    
    def __init__(self):
        """Initialize insight generator with Claude 3.5 Sonnet."""
        # AnthropicModel reads API key from ANTHROPIC_API_KEY env var automatically
        system_prompt = _load_system_prompt()
        
        self.agent = Agent(
            model='anthropic:claude-sonnet-4-5',
            output_type=OptimizationInsight,
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
        return result_obj.output

