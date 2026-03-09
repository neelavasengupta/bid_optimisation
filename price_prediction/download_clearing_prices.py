"""Download historical clearing prices (final prices) from EMI website."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import httpx


DATA_DIR = Path(__file__).parent.parent / "data" / "raw" / "clearings"
BASE_URL = "https://www.emi.ea.govt.nz/Wholesale/Datasets/DispatchAndPricing/DispatchEnergyPrices"
START_DATE = datetime(2024, 3, 7)
END_DATE = datetime(2026, 3, 7)
MAX_CONCURRENT = 20
MIN_FILE_SIZE = 10_000  # bytes


async def download_file(client: httpx.AsyncClient, date: datetime) -> tuple[datetime, bool, float]:
    """Download clearing price file for given date. Returns (date, success, size_mb)."""
    filepath = DATA_DIR / f"{date:%Y%m%d}_DispatchEnergyPrices.csv"
    
    if filepath.exists():
        return date, True, 0.0
    
    # URL format: BASE_URL/YYYY/YYYYMMDD_DispatchEnergyPrices.csv
    url = f"{BASE_URL}/{date:%Y}/{date:%Y%m%d}_DispatchEnergyPrices.csv"
    
    try:
        response = await client.get(url, timeout=30.0, follow_redirects=True)
        if response.status_code == 200 and len(response.content) > MIN_FILE_SIZE:
            filepath.write_bytes(response.content)
            return date, True, len(response.content) / 1024 / 1024
        return date, False, 0.0
    except Exception:
        return date, False, 0.0


async def main():
    """Download all clearing price files in date range."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    dates = [START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)]
    existing = {f.stem.split('_')[0] for f in DATA_DIR.glob('*_DispatchEnergyPrices.csv')}
    to_download = [d for d in dates if f"{d:%Y%m%d}" not in existing]
    
    print(f"Date range: {START_DATE:%Y-%m-%d} to {END_DATE:%Y-%m-%d} ({len(dates)} days)")
    print(f"Already downloaded: {len(existing)} files")
    print(f"To download: {len(to_download)} files")
    
    if not to_download:
        return
    
    print(f"\nDownloading with {MAX_CONCURRENT} concurrent connections...")
    
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=MAX_CONCURRENT)) as client:
        results = await asyncio.gather(*[download_file(client, date) for date in to_download])
    
    success = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    total_mb = sum(size for _, ok, size in results if ok and size > 0)
    
    print(f"\nComplete: {success} downloaded, {failed} failed, {total_mb:.1f} MB total")
    print(f"Total files: {len(list(DATA_DIR.glob('*_DispatchEnergyPrices.csv')))}")


if __name__ == "__main__":
    asyncio.run(main())
