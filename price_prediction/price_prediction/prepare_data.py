"""Prepare time series data for AutoGluon TimeSeriesPredictor."""

import polars as pl
import pandas as pd
from pathlib import Path
import holidays

# Inline config
GROUND_TRUTH_FILE = Path(__file__).parent.parent / "evaluation" / "ground_truth.csv"


DATA_DIR = Path(__file__).parent.parent.parent / "data" / "raw" / "clearings"
WEATHER_DIR = Path(__file__).parent.parent.parent / "data" / "weather"


def load_weather_data():
    """Load and aggregate weather data by island."""
    weather_file = WEATHER_DIR / "weather_all_locations.csv"
    
    if not weather_file.exists():
        print("Warning: Weather data not found. Run download_weather.py first.")
        return None
    
    print("Loading weather data...")
    weather_df = pl.read_csv(weather_file)
    
    # Convert timestamp to datetime
    weather_df = weather_df.with_columns([
        pl.col('timestamp').str.to_datetime()
    ])
    
    # Aggregate by island and timestamp (average across cities in each island)
    weather_agg = weather_df.group_by(['island', 'timestamp']).agg([
        pl.col('temperature').mean().alias('temperature'),
        pl.col('humidity').mean().alias('humidity'),
        pl.col('precipitation').mean().alias('precipitation'),
        pl.col('wind_speed').mean().alias('wind_speed'),
        pl.col('solar_radiation').mean().alias('solar_radiation'),
    ])
    
    print(f"  Loaded {len(weather_agg)} weather records")
    print(f"  Date range: {weather_agg['timestamp'].min()} to {weather_agg['timestamp'].max()}")
    
    return weather_agg


def prepare_timeseries_data():
    """Prepare per-location time series with features using Polars."""
    clearing_files = sorted(DATA_DIR.glob("*_DispatchEnergyPrices.csv"))
    print(f"Loading {len(clearing_files)} clearing price files with Polars...")
    
    # Get NZ holidays upfront
    nz_holidays = holidays.country_holidays('NZ', years=range(2024, 2027))
    holiday_dates = pl.Series('date', list(nz_holidays.keys()), dtype=pl.Date)
    
    # Single lazy query: load, dedupe, filter, add features
    df = (
        pl.scan_csv(
            clearing_files,
            schema_overrides={
                'TradingDate': pl.Date,
                'TradingPeriod': pl.Int32,
                'PublishDateTime': pl.Utf8,
                'PointOfConnection': pl.Utf8,
                'Island': pl.Utf8,
                'DollarsPerMegawattHour': pl.Float64,
            }
        )
        .filter(pl.col('DollarsPerMegawattHour').is_not_null())
        .with_columns([
            (pl.col('TradingDate').cast(pl.Datetime) + 
             pl.duration(minutes=(pl.col('TradingPeriod') - 1) * 30)).alias('timestamp'),
        ])
        # Dedupe: take latest published price per (date, period, location)
        .sort('PublishDateTime')
        .group_by(['TradingDate', 'TradingPeriod', 'PointOfConnection'], maintain_order=True)
        .agg([
            pl.col('timestamp').last(),
            pl.col('Island').last(),
            pl.col('DollarsPerMegawattHour').last().alias('target')
        ])
        .collect()
    )
    
    # Filter locations with sufficient data (>= 1000 periods)
    location_counts = df.group_by('PointOfConnection').len()
    valid_locations = location_counts.filter(pl.col('len') >= 1000)['PointOfConnection'].to_list()
    df = df.filter(pl.col('PointOfConnection').is_in(valid_locations))
    
    # Add all features in Polars
    df = df.with_columns([
        pl.col('PointOfConnection').alias('item_id'),
        pl.col('timestamp').dt.hour().alias('hour'),
        pl.col('timestamp').dt.weekday().alias('day_of_week'),
        pl.col('timestamp').dt.month().alias('month'),
        (pl.col('timestamp').dt.weekday() >= 5).cast(pl.Float64).alias('is_weekend'),
        pl.col('timestamp').dt.date().is_in(holiday_dates.to_list()).cast(pl.Float64).alias('is_holiday'),
    ]).select([
        'item_id', 'timestamp', 'target', 'Island',
        'hour', 'day_of_week', 'month', 'is_weekend', 'is_holiday'
    ]).sort(['item_id', 'timestamp'])
    
    # Load and join weather data
    weather_df = load_weather_data()
    if weather_df is not None:
        print("\nJoining weather data...")
        # Join on Island and timestamp
        df = df.join(
            weather_df,
            left_on=['Island', 'timestamp'],
            right_on=['island', 'timestamp'],
            how='left'
        )
        
        # Add derived weather features
        df = df.with_columns([
            # Temperature squared (for heating/cooling curves)
            (pl.col('temperature') ** 2).alias('temperature_sq'),
            # Heating degree days (base 18°C)
            pl.max_horizontal(18.0 - pl.col('temperature'), 0.0).alias('heating_degree_days'),
            # Cooling degree days (base 18°C)
            pl.max_horizontal(pl.col('temperature') - 18.0, 0.0).alias('cooling_degree_days'),
        ])
        
        print(f"  Weather features added: temperature, humidity, precipitation, wind_speed, solar_radiation")
        print(f"  Derived features: temperature_sq, heating_degree_days, cooling_degree_days")
        print(f"  Missing weather data: {df['temperature'].null_count()} records")
    
    # Static features (Island and PointOfConnection as categorical)
    static_features = (
        df.group_by('item_id')
        .agg([
            pl.col('Island').mode().first(),
            pl.col('item_id').first().alias('PointOfConnection')
        ])
        .sort('item_id')
    )
    
    print(f"Loaded {len(df)} records for {len(static_features)} locations")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"\nPrice stats:\n{df['target'].describe()}")
    print(f"\nStatic features: Island (NI/SI), PointOfConnection (location code)")
    
    # Save directly with Polars
    GROUND_TRUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.drop('Island').write_csv(GROUND_TRUTH_FILE)
    static_features.write_csv(GROUND_TRUTH_FILE.parent / "static_features.csv")
    
    print(f"\nSaved: {GROUND_TRUTH_FILE}")
    print("Note: AutoGluon handles train/test splitting with time series CV")


if __name__ == "__main__":
    prepare_timeseries_data()
