import pandas as pd
import numpy as np
from pathlib import Path

# Load the data
bids = pd.read_csv('../data/20260303_Bids.csv')
offers = pd.read_csv('../data/20260304_Offers.csv')

print("=== BIDS DATA ===")
print(f"Shape: {bids.shape}")
print(f"\nColumns: {bids.columns.tolist()}")
print(f"\nFirst few rows:")
print(bids.head(10))
print(f"\nPrice statistics:")
print(bids['DollarsPerMegawattHour'].describe())
print(f"\nUnique trading periods: {sorted(bids['TradingPeriod'].unique())}")
print(f"\nParticipants: {bids['ParticipantCode'].unique()}")

print("\n\n=== OFFERS DATA ===")
print(f"Shape: {offers.shape}")
print(f"\nColumns: {offers.columns.tolist()}")
print(f"\nFirst few rows:")
print(offers.head(10))
print(f"\nPrice statistics:")
print(offers['DollarsPerMegawattHour'].describe())
print(f"\nUnique trading periods: {sorted(offers['TradingPeriod'].unique())}")
print(f"\nParticipants: {offers['ParticipantCode'].unique()}")

# Analyze price variability by trading period
print("\n\n=== PRICE VARIABILITY ANALYSIS ===")

# For bids - group by trading period and get price stats
bid_by_period = bids.groupby('TradingPeriod')['DollarsPerMegawattHour'].agg(['min', 'max', 'mean', 'std', 'count'])
print("\nBid prices by trading period:")
print(bid_by_period)

# For offers - group by trading period and get price stats
offer_by_period = offers.groupby('TradingPeriod')['DollarsPerMegawattHour'].agg(['min', 'max', 'mean', 'std', 'count'])
print("\nOffer prices by trading period:")
print(offer_by_period.head(20))

# Save results
bid_by_period.to_csv('bid_prices_by_period.csv')
offer_by_period.to_csv('offer_prices_by_period.csv')

print("\n\nResults saved to CSV files")
