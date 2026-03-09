# Bid Optimisation

Energy market bid optimisation and price prediction system.

## Project Structure

- **analysis/** - Market data analysis and clearing price analysis
- **price_prediction/** - ML-based price prediction models
- **load_distribution/** - Load distribution optimization for paper mill operations

## Getting Started

### Prerequisites

- Python 3.11+
- uv (Python package manager)
- Git LFS (for model files)

### Installation

1. **Install Git LFS** (one-time setup per machine):
```bash
git lfs install
```

2. **Clone the repository**:
```bash
git clone https://github.com/neelavasengupta/bid_optimisation.git
cd bid_optimisation
```

Git LFS will automatically download:
- Trained ML models (721MB) - required for price prediction
- Evaluation data (927MB) - required for both CLIs
- Analysis outputs and figures

3. **Download market data** (5.3GB, not in repo):
```bash
cd price_prediction
uv run python download_clearing_prices.py  # Required for training
uv run python download_bid_data.py         # Optional, for analysis
```

4. **Navigate to specific project** and follow its README for usage.

## What's Included vs What You Download

**In the repo (via Git LFS):**
- Trained models ready to use
- Evaluation datasets
- Sample predictions
- Analysis outputs

**You download separately:**
- Raw market data from NZ Electricity Market API (5.3GB)
- Weather data (manual process)

This means you can run the prediction and optimization CLIs immediately after cloning!
