# Bid Optimisation

Energy market bid optimisation and price prediction system.

## Project Structure

- **analysis/** - Market data analysis and clearing price analysis
- **price_prediction/** - ML-based price prediction models
- **load_distribution/** - Load distribution optimization for paper mill operations

## Getting Started

Each subdirectory contains its own README with specific setup and usage instructions.

### Prerequisites

- Python 3.11+
- uv (Python package manager)

### Installation

Navigate to the specific project directory and follow its README instructions.

## Data Setup

**Data files are NOT included in this repository** (5.3GB excluded to keep repo lightweight).

To download data:

```bash
# Download clearing prices (required for price prediction)
cd price_prediction
uv run python download_clearing_prices.py

# Download bid data (optional, for analysis)
uv run python download_bid_data.py
```

This will download ~5GB of data from the NZ Electricity Market (EMI) public API.

**Note**: Weather data must be obtained separately (not automated).
