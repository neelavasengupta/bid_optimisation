import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Load all bid files
data_dir = Path('../data')
bid_files = sorted(data_dir.glob('*_Bids.csv'))

print("=" * 80)
print("COMPREHENSIVE BID ANALYSIS - GENERATOR PRICING PATTERNS")
print("=" * 80)
print(f"\nLoading {len(bid_files)} bid files...")

all_bids = []
for file in bid_files:
    df = pd.read_csv(file)
    df['file_date'] = file.stem.split('_')[0]
    all_bids.append(df)

bids = pd.concat(all_bids, ignore_index=True)
print(f"Total records: {len(bids):,}")
print(f"Date range: {bids['file_date'].min()} to {bids['file_date'].max()}")

# Convert to datetime
bids['date'] = pd.to_datetime(bids['TradingDate'])
bids['month'] = bids['date'].dt.month
bids['day_of_week'] = bids['date'].dt.dayofweek  # 0=Monday, 6=Sunday
bids['is_weekend'] = bids['day_of_week'].isin([5, 6])

# Filter realistic prices
realistic_bids = bids[bids['DollarsPerMegawattHour'] < 1000].copy()

print(f"\nRealistic bids (< $1000/MWh): {len(realistic_bids):,} ({len(realistic_bids)/len(bids)*100:.1f}%)")
print(f"Price range: ${realistic_bids['DollarsPerMegawattHour'].min():.2f} - ${realistic_bids['DollarsPerMegawattHour'].max():.2f}")

print("\n" + "=" * 80)
print("PATTERN 1: TIME OF DAY")
print("=" * 80)

# Group by trading period
period_stats = realistic_bids.groupby('TradingPeriod')['DollarsPerMegawattHour'].agg([
    'mean', 'median', 'std', 'min', 'max', 'count'
]).round(2)

# Add time labels
period_stats['hour'] = (period_stats.index - 1) // 2
period_stats['time_label'] = period_stats.apply(
    lambda x: f"{int(x['hour']):02d}:00" if (x.name-1) % 2 == 0 else f"{int(x['hour']):02d}:30",
    axis=1
)

print("\nBid prices by time of day (every 2 hours):")
print("-" * 80)
for period in range(1, 49, 4):  # Every 2 hours
    row = period_stats.loc[period]
    print(f"Period {period:2d} ({row['time_label']}): Mean=${row['mean']:6.2f}, Median=${row['median']:6.2f}, Std=${row['std']:5.2f}, Range=${row['min']:6.2f}-${row['max']:6.2f}")

# Identify peak periods
peak_periods = period_stats.nlargest(8, 'mean')
offpeak_periods = period_stats.nsmallest(8, 'mean')

print(f"\n\nPEAK PERIODS (highest 8):")
for idx in peak_periods.index:
    row = period_stats.loc[idx]
    print(f"  Period {idx:2d} ({row['time_label']}): ${row['mean']:.2f}")

print(f"\nOFF-PEAK PERIODS (lowest 8):")
for idx in offpeak_periods.index:
    row = period_stats.loc[idx]
    print(f"  Period {idx:2d} ({row['time_label']}): ${row['mean']:.2f}")

print(f"\nPeak vs Off-peak:")
print(f"  Peak average: ${peak_periods['mean'].mean():.2f}/MWh")
print(f"  Off-peak average: ${offpeak_periods['mean'].mean():.2f}/MWh")
print(f"  Difference: ${peak_periods['mean'].mean() - offpeak_periods['mean'].mean():.2f}/MWh")
print(f"  Ratio: {peak_periods['mean'].mean() / offpeak_periods['mean'].mean():.2f}x")

print("\n" + "=" * 80)
print("PATTERN 2: DAY OF WEEK")
print("=" * 80)

dow_stats = realistic_bids.groupby('day_of_week')['DollarsPerMegawattHour'].agg([
    'mean', 'median', 'std', 'count'
]).round(2)

dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
dow_stats['day_name'] = [dow_names[i] for i in dow_stats.index]

print("\nBid prices by day of week:")
print("-" * 80)
for idx, row in dow_stats.iterrows():
    print(f"{row['day_name']:9s}: Mean=${row['mean']:6.2f}, Median=${row['median']:6.2f}, Std=${row['std']:5.2f}")

weekday_avg = dow_stats.loc[0:4, 'mean'].mean()
weekend_avg = dow_stats.loc[5:6, 'mean'].mean()
print(f"\nWeekday average: ${weekday_avg:.2f}/MWh")
print(f"Weekend average: ${weekend_avg:.2f}/MWh")
print(f"Difference: ${weekday_avg - weekend_avg:.2f}/MWh")

print("\n" + "=" * 80)
print("PATTERN 3: SEASONAL (MONTHLY)")
print("=" * 80)

month_stats = realistic_bids.groupby('month')['DollarsPerMegawattHour'].agg([
    'mean', 'median', 'std', 'count'
]).round(2)

month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

print("\nBid prices by month:")
print("-" * 80)
for idx, row in month_stats.iterrows():
    print(f"{month_names[idx]:3s}: Mean=${row['mean']:6.2f}, Median=${row['median']:6.2f}, Std=${row['std']:5.2f}, Count={int(row['count']):,}")

# Winter vs Summer
winter_months = [5, 6, 7, 8]  # May-Aug
summer_months = [11, 12, 1, 2]  # Nov-Feb

winter_avg = month_stats.loc[month_stats.index.isin(winter_months), 'mean'].mean()
summer_avg = month_stats.loc[month_stats.index.isin(summer_months), 'mean'].mean()

print(f"\nWinter (May-Aug) average: ${winter_avg:.2f}/MWh")
print(f"Summer (Nov-Feb) average: ${summer_avg:.2f}/MWh")
print(f"Difference: ${winter_avg - summer_avg:.2f}/MWh")
print(f"Ratio: {winter_avg / summer_avg:.2f}x")

print("\n" + "=" * 80)
print("PATTERN 4: PARTICIPANT BEHAVIOR")
print("=" * 80)

participant_stats = realistic_bids.groupby('ParticipantCode').agg({
    'DollarsPerMegawattHour': ['mean', 'median', 'std', 'min', 'max'],
    'Megawatts': ['sum', 'mean'],
    'TradingPeriod': 'count'
}).round(2)

participant_stats.columns = ['Price_Mean', 'Price_Median', 'Price_Std', 'Price_Min', 'Price_Max', 
                              'Total_MW', 'Avg_MW', 'Count']
participant_stats = participant_stats.sort_values('Total_MW', ascending=False)

print("\nTop 10 participants by volume:")
print("-" * 80)
print(participant_stats.head(10).to_string())

print("\n" + "=" * 80)
print("PATTERN 5: COMBINED TIME-OF-DAY + DAY-OF-WEEK")
print("=" * 80)

# Create time blocks
def get_time_block(period):
    hour = (period - 1) // 2
    if 0 <= hour < 6:
        return 'Night (12am-6am)'
    elif 6 <= hour < 9:
        return 'Morning (6am-9am)'
    elif 9 <= hour < 17:
        return 'Day (9am-5pm)'
    elif 17 <= hour < 21:
        return 'Evening (5pm-9pm)'
    else:
        return 'Late (9pm-12am)'

realistic_bids['time_block'] = realistic_bids['TradingPeriod'].apply(get_time_block)

combined_stats = realistic_bids.groupby(['is_weekend', 'time_block'])['DollarsPerMegawattHour'].agg([
    'mean', 'median', 'count'
]).round(2)

print("\nWeekday prices by time block:")
print("-" * 80)
weekday_data = combined_stats.loc[False]
for block in ['Night (12am-6am)', 'Morning (6am-9am)', 'Day (9am-5pm)', 'Evening (5pm-9pm)', 'Late (9pm-12am)']:
    if block in weekday_data.index:
        row = weekday_data.loc[block]
        print(f"{block:20s}: Mean=${row['mean']:6.2f}, Median=${row['median']:6.2f}")

print("\nWeekend prices by time block:")
print("-" * 80)
weekend_data = combined_stats.loc[True]
for block in ['Night (12am-6am)', 'Morning (6am-9am)', 'Day (9am-5pm)', 'Evening (5pm-9pm)', 'Late (9pm-12am)']:
    if block in weekend_data.index:
        row = weekend_data.loc[block]
        print(f"{block:20s}: Mean=${row['mean']:6.2f}, Median=${row['median']:6.2f}")

print("\n" + "=" * 80)
print("KEY FINDINGS SUMMARY")
print("=" * 80)

overall_mean = realistic_bids['DollarsPerMegawattHour'].mean()
overall_std = realistic_bids['DollarsPerMegawattHour'].std()

print(f"\nOverall Statistics:")
print(f"  Mean price: ${overall_mean:.2f}/MWh")
print(f"  Std deviation: ${overall_std:.2f}/MWh")
print(f"  Coefficient of variation: {overall_std/overall_mean:.2f}")

print(f"\nPrice Variation:")
print(f"  Time of day: ${peak_periods['mean'].mean() - offpeak_periods['mean'].mean():.2f}/MWh ({(peak_periods['mean'].mean() - offpeak_periods['mean'].mean())/overall_mean*100:.1f}%)")
print(f"  Weekday vs Weekend: ${abs(weekday_avg - weekend_avg):.2f}/MWh ({abs(weekday_avg - weekend_avg)/overall_mean*100:.1f}%)")
print(f"  Winter vs Summer: ${abs(winter_avg - summer_avg):.2f}/MWh ({abs(winter_avg - summer_avg)/overall_mean*100:.1f}%)")

print(f"\nPredictability:")
if overall_std/overall_mean < 0.5:
    print("  ✓ LOW variability - highly predictable")
elif overall_std/overall_mean < 1.0:
    print("  ✓ MODERATE variability - reasonably predictable")
else:
    print("  ✗ HIGH variability - less predictable")

# Save detailed results
period_stats.to_csv('bid_analysis_by_period.csv')
dow_stats.to_csv('bid_analysis_by_dow.csv')
month_stats.to_csv('bid_analysis_by_month.csv')
participant_stats.to_csv('bid_analysis_by_participant.csv')

print("\n✓ Detailed results saved to CSV files")
