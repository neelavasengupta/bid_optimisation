import pandas as pd
import numpy as np

print("=" * 80)
print("UNDERSTANDING NZ ELECTRICITY MARKET MECHANICS")
print("=" * 80)

print("""
KEY QUESTION: What data do we actually need?

In NZ wholesale electricity market:

1. OFFERS (Supply Side):
   - Generators submit offers: "I will supply X MW at $Y/MWh"
   - Multiple tranches per generator (e.g., first 50 MW @ $10, next 20 MW @ $50)
   - These are SUPPLY CURVES

2. BIDS (Demand Side):
   - Large consumers submit bids: "I will consume X MW at $Y/MWh"
   - Most demand is "price-taker" (will pay whatever the market clears at)
   - These are DEMAND CURVES

3. CLEARING PRICE (What we need!):
   - Market operator stacks offers from cheapest to most expensive
   - Matches with demand
   - The LAST offer accepted sets the clearing price for that node/period
   - This is what everyone actually pays/receives

CURRENT DATA:
- We have OFFERS (supply curves) ✓
- We have BIDS (demand curves) ✓
- We DON'T have clearing prices ✗

FOR PAPER MILL OPTIMIZATION:
- Paper mill is a BUYER (demand side)
- They pay the CLEARING PRICE, not the offer prices
- We need to either:
  a) Calculate clearing prices from offers + bids
  b) Get actual clearing price data from market operator
""")

print("\n" + "=" * 80)
print("ANALYZING WHAT WE CAN INFER")
print("=" * 80)

# Load data
bids = pd.read_csv('../data/20260303_Bids.csv')
offers = pd.read_csv('../data/20260304_Offers.csv')

print(f"\nBIDS (Demand Side):")
print(f"  Total records: {len(bids):,}")
print(f"  Unique participants: {bids['ParticipantCode'].nunique()}")
print(f"  Date: {bids['TradingDate'].unique()}")

print(f"\nOFFERS (Supply Side):")
print(f"  Total records: {len(offers):,}")
print(f"  Unique participants: {offers['ParticipantCode'].nunique()}")
print(f"  Date: {offers['TradingDate'].unique()}")

print("\n⚠️  PROBLEM: Different dates! Bids are March 3, Offers are March 4")
print("   Cannot calculate clearing prices without matching dates")

print("\n" + "=" * 80)
print("WHAT WE NEED FOR PROPER ANALYSIS")
print("=" * 80)

print("""
OPTION 1: Get matching bid + offer data for same dates
- Need both bids and offers for same trading periods
- Can then simulate market clearing
- Calculate approximate clearing prices

OPTION 2: Get actual clearing price data
- Final prices published by Electricity Authority
- This is what paper mill actually pays
- Much better for optimization analysis

OPTION 3: Get dispatch data
- Shows which offers were actually accepted
- Can infer clearing prices from highest accepted offer

RECOMMENDATION:
→ We need CLEARING PRICE data (final prices paid)
→ Or at minimum: matching bid/offer data for same dates
→ Ideally: 3-6 months of data to see patterns

Current analysis is LIMITED because:
- Offer prices ≠ clearing prices
- Can't match supply/demand without same dates
- Single day is not representative
""")

print("\n" + "=" * 80)
print("QUICK CHECK: Can we estimate anything useful?")
print("=" * 80)

# Look at high-priced offers (likely marginal units)
high_offers = offers[(offers['DollarsPerMegawattHour'] > 50) & 
                     (offers['DollarsPerMegawattHour'] < 500) &
                     (offers['Megawatts'] > 0)]

print(f"\nHigh-priced offers (>$50/MWh, likely marginal units):")
print(f"  Count: {len(high_offers):,}")
print(f"  Price range: ${high_offers['DollarsPerMegawattHour'].min():.2f} - ${high_offers['DollarsPerMegawattHour'].max():.2f}")
print(f"  Mean: ${high_offers['DollarsPerMegawattHour'].mean():.2f}")

# Group by period
marginal_by_period = high_offers.groupby('TradingPeriod')['DollarsPerMegawattHour'].agg(['mean', 'min', 'max', 'count'])
print(f"\nMarginal offer prices by time of day (sample):")
for period in [1, 13, 19, 25, 31, 37, 43]:
    if period in marginal_by_period.index:
        row = marginal_by_period.loc[period]
        hour = (period - 1) // 2
        minute = "00" if (period - 1) % 2 == 0 else "30"
        print(f"  Period {period:2d} ({hour:02d}:{minute}): ${row['mean']:6.2f} (range: ${row['min']:6.2f}-${row['max']:6.2f})")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
CURRENT DATA IS INSUFFICIENT for proper price analysis because:

1. Offers show what generators WANT to charge, not what market clears at
2. Bids and offers are from different dates (can't match supply/demand)
3. Single day snapshot doesn't show patterns

TO DO PROPER ANALYSIS, WE NEED:
✓ Clearing price data (actual final prices) - BEST OPTION
✓ Or: Matching bid/offer data for same dates over 3-6 months
✓ Or: Dispatch data showing which offers were accepted

NEXT STEPS:
1. Ask user if they can get clearing price data
2. Or get matching bid/offer datasets for same dates
3. Need at least 1-3 months to see patterns
4. Then we can properly answer: is optimization worth it?
""")
