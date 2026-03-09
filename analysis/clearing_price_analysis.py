"""Comprehensive analysis of NZ electricity clearing prices (2024-2026)."""

import polars as pl
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# Setup
DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "clearings"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)


def load_clearing_prices() -> pl.DataFrame:
    """Load and process clearing price data."""
    print("Loading clearing price files...")
    files = sorted(DATA_DIR.glob("*_DispatchEnergyPrices.csv"))
    
    df = (
        pl.scan_csv(
            files,
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
        # Take latest published price
        .sort('PublishDateTime')
        .group_by(['TradingDate', 'TradingPeriod', 'PointOfConnection'], maintain_order=True)
        .agg([
            pl.col('timestamp').last(),
            pl.col('Island').last(),
            pl.col('DollarsPerMegawattHour').last().alias('price')
        ])
        .with_columns([
            pl.col('timestamp').dt.hour().alias('hour'),
            pl.col('timestamp').dt.weekday().alias('day_of_week'),
            pl.col('timestamp').dt.month().alias('month'),
            pl.col('timestamp').dt.quarter().alias('quarter'),
            (pl.col('timestamp').dt.weekday() >= 5).alias('is_weekend'),
        ])
        .collect()
    )
    
    print(f"Loaded {len(df):,} records")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Locations: {df['PointOfConnection'].n_unique()}")
    print(f"Islands: {df['Island'].unique().to_list()}")
    
    return df


def analyze_price_statistics(df: pl.DataFrame):
    """Analyze basic price statistics."""
    print("\n" + "="*70)
    print("PRICE STATISTICS")
    print("="*70)
    
    stats = df.select([
        pl.col('price').count().alias('count'),
        pl.col('price').mean().alias('mean'),
        pl.col('price').median().alias('median'),
        pl.col('price').std().alias('std'),
        pl.col('price').min().alias('min'),
        pl.col('price').quantile(0.25).alias('p25'),
        pl.col('price').quantile(0.75).alias('p75'),
        pl.col('price').max().alias('max'),
    ]).to_pandas().iloc[0]
    
    print(f"\nOverall Statistics:")
    print(f"  Count:    {stats['count']:,.0f}")
    print(f"  Mean:     ${stats['mean']:.2f}/MWh")
    print(f"  Median:   ${stats['median']:.2f}/MWh")
    print(f"  Std Dev:  ${stats['std']:.2f}/MWh")
    print(f"  Min:      ${stats['min']:.2f}/MWh")
    print(f"  25th %:   ${stats['p25']:.2f}/MWh")
    print(f"  75th %:   ${stats['p75']:.2f}/MWh")
    print(f"  Max:      ${stats['max']:.2f}/MWh")
    
    # By island
    print(f"\nBy Island:")
    island_stats = df.group_by('Island').agg([
        pl.col('price').mean().alias('mean'),
        pl.col('price').median().alias('median'),
        pl.col('price').std().alias('std'),
    ]).sort('Island')
    
    for row in island_stats.iter_rows(named=True):
        print(f"  {row['Island']}: Mean=${row['mean']:.2f}, Median=${row['median']:.2f}, Std=${row['std']:.2f}")
    
    # Negative prices
    negative = df.filter(pl.col('price') < 0)
    print(f"\nNegative Prices:")
    print(f"  Count: {len(negative):,} ({len(negative)/len(df)*100:.2f}%)")
    print(f"  Min: ${negative['price'].min():.2f}/MWh")
    
    # Extreme prices
    extreme = df.filter(pl.col('price') > 1000)
    print(f"\nExtreme Prices (>$1000/MWh):")
    print(f"  Count: {len(extreme):,} ({len(extreme)/len(df)*100:.2f}%)")
    print(f"  Max: ${extreme['price'].max():.2f}/MWh")
    
    return stats


def analyze_temporal_patterns(df: pl.DataFrame):
    """Analyze time-based price patterns."""
    print("\n" + "="*70)
    print("TEMPORAL PATTERNS")
    print("="*70)
    
    # By hour
    hourly = df.group_by('hour').agg([
        pl.col('price').mean().alias('mean_price'),
        pl.col('price').median().alias('median_price'),
        pl.col('price').std().alias('std_price'),
    ]).sort('hour')
    
    print("\nHourly Patterns:")
    print(f"  Peak hour: {hourly.filter(pl.col('mean_price') == pl.col('mean_price').max())['hour'][0]}:00 (${hourly['mean_price'].max():.2f}/MWh)")
    print(f"  Off-peak hour: {hourly.filter(pl.col('mean_price') == pl.col('mean_price').min())['hour'][0]}:00 (${hourly['mean_price'].min():.2f}/MWh)")
    
    # By day of week
    dow = df.group_by('day_of_week').agg([
        pl.col('price').mean().alias('mean_price'),
    ]).sort('day_of_week')
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    print("\nDay of Week Patterns:")
    dow_dict = {row['day_of_week']: row['mean_price'] for row in dow.to_dicts()}
    for i, day in enumerate(days):
        if i in dow_dict:
            print(f"  {day}: ${dow_dict[i]:.2f}/MWh")
    
    # Weekend vs weekday
    weekend_avg = df.filter(pl.col('is_weekend')).select(pl.col('price').mean())[0, 0]
    weekday_avg = df.filter(~pl.col('is_weekend')).select(pl.col('price').mean())[0, 0]
    print(f"\nWeekend vs Weekday:")
    print(f"  Weekday: ${weekday_avg:.2f}/MWh")
    print(f"  Weekend: ${weekend_avg:.2f}/MWh")
    print(f"  Difference: ${weekday_avg - weekend_avg:.2f}/MWh ({(weekday_avg/weekend_avg-1)*100:.1f}%)")
    
    # By month
    monthly = df.group_by('month').agg([
        pl.col('price').mean().alias('mean_price'),
    ]).sort('month')
    
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    print("\nMonthly Patterns:")
    monthly_dict = {row['month']: row['mean_price'] for row in monthly.to_dicts()}
    for i, month in enumerate(months, 1):
        if i in monthly_dict:
            print(f"  {month}: ${monthly_dict[i]:.2f}/MWh")
    
    return hourly, dow, monthly


def analyze_location_patterns(df: pl.DataFrame):
    """Analyze location-based price patterns."""
    print("\n" + "="*70)
    print("LOCATION PATTERNS")
    print("="*70)
    
    location_stats = df.group_by('PointOfConnection').agg([
        pl.col('price').mean().alias('mean_price'),
        pl.col('price').std().alias('std_price'),
        pl.col('price').min().alias('min_price'),
        pl.col('price').max().alias('max_price'),
        pl.col('Island').first(),
    ]).sort('mean_price', descending=True)
    
    print(f"\nTop 10 Highest Average Price Locations:")
    for row in location_stats.head(10).iter_rows(named=True):
        print(f"  {row['PointOfConnection']} ({row['Island']}): ${row['mean_price']:.2f}/MWh (std=${row['std_price']:.2f})")
    
    print(f"\nTop 10 Lowest Average Price Locations:")
    for row in location_stats.tail(10).iter_rows(named=True):
        print(f"  {row['PointOfConnection']} ({row['Island']}): ${row['mean_price']:.2f}/MWh (std=${row['std_price']:.2f})")
    
    print(f"\nMost Volatile Locations (highest std dev):")
    for row in location_stats.sort('std_price', descending=True).head(10).iter_rows(named=True):
        print(f"  {row['PointOfConnection']} ({row['Island']}): std=${row['std_price']:.2f}/MWh (mean=${row['mean_price']:.2f})")
    
    return location_stats


def create_visualizations(df: pl.DataFrame, hourly: pl.DataFrame, dow: pl.DataFrame, monthly: pl.DataFrame):
    """Create comprehensive visualizations."""
    print("\n" + "="*70)
    print("CREATING VISUALIZATIONS")
    print("="*70)
    
    df_pd = df.to_pandas()
    
    # Figure 1: Price distribution
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Overall distribution
    axes[0, 0].hist(df_pd['price'], bins=100, edgecolor='black', alpha=0.7)
    axes[0, 0].axvline(df_pd['price'].median(), color='red', linestyle='--', label=f'Median: ${df_pd["price"].median():.2f}')
    axes[0, 0].set_xlabel('Price ($/MWh)')
    axes[0, 0].set_ylabel('Frequency')
    axes[0, 0].set_title('Overall Price Distribution')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    
    # Distribution by island
    for island in df_pd['Island'].unique():
        island_data = df_pd[df_pd['Island'] == island]['price']
        axes[0, 1].hist(island_data, bins=50, alpha=0.6, label=island, edgecolor='black')
    axes[0, 1].set_xlabel('Price ($/MWh)')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Price Distribution by Island')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    
    # Box plot by island
    df_pd.boxplot(column='price', by='Island', ax=axes[1, 0])
    axes[1, 0].set_xlabel('Island')
    axes[1, 0].set_ylabel('Price ($/MWh)')
    axes[1, 0].set_title('Price Distribution by Island')
    plt.sca(axes[1, 0])
    plt.xticks(rotation=0)
    
    # Log scale distribution (for extreme values)
    positive_prices = df_pd[df_pd['price'] > 0]['price']
    axes[1, 1].hist(np.log10(positive_prices), bins=100, edgecolor='black', alpha=0.7)
    axes[1, 1].set_xlabel('Log10(Price)')
    axes[1, 1].set_ylabel('Frequency')
    axes[1, 1].set_title('Price Distribution (Log Scale, Positive Prices Only)')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'clearing_fig1_distribution.png', dpi=300, bbox_inches='tight')
    print("  Saved: clearing_fig1_distribution.png")
    plt.close()
    
    # Figure 2: Temporal patterns
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Hourly pattern
    hourly_pd = hourly.to_pandas()
    axes[0, 0].plot(hourly_pd['hour'], hourly_pd['mean_price'], marker='o', linewidth=2, markersize=8)
    axes[0, 0].fill_between(hourly_pd['hour'], 
                            hourly_pd['mean_price'] - hourly_pd['std_price'],
                            hourly_pd['mean_price'] + hourly_pd['std_price'],
                            alpha=0.3)
    axes[0, 0].set_xlabel('Hour of Day')
    axes[0, 0].set_ylabel('Price ($/MWh)')
    axes[0, 0].set_title('Average Price by Hour of Day')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_xticks(range(0, 24, 2))
    
    # Day of week pattern
    dow_pd = dow.to_pandas()
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    axes[0, 1].bar(days, dow_pd['mean_price'], edgecolor='black', alpha=0.7)
    axes[0, 1].set_xlabel('Day of Week')
    axes[0, 1].set_ylabel('Price ($/MWh)')
    axes[0, 1].set_title('Average Price by Day of Week')
    axes[0, 1].grid(True, alpha=0.3, axis='y')
    plt.sca(axes[0, 1])
    plt.xticks(rotation=45)
    
    # Monthly pattern
    monthly_pd = monthly.to_pandas()
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    axes[1, 0].bar(months, monthly_pd['mean_price'], edgecolor='black', alpha=0.7)
    axes[1, 0].set_xlabel('Month')
    axes[1, 0].set_ylabel('Price ($/MWh)')
    axes[1, 0].set_title('Average Price by Month')
    axes[1, 0].grid(True, alpha=0.3, axis='y')
    plt.sca(axes[1, 0])
    plt.xticks(rotation=45)
    
    # Heatmap: Hour vs Day of Week
    heatmap_data = df.group_by(['hour', 'day_of_week']).agg([
        pl.col('price').mean().alias('mean_price')
    ]).to_pandas().pivot(index='hour', columns='day_of_week', values='mean_price')
    
    sns.heatmap(heatmap_data, cmap='RdYlGn_r', annot=False, fmt='.0f', ax=axes[1, 1], cbar_kws={'label': 'Price ($/MWh)'})
    axes[1, 1].set_xlabel('Day of Week')
    axes[1, 1].set_ylabel('Hour of Day')
    axes[1, 1].set_title('Price Heatmap: Hour vs Day of Week')
    axes[1, 1].set_xticklabels(days)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'clearing_fig2_temporal.png', dpi=300, bbox_inches='tight')
    print("  Saved: clearing_fig2_temporal.png")
    plt.close()
    
    # Figure 3: Time series
    fig, axes = plt.subplots(2, 1, figsize=(16, 10))
    
    # Daily average price over time
    daily_avg = df.group_by('TradingDate').agg([
        pl.col('price').mean().alias('mean_price'),
        pl.col('price').std().alias('std_price'),
    ]).sort('TradingDate').to_pandas()
    
    axes[0].plot(daily_avg['TradingDate'], daily_avg['mean_price'], linewidth=1, alpha=0.8)
    axes[0].set_xlabel('Date')
    axes[0].set_ylabel('Price ($/MWh)')
    axes[0].set_title('Daily Average Clearing Price Over Time')
    axes[0].grid(True, alpha=0.3)
    
    # Weekly rolling average
    weekly_avg = df.group_by('TradingDate').agg([
        pl.col('price').mean().alias('mean_price')
    ]).sort('TradingDate').to_pandas()
    weekly_avg['rolling_7d'] = weekly_avg['mean_price'].rolling(7, center=True).mean()
    
    axes[1].plot(weekly_avg['TradingDate'], weekly_avg['mean_price'], linewidth=0.5, alpha=0.3, label='Daily')
    axes[1].plot(weekly_avg['TradingDate'], weekly_avg['rolling_7d'], linewidth=2, label='7-day rolling avg')
    axes[1].set_xlabel('Date')
    axes[1].set_ylabel('Price ($/MWh)')
    axes[1].set_title('Clearing Price Trend (7-day Rolling Average)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'clearing_fig3_timeseries.png', dpi=300, bbox_inches='tight')
    print("  Saved: clearing_fig3_timeseries.png")
    plt.close()
    
    # Figure 4: Hour vs Month heatmap (shows when time-of-day matters)
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    
    heatmap_month = df.group_by(['hour', 'month']).agg([
        pl.col('price').mean().alias('mean_price')
    ]).to_pandas().pivot(index='hour', columns='month', values='mean_price')
    
    sns.heatmap(heatmap_month, cmap='RdYlGn_r', annot=True, fmt='.0f', ax=ax, 
                cbar_kws={'label': 'Price ($/MWh)'}, linewidths=0.5)
    ax.set_xlabel('Month')
    ax.set_ylabel('Hour of Day')
    ax.set_title('Price Heatmap: Hour vs Month\n(Shows when time-of-day optimization matters)')
    ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'clearing_fig4_hour_month_heatmap.png', dpi=300, bbox_inches='tight')
    print("  Saved: clearing_fig4_hour_month_heatmap.png")
    plt.close()


def main():
    """Run comprehensive clearing price analysis."""
    print("\n" + "="*70)
    print("NZ ELECTRICITY CLEARING PRICE ANALYSIS (2024-2026)")
    print("="*70)
    
    # Load data
    df = load_clearing_prices()
    
    # Analyze
    stats = analyze_price_statistics(df)
    hourly, dow, monthly = analyze_temporal_patterns(df)
    location_stats = analyze_location_patterns(df)
    
    # Visualize
    create_visualizations(df, hourly, dow, monthly)
    
    # Save summary stats
    summary = {
        'overall_stats': stats.to_dict(),
        'hourly_pattern': hourly.to_pandas().to_dict('records'),
        'dow_pattern': dow.to_pandas().to_dict('records'),
        'monthly_pattern': monthly.to_pandas().to_dict('records'),
    }
    
    import json
    with open(OUTPUT_DIR / 'clearing_price_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print("\n  Saved: clearing_price_summary.json")
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
