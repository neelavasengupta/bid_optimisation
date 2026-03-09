import pandas as pd
import numpy as np

# Load data
bids = pd.read_csv('../data/20260303_Bids.csv')
offers = pd.read_csv('../data/20260304_Offers.csv')

print("=" * 80)
print("QUESTION 1: IS PRICE REALLY VARIABLE?")
print("=" * 80)

# Filter realistic prices (bids often have placeholder prices like 9998, 10000, 999999)
realistic_bids = bids[bids['DollarsPerMegawattHour'] < 1000]
realistic_offers = offers[offers['DollarsPerMegawattHour'] < 1000]

print(f"\nRealistic bid prices (< $1000/MWh):")
print(f"  Count: {len(realistic_bids)}")
print(f"  Range: ${realistic_bids['DollarsPerMegawattHour'].min():.2f} - ${realistic_bids['DollarsPerMegawattHour'].max():.2f}")
print(f"  Mean: ${realistic_bids['DollarsPerMegawattHour'].mean():.2f}")
print(f"  Std Dev: ${realistic_bids['DollarsPerMegawattHour'].std():.2f}")

print(f"\nRealistic offer prices (< $1000/MWh):")
print(f"  Count: {len(realistic_offers)}")
print(f"  Range: ${realistic_offers['DollarsPerMegawattHour'].min():.2f} - ${realistic_offers['DollarsPerMegawattHour'].max():.2f}")
print(f"  Mean: ${realistic_offers['DollarsPerMegawattHour'].mean():.2f}")
print(f"  Std Dev: ${realistic_offers['DollarsPerMegawattHour'].std():.2f}")

# Group by trading period to see time-of-day patterns
print("\n\nOFFER PRICES BY TIME OF DAY (Trading Period):")
print("-" * 80)
offer_by_period = realistic_offers.groupby('TradingPeriod')['DollarsPerMegawattHour'].agg(['mean', 'std', 'min', 'max', 'count'])
offer_by_period['hour'] = (offer_by_period.index - 1) // 2
offer_by_period['time'] = offer_by_period['hour'].apply(lambda x: f"{x:02d}:00-{x:02d}:30" if (offer_by_period.index[offer_by_period['hour']==x].min()-1) % 2 == 0 else f"{x:02d}:30-{x+1:02d}:00")

for period in [1, 7, 13, 19, 25, 31, 37, 43]:  # Sample periods throughout the day
    row = offer_by_period.loc[period]
    hour = (period - 1) // 2
    minute = "00" if (period - 1) % 2 == 0 else "30"
    print(f"Period {period:2d} ({hour:02d}:{minute}): Mean=${row['mean']:6.2f}, Std=${row['std']:6.2f}, Range=${row['min']:6.2f}-${row['max']:6.2f}")

print("\n\n" + "=" * 80)
print("QUESTION 2: HOW PREDICTABLE IS IT?")
print("=" * 80)

# Calculate coefficient of variation (CV) = std/mean for each period
offer_by_period['cv'] = offer_by_period['std'] / offer_by_period['mean']
print(f"\nCoefficient of Variation (CV = std/mean) by period:")
print(f"  Mean CV: {offer_by_period['cv'].mean():.2f}")
print(f"  Min CV: {offer_by_period['cv'].min():.2f}")
print(f"  Max CV: {offer_by_period['cv'].max():.2f}")
print(f"\nInterpretation:")
print(f"  CV < 0.5: Low variability (predictable)")
print(f"  CV 0.5-1.0: Moderate variability")
print(f"  CV > 1.0: High variability (unpredictable)")

# Identify peak vs off-peak patterns
morning_peak = offer_by_period.loc[13:20, 'mean'].mean()  # 6:30am - 10:00am
day_peak = offer_by_period.loc[33:40, 'mean'].mean()      # 4:00pm - 8:00pm
off_peak = offer_by_period.loc[1:12, 'mean'].mean()       # 12:00am - 6:00am

print(f"\n\nTime-of-Day Patterns:")
print(f"  Off-peak (12am-6am): ${off_peak:.2f}/MWh")
print(f"  Morning peak (6:30am-10am): ${morning_peak:.2f}/MWh")
print(f"  Day peak (4pm-8pm): ${day_peak:.2f}/MWh")
print(f"  Peak vs Off-peak ratio: {day_peak/off_peak:.2f}x")

print("\n\n" + "=" * 80)
print("QUESTION 3: WHAT ARE THE INFLUENCERS?")
print("=" * 80)

# Analyze by participant (generator type)
print("\nTop 10 Offer Participants by Volume:")
participant_stats = realistic_offers.groupby('ParticipantCode').agg({
    'Megawatts': 'sum',
    'DollarsPerMegawattHour': ['mean', 'std', 'count']
}).round(2)
participant_stats.columns = ['Total_MW', 'Avg_Price', 'Std_Price', 'Count']
participant_stats = participant_stats.sort_values('Total_MW', ascending=False)
print(participant_stats.head(10))

# Analyze by product type
print("\n\nOffer Prices by Product Type:")
product_stats = realistic_offers.groupby('ProductType')['DollarsPerMegawattHour'].agg(['mean', 'std', 'count']).round(2)
print(product_stats)

print("\n\n" + "=" * 80)
print("QUESTION 4: IS THERE A CLEAR DECISION TREE?")
print("=" * 80)

# Create simple decision rules based on time of day
print("\nSIMPLE DECISION TREE FOR PAPER MILL:")
print("-" * 80)

# Define price thresholds based on quartiles
q25 = realistic_offers['DollarsPerMegawattHour'].quantile(0.25)
q50 = realistic_offers['DollarsPerMegawattHour'].quantile(0.50)
q75 = realistic_offers['DollarsPerMegawattHour'].quantile(0.75)

print(f"\nPrice Quartiles:")
print(f"  Q1 (25%): ${q25:.2f}/MWh")
print(f"  Q2 (50%): ${q50:.2f}/MWh")
print(f"  Q3 (75%): ${q75:.2f}/MWh")

print(f"\n\nDECISION RULES:")
print(f"1. OFF-PEAK HOURS (12am-6am, Periods 1-12):")
print(f"   → RUN PULPERS AT 120% (build inventory)")
print(f"   → Expected price: ${off_peak:.2f}/MWh")
print(f"")
print(f"2. SHOULDER HOURS (6am-4pm, Periods 13-32):")
print(f"   → RUN PULPERS AT 100% (maintain inventory)")
print(f"   → Expected price: ${offer_by_period.loc[13:32, 'mean'].mean():.2f}/MWh")
print(f"")
print(f"3. PEAK HOURS (4pm-10pm, Periods 33-44):")
print(f"   → RUN PULPERS AT 60% (draw down inventory)")
print(f"   → Expected price: ${day_peak:.2f}/MWh")
print(f"")
print(f"4. LATE EVENING (10pm-12am, Periods 45-48):")
print(f"   → RUN PULPERS AT 100% (rebuild inventory)")
print(f"   → Expected price: ${offer_by_period.loc[45:48, 'mean'].mean():.2f}/MWh")

# Calculate potential savings
print(f"\n\nPOTENTIAL SAVINGS CALCULATION:")
print(f"  Baseline (constant 20 MW): 20 MW × 24h × ${realistic_offers['DollarsPerMegawattHour'].mean():.2f}/MWh = ${20 * 24 * realistic_offers['DollarsPerMegawattHour'].mean():.2f}/day")
print(f"  Optimized (shift 2 MW from peak to off-peak):")
print(f"    - Save during peak: 2 MW × 8h × ${day_peak:.2f}/MWh = ${2 * 8 * day_peak:.2f}")
print(f"    - Cost during off-peak: 2 MW × 8h × ${off_peak:.2f}/MWh = ${2 * 8 * off_peak:.2f}")
print(f"    - Net daily savings: ${2 * 8 * (day_peak - off_peak):.2f}")
print(f"    - Annual savings: ${2 * 8 * (day_peak - off_peak) * 365:.2f}")

print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\n1. YES, price is variable: ${realistic_offers['DollarsPerMegawattHour'].min():.2f} to ${realistic_offers['DollarsPerMegawattHour'].max():.2f}")
print(f"2. MODERATELY predictable: Time-of-day patterns are clear")
print(f"3. Main influencers: Time of day, participant/generator type")
print(f"4. YES, simple decision tree exists: 3-4 time blocks with clear rules")
