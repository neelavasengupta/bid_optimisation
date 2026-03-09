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

from .models import OptimizationRequest, MillState, PriceForecast
from .optimizer import LoadOptimizer
from .insights import InsightGenerator

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
@click.option('--date', type=str, default='2024-03-07', show_default=True,
              help='Forecast start date (YYYY-MM-DD)')
@click.option('--time', type=str, default='00:00', show_default=True,
              help='Forecast start time (HH:MM)')
@click.option('--current-inventory', type=float, default=5.0, show_default=True,
              help='Current inventory level (hours)')
@click.option('--current-load', type=float, default=22.8, show_default=True,
              help='Current load (MW) - affects ramp rate constraint')
@click.option('--forecast-horizon', type=int, default=48, show_default=True,
              help='Forecast horizon (hours)')
@click.option('--output', type=click.Path(), default=None,
              help='Output CSV file path (optional)')
# Configurable constraints
@click.option('--min-inventory', type=float, default=2.0, show_default=True,
              help='Minimum inventory level (hours) - safety buffer')
@click.option('--max-inventory', type=float, default=8.0, show_default=True,
              help='Maximum inventory level (hours) - tank capacity')
@click.option('--production-target', type=float, default=500.0, show_default=True,
              help='Daily production target (tons) - affects minimum pulper speed')
@click.option('--ramp-rate', type=float, default=0.5, show_default=True,
              help='Maximum load change rate (MW/min) - grid stability')
@click.option('--wastewater-frequency', type=int, default=4, show_default=True,
              help='Wastewater must run every N hours - environmental compliance')
@click.option('--min-compressors', type=int, default=1, show_default=True,
              help='Minimum compressors that must be ON - process requirements')
@click.option('--enable-insights/--no-insights', default=True, show_default=True,
              help='Generate AI-powered insights (requires OPENAI_API_KEY)')
def optimize(location, date, time, current_inventory, current_load,
             forecast_horizon, output,
             min_inventory, max_inventory, production_target,
             ramp_rate, wastewater_frequency, min_compressors,
             enable_insights):
    """Optimize load distribution using integrated price forecasting."""
    
    console.print("\n[bold cyan]Paper Mill Load Optimization[/bold cyan]\n")
    
    # Parse forecast start time
    date_str = f"{date} {time}"
    try:
        forecast_start_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        console.print("[red]✗ Invalid date/time format. Use: YYYY-MM-DD for date, HH:MM for time[/red]")
        return
    
    # Display all inputs
    _display_inputs(
        location, forecast_start_dt, forecast_horizon,
        current_inventory, current_load
    )
    
    # Display configuration
    _display_configuration(
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
            forecast_start=forecast_start_dt,
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
        timestamp=forecast_start_dt,
        inventory_level=current_inventory,
        current_load=current_load,
        production_today=0.0,  # Fixed - always start fresh day
        current_pulper_speed=100
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
    
    # Create optimizer with custom config (fixed load bounds and all pulper speeds allowed)
    optimizer = LoadOptimizer(
        min_inventory=min_inventory,
        max_inventory=max_inventory,
        production_target=production_target,
        min_load=15.6,  # Fixed
        max_load=28.2,  # Fixed
        ramp_rate=ramp_rate,
        wastewater_frequency=wastewater_frequency,
        min_compressors=min_compressors,
        allow_pulper_60=True,  # Always allowed
        allow_pulper_120=True  # Always allowed
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
    
    # Generate AI insights if enabled
    if enable_insights:
        _display_ai_insights(result, location, forecast_start_dt)
    
    _display_schedule_sample(result)
    
    # Save if requested
    if output:
        _save_schedule(result, output)
        console.print(f"\n[green]✓ Schedule saved to: {output}[/green]")


def _display_inputs(location, forecast_start, horizon, inventory, current_load):
    """Display optimization inputs."""
    table = Table(show_header=True, box=box.ROUNDED, title="[bold]Inputs[/bold]")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="white", justify="right")
    
    table.add_row("Location", location)
    table.add_row("Start Date/Time", forecast_start.strftime("%Y-%m-%d %H:%M"))
    table.add_row("Forecast Horizon", f"{horizon} hours")
    table.add_row("Context Days", "60 days")
    table.add_row("Current Inventory", f"{inventory} hours")
    table.add_row("Current Load", f"{current_load} MW")
    table.add_row("Production Today", "0.0 tons")
    
    console.print()
    console.print(table)
    console.print()


def _display_configuration(min_inv, max_inv, prod_target, ramp_rate, ww_freq, min_comp):
    """Display factory configuration (constraints)."""
    table = Table(show_header=True, box=box.ROUNDED, title="[bold]Factory Configuration[/bold]")
    table.add_column("Constraint", style="cyan")
    table.add_column("Value", style="white", justify="right")
    table.add_column("Description", style="yellow")
    
    table.add_row("Inventory Range", f"{min_inv} - {max_inv} hours", 
                  "Storage tank capacity")
    table.add_row("Production Target", f"{prod_target} tons/day",
                  "Daily production requirement")
    table.add_row("Ramp Rate Limit", f"{ramp_rate} MW/min",
                  "Max load change speed")
    table.add_row("Wastewater Frequency", f"Every {ww_freq} hours",
                  "Environmental compliance")
    table.add_row("Min Compressors", f"{min_comp}",
                  "Process requirements")
    table.add_row("Load Range", "15.6 - 28.2 MW",
                  "Equipment capacity limits")
    table.add_row("Pulper Speeds", "60%, 100%, 120%",
                  "Available operating modes")
    
    console.print()
    console.print(table)
    console.print()


def _display_summary(result):
    """Display optimization results and metrics."""
    console.print()
    console.print(Panel.fit(
        f"[bold green]Optimization Results[/bold green]\n\n"
        f"[white]Total Cost:[/white] ${result.total_cost:,.2f}\n"
        f"[white]Baseline Cost:[/white] ${result.baseline_cost:,.2f}\n"
        f"[green]Savings:[/green] ${result.savings:,.2f} ({result.savings_percent:.1f}%)\n\n"
        f"[white]Solve Time:[/white] {result.solve_time:.2f}s\n"
        f"[white]Status:[/white] {result.solver_status}",
        border_style="green",
        box=box.DOUBLE
    ))
    
    # Metrics table - characteristics of the solution
    table = Table(show_header=True, box=box.ROUNDED, title="[bold]Solution Metrics[/bold]")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white", justify="right")
    table.add_column("Description", style="yellow")
    
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


def _display_ai_insights(result, location: str, forecast_start: datetime):
    """Display AI-generated insights about the optimization."""
    console.print()
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        console.print("[yellow]⚠ AI insights disabled: OPENAI_API_KEY not set[/yellow]")
        console.print("[dim]Set OPENAI_API_KEY environment variable to enable insights[/dim]\n")
        return
    
    console.print("[cyan]Generating AI insights...[/cyan]")
    
    try:
        # Generate insights
        generator = InsightGenerator()
        insights = asyncio.run(
            generator.generate_insights(result, location, forecast_start)
        )
        
        # Display insights
        console.print()
        console.print(Panel.fit(
            f"[bold magenta]AI-Powered Insights[/bold magenta]\n\n"
            f"[white]{insights.executive_summary}[/white]",
            border_style="magenta",
            box=box.DOUBLE
        ))
        
        # Key decisions
        console.print()
        console.print("[bold cyan]Key Decisions:[/bold cyan]")
        for i, decision in enumerate(insights.key_decisions, 1):
            console.print(f"  [cyan]{i}.[/cyan] {decision}")
        
        # Strategies
        console.print()
        console.print("[bold cyan]Price Strategy:[/bold cyan]")
        console.print(f"  {insights.price_strategy}")
        
        console.print()
        console.print("[bold cyan]Inventory Strategy:[/bold cyan]")
        console.print(f"  {insights.inventory_strategy}")
        
        # Risk considerations
        if insights.risk_considerations:
            console.print()
            console.print("[bold yellow]⚠ Risk Considerations:[/bold yellow]")
            for risk in insights.risk_considerations:
                console.print(f"  [yellow]•[/yellow] {risk}")
        
        console.print()
        
    except Exception as e:
        console.print(f"[yellow]⚠ Could not generate insights: {e}[/yellow]\n")


def _display_schedule_sample(result):
    """Display sample of optimized schedule."""
    console.print()
    console.print("[bold cyan]Schedule Sample (First 12 Periods)[/bold cyan]\n")
    
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
