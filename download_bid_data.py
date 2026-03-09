"""Download sampled historical bid data from EMI website."""

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import time

# Configuration
DATA_DIR = Path("data")
BASE_URL = "https://www.emi.ea.govt.nz/Wholesale/Datasets/BidsAndOffers/Bids"
END_DATE = datetime(2026, 3, 7)  # Today
START_DATE = datetime(2024, 3, 7)  # 2 years back

DATA_DIR.mkdir(exist_ok=True)


def get_sample_dates(start_date: datetime, end_date: datetime) -> list[datetime]:
    """
    Get sampled dates: 1 week per month over the date range.
    This captures seasonal patterns without downloading all data.
    """
    dates = []
    current = start_date
    
    while current <= end_date:
        # Take first 7 days of each month
        month_start = current.replace(day=1)
        for day_offset in range(7):
            date = month_start + timedelta(days=day_offset)
            if date <= end_date:
                dates.append(date)
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    return dates

def download_bid_file(date: datetime) -> bool:
    """Download bid file for a specific date using curl."""
    date_str = date.strftime("%Y%m%d")
    year = date.strftime("%Y")
    filename = f"{date_str}_Bids.csv"
    filepath = DATA_DIR / filename
    
    # Skip if already exists
    if filepath.exists():
        print(f"✓ {filename} already exists")
        return True
    
    # URL format: BASE_URL/YYYY/YYYYMMDD_Bids.csv
    url = f"{BASE_URL}/{year}/{filename}"
    
    try:
        print(f"Downloading {filename}...", end=" ", flush=True)
        
        # Use curl to download
        result = subprocess.run(
            ["curl", "-sS", "-L", "-o", str(filepath), url],
            capture_output=True,
            timeout=60
        )
        
        if result.returncode == 0 and filepath.exists():
            size_mb = filepath.stat().st_size / 1024 / 1024
            if size_mb > 0.01:  # More than 10KB
                print(f"✓ ({size_mb:.1f} MB)")
                return True
            else:
                # File too small, probably an error page
                filepath.unlink()
                print(f"✗ Not found")
                return False
        else:
            print(f"✗ Download failed")
            if filepath.exists():
                filepath.unlink()
            return False
            
    except Exception as e:
        print(f"✗ {e}")
        if filepath.exists():
            filepath.unlink()
        return False


def main():
    """Download sampled bid files."""
    sample_dates = get_sample_dates(START_DATE, END_DATE)
    
    print(f"Downloading sampled bid data from {START_DATE.date()} to {END_DATE.date()}")
    print(f"Strategy: First 7 days of each month")
    print(f"Total dates to download: {len(sample_dates)} days")
    print()
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for date in sample_dates:
        filepath = DATA_DIR / f"{date.strftime('%Y%m%d')}_Bids.csv"
        
        if filepath.exists():
            skip_count += 1
            continue
        
        if download_bid_file(date):
            success_count += 1
            time.sleep(0.5)  # Be nice to the server
        else:
            fail_count += 1
    
    print()
    print("=" * 70)
    print(f"Download complete!")
    print(f"  Downloaded: {success_count} files")
    print(f"  Skipped (already exist): {skip_count} files")
    print(f"  Failed: {fail_count} files")
    print(f"  Total files in data/: {len(list(DATA_DIR.glob('*_Bids.csv')))}")
    print("=" * 70)


if __name__ == "__main__":
    main()
