#!/usr/bin/env bash
# Reproduce the full analysis end-to-end.
set -e
cd "$(dirname "$0")/src"
echo "1/5 Generating synthetic data..."      && python 01_generate_data.py
echo "2/5 Checking input tables..."           && python validate_data.py
echo "3/5 EDA + behavioural signals..."       && python 02_eda_signals.py
echo "4/5 Recovery-propensity model..."       && python 03_model.py
echo "5/5 Call-transcript NLP..."             && python 04_text_analytics.py
echo "Done. See outputs/ for charts, scores and dashboard.html"
