"""Command-line interface for load optimization."""

import sys
import os
import asyncio
import click
import pandas as pd
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.markdown import Markdown
from rich.columns import Columns
from rich.rule import Rule
from dotenv import load_dotenv

from .models import OptimizationRequest, OptimizationResult, MillState, PriceForecast
from .optimizer import LoadOptimizer
from .insights import InsightGenerator

# Load environment variables from .env file
load_dotenv()

console = Console()

# Try to import price prediction engine
PRICE_PREDICTION_AVAILABLE = False
predict_prices = None

try:
    # Add price_prediction to path
    price_pred_path = Path(__file__).parent.parent.parent / "price_prediction"
    if price_pred_path.exists():
        sys.path.insert(0, str(price_pred_path))
        from price_prediction.predict import predict_prices
        PRICE_PREDICTION_AVAILABLE = True
except ImportError as e:
    pass


@click.group()
def cli():
    """Paper mill load distribution optimizer."""
    pass


@cli.command()
@click.option('--location', type=str, required=True,
              help='Location ID (e.g., HAY2201)')
@click.option('--forecast-start', type=click.DateTime(formats=['%Y-%m-%d %H:%M', '%Y-%m-%d']),
              default='2024-03-07 00:00', show_default=True,
              help='Forecast start date and time (YYYY-MM-DD HH:MM or YYYY-MM-DD)')
@click.option('--current-inventory', type=click.FloatRange(2.0, 8.0), default=5.0, show_default=True,
              help='Current inventory level (hours)')
@click.option('--current-load', type=click.FloatRange(15.6, 28.2), default=22.8, show_default=True,
              help='Current load (MW) - affects ramp rate constraint')
@click.option('--current-pulper-speed', type=click.Choice(['0', '60', '100', '120']), default='100', show_default=True,
              help='Current pulper speed')
@click.option('--forecast-horizon', type=click.IntRange(1, 168), default=48, show_default=True,
              help='Forecast horizon (hours)')
@click.option('--output', type=click.Path(dir_okay=False, writable=True), default=None,
              help='Output CSV file path (optional)')
# Configurable constraints
@click.option('--min-inventory', type=click.FloatRange(0.0, 8.0), default=2.0, show_default=True,
              help='Minimum inventory level (hours) - safety buffer')
@click.option('--max-inventory', type=click.FloatRange(2.0, 10.0), default=8.0, show_default=True,
              help='Maximum inventory level (hours) - tank capacity')
@click.option('--production-target', type=click.FloatRange(0.0), default=250.0, show_default=True,
              help='Total production target for forecast period (tons) - not per day')
@click.option('--ramp-rate', type=click.FloatRange(min=0.1), default=0.5, show_default=True,
              help='Maximum load change rate (MW/min) - grid stability')
@click.option('--wastewater-frequency', type=click.IntRange(min=1), default=4, show_default=True,
              help='Wastewater must run every N hours - environmental compliance')
@click.option('--min-compressors', type=click.IntRange(1, 3), default=1, show_default=True,
              help='Minimum compressors that must be ON - process requirements')
@click.option('--ai-insights', is_flag=True, default=False,
              help='Generate AI-powered insights using Claude (requires ANTHROPIC_API_KEY)')
def optimize(location, forecast_start, current_inventory, current_load,
             current_pulper_speed, forecast_horizon, output,
             min_inventory, max_inventory, production_target,
             ramp_rate, wastewater_frequency, min_compressors,
             ai_insights):
    """Optimize load distribution using integrated price forecasting."""
    
    console.print()
    console.print(Rule("[bold cyan]Paper Mill Load Optimization[/bold cyan]", style="cyan"))
    console.print()
    
    # Convert string to int for pulper speed
    current_pulper_speed = int(current_pulper_speed)
    
    # Display all inputs
    _display_inputs_and_config(
        location, forecast_start, forecast_horizon,
        current_inventory, current_load, current_pulper_speed,
        min_inventory, max_inventory, production_target,
        ramp_rate, wastewater_frequency, min_compressors
    )
    
    # Call price prediction engine
    if not PRICE_PREDICTION_AVAILABLE:
        console.print("[red]✗ Price prediction engine not available[/red]")
        console.print("[yellow]Ensure price_prediction module dependencies are installed[/yellow]")
        return
    
    console.print("[cyan]Calling price prediction engine...[/cyan]\n")
    
    try:
        # Call price prediction engine with fixed context_days
        df_loc = predict_prices(
            forecast_start=forecast_start,
            forecast_hours=forecast_horizon,
            locations=[location],
            context_days=60  # Fixed at 60 days
        )
        
        if len(df_loc) == 0:
            console.print(f"[red]✗ No predictions generated for location {location}[/red]")
            return
            
    except Exception as e:
        console.print(f"[red]✗ Price prediction failed: {e}[/red]")
        raise
    
    # Create mill state
    mill_state = MillState(
        timestamp=forecast_start,
        inventory_level=current_inventory,
        current_load=current_load,
        production_today=0.0,  # Not used anymore
        current_pulper_speed=current_pulper_speed
    )
    
    # Create price forecast
    price_forecasts = [
        PriceForecast(
            timestamp=row['timestamp'],
            price_mean=row['mean'],
            price_p10=row.get('0.1'),
            price_p90=row.get('0.9')
        )
        for _, row in df_loc.iterrows()
    ]
    
    # Create request with custom constraints
    request = OptimizationRequest(
        mill_state=mill_state,
        price_forecast=price_forecasts,
        location=location,
        forecast_horizon=len(price_forecasts) // 2  # Convert periods to hours
    )
    
    # Create optimizer with custom config
    optimizer = LoadOptimizer(
        min_inventory=min_inventory,
        max_inventory=max_inventory,
        production_target=production_target,
        ramp_rate=ramp_rate,
        wastewater_frequency=wastewater_frequency,
        min_compressors=min_compressors
    )
    
    # Optimize
    console.print(f"[cyan]Optimizing {forecast_horizon}-hour schedule...[/cyan]")
    
    try:
        result = optimizer.optimize(request)
    except Exception as e:
        console.print(f"[red]✗ Optimization failed: {e}[/red]")
        raise
    
    # Display results
    _display_summary(result)
    
    _display_schedule_sample(result)
    
    # Generate AI insights if enabled (moved to end for better flow)
    if ai_insights:
        optimizer_config = {
            'min_inventory': min_inventory,
            'max_inventory': max_inventory,
            'production_target': production_target,
            'ramp_rate': ramp_rate,
            'wastewater_frequency': wastewater_frequency,
            'min_compressors': min_compressors
        }
        _display_ai_insights(result, request, optimizer_config)
    
    # Save if requested
    if output:
        _save_schedule(result, output)
        console.print(f"\n[green]✓ Schedule saved to: {output}[/green]")


def _display_inputs_and_config(location, forecast_start, horizon, inventory, current_load,
                               current_pulper_speed,
                               min_inv, max_inv, prod_target, ramp_rate, ww_freq, min_comp):
    """Display optimization inputs and configuration side-by-side."""
    
    # Calculate production bounds
    max_production = horizon * 2 * 120 * 0.25  # periods * max_speed * tons_per_period
    
    # Inputs table
    inputs_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    inputs_table.add_column("Parameter", style="cyan", no_wrap=True)
    inputs_table.add_column("Value", style="white", justify="right")
    
    inputs_table.add_row("Location", location)
    inputs_table.add_row("Start Date/Time", forecast_start.strftime("%Y-%m-%d %H:%M"))
    inputs_table.add_row("Forecast Horizon", f"{horizon} hours")
    inputs_table.add_row("Context Days", "60 days")
    inputs_table.add_row("Current Inventory", f"{inventory} hours")
    inputs_table.add_row("Current Load", f"{current_load} MW")
    inputs_table.add_row("Current Pulper Speed", f"{current_pulper_speed}%")
    
    inputs_panel = Panel(
        inputs_table,
        title="[bold]📊 Inputs[/bold]",
        border_style="cyan",
        box=box.ROUNDED
    )
    
    # Configuration table
    config_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    config_table.add_column("Constraint", style="yellow", no_wrap=True)
    config_table.add_column("Value", style="white", justify="right")
    
    config_table.add_row("Inventory Range", f"{min_inv}-{max_inv}h")
    config_table.add_row("Production Target", f"{prod_target} tons")
    config_table.add_row("Production Bounds", f"0-{max_production:.0f} tons")
    config_table.add_row("Ramp Rate Limit", f"{ramp_rate} MW/min")
    config_table.add_row("Wastewater Freq", f"Every {ww_freq}h")
    config_table.add_row("Min Compressors", f"{min_comp}")
    config_table.add_row("Load Range", "15.6-28.2 MW")
    config_table.add_row("Pulper Speeds", "0%, 60%, 100%, 120%")
    
    config_panel = Panel(
        config_table,
        title="[bold]⚙️  Configuration[/bold]",
        border_style="yellow",
        box=box.ROUNDED
    )
    
    # Display side-by-side
    console.print(Columns([inputs_panel, config_panel], equal=True, expand=True))
    console.print()





def _display_summary(result):
    """Display optimization results and metrics."""
    console.print()
    console.print(Rule("[bold green]✓ Optimization Complete[/bold green]", style="green"))
    console.print()
    
    # Results in a prominent panel
    savings_text = f"[green]${result.savings:,.2f} ({result.savings_percent:.1f}%)[/green]" if result.savings > 0 else f"[red]${result.savings:,.2f} ({result.savings_percent:.1f}%)[/red]"
    console.print(Panel(
        f"[white]Total Cost:[/white] [bold]${result.total_cost:,.2f}[/bold]\n"
        f"[white]Baseline Cost:[/white] ${result.baseline_cost:,.2f}\n"
        f"[white]Savings:[/white] [bold]{savings_text}[/bold]\n\n"
        f"[dim]Solve Time: {result.solve_time:.2f}s | Status: {result.solver_status}[/dim]",
        title="[bold green]💰 Financial Results[/bold green]",
        border_style="green",
        box=box.DOUBLE,
        padding=(1, 2)
    ))
    
    # Metrics table - characteristics of the solution
    table = Table(show_header=True, box=box.ROUNDED, title="[bold]📈 Solution Metrics[/bold]")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white", justify="right")
    table.add_column("Description", style="dim")
    
    table.add_row("Average Load", f"{result.avg_load:.1f} MW", 
                  "Mean power consumption")
    table.add_row("Load Range", f"{result.min_load:.1f} - {result.max_load:.1f} MW",
                  "Min/max power used")
    table.add_row("Average Inventory", f"{result.avg_inventory:.1f} hours",
                  "Mean pulp storage level")
    table.add_row("Inventory Range", f"{result.min_inventory:.1f} - {result.max_inventory:.1f} hours",
                  "Min/max storage used")
    table.add_row("Total Production", f"{result.total_production:.1f} tons",
                  "Paper produced")
    table.add_row("Production Target", f"{result.production_target:.1f} tons",
                  "Required production")
    
    console.print()
    console.print(table)


def _display_ai_insights(result, request: OptimizationRequest, optimizer_config: dict):
    """Display AI-generated insights about the optimization."""
    
    from .config import MILL_CONFIG
    
    # Check for API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        console.print("\n[yellow]⚠ AI insights disabled: ANTHROPIC_API_KEY not set[/yellow]")
        console.print("[dim]Set ANTHROPIC_API_KEY in .env file[/dim]\n")
        return
    
    console.print()
    console.print(Rule("[bold magenta]🤖 AI-Powered Analysis[/bold magenta]", style="magenta"))
    console.print()
    console.print("[cyan]Generating insights using Claude Sonnet 4.5...[/cyan]")
    
    try:
        # Prepare comprehensive context
        context = _prepare_optimization_context(result, request, optimizer_config)
        
        # Generate insights
        generator = InsightGenerator()
        insights = asyncio.run(generator.generate_insights(context))
        
        # Display optimization context header
        console.print()
        context_text = (
            f"[bold]Location:[/bold] {request.location}\n"
            f"[bold]Optimization Date:[/bold] {request.mill_state.timestamp.strftime('%Y-%m-%d %H:%M')}\n"
            f"[bold]Forecast Horizon:[/bold] {request.forecast_horizon} hours ({len(result.schedule)} periods)\n"
            f"[bold]Initial Conditions:[/bold] {request.mill_state.inventory_level:.1f}h inventory, "
            f"{request.mill_state.current_load:.1f} MW load\n"
            f"[bold]Constraints:[/bold] Inventory {optimizer_config['min_inventory']:.1f}-{optimizer_config['max_inventory']:.1f}h, "
            f"Load {MILL_CONFIG['min_load']:.1f}-{MILL_CONFIG['max_load']:.1f} MW, "
            f"Production target {optimizer_config['production_target']:.0f} tons/day"
        )
        console.print(Panel(
            context_text,
            title="[bold white]📋 Optimization Context[/bold white]",
            border_style="white",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        
        # Display insights with improved formatting
        console.print()
        console.print(Panel(
            f"[bold white]{insights.executive_summary}[/bold white]",
            title="[bold magenta]💡 AI-Powered Insights[/bold magenta]",
            border_style="magenta",
            box=box.DOUBLE,
            padding=(1, 2)
        ))
        
        # Key decisions in a panel
        decisions_text = "\n".join([
            f"[cyan]{i}.[/cyan] {decision}" 
            for i, decision in enumerate(insights.key_decisions, 1)
        ])
        console.print()
        console.print(Panel(
            decisions_text,
            title="[bold cyan]🎯 Key Decisions[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        
        # Strategies in panels
        console.print()
        console.print(Panel(
            f"[white]{insights.price_strategy}[/white]",
            title="[bold green]💰 Price Exploitation Strategy[/bold green]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        
        console.print()
        console.print(Panel(
            f"[white]{insights.inventory_strategy}[/white]",
            title="[bold blue]📦 Inventory Management Strategy[/bold blue]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        
        # Risk considerations
        if insights.risk_considerations:
            risks_text = "\n".join([
                f"[yellow]•[/yellow] {risk}" 
                for risk in insights.risk_considerations
            ])
            console.print()
            console.print(Panel(
                risks_text,
                title="[bold yellow]⚠️  Risk Considerations[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(1, 2)
            ))
        
        console.print()
        
    except Exception as e:
        console.print(f"\n[yellow]⚠ Could not generate insights: {e}[/yellow]\n")


def _prepare_optimization_context(
    result: OptimizationResult,
    request: OptimizationRequest,
    optimizer_config: dict
) -> str:
    """Prepare optimization context for LLM analysis."""
    
    from .config import MILL_CONFIG
    
    schedule = result.schedule
    prices = [p.price for p in schedule]
    loads = [p.expected_load for p in schedule]
    inventories = [p.expected_inventory for p in schedule]
    
    # Price analysis
    min_price, max_price, avg_price = min(prices), max(prices), sum(prices) / len(prices)
    
    # Equipment patterns
    pulper_speeds = [p.equipment.pulper_speed for p in schedule]
    speed_counts = {s: pulper_speeds.count(s) for s in [60, 100, 120]}
    
    # Build context
    context = f"""# OPTIMIZATION ANALYSIS

## Setup
Location: {request.location} | Start: {request.mill_state.timestamp.strftime('%Y-%m-%d %H:%M')} | Horizon: {request.forecast_horizon}h
Initial: {request.mill_state.inventory_level:.1f}h inventory, {request.mill_state.current_load:.1f}MW load
Constraints: Inventory {optimizer_config['min_inventory']:.1f}-{optimizer_config['max_inventory']:.1f}h, Load {MILL_CONFIG['min_load']:.1f}-{MILL_CONFIG['max_load']:.1f}MW, Target {optimizer_config['production_target']:.0f} tons/day

## Results
Cost: ${result.total_cost:,.2f} (baseline ${result.baseline_cost:,.2f}) → Savings: ${result.savings:,.2f} ({result.savings_percent:.1f}%)
Load: {result.avg_load:.1f}MW avg ({result.min_load:.1f}-{result.max_load:.1f}MW)
Inventory: {result.avg_inventory:.1f}h avg ({result.min_inventory:.1f}-{result.max_inventory:.1f}h)
Production: {result.total_production:.1f}/{result.production_target:.1f} tons

## Price Pattern
Range: ${min_price:.2f}-${max_price:.2f}/MWh (avg ${avg_price:.2f}, spread ${max_price-min_price:.2f})

## Equipment Strategy
Pulper: 60%={speed_counts[60]}p, 100%={speed_counts[100]}p, 120%={speed_counts[120]}p

## Schedule (first 24 periods)
"""
    
    # Add schedule sample (first 24 periods = 12 hours)
    for i, p in enumerate(schedule[:24]):
        eq = p.equipment
        comp = sum([eq.compressor_1, eq.compressor_2, eq.compressor_3])
        ww = "WW" if eq.wastewater_pump else "--"
        context += f"\n{i:2d} {p.timestamp.strftime('%H:%M')} | P:{eq.pulper_speed:3d}% C:{comp} {ww} | {p.expected_load:4.1f}MW {p.expected_inventory:3.1f}h | ${p.price:5.2f}/MWh ${p.period_cost:6.2f}"
    
    context += f"\n... {len(schedule)-24} more periods\n"
    
    return context


def _display_schedule_sample(result):
    """Display sample of optimized schedule."""
    console.print()
    console.print(Rule("[bold cyan]📅 Recommended Schedule[/bold cyan]", style="cyan"))
    console.print()
    console.print("[dim]First 12 periods (30-minute intervals)[/dim]\n")
    
    table = Table(show_header=True, box=box.ROUNDED)
    table.add_column("Time", style="cyan", width=16)
    table.add_column("Pulper\n%", justify="right", style="yellow", width=8)
    table.add_column("Comp.", justify="center", style="green", width=6)
    table.add_column("WW", justify="center", style="blue", width=4)
    table.add_column("Load\nMW", justify="right", style="white", width=8)
    table.add_column("Inv.\nhrs", justify="right", style="magenta", width=8)
    table.add_column("Price\n$/MWh", justify="right", style="yellow", width=10)
    table.add_column("Cost\n$", justify="right", style="red", width=10)
    
    for period in result.schedule[:12]:
        eq = period.equipment
        compressors = sum([eq.compressor_1, eq.compressor_2, eq.compressor_3])
        ww = "ON" if eq.wastewater_pump else "OFF"
        
        table.add_row(
            period.timestamp.strftime("%m/%d %I:%M %p"),
            f"{eq.pulper_speed}",
            f"{compressors}/3",
            ww,
            f"{period.expected_load:.1f}",
            f"{period.expected_inventory:.1f}",
            f"${period.price:.2f}",
            f"${period.period_cost:.2f}"
        )
    
    console.print(table)
    console.print(f"\n[dim]... {len(result.schedule) - 12} more periods[/dim]\n")


def _save_schedule(result, output_path: str):
    """Save schedule to CSV."""
    data = []
    for period in result.schedule:
        eq = period.equipment
        data.append({
            'timestamp': period.timestamp,
            'pulper_speed': eq.pulper_speed,
            'compressor_1': eq.compressor_1,
            'compressor_2': eq.compressor_2,
            'compressor_3': eq.compressor_3,
            'wastewater_pump': eq.wastewater_pump,
            'expected_load': period.expected_load,
            'expected_inventory': period.expected_inventory,
            'price': period.price,
            'period_cost': period.period_cost
        })
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)


if __name__ == '__main__':
    cli()
