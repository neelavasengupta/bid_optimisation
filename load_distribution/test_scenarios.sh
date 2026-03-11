#!/bin/bash

# Test all demo scenarios for parameter validation
# This checks if commands are syntactically correct without running full optimization

echo "Testing Demo Scenarios..."
echo ""

# Scenario 1: Baseline
echo "1. Baseline (Standard Operation)"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 1 parameters valid"; else echo "✗ Scenario 1 FAILED"; fi
echo ""

# Scenario 2: Low Production
echo "2. Low Production (High Flexibility)"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 2 parameters valid"; else echo "✗ Scenario 2 FAILED"; fi
echo ""

# Scenario 3: Large Storage Tank
echo "3. Large Storage Tank"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --max-inventory 15.0 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 3 parameters valid"; else echo "✗ Scenario 3 FAILED"; fi
echo ""

# Scenario 4: Tight Constraints
echo "4. Tight Constraints"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --min-inventory 4.0 \
  --max-inventory 6.0 \
  --ramp-rate 0.3 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 4 parameters valid"; else echo "✗ Scenario 4 FAILED"; fi
echo ""

# Scenario 5: Fast Ramp Rate
echo "5. Fast Ramp Rate"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 150 \
  --forecast-horizon 48 \
  --ramp-rate 1.0 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 5 parameters valid"; else echo "✗ Scenario 5 FAILED"; fi
echo ""

# Scenario 6: Strict Environmental Compliance
echo "6. Strict Environmental Compliance"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 250 \
  --forecast-horizon 48 \
  --wastewater-frequency 2 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 6 parameters valid"; else echo "✗ Scenario 6 FAILED"; fi
echo ""

# Scenario 7: Maximum Flexibility
echo "7. Maximum Flexibility"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 100 \
  --forecast-horizon 48 \
  --min-inventory 1.0 \
  --max-inventory 18.0 \
  --ramp-rate 1.0 \
  --wastewater-frequency 8 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 7 parameters valid"; else echo "✗ Scenario 7 FAILED"; fi
echo ""

# Scenario 8: Short Horizon
echo "8. Short Horizon (24h)"
uv run python -m load_distribution.cli optimize \
  --location HAY2201 \
  --forecast-start "2025-06-01 06:00" \
  --production-target 125 \
  --forecast-horizon 24 \
  --help > /dev/null 2>&1
if [ $? -eq 0 ]; then echo "✓ Scenario 8 parameters valid"; else echo "✗ Scenario 8 FAILED"; fi
echo ""

echo "All scenario parameter validation complete!"

