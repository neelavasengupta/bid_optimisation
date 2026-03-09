"""Generate comprehensive evaluation report with visualizations."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from autogluon.timeseries import TimeSeriesPredictor, TimeSeriesDataFrame
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

from .config import MODEL_PATH, GROUND_TRUTH_FILE, PREDICTION_LENGTH, REPORT_DIR, KNOWN_COVARIATES, BEST_MODEL

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10


class ReportGenerator:
    """Generate comprehensive evaluation report with plots and analysis."""
    
    def __init__(self, model_path: Path, data_path: Path):
        self.model_path = model_path
        self.data_path = data_path
        self.output_dir = REPORT_DIR
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        self.predictor = None
        self.eval_df = None
        self.results = {}
        
    def load_and_prepare_data(self):
        """Load model and generate holdout predictions."""
        print("Loading model and data...")
        self.predictor = TimeSeriesPredictor.load(str(self.model_path))
        
        # Use best model from config (TFT performs better on test data than WeightedEnsemble)
        self.model_to_use = BEST_MODEL
        print(f"Using model: {self.model_to_use}")
        
        # Load data
        df = pd.read_csv(self.data_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        static_file = self.data_path.parent / "static_features.csv"
        static_df = pd.read_csv(static_file).set_index('item_id')
        
        # Create holdout set - mix of periods with rolling 48h forecasts
        # For each test period, generate multiple 48h forecasts (rolling window)
        # This matches how the model will be used in production
        
        test_periods = [
            ('2025-08-18', '2025-08-25', 'Winter'),   # 7 days
            ('2024-12-18', '2024-12-25', 'Summer'),   # 7 days  
            ('2025-04-18', '2025-04-25', 'Shoulder'), # 7 days
        ]
        
        # Find locations that exist in all periods
        all_locations = set(df['item_id'].unique())
        for start_str, end_str, season in test_periods:
            period_start = pd.Timestamp(start_str)
            period_end = pd.Timestamp(end_str)
            period_locations = set(df[(df['timestamp'] >= period_start) & (df['timestamp'] < period_end)]['item_id'].unique())
            all_locations = all_locations.intersection(period_locations)
        
        print(f"Found {len(all_locations)} locations present in all test periods")
        
        # Filter data to only these locations
        df = df[df['item_id'].isin(all_locations)].copy()
        static_df = static_df[static_df.index.isin(all_locations)]
        
        all_predictions = []
        
        for start_str, end_str, season in test_periods:
            period_start = pd.Timestamp(start_str)
            period_end = pd.Timestamp(end_str)
            
            print(f"\n{season} period: {period_start.date()} to {period_end.date()}")
            
            # Generate rolling 48h forecasts
            # Start from period_start, generate 48h forecast, then roll forward by 24h
            forecast_starts = pd.date_range(period_start, period_end - pd.Timedelta(hours=48), freq='24H')
            
            for forecast_start in forecast_starts:
                context_start = forecast_start - pd.Timedelta(days=60)
                forecast_end = forecast_start + pd.Timedelta(hours=48)
                
                # Get context data (60 days before forecast)
                context_df = df[(df['timestamp'] >= context_start) & (df['timestamp'] < forecast_start)].copy()
                
                # Get actual data for the 48h forecast period
                actual_df = df[(df['timestamp'] >= forecast_start) & (df['timestamp'] < forecast_end)].copy()
                
                if len(actual_df) == 0:
                    continue
                
                # Generate 48h forecast
                context_ts = TimeSeriesDataFrame.from_data_frame(
                    context_df, id_column='item_id', timestamp_column='timestamp'
                )
                context_ts.static_features = static_df
                
                actual_covariates = TimeSeriesDataFrame.from_data_frame(
                    actual_df, id_column='item_id', timestamp_column='timestamp'
                )
                
                predictions = self.predictor.predict(context_ts, known_covariates=actual_covariates, model=self.model_to_use)
                pred_df = predictions.reset_index()
                pred_df.columns = ['item_id', 'timestamp'] + [c for c in pred_df.columns if c not in ['item_id', 'timestamp']]
                
                # Merge with actuals
                forecast_eval = actual_df.merge(
                    pred_df[['item_id', 'timestamp', 'mean']],
                    on=['item_id', 'timestamp'], how='inner'
                )
                
                # Add forecast metadata
                forecast_eval['forecast_start'] = forecast_start
                forecast_eval['hours_ahead'] = (pd.to_datetime(forecast_eval['timestamp']) - forecast_start).dt.total_seconds() / 3600
                
                all_predictions.append(forecast_eval)
            
            print(f"  Generated {len(forecast_starts)} rolling 48h forecasts")
        
        # Combine all forecasts
        self.eval_df = pd.concat(all_predictions, ignore_index=True)
        self.eval_df.rename(columns={'target': 'actual', 'mean': 'predicted'}, inplace=True)
        self.eval_df['error'] = self.eval_df['predicted'] - self.eval_df['actual']
        self.eval_df['abs_error'] = np.abs(self.eval_df['error'])
        
        # Add time features for analysis
        self.eval_df['hour'] = pd.to_datetime(self.eval_df['timestamp']).dt.hour
        self.eval_df['day_of_week'] = pd.to_datetime(self.eval_df['timestamp']).dt.dayofweek
        self.eval_df['month'] = pd.to_datetime(self.eval_df['timestamp']).dt.month
        
        # Add static features
        self.static_features = static_df.reset_index()
        self.eval_df = self.eval_df.merge(
            self.static_features[['item_id', 'Island']], on='item_id', how='left'
        )
        
        print(f"\nTotal: {len(self.eval_df)} predictions for {self.eval_df['item_id'].nunique()} locations")
        print(f"Overall mean price: ${self.eval_df['actual'].mean():.2f} per MWh")
        print(f"Overall price range: ${self.eval_df['actual'].min():.2f} to ${self.eval_df['actual'].max():.2f} per MWh")

    def plot_actual_vs_predicted(self):
        """Scatter plot of actual vs predicted prices."""
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        
        # Full range
        axes[0].scatter(self.eval_df['actual'], self.eval_df['predicted'], 
                       alpha=0.1, s=1, c='blue')
        axes[0].plot([0, self.eval_df['actual'].max()], [0, self.eval_df['actual'].max()], 
                    'r--', label='Perfect prediction', linewidth=2)
        axes[0].set_xlabel('Actual Price ($/MWh)', fontsize=12)
        axes[0].set_ylabel('Predicted Price ($/MWh)', fontsize=12)
        axes[0].set_title('Actual vs Predicted Prices (All Data)', fontsize=14, fontweight='bold')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Zoomed to typical range
        mask = (self.eval_df['actual'] < 300) & (self.eval_df['predicted'] < 300)
        axes[1].scatter(self.eval_df[mask]['actual'], self.eval_df[mask]['predicted'], 
                       alpha=0.1, s=1, c='blue')
        axes[1].plot([0, 300], [0, 300], 'r--', label='Perfect prediction', linewidth=2)
        axes[1].set_xlabel('Actual Price ($/MWh)', fontsize=12)
        axes[1].set_ylabel('Predicted Price ($/MWh)', fontsize=12)
        axes[1].set_title('Actual vs Predicted (Zoomed: <$300)', fontsize=14, fontweight='bold')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '01_actual_vs_predicted.png', dpi=300, bbox_inches='tight')
        plt.close()
        
    def plot_error_distribution(self):
        """Plot error distribution and bias."""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Error histogram
        axes[0, 0].hist(self.eval_df['error'], bins=100, edgecolor='black', alpha=0.7)
        axes[0, 0].axvline(0, color='red', linestyle='--', linewidth=2, label='Zero error')
        axes[0, 0].axvline(self.eval_df['error'].mean(), color='green', linestyle='--', 
                          linewidth=2, label=f'Mean: ${self.eval_df["error"].mean():.2f}')
        axes[0, 0].set_xlabel('Prediction Error ($/MWh)', fontsize=12)
        axes[0, 0].set_ylabel('Frequency', fontsize=12)
        axes[0, 0].set_title('Distribution of Prediction Errors', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Absolute error histogram
        axes[0, 1].hist(self.eval_df['abs_error'], bins=100, edgecolor='black', alpha=0.7, color='orange')
        axes[0, 1].axvline(self.eval_df['abs_error'].mean(), color='red', linestyle='--', 
                          linewidth=2, label=f'MAE: ${self.eval_df["abs_error"].mean():.2f}')
        axes[0, 1].set_xlabel('Absolute Error ($/MWh)', fontsize=12)
        axes[0, 1].set_ylabel('Frequency', fontsize=12)
        axes[0, 1].set_title('Distribution of Absolute Errors', fontsize=14, fontweight='bold')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Error vs actual price
        axes[1, 0].scatter(self.eval_df['actual'], self.eval_df['error'], 
                          alpha=0.1, s=1, c='blue')
        axes[1, 0].axhline(0, color='red', linestyle='--', linewidth=2)
        axes[1, 0].set_xlabel('Actual Price ($/MWh)', fontsize=12)
        axes[1, 0].set_ylabel('Prediction Error ($/MWh)', fontsize=12)
        axes[1, 0].set_title('Error vs Actual Price', fontsize=14, fontweight='bold')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Percentage error distribution
        pct_error = (self.eval_df['error'] / self.eval_df['actual'].clip(lower=1)) * 100
        pct_error = pct_error.clip(-200, 200)  # Clip extreme values
        axes[1, 1].hist(pct_error, bins=100, edgecolor='black', alpha=0.7, color='green')
        axes[1, 1].axvline(0, color='red', linestyle='--', linewidth=2)
        axes[1, 1].set_xlabel('Percentage Error (%)', fontsize=12)
        axes[1, 1].set_ylabel('Frequency', fontsize=12)
        axes[1, 1].set_title('Distribution of Percentage Errors', fontsize=14, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '02_error_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_time_of_day_analysis(self):
        """Analyze performance by time of day."""
        hourly_metrics = self.eval_df.groupby('hour').agg({
            'abs_error': 'mean',
            'actual': 'mean',
            'predicted': 'mean',
            'error': 'mean'
        }).reset_index()
        hourly_metrics.columns = ['hour', 'MAE', 'Mean_Actual', 'Mean_Predicted', 'Bias']
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # MAE by hour
        axes[0, 0].bar(hourly_metrics['hour'], hourly_metrics['MAE'], 
                      color='steelblue', edgecolor='black')
        axes[0, 0].set_xlabel('Hour of Day', fontsize=12)
        axes[0, 0].set_ylabel('MAE ($/MWh)', fontsize=12)
        axes[0, 0].set_title('Mean Absolute Error by Hour of Day', fontsize=14, fontweight='bold')
        axes[0, 0].set_xticks(range(0, 24))
        axes[0, 0].grid(True, alpha=0.3, axis='y')
        
        # Actual vs Predicted by hour
        axes[0, 1].plot(hourly_metrics['hour'], hourly_metrics['Mean_Actual'], 
                       marker='o', linewidth=2, label='Actual', color='blue')
        axes[0, 1].plot(hourly_metrics['hour'], hourly_metrics['Mean_Predicted'], 
                       marker='s', linewidth=2, label='Predicted', color='red')
        axes[0, 1].set_xlabel('Hour of Day', fontsize=12)
        axes[0, 1].set_ylabel('Mean Price ($/MWh)', fontsize=12)
        axes[0, 1].set_title('Mean Actual vs Predicted Price by Hour', fontsize=14, fontweight='bold')
        axes[0, 1].set_xticks(range(0, 24))
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Bias by hour
        axes[1, 0].bar(hourly_metrics['hour'], hourly_metrics['Bias'], 
                      color=['red' if x < 0 else 'green' for x in hourly_metrics['Bias']], 
                      edgecolor='black')
        axes[1, 0].axhline(0, color='black', linestyle='--', linewidth=1)
        axes[1, 0].set_xlabel('Hour of Day', fontsize=12)
        axes[1, 0].set_ylabel('Bias ($/MWh)', fontsize=12)
        axes[1, 0].set_title('Prediction Bias by Hour (Negative = Underestimate)', 
                            fontsize=14, fontweight='bold')
        axes[1, 0].set_xticks(range(0, 24))
        axes[1, 0].grid(True, alpha=0.3, axis='y')
        
        # Heatmap of errors by hour
        hour_error_matrix = self.eval_df.pivot_table(
            values='abs_error', index='hour', aggfunc='mean'
        )
        im = axes[1, 1].imshow(hour_error_matrix.values.reshape(-1, 1).T, 
                              cmap='YlOrRd', aspect='auto')
        axes[1, 1].set_xticks(range(24))
        axes[1, 1].set_xticklabels(range(24))
        axes[1, 1].set_yticks([])
        axes[1, 1].set_xlabel('Hour of Day', fontsize=12)
        axes[1, 1].set_title('Error Intensity Heatmap', fontsize=14, fontweight='bold')
        plt.colorbar(im, ax=axes[1, 1], label='MAE ($/MWh)')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '03_time_of_day_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_price_range_analysis(self):
        """Analyze performance across price ranges."""
        bins = [0, 50, 100, 150, 200, 300, 500, np.inf]
        labels = ['$0-50', '$50-100', '$100-150', '$150-200', '$200-300', '$300-500', '$500+']
        self.eval_df['price_bin'] = pd.cut(self.eval_df['actual'], bins=bins, labels=labels)
        
        price_metrics = self.eval_df.groupby('price_bin').agg({
            'abs_error': 'mean',
            'actual': ['mean', 'count'],
            'predicted': 'mean',
            'error': 'mean'
        }).reset_index()
        price_metrics.columns = ['price_bin', 'MAE', 'Mean_Actual', 'Count', 'Mean_Predicted', 'Bias']
        price_metrics['Pct'] = (price_metrics['Count'] / len(self.eval_df)) * 100
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # MAE by price range
        axes[0, 0].bar(range(len(price_metrics)), price_metrics['MAE'], 
                      color='steelblue', edgecolor='black')
        axes[0, 0].set_xticks(range(len(price_metrics)))
        axes[0, 0].set_xticklabels(price_metrics['price_bin'], rotation=45)
        axes[0, 0].set_ylabel('MAE ($/MWh)', fontsize=12)
        axes[0, 0].set_title('MAE by Price Range', fontsize=14, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3, axis='y')
        
        # Distribution of data across price ranges
        axes[0, 1].bar(range(len(price_metrics)), price_metrics['Pct'], 
                      color='orange', edgecolor='black')
        axes[0, 1].set_xticks(range(len(price_metrics)))
        axes[0, 1].set_xticklabels(price_metrics['price_bin'], rotation=45)
        axes[0, 1].set_ylabel('Percentage of Data (%)', fontsize=12)
        axes[0, 1].set_title('Data Distribution Across Price Ranges', fontsize=14, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3, axis='y')
        
        # Actual vs Predicted by price range
        x = range(len(price_metrics))
        width = 0.35
        axes[1, 0].bar([i - width/2 for i in x], price_metrics['Mean_Actual'], 
                      width, label='Actual', color='blue', edgecolor='black')
        axes[1, 0].bar([i + width/2 for i in x], price_metrics['Mean_Predicted'], 
                      width, label='Predicted', color='red', edgecolor='black')
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(price_metrics['price_bin'], rotation=45)
        axes[1, 0].set_ylabel('Mean Price ($/MWh)', fontsize=12)
        axes[1, 0].set_title('Actual vs Predicted by Price Range', fontsize=14, fontweight='bold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3, axis='y')
        
        # Bias by price range
        axes[1, 1].bar(range(len(price_metrics)), price_metrics['Bias'], 
                      color=['red' if x < 0 else 'green' for x in price_metrics['Bias']], 
                      edgecolor='black')
        axes[1, 1].axhline(0, color='black', linestyle='--', linewidth=1)
        axes[1, 1].set_xticks(range(len(price_metrics)))
        axes[1, 1].set_xticklabels(price_metrics['price_bin'], rotation=45)
        axes[1, 1].set_ylabel('Bias ($/MWh)', fontsize=12)
        axes[1, 1].set_title('Bias by Price Range (Negative = Underestimate)', 
                            fontsize=14, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '04_price_range_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        return price_metrics

    def plot_forecast_horizon_analysis(self):
        """Analyze how error changes with forecast horizon (0-48 hours)."""
        # hours_ahead is already calculated correctly during data prep (0-48 hours from forecast start)
        # Group into 6-hour buckets for cleaner visualization
        self.eval_df['horizon_bucket'] = (self.eval_df['hours_ahead'] / 6).astype(int)
        self.eval_df['horizon_bucket'] = self.eval_df['horizon_bucket'].clip(0, 7)  # 0-48h = 8 buckets
        
        horizon_metrics = self.eval_df.groupby('horizon_bucket').agg({
            'abs_error': 'mean',
            'error': 'mean',
            'actual': 'mean',
            'predicted': 'mean',
            'hours_ahead': 'mean'
        }).reset_index()
        horizon_metrics.columns = ['bucket', 'MAE', 'Bias', 'Mean_Actual', 'Mean_Predicted', 'Hours_Ahead']
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # MAE over forecast horizon
        axes[0, 0].plot(horizon_metrics['Hours_Ahead'], horizon_metrics['MAE'], 
                       marker='o', linewidth=2, markersize=8, color='steelblue')
        axes[0, 0].set_xlabel('Hours Ahead', fontsize=12)
        axes[0, 0].set_ylabel('MAE ($/MWh)', fontsize=12)
        axes[0, 0].set_title('Forecast Error vs Horizon (0-48 hours)', fontsize=14, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].set_xlim(0, 48)
        
        # Bias over forecast horizon
        axes[0, 1].plot(horizon_metrics['Hours_Ahead'], horizon_metrics['Bias'], 
                       marker='s', linewidth=2, markersize=8, color='red')
        axes[0, 1].axhline(0, color='black', linestyle='--', linewidth=1)
        axes[0, 1].set_xlabel('Hours Ahead', fontsize=12)
        axes[0, 1].set_ylabel('Bias ($/MWh)', fontsize=12)
        axes[0, 1].set_title('Forecast Bias vs Horizon', fontsize=14, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].set_xlim(0, 48)
        
        # Actual vs Predicted over horizon
        axes[1, 0].plot(horizon_metrics['Hours_Ahead'], horizon_metrics['Mean_Actual'], 
                       marker='o', linewidth=2, label='Actual', color='blue')
        axes[1, 0].plot(horizon_metrics['Hours_Ahead'], horizon_metrics['Mean_Predicted'], 
                       marker='s', linewidth=2, label='Predicted', color='red')
        axes[1, 0].set_xlabel('Hours Ahead', fontsize=12)
        axes[1, 0].set_ylabel('Mean Price ($/MWh)', fontsize=12)
        axes[1, 0].set_title('Mean Prices Over Forecast Horizon', fontsize=14, fontweight='bold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].set_xlim(0, 48)
        
        # Degradation percentage
        first_bucket_mae = horizon_metrics.loc[0, 'MAE']
        horizon_metrics['Degradation_%'] = ((horizon_metrics['MAE'] - first_bucket_mae) / first_bucket_mae) * 100
        axes[1, 1].bar(horizon_metrics['Hours_Ahead'], horizon_metrics['Degradation_%'], 
                      width=5,
                      color=['red' if x > 0 else 'green' for x in horizon_metrics['Degradation_%']], 
                      edgecolor='black')
        axes[1, 1].axhline(0, color='black', linestyle='--', linewidth=1)
        axes[1, 1].set_xlabel('Hours Ahead', fontsize=12)
        axes[1, 1].set_ylabel('Degradation from 0-6h (%)', fontsize=12)
        axes[1, 1].set_title('Forecast Degradation Over 48h Horizon', fontsize=14, fontweight='bold')
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        axes[1, 1].set_xlim(0, 48)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '05_forecast_horizon_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        return horizon_metrics

    def plot_location_analysis(self):
        """Analyze performance by location."""
        location_metrics = self.eval_df.groupby('item_id').agg({
            'abs_error': 'mean',
            'actual': ['mean', 'std'],
            'predicted': 'std',
            'error': 'mean'
        }).reset_index()
        location_metrics.columns = ['item_id', 'MAE', 'Mean_Actual', 'Actual_Volatility', 
                                    'Predicted_Volatility', 'Bias']
        location_metrics['Volatility_Ratio'] = (location_metrics['Predicted_Volatility'] / 
                                                location_metrics['Actual_Volatility'])
        
        # Merge with island info
        location_metrics = location_metrics.merge(
            self.static_features[['item_id', 'Island']], on='item_id', how='left'
        )
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # MAE distribution across locations
        axes[0, 0].hist(location_metrics['MAE'], bins=30, edgecolor='black', alpha=0.7, color='steelblue')
        axes[0, 0].axvline(location_metrics['MAE'].mean(), color='red', linestyle='--', 
                          linewidth=2, label=f'Mean: ${location_metrics["MAE"].mean():.2f}')
        axes[0, 0].set_xlabel('MAE ($/MWh)', fontsize=12)
        axes[0, 0].set_ylabel('Number of Locations', fontsize=12)
        axes[0, 0].set_title('Distribution of MAE Across Locations', fontsize=14, fontweight='bold')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3, axis='y')
        
        # MAE vs Mean Actual Price
        axes[0, 1].scatter(location_metrics['Mean_Actual'], location_metrics['MAE'], 
                          alpha=0.6, s=50, c='blue')
        axes[0, 1].set_xlabel('Mean Actual Price ($/MWh)', fontsize=12)
        axes[0, 1].set_ylabel('MAE ($/MWh)', fontsize=12)
        axes[0, 1].set_title('MAE vs Mean Price by Location', fontsize=14, fontweight='bold')
        axes[0, 1].grid(True, alpha=0.3)
        
        # Volatility capture
        axes[1, 0].scatter(location_metrics['Actual_Volatility'], 
                          location_metrics['Predicted_Volatility'], 
                          alpha=0.6, s=50, c='green')
        max_vol = max(location_metrics['Actual_Volatility'].max(), 
                     location_metrics['Predicted_Volatility'].max())
        axes[1, 0].plot([0, max_vol], [0, max_vol], 'r--', linewidth=2, label='Perfect capture')
        axes[1, 0].set_xlabel('Actual Volatility ($/MWh)', fontsize=12)
        axes[1, 0].set_ylabel('Predicted Volatility ($/MWh)', fontsize=12)
        axes[1, 0].set_title('Volatility Capture by Location', fontsize=14, fontweight='bold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # Island comparison
        island_metrics = location_metrics.groupby('Island').agg({
            'MAE': 'mean',
            'Mean_Actual': 'mean',
            'Bias': 'mean',
            'item_id': 'count'
        }).reset_index()
        island_metrics.columns = ['Island', 'MAE', 'Mean_Actual', 'Bias', 'Count']
        
        x = range(len(island_metrics))
        width = 0.35
        axes[1, 1].bar([i - width/2 for i in x], island_metrics['MAE'], 
                      width, label='MAE', color='steelblue', edgecolor='black')
        axes[1, 1].bar([i + width/2 for i in x], -island_metrics['Bias'], 
                      width, label='Abs(Bias)', color='orange', edgecolor='black')
        axes[1, 1].set_xticks(x)
        axes[1, 1].set_xticklabels(island_metrics['Island'])
        axes[1, 1].set_ylabel('Error ($/MWh)', fontsize=12)
        axes[1, 1].set_title('Performance by Island', fontsize=14, fontweight='bold')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '06_location_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        return location_metrics

    def plot_extreme_price_analysis(self):
        """Analyze model behavior on extreme prices."""
        p95 = self.eval_df['actual'].quantile(0.95)
        p5 = self.eval_df['actual'].quantile(0.05)
        
        self.eval_df['price_category'] = 'Normal'
        self.eval_df.loc[self.eval_df['actual'] >= p95, 'price_category'] = 'High (>P95)'
        self.eval_df.loc[self.eval_df['actual'] <= p5, 'price_category'] = 'Low (<P5)'
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # Box plot of errors by category
        categories = ['Low (<P5)', 'Normal', 'High (>P95)']
        data_to_plot = [self.eval_df[self.eval_df['price_category'] == cat]['error'] 
                       for cat in categories]
        axes[0, 0].boxplot(data_to_plot, labels=categories)
        axes[0, 0].axhline(0, color='red', linestyle='--', linewidth=1)
        axes[0, 0].set_ylabel('Prediction Error ($/MWh)', fontsize=12)
        axes[0, 0].set_title('Error Distribution by Price Category', fontsize=14, fontweight='bold')
        axes[0, 0].grid(True, alpha=0.3, axis='y')
        
        # Scatter: High prices
        high_prices = self.eval_df[self.eval_df['actual'] >= p95]
        axes[0, 1].scatter(high_prices['actual'], high_prices['predicted'], 
                          alpha=0.3, s=20, c='red')
        axes[0, 1].plot([p95, high_prices['actual'].max()], 
                       [p95, high_prices['actual'].max()], 
                       'k--', linewidth=2, label='Perfect prediction')
        axes[0, 1].set_xlabel('Actual Price ($/MWh)', fontsize=12)
        axes[0, 1].set_ylabel('Predicted Price ($/MWh)', fontsize=12)
        axes[0, 1].set_title(f'High Prices (≥${p95:.0f}/MWh)', fontsize=14, fontweight='bold')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Scatter: Low prices
        low_prices = self.eval_df[self.eval_df['actual'] <= p5]
        axes[1, 0].scatter(low_prices['actual'], low_prices['predicted'], 
                          alpha=0.3, s=20, c='blue')
        axes[1, 0].plot([0, p5], [0, p5], 'k--', linewidth=2, label='Perfect prediction')
        axes[1, 0].set_xlabel('Actual Price ($/MWh)', fontsize=12)
        axes[1, 0].set_ylabel('Predicted Price ($/MWh)', fontsize=12)
        axes[1, 0].set_title(f'Low Prices (≤${p5:.2f}/MWh)', fontsize=14, fontweight='bold')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # MAE by category
        category_metrics = self.eval_df.groupby('price_category').agg({
            'abs_error': 'mean',
            'error': 'mean',
            'item_id': 'count'
        }).reindex(categories)
        category_metrics.columns = ['MAE', 'Bias', 'Count']
        
        x = range(len(categories))
        width = 0.35
        axes[1, 1].bar([i - width/2 for i in x], category_metrics['MAE'], 
                      width, label='MAE', color='steelblue', edgecolor='black')
        axes[1, 1].bar([i + width/2 for i in x], -category_metrics['Bias'], 
                      width, label='Abs(Bias)', color='orange', edgecolor='black')
        axes[1, 1].set_xticks(x)
        axes[1, 1].set_xticklabels(categories)
        axes[1, 1].set_ylabel('Error ($/MWh)', fontsize=12)
        axes[1, 1].set_title('MAE and Bias by Price Category', fontsize=14, fontweight='bold')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '07_extreme_price_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_weather_impact_analysis(self):
        """Analyze how weather variables impact price prediction accuracy."""
        print("  ✓ Weather Impact Analysis")
        
        # Load weather data
        weather_path = Path("../data/weather/weather_all_locations.csv")
        if not weather_path.exists():
            print("    ⚠ Weather data not found, skipping weather analysis")
            return None
        
        weather_df = pd.read_csv(weather_path)
        weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp']).dt.floor('30min')
        
        # Weather data has 'location' column, eval_df has 'item_id'
        # We need to map between them - for now, just merge on timestamp and aggregate
        # Since weather is by city and prices are by grid point, we'll analyze at timestamp level
        
        # Aggregate weather by timestamp (average across all locations)
        weather_agg = weather_df.groupby('timestamp').agg({
            'temperature': 'mean',
            'wind_speed': 'mean',
            'solar_radiation': 'mean',
            'precipitation': 'mean'
        }).reset_index()
        
        # Ensure eval_df timestamps are also floored to 30min
        eval_df_copy = self.eval_df.copy()
        eval_df_copy['timestamp'] = pd.to_datetime(eval_df_copy['timestamp']).dt.floor('30min')
        
        # Merge with predictions
        eval_with_weather = eval_df_copy.merge(
            weather_agg,
            on='timestamp',
            how='inner'  # Use inner to only keep matching timestamps
        )
        
        print(f"    Debug: eval_df timestamps: {eval_df_copy['timestamp'].min()} to {eval_df_copy['timestamp'].max()}")
        print(f"    Debug: weather timestamps: {weather_agg['timestamp'].min()} to {weather_agg['timestamp'].max()}")
        print(f"    Debug: Merged rows: {len(eval_with_weather)} out of {len(eval_df_copy)}")
        print(f"    Debug: Merged columns: {list(eval_with_weather.columns)}")
        
        # Check if merge was successful
        if len(eval_with_weather) == 0:
            print("    ⚠ Weather merge failed, skipping weather analysis")
            return None
        
        # Use the weather columns (suffixed with _y after merge)
        # Rename them for clarity
        eval_with_weather = eval_with_weather.rename(columns={
            'temperature_y': 'weather_temp',
            'wind_speed_y': 'weather_wind',
            'solar_radiation_y': 'weather_solar',
            'precipitation_y': 'weather_precip'
        })
        
        # Calculate derived weather features
        eval_with_weather['temp_squared'] = eval_with_weather['weather_temp'] ** 2
        eval_with_weather['heating_dd'] = np.maximum(18 - eval_with_weather['weather_temp'], 0)
        eval_with_weather['cooling_dd'] = np.maximum(eval_with_weather['weather_temp'] - 18, 0)
        
        # Create weather bins
        eval_with_weather['temp_bin'] = pd.cut(eval_with_weather['weather_temp'], 
                                                bins=[-np.inf, 5, 10, 15, 20, 25, np.inf],
                                                labels=['<5°C', '5-10°C', '10-15°C', '15-20°C', '20-25°C', '>25°C'])
        
        eval_with_weather['wind_bin'] = pd.cut(eval_with_weather['weather_wind'],
                                                bins=[-np.inf, 5, 10, 15, np.inf],
                                                labels=['<5 m/s', '5-10 m/s', '10-15 m/s', '>15 m/s'])
        
        eval_with_weather['solar_bin'] = pd.cut(eval_with_weather['weather_solar'],
                                                 bins=[-np.inf, 100, 300, 500, np.inf],
                                                 labels=['Night', 'Low', 'Medium', 'High'])
        
        eval_with_weather['rain'] = eval_with_weather['weather_precip'] > 0
        
        # Create 2x2 plot
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Temperature impact
        temp_metrics = eval_with_weather.groupby('temp_bin').agg({
            'error': lambda x: np.abs(x).mean(),
            'actual': 'mean',
            'predicted': 'count'
        }).reset_index()
        temp_metrics.columns = ['temp_bin', 'MAE', 'Mean_Price', 'Count']
        
        ax1 = axes[0, 0]
        x = range(len(temp_metrics))
        ax1_twin = ax1.twinx()
        
        bars = ax1.bar(x, temp_metrics['MAE'], color='steelblue', alpha=0.7, label='MAE')
        line = ax1_twin.plot(x, temp_metrics['Mean_Price'], 'o-', color='red', linewidth=2, markersize=8, label='Mean Price')
        
        ax1.set_xlabel('Temperature Range', fontsize=12)
        ax1.set_ylabel('MAE ($/MWh)', fontsize=12, color='steelblue')
        ax1_twin.set_ylabel('Mean Price ($/MWh)', fontsize=12, color='red')
        ax1.set_title('Temperature Impact on Prediction Accuracy', fontsize=14, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(temp_metrics['temp_bin'], rotation=45)
        ax1.tick_params(axis='y', labelcolor='steelblue')
        ax1_twin.tick_params(axis='y', labelcolor='red')
        ax1.grid(True, alpha=0.3, axis='y')
        
        # Add legend
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # 2. Wind speed impact
        wind_metrics = eval_with_weather.groupby('wind_bin').agg({
            'error': lambda x: np.abs(x).mean(),
            'actual': 'mean',
            'predicted': 'count'
        }).reset_index()
        wind_metrics.columns = ['wind_bin', 'MAE', 'Mean_Price', 'Count']
        
        ax2 = axes[0, 1]
        x = range(len(wind_metrics))
        ax2_twin = ax2.twinx()
        
        ax2.bar(x, wind_metrics['MAE'], color='steelblue', alpha=0.7, label='MAE')
        ax2_twin.plot(x, wind_metrics['Mean_Price'], 'o-', color='red', linewidth=2, markersize=8, label='Mean Price')
        
        ax2.set_xlabel('Wind Speed Range', fontsize=12)
        ax2.set_ylabel('MAE ($/MWh)', fontsize=12, color='steelblue')
        ax2_twin.set_ylabel('Mean Price ($/MWh)', fontsize=12, color='red')
        ax2.set_title('Wind Speed Impact on Prediction Accuracy', fontsize=14, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(wind_metrics['wind_bin'], rotation=45)
        ax2.tick_params(axis='y', labelcolor='steelblue')
        ax2_twin.tick_params(axis='y', labelcolor='red')
        ax2.grid(True, alpha=0.3, axis='y')
        
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # 3. Solar radiation impact
        solar_metrics = eval_with_weather.groupby('solar_bin').agg({
            'error': lambda x: np.abs(x).mean(),
            'actual': 'mean',
            'predicted': 'count'
        }).reset_index()
        solar_metrics.columns = ['solar_bin', 'MAE', 'Mean_Price', 'Count']
        
        ax3 = axes[1, 0]
        x = range(len(solar_metrics))
        ax3_twin = ax3.twinx()
        
        ax3.bar(x, solar_metrics['MAE'], color='steelblue', alpha=0.7, label='MAE')
        ax3_twin.plot(x, solar_metrics['Mean_Price'], 'o-', color='red', linewidth=2, markersize=8, label='Mean Price')
        
        ax3.set_xlabel('Solar Radiation Level', fontsize=12)
        ax3.set_ylabel('MAE ($/MWh)', fontsize=12, color='steelblue')
        ax3_twin.set_ylabel('Mean Price ($/MWh)', fontsize=12, color='red')
        ax3.set_title('Solar Radiation Impact on Prediction Accuracy', fontsize=14, fontweight='bold')
        ax3.set_xticks(x)
        ax3.set_xticklabels(solar_metrics['solar_bin'], rotation=45)
        ax3.tick_params(axis='y', labelcolor='steelblue')
        ax3_twin.tick_params(axis='y', labelcolor='red')
        ax3.grid(True, alpha=0.3, axis='y')
        
        lines1, labels1 = ax3.get_legend_handles_labels()
        lines2, labels2 = ax3_twin.get_legend_handles_labels()
        ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        # 4. Precipitation impact
        rain_metrics = eval_with_weather.groupby('rain').agg({
            'error': lambda x: np.abs(x).mean(),
            'actual': 'mean',
            'predicted': 'count'
        }).reset_index()
        rain_metrics['rain'] = rain_metrics['rain'].map({False: 'No Rain', True: 'Rain'})
        rain_metrics.columns = ['condition', 'MAE', 'Mean_Price', 'Count']
        
        ax4 = axes[1, 1]
        x = range(len(rain_metrics))
        ax4_twin = ax4.twinx()
        
        ax4.bar(x, rain_metrics['MAE'], color='steelblue', alpha=0.7, label='MAE')
        ax4_twin.plot(x, rain_metrics['Mean_Price'], 'o-', color='red', linewidth=2, markersize=8, label='Mean Price')
        
        ax4.set_xlabel('Precipitation Condition', fontsize=12)
        ax4.set_ylabel('MAE ($/MWh)', fontsize=12, color='steelblue')
        ax4_twin.set_ylabel('Mean Price ($/MWh)', fontsize=12, color='red')
        ax4.set_title('Precipitation Impact on Prediction Accuracy', fontsize=14, fontweight='bold')
        ax4.set_xticks(x)
        ax4.set_xticklabels(rain_metrics['condition'])
        ax4.tick_params(axis='y', labelcolor='steelblue')
        ax4_twin.tick_params(axis='y', labelcolor='red')
        ax4.grid(True, alpha=0.3, axis='y')
        
        lines1, labels1 = ax4.get_legend_handles_labels()
        lines2, labels2 = ax4_twin.get_legend_handles_labels()
        ax4.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / '08_weather_impact_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Return metrics for report
        return {
            'temperature': temp_metrics.to_dict('records'),
            'wind': wind_metrics.to_dict('records'),
            'solar': solar_metrics.to_dict('records'),
            'precipitation': rain_metrics.to_dict('records')
        }

    def generate_markdown_report(self, price_metrics, horizon_metrics, location_metrics, weather_metrics=None):
        """Generate comprehensive markdown report using template."""
        report_path = self.output_dir / 'EVALUATION_REPORT.md'
        
        # Calculate key metrics
        mae = self.eval_df['abs_error'].mean()
        rmse = np.sqrt(mean_squared_error(self.eval_df['actual'], self.eval_df['predicted']))
        r2 = r2_score(self.eval_df['actual'], self.eval_df['predicted'])
        bias = self.eval_df['error'].mean()
        
        # Get model info
        best_model = self.model_to_use
        
        # Calculate additional metrics
        p95 = self.eval_df['actual'].quantile(0.95)
        p5 = self.eval_df['actual'].quantile(0.05)
        high_mae = self.eval_df[self.eval_df['actual'] >= p95]['abs_error'].mean()
        low_mae = self.eval_df[self.eval_df['actual'] <= p5]['abs_error'].mean()
        high_count = (self.eval_df['actual'] >= p95).sum()
        
        # Calculate extreme price bias (for $500+ prices)
        extreme_threshold = 500
        extreme_df = self.eval_df[self.eval_df['actual'] >= extreme_threshold]
        extreme_bias = extreme_df['error'].mean() if len(extreme_df) > 0 else 0
        
        actual_vol = self.eval_df.groupby('item_id')['actual'].std().mean()
        pred_vol = self.eval_df.groupby('item_id')['predicted'].std().mean()
        vol_ratio = pred_vol/actual_vol
        
        hourly = self.eval_df.groupby('hour')['abs_error'].mean()
        best_hour = hourly.idxmin()
        worst_hour = hourly.idxmax()
        
        day0_mae = horizon_metrics.loc[0, 'MAE']
        day1_mae = horizon_metrics.loc[horizon_metrics.index.max(), 'MAE']
        improvement = ((day0_mae - day1_mae) / day0_mae) * 100
        
        worst_locs = location_metrics.nlargest(5, 'MAE')['item_id'].tolist()
        
        # Location metrics
        mean_location_mae = location_metrics['MAE'].mean()
        std_location_mae = location_metrics['MAE'].std()
        best_location_mae = location_metrics['MAE'].min()
        worst_location_mae = location_metrics['MAE'].max()
        
        # Prepare context for template
        mean_actual = self.eval_df['actual'].mean()
        mean_predicted = self.eval_df['predicted'].mean()
        bias_pct = (bias / mean_actual) * 100 if mean_actual != 0 else 0
        
        context = {
            'generated_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'model_path': self.model_path,
            'prediction_length': PREDICTION_LENGTH,
            'best_model': best_model,
            'num_features': len(KNOWN_COVARIATES) + 2,
            'mae': mae,
            'rmse': rmse,
            'r2': r2,
            'r2_pct': r2*100,
            'bias': bias,
            'bias_pct': bias_pct,
            'mean_actual': mean_actual,
            'mean_predicted': mean_predicted,
            'p95': p95,
            'p5': p5,
            'high_mae': high_mae,
            'low_mae': low_mae,
            'high_count': high_count,
            'high_pct': high_count/len(self.eval_df)*100,
            'extreme_bias': abs(extreme_bias),
            'actual_vol': actual_vol,
            'pred_vol': pred_vol,
            'vol_ratio': vol_ratio,
            'vol_pct': vol_ratio*100,
            'best_hour': best_hour,
            'worst_hour': worst_hour,
            'best_hour_mae': hourly[best_hour],
            'worst_hour_mae': hourly[worst_hour],
            'hour_ratio': hourly[worst_hour]/hourly[best_hour],
            'day0_mae': day0_mae,
            'day1_mae': day1_mae,
            'improvement': improvement,
            'worst_locs': ', '.join(worst_locs),
            'worst_locs_mae': location_metrics.nlargest(5, 'MAE')['MAE'].mean(),
            'mean_location_mae': mean_location_mae,
            'std_location_mae': std_location_mae,
            'best_location_mae': best_location_mae,
            'worst_location_mae': worst_location_mae,
            'overpredict_pct': (self.eval_df['error'] > 0).mean()*100,
            'underpredict_pct': (self.eval_df['error'] < 0).mean()*100,
            'price_metrics_table': price_metrics.to_markdown(index=False),
            'best_locations_table': location_metrics.nsmallest(10, 'MAE')[['item_id', 'MAE', 'Mean_Actual', 'Bias']].to_markdown(index=False),
            'worst_locations_table': location_metrics.nlargest(10, 'MAE')[['item_id', 'MAE', 'Mean_Actual', 'Bias', 'Actual_Volatility']].to_markdown(index=False),
            'total_locations': location_metrics['item_id'].nunique(),
            'mean_location_mae': location_metrics['MAE'].mean(),
            'std_location_mae': location_metrics['MAE'].std(),
            'best_location': location_metrics.nsmallest(1, 'MAE')['item_id'].values[0],
            'best_location_mae': location_metrics['MAE'].min(),
            'worst_location': location_metrics.nlargest(1, 'MAE')['item_id'].values[0],
            'worst_location_mae': location_metrics['MAE'].max(),
        }
        
        # Load and render template
        template_path = Path(__file__).parent / 'report_template.md'
        if template_path.exists():
            with open(template_path, 'r') as f:
                template = f.read()
            
            # Simple template rendering
            report_content = template.format(**context)
        else:
            # Fallback: generate basic report
            report_content = self._generate_basic_report(context)
        
        # Write report
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        print(f"\nMarkdown report saved to: {report_path}")
        return report_path
    
    def _generate_basic_report(self, ctx):
        """Fallback basic report if template not found."""
        return f"""# NZ Electricity Price Prediction Model - Evaluation Report

**Generated:** {ctx['generated_time']}
**Model:** {ctx['best_model']}
**MAE:** ${ctx['mae']:.2f}/MWh
**Bias:** ${ctx['bias']:.2f}/MWh

See evaluation plots in the report directory.
"""
    def generate_all(self):
        """Generate all plots and reports."""
        print("\n" + "="*80)
        print("GENERATING COMPREHENSIVE EVALUATION REPORT")
        print("="*80 + "\n")
        
        self.load_and_prepare_data()
        
        print("Generating plots...")
        self.plot_actual_vs_predicted()
        print("  ✓ Actual vs Predicted")
        
        self.plot_error_distribution()
        print("  ✓ Error Distribution")
        
        self.plot_time_of_day_analysis()
        print("  ✓ Time of Day Analysis")
        
        price_metrics = self.plot_price_range_analysis()
        print("  ✓ Price Range Analysis")
        
        horizon_metrics = self.plot_forecast_horizon_analysis()
        print("  ✓ Forecast Horizon Analysis")
        
        location_metrics = self.plot_location_analysis()
        print("  ✓ Location Analysis")
        
        self.plot_extreme_price_analysis()
        print("  ✓ Extreme Price Analysis")
        
        weather_metrics = self.plot_weather_impact_analysis()
        
        print("\nGenerating markdown report...")
        report_path = self.generate_markdown_report(price_metrics, horizon_metrics, location_metrics, weather_metrics)
        
        print("\n" + "="*80)
        print("REPORT GENERATION COMPLETE")
        print("="*80)
        print(f"\nAll outputs saved to: {self.output_dir}")
        print(f"Main report: {report_path}")


if __name__ == "__main__":
    generator = ReportGenerator(MODEL_PATH, GROUND_TRUTH_FILE)
    generator.generate_all()
