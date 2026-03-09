"""Price prediction using trained AutoGluon TimeSeriesPredictor."""

import pandas as pd
import click
import plotext as plt
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError
from autogluon.timeseries import TimeSeriesPredictor, TimeSeriesDataFrame
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich import box

from .config import MODEL_PATH, GROUND_TRUTH_FILE, PREDICTION_HOURS, BEST_MODEL

console = Console()


class ForecastRequest(BaseModel):
    """Request parameters for price forecasting."""
    model_config = ConfigDict(frozen=True, validate_assignment=True)
    
    forecast_start: datetime
    forecast_hours: int = Field(default=PREDICTION_HOURS, ge=1, le=PREDICTION_HOURS)
    locations: Optional[List[str]] = None
    context_days: int = Field(default=60, ge=1, le=365)


class ForecastMetrics(BaseModel):
    """Performance metrics for forecast evaluation."""
    model_config = ConfigDict(frozen=True)
    
    mae: float = Field(description="Mean Absolute Error", ge=0)
    rmse: float = Field(description="Root Mean Squared Error", ge=0)
    mean_actual: float = Field(description="Mean actual price")
    mean_predicted: float = Field(description="Mean predicted price")
    mean_uncertainty: float = Field(description="Mean uncertainty (P90-P10)", ge=0)
    
    @classmethod
    def from_forecast(cls, forecast_df: pd.DataFrame) -> 'ForecastMetrics':
        """Calculate metrics from forecast DataFrame."""
        return cls(
            mae=forecast_df['error'].abs().mean(),
            rmse=(forecast_df['error'] ** 2).mean() ** 0.5,
            mean_actual=forecast_df['actual'].mean(),
            mean_predicted=forecast_df['mean'].mean(),
            mean_uncertainty=forecast_df['uncertainty'].mean()
        )


def load_predictor() -> TimeSeriesPredictor:
    """Load the trained TimeSeriesPredictor from default path."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run train.py first."
        )
    return TimeSeriesPredictor.load(str(MODEL_PATH))


def prepare_historical_context(
    historical_data: pd.DataFrame,
    forecast_start: datetime,
    context_days: int
) -> pd.DataFrame:
    """
    Prepare historical context data for prediction.
    
    Args:
        historical_data: DataFrame with columns [item_id, timestamp, target, ...covariates]
        forecast_start: Timestamp to start forecasting from
        context_days: Number of days of history to use as context
    
    Returns:
        DataFrame with context data (all data before forecast_start)
    """
    context_start = forecast_start - timedelta(days=context_days)
    context_df = historical_data[
        (historical_data['timestamp'] >= context_start) & 
        (historical_data['timestamp'] < forecast_start)
    ].copy()
    
    if len(context_df) == 0:
        raise ValueError(
            f"No historical data found between {context_start} and {forecast_start}. "
            f"Ensure ground_truth.csv contains data before forecast_start."
        )
    
    return context_df


def predict_prices(
    forecast_start: datetime,
    forecast_hours: int = PREDICTION_HOURS,
    locations: List[str] = None,
    context_days: int = 60
) -> pd.DataFrame:
    """
    Generate price forecasts for specified locations (BACKTESTING MODE ONLY).
    
    This system requires actual future data (covariates) from ground_truth.csv
    for the forecast period. It cannot generate true forecasts for dates beyond
    the available data.
    
    Args:
        forecast_start: Timestamp to start forecasting from (REQUIRED)
        forecast_hours: Number of hours to forecast ahead (default: 48, max: 48)
        locations: List of location IDs to forecast for. If None, forecasts for all locations
        context_days: Number of days of historical data to use as context (default: 60)
    
    Returns:
        DataFrame with predictions including actual prices, errors, and uncertainty
    """
    # Validate inputs using Pydantic
    request = ForecastRequest(
        forecast_start=forecast_start,
        forecast_hours=forecast_hours,
        locations=locations,
        context_days=context_days
    )
    
    # Display header
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]NZ ELECTRICITY PRICE FORECASTING[/bold cyan]\n"
        f"[white]Forecast Start:[/white] {request.forecast_start.strftime('%Y-%m-%d %H:%M')}\n"
        f"[white]Forecast Horizon:[/white] {request.forecast_hours} hours ({request.forecast_hours * 2} periods)",
        border_style="cyan",
        box=box.DOUBLE
    ))
    console.print()
    
    forecast_end = request.forecast_start + timedelta(hours=request.forecast_hours)
    model_forecast_end = request.forecast_start + timedelta(hours=PREDICTION_HOURS)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        # Step 1: Load model
        task1 = progress.add_task("[cyan]Loading trained model...", total=1)
        predictor = load_predictor()
        progress.update(task1, advance=1, description="[green]✓ Model loaded")
        
        # Step 2: Load all data from ground_truth.csv
        task2 = progress.add_task("[cyan]Loading ground truth data...", total=1)
        all_data = pd.read_csv(GROUND_TRUTH_FILE)
        all_data['timestamp'] = pd.to_datetime(all_data['timestamp'])
        
        # Filter to relevant date range
        data_start = request.forecast_start - timedelta(days=request.context_days)
        data_end = request.forecast_start + timedelta(hours=PREDICTION_HOURS)
        
        all_data = all_data[
            (all_data['timestamp'] >= data_start) & 
            (all_data['timestamp'] <= data_end)
        ]
        
        progress.update(task2, advance=1, 
                       description=f"[green]✓ Data loaded: {all_data['timestamp'].min().date()} to {all_data['timestamp'].max().date()}")
        
        # Step 3: Prepare data for forecasting
        task3 = progress.add_task("[cyan]Preparing forecast data...", total=1)
        historical_data = all_data[all_data['timestamp'] < request.forecast_start].copy()
        future_data = all_data[all_data['timestamp'] >= request.forecast_start].copy()
        
        if len(historical_data) == 0:
            console.print("[red]✗ Error: No historical data available before forecast start[/red]")
            raise ValueError(
                f"No historical data available before {request.forecast_start}. "
                f"Available data range: {all_data['timestamp'].min()} to {all_data['timestamp'].max()}"
            )
        
        # Check if we have required future data for model
        if len(future_data) == 0 or future_data['timestamp'].max() < model_forecast_end:
            console.print("[red]✗ Error: Insufficient future data for backtesting[/red]")
            console.print(f"[yellow]Model requires data from {request.forecast_start} to {model_forecast_end}[/yellow]")
            console.print(f"[yellow]Available data ends at: {all_data['timestamp'].max()}[/yellow]")
            raise ValueError(
                f"Insufficient future data for backtesting. "
                f"Model requires {PREDICTION_HOURS} hours of future covariates."
            )
        
        # Filter to only locations that have complete data
        hist_locations = set(historical_data['item_id'].unique())
        future_locations = set(future_data['item_id'].unique())
        valid_locations = hist_locations & future_locations
        
        historical_data = historical_data[historical_data['item_id'].isin(valid_locations)].copy()
        future_data = future_data[future_data['item_id'].isin(valid_locations)].copy()
        
        all_locations = sorted(list(valid_locations))
        context_df = prepare_historical_context(historical_data, request.forecast_start, request.context_days)
        progress.update(task3, advance=1, 
                       description=f"[green]✓ Prepared: {request.context_days} days context, {len(all_locations)} locations")
        
        # Step 4: Load static features
        task4 = progress.add_task("[cyan]Loading location features...", total=1)
        static_file = GROUND_TRUTH_FILE.parent / "static_features.csv"
        static_features = None
        if static_file.exists():
            static_features = pd.read_csv(static_file).set_index('item_id')
            progress.update(task4, advance=1, 
                          description=f"[green]✓ Static features loaded: {len(static_features)} locations")
        else:
            progress.update(task4, advance=1, 
                          description="[yellow]⚠ Static features not found (optional)")
        
        # Step 5: Prepare model inputs
        task5 = progress.add_task("[cyan]Preparing model inputs...", total=1)
        context_ts = TimeSeriesDataFrame.from_data_frame(
            context_df,
            id_column='item_id',
            timestamp_column='timestamp'
        )
        
        if static_features is not None:
            context_ts.static_features = static_features
        
        known_covariates_ts = TimeSeriesDataFrame.from_data_frame(
            future_data,
            id_column='item_id',
            timestamp_column='timestamp'
        )
        progress.update(task5, advance=1, description="[green]✓ Model inputs prepared")
        
        # Step 6: Generate predictions
        task6 = progress.add_task(
            f"[cyan]Generating {request.forecast_hours}h forecast...", 
            total=1
        )
        predictions = predictor.predict(
            context_ts,
            known_covariates=known_covariates_ts,
            model=BEST_MODEL
        )
        progress.update(task6, advance=1, description="[green]✓ Predictions generated")
    
    console.print()
    
    # Determine which locations to return
    requested_locations = request.locations if request.locations else all_locations
    
    # Display what data was used
    data_table = Table(show_header=True, box=box.ROUNDED, title="[bold]Data Used for Forecasting[/bold]", 
                      title_style="bold cyan", padding=(0, 1))
    data_table.add_column("Data Type", style="cyan", width=20)
    data_table.add_column("Date Range", style="white", width=35)
    data_table.add_column("Records", justify="right", style="yellow", width=10)
    data_table.add_column("Features Included", style="green", width=50)
    
    context_start = request.forecast_start - timedelta(days=request.context_days)
    data_table.add_row(
        "Historical Context",
        f"{context_start.date()} to {request.forecast_start.date()}",
        f"{len(context_df):,}",
        "Past prices, time features, weather, holidays"
    )
    data_table.add_row(
        "Future Covariates",
        f"{request.forecast_start.date()} to {model_forecast_end.date()}",
        f"{len(future_data):,}",
        "Time features (hour, day, month), weather forecasts, holidays"
    )
    data_table.add_row(
        "Forecast Output",
        f"{request.forecast_start.strftime('%Y-%m-%d %I:%M %p')} to {forecast_end.strftime('%Y-%m-%d %I:%M %p')}",
        f"{request.forecast_hours * 2}",
        "Price predictions with uncertainty (P10, P50, P90)"
    )
    
    console.print(data_table)
    console.print()
    
    # Convert to regular DataFrame
    pred_df = predictions.reset_index()
    
    # Filter to requested locations and forecast horizon
    pred_df = pred_df[pred_df['item_id'].isin(requested_locations)].copy()
    pred_df = pred_df[pred_df['timestamp'] < forecast_end].copy()
    
    # Add hours_ahead column
    pred_df['hours_ahead'] = (
        pd.to_datetime(pred_df['timestamp']) - request.forecast_start
    ).dt.total_seconds() / 3600
    
    # Add uncertainty column (P90 - P10)
    pred_df['uncertainty'] = pred_df['0.9'] - pred_df['0.1']
    
    # Merge actual prices from future_data for backtesting comparison
    actual_prices = future_data[future_data['timestamp'] < forecast_end][['item_id', 'timestamp', 'target']].copy()
    actual_prices = actual_prices.rename(columns={'target': 'actual'})
    pred_df = pred_df.merge(actual_prices, on=['item_id', 'timestamp'], how='left')
    
    # Calculate error if actual price exists
    pred_df['error'] = pred_df['actual'] - pred_df['mean']
    
    # Reorder columns for clarity
    quantiles = ['0.1', '0.5', '0.9']
    base_cols = ['item_id', 'timestamp', 'hours_ahead', 'actual', 'mean', 'error', 'uncertainty']
    quantile_cols = [q for q in quantiles if q in pred_df.columns]
    other_cols = [c for c in pred_df.columns if c not in base_cols + quantile_cols]
    
    pred_df = pred_df[base_cols + quantile_cols + other_cols]
    
    # Display summary
    summary_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    summary_table.add_row("Total predictions", f"{len(pred_df):,}")
    summary_table.add_row("Locations", f"{len(requested_locations)}")
    summary_table.add_row("Time periods", f"{request.forecast_hours * 2} (30-min intervals)")
    summary_table.add_row("Mean price", f"${pred_df['mean'].mean():.2f}/MWh")
    summary_table.add_row("Price range", 
                         f"${pred_df['mean'].min():.2f} - ${pred_df['mean'].max():.2f}/MWh")
    
    console.print(Panel(summary_table, title="[bold green]✓ Forecast Complete[/bold green]", border_style="green"))
    console.print()
    
    return pred_df


def get_location_forecast(predictions: pd.DataFrame, location: str) -> pd.DataFrame:
    """
    Extract forecast for a specific location.
    
    Args:
        predictions: Full predictions DataFrame from predict_prices()
        location: Location ID (e.g., 'ALB0331')
    
    Returns:
        DataFrame with forecast for the specified location
    """
    return predictions[predictions['item_id'] == location].copy()


def save_predictions(predictions: pd.DataFrame, output_path: Path) -> Path:
    """
    Save predictions to CSV file.
    
    Args:
        predictions: Predictions DataFrame
        output_path: Output file path
    
    Returns:
        Path where predictions were saved
    """
    predictions.to_csv(output_path, index=False)
    console.print(f"[green]✓ Saved predictions to: {output_path}[/green]")
    return output_path


def display_forecast_table(loc_forecast: pd.DataFrame, location: str) -> None:
    """Display forecast results in a formatted table."""
    console.print(f"\n[bold cyan]Forecast: {location}[/bold cyan]\n")
    
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
    table.add_column("Date & Time", style="cyan", width=17)
    table.add_column("Hrs", justify="right", style="yellow", width=5)
    table.add_column("Actual\n($/MWh)", justify="right", style="white", width=10)
    table.add_column("Mean\n($/MWh)", justify="right", style="green", width=10)
    table.add_column("Error\n($/MWh)", justify="right", style="magenta", width=10)
    table.add_column("P10\n($/MWh)", justify="right", style="blue", width=10)
    table.add_column("P90\n($/MWh)", justify="right", style="red", width=10)
    table.add_column("Uncert.\n($/MWh)", justify="right", style="yellow", width=10)
    
    for _, row in loc_forecast.iterrows():
        # Color error based on magnitude
        error_val = row['error']
        if abs(error_val) < 5:
            error_style = "green"
        elif abs(error_val) < 20:
            error_style = "yellow"
        else:
            error_style = "red"
        
        # Format timestamp
        ts = row['timestamp']
        time_str = f"{ts.month:02d}/{ts.day:02d} {ts.strftime('%I:%M %p')}"
        
        table.add_row(
            time_str,
            f"{row['hours_ahead']:.1f}",
            f"${row['actual']:.2f}",
            f"${row['mean']:.2f}",
            f"[{error_style}]{error_val:+.2f}[/{error_style}]",
            f"${row['0.1']:.2f}",
            f"${row['0.9']:.2f}",
            f"${row['uncertainty']:.2f}"
        )
    
    console.print(table)


def display_forecast_plot(loc_forecast: pd.DataFrame) -> None:
    """Display forecast visualization using plotext."""
    console.print(f"\n[bold cyan]Price Forecast[/bold cyan]\n")
    
    hours_list = loc_forecast['hours_ahead'].tolist()
    actual = loc_forecast['actual'].tolist()
    predicted = loc_forecast['mean'].tolist()
    
    plt.clf()
    plt.theme('clear')
    plt.plot(hours_list, actual, label="Actual", color="red")
    plt.plot(hours_list, predicted, label="Predicted", color="green")
    plt.title("Actual vs Predicted")
    plt.xlabel("Hours")
    plt.ylabel("$/MWh")
    plt.show()
    console.print()


def display_performance_metrics(loc_forecast: pd.DataFrame, forecast_hours: int) -> None:
    """Display forecast performance statistics using Pydantic metrics model."""
    metrics = ForecastMetrics.from_forecast(loc_forecast)
    
    console.print(f"[bold]Forecast Performance ({forecast_hours}-hour forecast):[/bold]")
    console.print(f"  Mean Actual Price: [white]${metrics.mean_actual:.2f}/MWh[/white]")
    console.print(f"  Mean Predicted Price: [green]${metrics.mean_predicted:.2f}/MWh[/green]")
    console.print(f"  MAE (Mean Absolute Error): [cyan]${metrics.mae:.2f}/MWh[/cyan]")
    console.print(f"  RMSE (Root Mean Squared Error): [cyan]${metrics.rmse:.2f}/MWh[/cyan]")
    console.print(f"  Mean Uncertainty (P10-P90): [yellow]${metrics.mean_uncertainty:.2f}/MWh[/yellow]")
    console.print()


# CLI Interface
@click.command()
@click.option(
    '--date',
    type=str,
    required=True,
    help='Forecast start date (YYYY-MM-DD). Must have future data in ground_truth.csv'
)
@click.option(
    '--time',
    type=str,
    default='00:00',
    help='Forecast start time (HH:MM). Default: 00:00'
)
@click.option(
    '--hours',
    type=int,
    default=48,
    help='Number of hours to forecast. Default: 48'
)
@click.option(
    '--context-days',
    type=int,
    default=60,
    help='Days of historical context to use. Default: 60'
)
@click.option(
    '--locations',
    multiple=True,
    help='Specific location IDs (can specify multiple). Default: all locations'
)
@click.option(
    '--output',
    type=click.Path(),
    help='Output CSV file path. If not specified, predictions are not saved'
)
def cli(date, time, hours, context_days, locations, output):
    """Generate electricity price forecasts for New Zealand (BACKTESTING MODE).
    
    This system requires actual future data (covariates) from ground_truth.csv
    for the forecast period. It is designed for backtesting and evaluation.
    
    Examples:
    
      # Backtest 48 hours from Feb 1, 2026
      python -m price_prediction.predict --date 2026-02-01
      
      # Use 90 days of context instead of default 60
      python -m price_prediction.predict --date 2026-02-01 --context-days 90
      
      # Backtest 24 hours for specific locations
      python -m price_prediction.predict --date 2026-02-01 --hours 24 --locations ALB0331 --locations HAY2201
      
      # Save predictions to file
      python -m price_prediction.predict --date 2026-02-01 --output forecast.csv
    """
    date_str = f"{date} {time}"
    forecast_start = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
    
    try:
        # Generate predictions
        predictions = predict_prices(
            forecast_start=forecast_start,
            forecast_hours=hours,
            locations=list(locations) if locations else None,
            context_days=context_days
        )
        
        # Display results for first location
        sample_location = predictions['item_id'].iloc[0]
        loc_forecast = get_location_forecast(predictions, sample_location)
        
        display_forecast_table(loc_forecast, sample_location)
        display_forecast_plot(loc_forecast)
        display_performance_metrics(loc_forecast, hours)
        
        # Save if output specified
        if output:
            save_predictions(predictions, output_path=Path(output))
    
    except ValidationError as e:
        console.print(f"\n[red]✗ Validation Error:[/red]")
        for error in e.errors():
            field = " -> ".join(str(x) for x in error['loc'])
            console.print(f"  [yellow]{field}:[/yellow] {error['msg']}")
        raise click.Abort()
    except FileNotFoundError as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        console.print("\n[yellow]Please train the model first:[/yellow]")
        console.print("  [cyan]uv run python -m price_prediction.train[/cyan]")
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
        raise click.Abort()


if __name__ == "__main__":
    cli()
