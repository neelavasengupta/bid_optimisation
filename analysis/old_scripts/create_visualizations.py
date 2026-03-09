import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import seaborn as sns

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

# Load all bid files
data_dir = Path('../data')
bid_files = sorted(data_dir.glob('*_Bids.csv'))

all_bids = []
for file in bid_files:
    df = pd.read_csv(file)
    df['file_date'] = file.stem.split('_')[0]
    all_bids.append(df)

bids = pd.concat(all_bids, ignore_index=True)
bids['date'] = pd.to_datetime(bids['TradingDate'])
bids['month'] = bids['date'].dt.month
bids['day_of_week'] = bids['date'].dt.dayofweek
bids['is_weekend'] = bids['day_of_week'].isin([5, 6])

realistic_bids = bids[bids['DollarsPerMegawattHour'] < 1000].copy()

# Create time block
def get_time_block(period):
    hour = (period - 1) // 2
    if 0 <= hour < 6:
        return 'Night'
    elif 6 <= hour < 9:
        return 'Morning'
    elif 9 <= hour < 17:
        return 'Day'
    elif 17 <= hour < 21:
        return 'Evening'
    else:
        return 'Late'

realistic_bids['time_block'] = realistic_bids['TradingPeriod'].apply(get_time_block)

print("Creating visualizations...")

# 1. Time of Day Pattern
fig, ax = plt.subplots(figsize=(14, 6))
period_stats = realistic_bids.groupby('TradingPeriod')['DollarsPerMegawattHour'].mean()
hours = [(p-1)//2 + ((p-1)%2)*0.5 for p in period_stats.index]
ax.plot(hours, period_stats.values, linewidth=2, marker='o', markersize=4)
ax.axhline(y=period_stats.mean(), color='r', linestyle='--', label=f'Average: ${period_stats.mean():.2f}/MWh')
ax.set_xlabel('Hour of Day', fontsize=12)
ax.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax.set_title('Bid Prices by Time of Day (All Days)', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.legend()
ax.set_xticks(range(0, 24, 2))
plt.tight_layout()
plt.savefig('fig1_time_of_day.png', dpi=300, bbox_inches='tight')
print("✓ Created fig1_time_of_day.png")
plt.close()

# 2. Seasonal Pattern
fig, ax = plt.subplots(figsize=(12, 6))
month_stats = realistic_bids.groupby('month')['DollarsPerMegawattHour'].mean().sort_index()
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
colors = ['#3498db' if m in [11, 12, 1, 2] else '#e74c3c' if m in [5, 6, 7, 8] else '#95a5a6' 
          for m in month_stats.index]
bars = ax.bar(range(len(month_stats)), month_stats.values, color=colors)
ax.set_xlabel('Month', fontsize=12)
ax.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax.set_title('Bid Prices by Month (Winter vs Summer)', fontsize=14, fontweight='bold')
ax.set_xticks(range(len(month_stats)))
ax.set_xticklabels([month_names[m-1] for m in month_stats.index])
ax.axhline(y=month_stats.mean(), color='black', linestyle='--', alpha=0.5, label=f'Average: ${month_stats.mean():.2f}/MWh')
ax.legend()
ax.grid(True, alpha=0.3, axis='y')
# Add legend for colors
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor='#e74c3c', label='Winter'),
                   Patch(facecolor='#3498db', label='Summer'),
                   Patch(facecolor='#95a5a6', label='Shoulder')]
ax.legend(handles=legend_elements, loc='upper left')
plt.tight_layout()
plt.savefig('fig2_seasonal.png', dpi=300, bbox_inches='tight')
print("✓ Created fig2_seasonal.png")
plt.close()

# 3. Day of Week Pattern
fig, ax = plt.subplots(figsize=(10, 6))
dow_stats = realistic_bids.groupby('day_of_week')['DollarsPerMegawattHour'].mean()
dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
colors = ['#e74c3c' if d < 5 else '#2ecc71' for d in dow_stats.index]
bars = ax.bar(range(len(dow_stats)), dow_stats.values, color=colors)
ax.set_xlabel('Day of Week', fontsize=12)
ax.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax.set_title('Bid Prices by Day of Week', fontsize=14, fontweight='bold')
ax.set_xticks(range(len(dow_stats)))
ax.set_xticklabels([dow_names[d] for d in dow_stats.index])
ax.grid(True, alpha=0.3, axis='y')
legend_elements = [Patch(facecolor='#e74c3c', label='Weekday'),
                   Patch(facecolor='#2ecc71', label='Weekend')]
ax.legend(handles=legend_elements)
plt.tight_layout()
plt.savefig('fig3_day_of_week.png', dpi=300, bbox_inches='tight')
print("✓ Created fig3_day_of_week.png")
plt.close()

# 4. Winter vs Summer Time-of-Day Comparison
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

winter_months = [5, 6, 7, 8]
summer_months = [11, 12, 1, 2]

winter_data = realistic_bids[realistic_bids['month'].isin(winter_months)]
summer_data = realistic_bids[realistic_bids['month'].isin(summer_months)]

winter_period = winter_data.groupby('TradingPeriod')['DollarsPerMegawattHour'].mean()
summer_period = summer_data.groupby('TradingPeriod')['DollarsPerMegawattHour'].mean()

hours = [(p-1)//2 + ((p-1)%2)*0.5 for p in winter_period.index]

ax1.plot(hours, winter_period.values, linewidth=2, marker='o', markersize=4, color='#e74c3c')
ax1.axhline(y=winter_period.mean(), color='black', linestyle='--', alpha=0.5)
ax1.set_xlabel('Hour of Day', fontsize=12)
ax1.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax1.set_title('Winter (May-Aug)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.set_xticks(range(0, 24, 2))
ax1.text(0.02, 0.98, f'Avg: ${winter_period.mean():.2f}/MWh', 
         transform=ax1.transAxes, fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

ax2.plot(hours, summer_period.values, linewidth=2, marker='o', markersize=4, color='#3498db')
ax2.axhline(y=summer_period.mean(), color='black', linestyle='--', alpha=0.5)
ax2.set_xlabel('Hour of Day', fontsize=12)
ax2.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax2.set_title('Summer (Nov-Feb)', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xticks(range(0, 24, 2))
ax2.text(0.02, 0.98, f'Avg: ${summer_period.mean():.2f}/MWh', 
         transform=ax2.transAxes, fontsize=11, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.suptitle('Time-of-Day Pattern: Winter vs Summer', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('fig4_winter_vs_summer.png', dpi=300, bbox_inches='tight')
print("✓ Created fig4_winter_vs_summer.png")
plt.close()

# 5. Variance Decomposition
fig, ax = plt.subplots(figsize=(10, 6))
factors = ['Participant', 'Season', 'Day of Week', 'Time of Day', 'Unexplained']
variance_pct = [39.3, 23.5, 11.0, 5.5, 20.7]
colors_var = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#95a5a6']
bars = ax.barh(factors, variance_pct, color=colors_var)
ax.set_xlabel('Variance Explained (%)', fontsize=12)
ax.set_title('What Drives Price Variation?', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3, axis='x')
for i, (bar, pct) in enumerate(zip(bars, variance_pct)):
    ax.text(pct + 1, i, f'{pct}%', va='center', fontsize=11, fontweight='bold')
plt.tight_layout()
plt.savefig('fig5_variance_decomposition.png', dpi=300, bbox_inches='tight')
print("✓ Created fig5_variance_decomposition.png")
plt.close()

# 6. Heatmap: Time of Day × Day of Week
fig, ax = plt.subplots(figsize=(12, 8))
pivot_data = realistic_bids.groupby(['day_of_week', 'TradingPeriod'])['DollarsPerMegawattHour'].mean().unstack()
# Subsample to every 4 periods (2 hours)
pivot_data = pivot_data.iloc[:, ::4]
sns.heatmap(pivot_data, cmap='RdYlGn_r', annot=True, fmt='.0f', cbar_kws={'label': '$/MWh'},
            yticklabels=dow_names, xticklabels=[f'{(p-1)//2:02d}:00' for p in pivot_data.columns], ax=ax)
ax.set_xlabel('Hour of Day', fontsize=12)
ax.set_ylabel('Day of Week', fontsize=12)
ax.set_title('Bid Price Heatmap: Day of Week × Time of Day', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('fig6_heatmap.png', dpi=300, bbox_inches='tight')
print("✓ Created fig6_heatmap.png")
plt.close()

# 7. Optimization Opportunity
fig, ax = plt.subplots(figsize=(12, 7))

# Winter weekday pattern
winter_weekday = realistic_bids[(realistic_bids['month'].isin(winter_months)) & 
                                 (~realistic_bids['is_weekend'])]
winter_wd_period = winter_weekday.groupby('TradingPeriod')['DollarsPerMegawattHour'].mean()
hours = [(p-1)//2 + ((p-1)%2)*0.5 for p in winter_wd_period.index]

ax.plot(hours, winter_wd_period.values, linewidth=3, marker='o', markersize=6, color='#e74c3c', label='Winter Weekday')

# Highlight optimization zones
cheap_periods = [13, 14, 15, 16, 17, 18]  # 6am-9am
expensive_periods = [43, 44, 45, 46, 47, 48]  # 9pm-12am

for p in cheap_periods:
    hour = (p-1)//2 + ((p-1)%2)*0.5
    ax.axvspan(hour-0.25, hour+0.25, alpha=0.2, color='green')
    
for p in expensive_periods:
    hour = (p-1)//2 + ((p-1)%2)*0.5
    ax.axvspan(hour-0.25, hour+0.25, alpha=0.2, color='red')

ax.set_xlabel('Hour of Day', fontsize=12)
ax.set_ylabel('Average Bid Price ($/MWh)', fontsize=12)
ax.set_title('Optimization Opportunity: Winter Weekdays', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
ax.set_xticks(range(0, 24, 2))
ax.legend()

# Add annotations
ax.annotate('CHEAP\nIncrease Load\n~$42/MWh', xy=(7.5, 42), xytext=(7.5, 20),
            fontsize=11, ha='center', color='green', fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.7),
            arrowprops=dict(arrowstyle='->', color='green', lw=2))

ax.annotate('EXPENSIVE\nReduce Load\n~$123/MWh', xy=(22.5, 123), xytext=(22.5, 140),
            fontsize=11, ha='center', color='red', fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightcoral', alpha=0.7),
            arrowprops=dict(arrowstyle='->', color='red', lw=2))

plt.tight_layout()
plt.savefig('fig7_optimization_opportunity.png', dpi=300, bbox_inches='tight')
print("✓ Created fig7_optimization_opportunity.png")
plt.close()

print("\n✓ All visualizations created successfully!")
print("\nFiles created:")
print("  - fig1_time_of_day.png")
print("  - fig2_seasonal.png")
print("  - fig3_day_of_week.png")
print("  - fig4_winter_vs_summer.png")
print("  - fig5_variance_decomposition.png")
print("  - fig6_heatmap.png")
print("  - fig7_optimization_opportunity.png")
