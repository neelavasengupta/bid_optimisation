"""Download historical weather data from Open-Meteo API for NZ locations."""

import httpx
import pandas as pd
from pathlib import Path

# Weather stations for NZ (major cities covering both islands)
WEATHER_LOCATIONS = {
    'Auckland': {'lat': -36.8485, 'lon': 174.7633, 'island': 'NI'},
    'Wellington': {'lat': -41.2865, 'lon': 174.7762, 'island': 'NI'},
    'Christchurch': {'lat': -43.5321, 'lon': 172.6362, 'island': 'SI'},
    'Dunedin': {'lat': -45.8788, 'lon': 170.5028, 'island': 'SI'},
}

# Date range (match clearing price data: March 2024 - March 2026)
START_DATE = '2024-03-07'
END_DATE = '2026-03-06'

# Open-Meteo API endpoint
API_URL = 'https://archive-api.open-meteo.com/v1/archive'

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "weather"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_weather_data(location_name: str, lat: float, lon: float, 
                          start_date: str, end_date: str) -> pd.DataFrame:
    """
    Download historical weather data from Open-Meteo.
    
    Args:
        location_name: Name of the location
        lat: Latitude
        lon: Longitude
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        DataFrame with weather data
    """
    print(f"Downloading weather data for {location_name}...")
    
    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': start_date,
        'end_date': end_date,
        'hourly': [
            'temperature_2m',
            'relative_humidity_2m',
            'precipitation',
            'wind_speed_10m',
            'wind_direction_10m',
            'shortwave_radiation',
        ],
        'timezone': 'Pacific/Auckland',
    }
    
    response = httpx.get(API_URL, params=params, follow_redirects=True)
    response.raise_for_status()
    
    data = response.json()
    
    # Convert to DataFrame
    df = pd.DataFrame({
        'timestamp': pd.to_datetime(data['hourly']['time']),
        'temperature': data['hourly']['temperature_2m'],
        'humidity': data['hourly']['relative_humidity_2m'],
        'precipitation': data['hourly']['precipitation'],
        'wind_speed': data['hourly']['wind_speed_10m'],
        'wind_direction': data['hourly']['wind_direction_10m'],
        'solar_radiation': data['hourly']['shortwave_radiation'],
    })
    
    df['location'] = location_name
    
    print(f"  Downloaded {len(df)} hourly records")
    print(f"  Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    return df


def resample_to_30min(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample hourly data to 30-minute intervals to match electricity data.
    Uses forward-fill for simplicity.
    
    Args:
        df: DataFrame with hourly weather data
    
    Returns:
        DataFrame with 30-minute intervals
    """
    df = df.set_index('timestamp')
    
    # Resample to 30min and forward-fill
    df_30min = df.resample('30min').ffill()
    
    df_30min = df_30min.reset_index()
    
    return df_30min


def main():
    """Download weather data for all locations."""
    all_weather = []
    
    for location_name, coords in WEATHER_LOCATIONS.items():
        try:
            df = download_weather_data(
                location_name=location_name,
                lat=coords['lat'],
                lon=coords['lon'],
                start_date=START_DATE,
                end_date=END_DATE
            )
            
            # Add island information
            df['island'] = coords['island']
            
            # Resample to 30-minute intervals
            df = resample_to_30min(df)
            
            all_weather.append(df)
            
        except Exception as e:
            print(f"  Error downloading {location_name}: {e}")
            continue
    
    # Combine all locations
    if all_weather:
        combined_df = pd.concat(all_weather, ignore_index=True)
        
        # Save combined file
        combined_file = OUTPUT_DIR / 'weather_all_locations.csv'
        combined_df.to_csv(combined_file, index=False)
        print(f"\nSaved combined weather data: {combined_file}")
        print(f"Total records: {len(combined_df)}")
        
        # Show summary statistics
        print("\nWeather data summary:")
        print(combined_df.groupby('location').agg({
            'temperature': ['mean', 'min', 'max'],
            'precipitation': 'sum',
            'wind_speed': 'mean',
        }).round(2))
    
    print("\nWeather data download complete!")


if __name__ == '__main__':
    main()
